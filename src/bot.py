import logging
import os

import discord
from dotenv import load_dotenv
from honcho import Honcho
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("discord").setLevel(logging.ERROR)

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")


honcho_client = Honcho()

assistant = honcho_client.peer(id="assistant", config={"observe_me": False})

openai = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=MODEL_API_KEY)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
bot = discord.Bot(intents=intents)


def llm(session, prompt) -> str:
    """
    Call the LLM with the given prompt and chat history.

    You should expand this function with custom logic, prompts, etc.
    """
    messages: list[dict[str, object]] = session.get_context().to_openai(
        assistant=assistant
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


def get_peer_id_from_discord(message):
    """Get a Honcho peer ID for the message author"""
    return f"discord_{str(message.author.id)}"


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

    peer = honcho_client.peer(id=get_peer_id_from_discord(message))
    session = honcho_client.session(id=str(message.channel.id))

    async with message.channel.typing():
        response = llm(session, input)

    await send_discord_message(message, response)

    # Save both the user's message and the bot's response to the session
    session.add_messages(
        [
            peer.message(input),
            assistant.message(response),
        ]
    )


@bot.slash_command(
    name="dialectic",
    description="Query the Honcho Dialectic endpoint.",
)
async def dialectic(ctx, query: str):
    await ctx.defer()

    try:
        peer = honcho_client.peer(id=get_peer_id_from_discord(ctx))
        session = honcho_client.session(id=str(ctx.channel.id))

        response = peer.chat(
            query=query,
            session_id=session.id,
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


bot.run(BOT_TOKEN)
