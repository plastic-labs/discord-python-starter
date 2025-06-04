import logging
import os
import json
import time
from collections import defaultdict, deque

import discord
from dotenv import load_dotenv
from honcho import Honcho

from honcho_utils import get_session, get_user_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("discord").setLevel(logging.ERROR)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# API Configuration - supports both OpenAI and Anthropic
API_PROVIDER = os.getenv("API_PROVIDER", "anthropic").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# Model configuration
MODEL_NAME = os.getenv("MODEL_NAME")
if not MODEL_NAME:
    MODEL_NAME = (
        "claude-3-5-sonnet-20241022" if API_PROVIDER == "anthropic" else "gpt-4"
    )

# Token configuration
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))

# Bot name and topic configuration for intelligent responses
BOT_NAME = os.getenv("BOT_NAME", "Assistant").strip('"')
BOT_NAME_VARIANTS = os.getenv("BOT_NAME_VARIANTS", "").strip('"')
BOT_TOPICS = os.getenv("BOT_TOPICS", "").strip('"')

APP_NAME = os.getenv("APP_NAME")

# System prompt configuration - can be from env var or file
SYSTEM_PROMPT_FILE = os.getenv("SYSTEM_PROMPT_FILE")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful AI assistant.")

BASE_CONTEXT_FILE = os.getenv("BASE_CONTEXT_FILE", "base_context.json")

# Rate limiting configuration
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "1"))
RATE_LIMIT_MESSAGE = os.getenv(
    "RATE_LIMIT_MESSAGE",
    "⏰ I'm responding too quickly! Please wait a moment before asking again.",
)
RATE_LIMIT_CONFIG_FILE = os.getenv("RATE_LIMIT_CONFIG_FILE", "rate_limits.json")

# Rate limiting storage: channel_id -> deque of recent response timestamps
response_timestamps = defaultdict(lambda: deque())

# Per-channel rate limits loaded from config file
channel_rate_limits = {}


def _build_name_variants():
    """Build set of bot name variants for intelligent message detection"""
    variants = set()

    # Add configured variants
    if BOT_NAME_VARIANTS:
        for variant in BOT_NAME_VARIANTS.split(","):
            clean_variant = variant.strip()
            if clean_variant:
                variants.add(clean_variant.lower())

    # Add bot name variants
    if BOT_NAME:
        variants.add(BOT_NAME.lower())

    return list(variants)


def _build_topics():
    """Build set of topics the bot should respond to"""
    topics = set()
    if BOT_TOPICS:
        for topic in BOT_TOPICS.split(","):
            clean_topic = topic.strip()
            if clean_topic:
                topics.add(clean_topic.lower())
    return list(topics)


# Build variants and topics at startup
NAME_VARIANTS = _build_name_variants()
TOPIC_VARIANTS = _build_topics()

honcho_client = Honcho()
app = honcho_client.apps.get_or_create(name=APP_NAME)

logger.info(f"Honcho app acquired with id {app.id}")
logger.info(f"Max tokens per response: {MAX_TOKENS}")
logger.info(
    f"Bot configured with {len(NAME_VARIANTS)} name variants and {len(TOPIC_VARIANTS)} topic variants"
)


def load_system_prompt():
    """Load system prompt from file if specified, otherwise use env variable"""
    if SYSTEM_PROMPT_FILE and os.path.exists(SYSTEM_PROMPT_FILE):
        try:
            with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
                logger.info(f"Loaded system prompt from {SYSTEM_PROMPT_FILE}")
                return prompt
        except Exception as e:
            logger.error(f"Error loading system prompt from file: {e}")
            logger.info("Falling back to environment variable")

    return SYSTEM_PROMPT


