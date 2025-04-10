import io
import os
import shutil
import tempfile
import threading
import time
import zipfile

import discord
import requests
import schedule
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
HONCHO_URL = get_env("HONCHO_URL")
HONCHO_API_KEY = get_env("HONCHO_API_KEY")
# ALLOWED_ROLES = get_env('ALLOWED_ROLES').split(',')

# Create temp directory to store repo files
REPO_DIR = tempfile.mkdtemp()
REPO_URL = "https://github.com/plastic-labs/honcho"
REPO_ZIP_URL = "https://github.com/plastic-labs/honcho/archive/refs/heads/main.zip"


def update_repo():
    """Download latest files from honcho repo"""
    print("Updating honcho repo...")
    try:
        # Clear existing directory
        if os.path.exists(REPO_DIR):
            shutil.rmtree(REPO_DIR)
            os.makedirs(REPO_DIR)

        # Download zip file
        response = requests.get(REPO_ZIP_URL)
        response.raise_for_status()

        # Extract zip file
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
            zip_ref.extractall(REPO_DIR)

        # The extracted folder will have a name like 'honcho-main'
        # Move all contents to REPO_DIR
        extracted_dir = os.path.join(REPO_DIR, os.listdir(REPO_DIR)[0])
        for item in os.listdir(extracted_dir):
            shutil.move(os.path.join(extracted_dir, item), REPO_DIR)

        # Remove the now-empty extracted directory
        shutil.rmtree(extracted_dir)

        print("Successfully updated honcho repo")
    except Exception as e:
        print(f"Error updating repo: {e}")


def run_scheduler():
    """Run the scheduler in a separate thread"""
    schedule.every(1).hour.do(update_repo)
    while True:
        schedule.run_pending()
        time.sleep(60)


# Start scheduler thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# Do initial repo update
update_repo()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

honcho = Honcho(
    base_url=HONCHO_URL, default_headers={"Authorization": f"Bearer {HONCHO_API_KEY}"}
)
app = honcho.apps.get_or_create(name=APP_NAME)

print(f"Honcho app acquired with id {app.id}")

openai = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=MODEL_API_KEY)

bot = discord.Bot(intents=intents)


def get_repo_context():
    """Get the latest code from the Honcho repository. Returns a formatted string of the documentation."""
    context = "Here is the latest documentation from the Honcho repository:\n"
    try:
        docs_dir = os.path.join(REPO_DIR, "docs")
        if os.path.exists(docs_dir):
            for root, _dirs, files in os.walk(docs_dir):
                for file in files:
                    if file.endswith(".mdx"):
                        file_path = os.path.join(root, file)
                        with open(file_path) as f:
                            context += f"\n{file}:\n{f.read()}\n"
    except Exception as e:
        print(f"Error reading repo documentation files: {e}")
    return context


repo_context = get_repo_context()


