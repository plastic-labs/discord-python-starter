import logging
import os

import discord
from dotenv import load_dotenv
from honcho import Honcho
from openai import OpenAI

from honcho_utils import get_session, get_user_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("discord").setLevel(logging.ERROR)

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
APP_NAME = os.getenv("APP_NAME")


honcho_client = Honcho()
app = honcho_client.apps.get_or_create(name=APP_NAME)

logger.info(f"Honcho app acquired with id {app.id}")

openai = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=MODEL_API_KEY)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
bot = discord.Bot(intents=intents)


def llm(prompt, chat_history=None) -> str:
    """
    Call the LLM with the given prompt and chat history.

    You should expand this function with custom logic, prompts, etc.
    """
    extra_headers = {"X-Title": "Honcho Chatbot"}
    messages = []
    if chat_history:
        messages.extend(
            [
                {"role": "user" if msg.is_user else "assistant", "content": msg.content}
                for msg in chat_history
            ]
        )
    messages.append({"role": "user", "content": prompt})

    try:
        completion = openai.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            extra_headers=extra_headers,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(e)
        return f"Error: {e}"


def validate_message(message) -> bool:
    """
    Determine if the message is valid for the bot to respond to.
    Return True if it is, False otherwise. Currently, the bot will
    only respond to messages that tag it with an @mention in a
    public channel and are not from the bot itself.
    """
    if message.author == bot.user:
        # ensure the bot does not reply to itself
        return False

    if isinstance(message.channel, discord.DMChannel):
        return False

    if not bot.user.mentioned_in(message):
        return False

    return True


def sanitize_message(message) -> str | None:
    """Remove the bot's mention from the message content if present"""
    content = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if not content:
        return None
    return content


async def send_discord_message(message, response_content: str):
    """Send a message to the Discord channel"""
    if len(response_content) > 1500:
        # Split response into chunks at newlines, keeping under 1500 chars
        chunks = []
        current_chunk = ""
        for line in response_content.splitlines(keepends=True):
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
        await message.channel.send(response_content)


def get_user_from_discord(message):
    """Get a Honcho user object for the message author"""
    user_id = f"discord_{str(message.author.id)}"
    user = honcho_client.apps.users.get_or_create(name=user_id, app_id=app.id)
    return user


def get_session_from_discord(channel_id, user_id):
    """Get a Honcho session object for the message"""
    location_id = str(channel_id)
    session, is_new = get_session(
        honcho_client, app.id, user_id, {location_id: True}, create=True
    )
    # session will always exist because create=True
    assert session is not None
    if is_new:
        logger.info(f"New session created for {user_id} in {location_id}")
    return session


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Waiting for messages...")


@bot.event
async def on_message(message):
    """
    Receive a message from Discord and respond with a message from our LLM assistant.
    """
    if not validate_message(message):
        return

    input = sanitize_message(message)

    # If the message is empty after sanitizing, ignore it
    if not input:
        return

    user = get_user_from_discord(message)

    session = get_session_from_discord(message.channel.id, user.id)

    # Get messages
    history_iter = honcho_client.apps.users.sessions.messages.list(
        app_id=app.id, session_id=session.id, user_id=user.id
    )
    history = list(msg for msg in history_iter)

    async with message.channel.typing():
        response = llm(input, history)

    await send_discord_message(message, response)

    # Save both the user's message and the bot's response to the session
    honcho_client.apps.users.sessions.messages.batch(
        app_id=app.id,
        user_id=user.id,
        session_id=session.id,
        messages=[
            {"content": input, "is_user": True},
            {"content": response, "is_user": False},
        ],
    )


@bot.slash_command(
    name="restart",
    description="Reset all of your messaging history with Honcho in this channel.",
)
async def restart(ctx):
    logger.info(f"Restarting conversation for {ctx.author.name}")
    async with ctx.typing():
        user = get_user_from_discord(ctx)
        session = get_session_from_discord(ctx.channel_id, user.id)

        if session:
            # Delete the session
            honcho_client.apps.users.sessions.delete(
                app_id=app.id, user_id=user.id, session_id=session.id
            )

    await ctx.respond("The conversation has been restarted.")


@bot.slash_command(
    name="dialectic",
    description="Query the Honcho Dialectic endpoint.",
)
async def dialectic(ctx, query: str):
    await ctx.defer()

    try:
        user = get_user_from_discord(ctx)
        session = get_session_from_discord(ctx.channel_id, user.id)

        response = honcho_client.apps.users.sessions.chat(
            app_id=app.id,
            user_id=user.id,
            session_id=session.id,
            queries=query,
            stream=True,
        )

        if response:
            await ctx.followup.send(response)
        else:
            await ctx.followup.send(
                f"I don't know anything about {ctx.author.name} because we haven't talked yet!"
            )
    except Exception as e:
        logger.error(f"Error calling Dialectic API: {e}")
        await ctx.followup.send(
            f"Sorry, there was an error processing your request: {str(e)}"
        )


@bot.slash_command(
    name="document",
    description="Save a document to Honcho.",
)
async def document(ctx, doc: str):
    await ctx.defer()

    try:
        user = get_user_from_discord(ctx)
        collection = get_user_collection(honcho_client, app.id, user.id)

        honcho_client.apps.users.collections.documents.create(
            app_id=app.id,
            user_id=user.id,
            collection_id=collection.id,
            content=doc,
        )

        await ctx.followup.send("Document saved.")
    except Exception as e:
        logger.error(f"Error saving document: {e}")
        await ctx.followup.send(
            f"Sorry, there was an error processing your request: {str(e)}"
        )


bot.run(BOT_TOKEN)
