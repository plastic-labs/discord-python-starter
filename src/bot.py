import os

import discord
from dotenv import load_dotenv
from honcho import Honcho
from openai import OpenAI

load_dotenv()


def get_env(key: str, default: str = None):
    var = os.getenv(key)
    if not var:
        return default
    return var


BOT_TOKEN = get_env("BOT_TOKEN")
MODEL_NAME = get_env("MODEL_NAME")
MODEL_API_KEY = get_env("MODEL_API_KEY")
APP_NAME = get_env("APP_NAME")


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

honcho = Honcho()
app = honcho.apps.get_or_create(name=APP_NAME)

print(f"Honcho app acquired with id {app.id}")

# user = honcho.apps.users.get_or_create(app_id=app.id, name="hello")
# session = honcho.apps.users.sessions.create(app_id=app.id, user_id=user.id)

# transaction_id = honcho.transactions.begin()

# with Honcho(transaction_id=transaction_id) as honcho_txn:
#     message = honcho_txn.apps.users.sessions.messages.create(
#         app_id=app.id,
#         session_id=session.id,
#         user_id=user.id,
#         is_user=True,
#         content="Hello, how are you?",
#     )


# # before commit, the message is not visible
# messages = honcho.apps.users.sessions.messages.list(app_id=app.id, session_id=session.id, user_id=user.id)
# assert messages.total == 0

# honcho.transactions.commit(transaction_id)

# # after commit, the message is visible
# messages = honcho.apps.users.sessions.messages.list(app_id=app.id, session_id=session.id, user_id=user.id)
# assert messages.total == 1

openai = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=MODEL_API_KEY)

bot = discord.Bot(intents=intents)


def llm(prompt, previous_chats=None):
    messages = []

    # Add system message with documentation context
    messages.append(
        {
            "role": "system",
            "content": f"You are a helpful assistant."
        }
    )

    if previous_chats:
        messages.extend(
            [
                {"role": "user" if msg.is_user else "assistant", "content": msg.content}
                for msg in previous_chats
            ]
        )


    messages.append({"role": "user", "content": prompt})

    try:
        completion = openai.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(e)
        return f"Error: {e}"


def get_session(user_id, location_id, create=False):
    """Get an existing session for the user and location or optionally create a new one if none exists.
    Returns a tuple of (session, is_new) where is_new indicates if a new session was created."""
    # Query for *active* sessions with both user_id and location_id
    sessions_iter = honcho.apps.users.sessions.list(
        app_id=app.id, user_id=user_id, reverse=True, is_active=True
    )
    sessions = list(session for session in sessions_iter)

    # Find the right session
    for session in sessions:
        if session.metadata.get("location_id") == location_id:
            return session, False

    # If no session is found and create is True, create a new one
    if create:
        print("No active session found, creating new one")
        return honcho.apps.users.sessions.create(
            user_id=user_id,
            app_id=app.id,
            metadata={"location_id": location_id},
        ), True

    return None, False


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Waiting for messages...")


@bot.event
async def on_message(message):
    """Event that is run when a message is sent in a channel or DM that the bot has access to"""
    if message.author == bot.user:
        # ensure the bot does not reply to itself
        return

    # if str(message.author.id) not in ALLOWED_ROLES:
    #     # ignore messages from users not in the allowed list
    #     return

    is_dm = isinstance(message.channel, discord.DMChannel)
    is_reply_to_bot = (
        message.reference and message.reference.resolved.author == bot.user
    )
    is_mention = bot.user.mentioned_in(message)

    if is_dm or is_reply_to_bot or is_mention:
        # Remove the bot's mention from the message content if present
        input = message.content.replace(f"<@{bot.user.id}>", "").strip()

        # If the message is empty after removing the mention, ignore it
        if not input:
            return

        # Get a user object for the message author
        user_id = f"discord_{str(message.author.id)}"
        user = honcho.apps.users.get_or_create(name=user_id, app_id=app.id)

        # Sessions are based on channel, not thread.
        # If in a thread, get the parent channel id
        location_id = str(message.channel.id)

        # Get or create a session for this user and location
        session, is_new = get_session(user.id, location_id, create=True)

        if is_new:
            print(f"New session created for {message.author.name} in {location_id}")

        # Get messages
        history_iter = honcho.apps.users.sessions.messages.list(
            app_id=app.id, session_id=session.id, user_id=user.id
        )
        history = list(msg for msg in history_iter)

        async with message.channel.typing():
            response = llm(input, history)

        if len(response) > 1500:
            # Split response into chunks at newlines, keeping under 1500 chars
            # This is for discord's default message limit
            chunks = []
            current_chunk = ""
            for line in response.splitlines(keepends=True):
                if len(current_chunk) + len(line) > 1500:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += line
            if current_chunk:
                chunks.append(current_chunk)

            for chunk in chunks:
                await message.channel.send(chunk)
        else:
            await message.channel.send(response)

        # Add user message to session
        honcho.apps.users.sessions.messages.create(
            app_id=app.id,
            user_id=user.id,
            session_id=session.id,
            content=input,
            is_user=True,
        )

        # Add bot message to session
        honcho.apps.users.sessions.messages.create(
            app_id=app.id,
            user_id=user.id,
            session_id=session.id,
            content=response,
            is_user=False,
        )


@bot.slash_command(
    name="restart",
    description="Reset all of your messaging history with Honcho in this channel.",
)
async def restart(ctx):
    print(f"restarting conversation for {ctx.author.name}")
    async with ctx.typing():
        user_name = f"discord_{str(ctx.author.id)}"
        user = honcho.apps.users.get_or_create(name=user_name, app_id=app.id)
        location_id = str(ctx.channel_id)

        # Get existing session
        session, _ = get_session(user.id, location_id, create=False)

        if session:
            # Delete the session
            honcho.apps.users.sessions.delete(
                app_id=app.id, user_id=user.id, session_id=session.id
            )

        msg = "The conversation has been restarted."

    await ctx.respond(msg)



bot.run(BOT_TOKEN)