def llm(prompt, previous_chats=None, current_chat=None):
    extra_headers = {"X-Title": "Honcho Chatbot"}
    messages = []

    # Add system message with documentation context
    messages.append(
        {
            "role": "system",
            "content": f"You are a helpful and highly technical assistant for Honcho. Use the following documentation to help answer questions. Make sure to be concise and answer the user's question as directly as possible without any additional commentary or explanation. If the user's question is not related to Honcho, remind them that you are an assistant for Honcho and do not answer questions that are not related to Honcho.\n\n{repo_context}",
        }
    )

    if previous_chats:
        messages.append(
            {
                "role": "system",
                "content": "Here are previous messages with this user in prior conversations:",
            }
        )
        messages.extend(
            [
                {"role": "user" if msg.is_user else "assistant", "content": msg.content}
                for msg in previous_chats
            ]
        )

    if current_chat:
        messages.append(
            {
                "role": "system",
                "content": "Here are the current messages in this conversation:",
            }
        )
        messages.extend(
            [
                {"role": "user" if msg.is_user else "assistant", "content": msg.content}
                for msg in current_chat
            ]
        )

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
    is_thread = isinstance(message.channel, discord.Thread)
    is_relevant_thread = False
    if is_thread:
        try:
            async for first_message in message.channel.history(
                limit=1, oldest_first=True
            ):
                break
            is_relevant_thread = first_message.author == bot.user
        except Exception as e:
            print(f"Error fetching first message in thread: {e}")
            is_relevant_thread = False
    else:
        is_relevant_thread = False

    if is_dm or is_reply_to_bot or is_mention or is_relevant_thread:
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
        if is_thread:
            location_id = str(message.channel.parent.id)

        # Get or create a session for this user and location
        session, is_new = get_session(user.id, location_id, create=True)

        if is_new:
            print(f"New session created for {message.author.name} in {location_id}")

        # Get messages
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

        # If not in a thread, create a new thread
        thread = message.channel
        if not is_relevant_thread:
            # Use the first few words of the response as the thread title
            thread_title = response[:50] + "..." if len(response) > 50 else response
            thread = await message.create_thread(
                name=thread_title, auto_archive_duration=60
            )

        if len(response) > 1500:
            # Split response into chunks at newlines, keeping under 1500 chars
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
                await thread.send(chunk)
        else:
            await thread.send(response)

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


@bot.slash_command(
    name="describe",
    description="Ask Honcho what it thinks about a user in this channel!",
)
async def describe(ctx, discord_user: discord.Member):
    print(f"describing {discord_user.name}")
    await ctx.defer()

    user_name = f"discord_{str(discord_user.id)}"

    try:
        user = honcho.apps.users.get_by_name(name=user_name, app_id=app.id)
    except Exception as e:
        print(f"Error getting user with id {user_name} in app {app.id}: {e}")
        await ctx.followup.send(
            f"I don't know anything about {discord_user.name} because we haven't talked yet!"
        )
        return

    location_id = str(ctx.channel_id)
    session, _ = get_session(user.id, location_id, create=False)
    if not session:
        await ctx.followup.send(
            f"I don't know anything about {discord_user.name} because we haven't talked yet!"
        )
        return

    try:
        # Call the Dialectic chat API
        response = honcho.apps.users.sessions.chat(
            app_id=app.id,
            user_id=user.id,
            session_id=session.id,
            queries=f"Describe the user, whose name is {discord_user.name}, in the context of this conversation. Refer to them by name and give a short summary of any biographical information you know about them, plus any insight into their personality as revealed in the conversation.",
        )
        if response.content and response.content != "None":
            print(f"Response: {response.content}")
            await ctx.followup.send(response.content)
        else:
            await ctx.followup.send(
                f"I don't know anything about {discord_user.name} because we haven't talked yet!"
            )
    except Exception as e:
        print(f"Error calling Dialectic API: {e}")
        await ctx.followup.send(
            f"Sorry, there was an error processing your request: {str(e)}"
        )


# @bot.slash_command(name="dialectic", description="Query the Dialectic chat API")
# async def dialectic(ctx, query: str):
#     print(f"dialectic query from {ctx.author.id}: {query}")

#     await ctx.defer()

#     response = ""
#     async with ctx.typing():
#         user_id = f"discord_{str(ctx.author.id)}"
#         user = honcho.apps.users.get_or_create(name=user_id, app_id=app.id)
#         location_id = str(ctx.channel_id)

#         # Get or create session
#         session, _ = get_session(user.id, location_id, create=True)

#         if not session:
#             await ctx.respond(
#                 "No active session found. Please start a conversation first."
#             )
#             return

#         try:
#             # Call the Dialectic chat API
#             response = honcho.apps.users.sessions.chat(
#                 app_id=app.id, user_id=user.id, session_id=session.id, queries=query
#             )
#             response = response.content
#         except Exception as e:
#             print(f"Error calling Dialectic API: {e}")
#             response = f"Sorry, there was an error processing your request: {str(e)}"
#     await ctx.followup.send(response)


bot.run(BOT_TOKEN)