def load_rate_limit_config():
    """Load per-channel rate limit configuration from JSON file"""
    global channel_rate_limits
    try:
        if os.path.exists(RATE_LIMIT_CONFIG_FILE):
            with open(RATE_LIMIT_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Convert string channel IDs to integers
                channel_rate_limits = {int(k): v for k, v in config.items()}
                logger.info(
                    f"Loaded rate limit config for {len(channel_rate_limits)} channels"
                )
        else:
            logger.info(
                f"No rate limit config file found ({RATE_LIMIT_CONFIG_FILE}), using global default"
            )
    except Exception as e:
        logger.error(f"Error loading rate limit config: {e}")
        channel_rate_limits = {}


def get_rate_limit_for_channel(channel_id: int) -> int:
    """Get the rate limit for a specific channel, falling back to global default"""
    return channel_rate_limits.get(channel_id, RATE_LIMIT_PER_MINUTE)


# Load configurations at startup
SYSTEM_PROMPT = load_system_prompt()
load_rate_limit_config()

logger.info(f"Default rate limiting: {RATE_LIMIT_PER_MINUTE} messages per minute")
if channel_rate_limits:
    logger.info(
        f"Custom rate limits configured for {len(channel_rate_limits)} channels"
    )

# Initialize API clients based on provider
if API_PROVIDER == "anthropic":
    try:
        import anthropic

        anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info("Using Anthropic API")
    except ImportError:
        logger.error("Anthropic library not installed. Run: pip install anthropic")
        exit(1)
elif API_PROVIDER == "openai":
    try:
        from openai import OpenAI

        openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        logger.info(f"Using OpenAI API with base URL: {OPENAI_BASE_URL}")
    except ImportError:
        logger.error("OpenAI library not installed. Run: pip install openai")
        exit(1)
else:
    logger.error(
        f"Unsupported API_PROVIDER: {API_PROVIDER}. Use 'anthropic' or 'openai'"
    )
    exit(1)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
bot = discord.Bot(intents=intents)


def load_base_context():
    """Load base context from JSON file"""
    try:
        if os.path.exists(BASE_CONTEXT_FILE):
            with open(BASE_CONTEXT_FILE, "r", encoding="utf-8") as f:
                base_context = json.load(f)
                logger.info(f"Loaded base context with {len(base_context)} messages")
                return base_context
        else:
            logger.warning(f"Base context file {BASE_CONTEXT_FILE} not found")
            return []
    except Exception as e:
        logger.error(f"Error loading base context: {e}")
        return []


def llm(prompt, chat_history=None) -> str:
    """
    Call the configured LLM API with the given prompt, base context, and chat history.
    Supports both OpenAI and Anthropic APIs.
    """
    try:
        messages = []

        # Add base context first (this prepends all other context)
        base_context = load_base_context()
        messages.extend(base_context)

        # Add chat history from Honcho
        if chat_history:
            messages.extend(
                [
                    {
                        "role": "user" if msg.is_user else "assistant",
                        "content": msg.content,
                    }
                    for msg in chat_history
                ]
            )

        # Add current user message
        messages.append({"role": "user", "content": prompt})

        # Create token-aware system prompt
        token_aware_prompt = f"{SYSTEM_PROMPT}\n\nIMPORTANT: You have a strict limit of {MAX_TOKENS} tokens for your response. Keep your answers concise and complete within this limit. If you need to provide a long response, prioritize the most important information and indicate if there's more to discuss."

        if API_PROVIDER == "anthropic":
            # Call Anthropic API
            response = anthropic_client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system=token_aware_prompt,
                messages=messages,
            )
            return response.content[0].text

        elif API_PROVIDER == "openai":
            # Call OpenAI API (or OpenAI-compatible APIs like OpenRouter)
            # For OpenAI, system prompt goes in messages array
            openai_messages = [{"role": "system", "content": token_aware_prompt}]
            openai_messages.extend(messages)

            response = openai_client.chat.completions.create(
                model=MODEL_NAME, messages=openai_messages, max_tokens=MAX_TOKENS
            )
            return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Error calling {API_PROVIDER.upper()} API: {e}")
        return f"Error: {e}"


def validate_message(message) -> bool:
    """
    Determine if the message is valid for the bot to respond to.
    Returns True if the message is a direct @mention in a public channel
    and is not from the bot itself.
    """
    if message.author == bot.user:
        return False

    if isinstance(message.channel, discord.DMChannel):
        return False

    if not bot.user.mentioned_in(message):
        return False

    return True


def relevant_message(message) -> bool:
    """
    Determine if the message contains references to the bot that
    warrant a response even without @mention. Checks for bot name
    variants configured in BOT_NAME_VARIANTS and topics from BOT_TOPICS.
    """
    if message.author == bot.user:
        return False

    if isinstance(message.channel, discord.DMChannel):
        return False

    content = message.content.lower()
    return any(variant in content for variant in NAME_VARIANTS) or any(
        topic in content for topic in TOPIC_VARIANTS
    )


def should_respond(message) -> bool:
    """
    Determine if the bot should respond to this message.
    Responds to either direct @mentions or relevant messages.
    """
    return validate_message(message) or relevant_message(message)


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
    if not should_respond(message):
        return

    input = sanitize_message(message)

    # If the message is empty after sanitizing, ignore it
    if not input:
        return

    # Check rate limiting for this channel
    if is_rate_limited(message.channel.id):
        await message.channel.send(RATE_LIMIT_MESSAGE)
        return

    user = get_user_from_discord(message)

    session = get_session_from_discord(message.channel.id, user.id)

    # Get messages
    history_iter = honcho_client.apps.users.sessions.messages.list(
        app_id=app.id, session_id=session.id, user_id=user.id, size=10
    )
    history = list(msg for msg in history_iter)

    async with message.channel.typing():
        response = llm(input, history)

    await send_discord_message(message, response)

    # Record that we sent a response (for rate limiting)
    record_response(message.channel.id)

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


def is_rate_limited(channel_id: int) -> bool:
    """
    Check if the bot is rate limited for this channel.
    Returns True if rate limited, False if ok to respond.
    """
    current_time = time.time()
    channel_timestamps = response_timestamps[channel_id]

    # Get rate limit for this specific channel
    rate_limit = get_rate_limit_for_channel(channel_id)

    # Remove timestamps older than 1 minute
    while channel_timestamps and current_time - channel_timestamps[0] > 60:
        channel_timestamps.popleft()

    # Check if we've hit the rate limit
    if len(channel_timestamps) >= rate_limit:
        return True

    return False


def record_response(channel_id: int):
    """Record that we just sent a response in this channel."""
    response_timestamps[channel_id].append(time.time())


bot.run(BOT_TOKEN)
