import os
from uuid import uuid1
import discord
from honcho import Honcho

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

app_name = "<YOUR APP NAME>"  # TODO replace with your app name

# honcho = Honcho(app_name=app_name, base_url="http://localhost:8000") # uncomment to use local
honcho = Honcho(app_name=app_name)  # uses demo server at https://demo.honcho.dev
honcho.initialize()

bot = discord.Bot(intents=intents)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.event
async def on_member_join(member):
    """Event that is run when a new member joins the server"""
    await member.send(f"*Hello {member.name}, welcome to the server!")


@bot.event
async def on_message(message):
    """Event that is run when a message is sent in a channel that the bot has access to"""

    if message.author == bot.user or message.guild is not None:
        # ensure the bot does not reply to itself
        return

    # Get a user object for the message author
    user_id = f"discord_{str(message.author.id)}"
    user = honcho.get_or_create_user(user_id)

    # Get the session associated with the user and location
    location_id = str(message.channel.id)  # Get the channel id for the message

    sessions = list(
        user.get_sessions_generator(location_id=location_id, is_active=True)
    )

    if len(sessions) > 0:
        session = sessions[0]
    else:
        session = user.create_session(location_id)

    # FIXME add logic to use session's messages
    # history = list(session.get_messages_generator())

    inp = message.content
    session.create_message(is_user=True, content=inp)  # Add user message to session

    async with message.channel.typing():
        response = "<YOUR CHAT MODEL>"  # TODO reply with logic to generate a response
        await message.channel.send(response)

    session.create_message(is_user=False, content=response)  # Add bot message to sesion


@bot.slash_command(name="restart", description="Restart the Conversation")
async def restart(ctx):
    """Close the Session associated with a specific user and channel"""
    user_id = f"discord_{str(ctx.author.id)}"
    user = honcho.get_or_create_user(user_id)
    location_id = str(ctx.channel_id)
    sessions = list(user.get_sessions_generator(location_id))
    sessions[0].close() if len(sessions) > 0 else None

    msg = (
        "Great! The conversation has been restarted. What would you like to talk about?"
    )
    await ctx.respond(msg)


bot.run(os.environ["BOT_TOKEN"])
