import os
import discord

from dotenv import load_dotenv
from honcho import Honcho
from openai import OpenAI

load_dotenv()


def get_env(key: str):
    var = os.getenv(key)
    if not var:
        raise ValueError(f"{key} is not set in .env")
    return var


BOT_TOKEN = get_env("BOT_TOKEN")
MODEL_NAME = get_env("MODEL_NAME")
MODEL_API_KEY = get_env("MODEL_API_KEY")
APP_NAME = get_env("APP_NAME")
# ALLOWED_ROLES = get_env('ALLOWED_ROLES').split(',')


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

honcho = Honcho(environment="demo")  # uses demo server at https://demo.honcho.dev
app = honcho.apps.get_or_create(name=APP_NAME)

openai = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=MODEL_API_KEY)

bot = discord.Bot(intents=intents)


def llm(prompt, chat_history=None):
    extra_headers = {"X-Title": "Honcho Chatbot"}
    messages = []
    if chat_history:
        messages.extend([
            {"role": "user" if msg.is_user else "assistant", "content": msg.content}
            for msg in chat_history
        ])
    messages.append({"role": "user", "content": prompt})
    try:
        completion = openai.chat.completions.create(
            extra_headers=extra_headers,
            model=MODEL_NAME,
            messages=messages,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(e)
        return f"Error: {e}"


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


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

        # Use the channel ID as the location_id (for DMs, this will be unique to the user)
        location_id = str(message.channel.id)

        # Query for active sessions with both user_id and location_id
        sessions_iter = honcho.apps.users.sessions.list(
            app_id=app.id, user_id=user.id, reverse=True
        )
        sessions = list(session for session in sessions_iter)

        session = None
        if sessions:
            # find the right session
            for s in sessions:
                if s.metadata.get("location_id") == location_id:
                    session = s
                    print(session.id)
                    break
            # if no session is found after the for loop, create a new one
            if not session:
                print("No session found amongst existing ones, creating new one")
                session = honcho.apps.users.sessions.create(
                    user_id=user.id,
                    app_id=app.id,
                    metadata={"location_id": location_id},
                )
                print(session.id)
        else:
            print("No active session found")
            session = honcho.apps.users.sessions.create(
                user_id=user.id, app_id=app.id, metadata={"location_id": location_id}
            )
            print(session.id)

        # get messages
        history_iter = honcho.apps.users.sessions.messages.list(
            app_id=app.id, session_id=session.id, user_id=user.id
        )
        history = list(msg for msg in history_iter)

        # Add user message to session
        honcho.apps.users.sessions.messages.create(
            app_id=app.id,
            user_id=user.id,
            session_id=session.id,
            content=input,
            is_user=True,
        )

        async with message.channel.typing():
            response = llm(input, history)
            await message.channel.send(response)

        # Add bot message to session
        honcho.apps.users.sessions.messages.create(
            app_id=app.id,
            user_id=user.id,
            session_id=session.id,
            content=response,
            is_user=False,
        )


@bot.slash_command(name="restart", description="Restart the Conversation")
async def restart(ctx):
    user_id = f"discord_{str(ctx.author.id)}"
    user = honcho.apps.users.get_or_create(name=user_id, app_id=app.id)
    location_id = str(ctx.channel_id)

    sessions = honcho.apps.users.sessions.list(
        app_id=app.id, user_id=user.id, reverse=True
    )

    sessions_list = list(sessions)

    if sessions_list:
        # find the right session to delete
        for session in sessions_list:
            if session.metadata.get("location_id") == location_id:
                honcho.apps.users.sessions.delete(
                    app_id=app.id, user_id=user.id, session_id=session.id
                )
                break
        msg = "The conversation has been restarted."
    else:
        msg = "No active conversation found to restart."

    await ctx.respond(msg)


bot.run(BOT_TOKEN)
