import os
import discord
import requests
from dotenv import load_dotenv
from honcho import Honcho

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
MODEL_NAME = os.getenv('MODEL_NAME')
MODEL_API_KEY = os.getenv('MODEL_API_KEY')
MODEL_ENDPOINT = os.getenv('MODEL_ENDPOINT')
MODEL_TYPE = os.getenv('MODEL_TYPE')
APP_NAME = os.getenv('APP_NAME')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

honcho = Honcho(environment="demo")  # uses demo server at https://demo.honcho.dev
app = honcho.apps.get_or_create(name=APP_NAME)

bot = discord.Bot(intents=intents)

def make_api_request(prompt, chat_history=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MODEL_API_KEY}"
    }
    
    if MODEL_TYPE == 'chat':
        messages = []
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": MODEL_NAME,
            "messages": messages
        }
    else:  # completions
        # For non-chat models, we'll concatenate the history and prompt
        full_prompt = ""
        if chat_history:
            for msg in chat_history:
                full_prompt += f"{msg['role']}: {msg['content']}\n"
        full_prompt += f"user: {prompt}"
        payload = {
            "model": MODEL_NAME,
            "prompt": full_prompt,
            "max_tokens": 150
        }

    response = requests.post(MODEL_ENDPOINT, headers=headers, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        if MODEL_TYPE == 'chat':
            return data['choices'][0]['message']['content']
        else:  # completions
            return data['choices'][0]['text']
    else:
        return f"Error: {response.status_code} - {response.text}"


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.event
async def on_message(message):
    """Event that is run when a message is sent in a channel that the bot has access to"""
    if message.author == bot.user:
        # ensure the bot does not reply to itself
        return

    print(message.content)
    # Get a user object for the message author
    user_id = f"discord_{str(message.author.id)}"
    user = honcho.apps.users.get_or_create(name=user_id, app_id=app.id)

    # Get the session associated with the user and location
    location_id = str(message.channel.id)  # Get the channel id for the message

    sessions = [
        session
        for session in honcho.apps.users.sessions.list(
            user_id=user.id, app_id=app.id, is_active=True, location_id=location_id
        )
    ]

    if len(sessions) > 0:
        session = sessions[0]
    else:
        session = honcho.apps.users.sessions.create(
            user_id=user.id, app_id=app.id, location_id=location_id
        )

    # Get the session's message history
    history = [
        message for message in 
        honcho.apps.users.sessions.messages.list(
            app_id=app.id,
            user_id=user.id,
            session_id=session.id
        )
    ]

    # Add user message to session
    input = message.content
    honcho.apps.users.sessions.messages.create(
        app_id=app.id,
        user_id=user.id,
        session_id=session.id,
        content=input,
        is_user=True,
    )

    async with message.channel.typing():
        response = make_api_request(input, history)  # Pass history to the function
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
    """Close the Session associated with a specific user and channel"""
    user_id = f"discord_{str(ctx.author.id)}"
    # user = honcho.get_or_create_user(user_id)
    user = honcho.apps.users.get_or_create(name=user_id, app_id=app.id)
    location_id = str(ctx.channel_id)
    # sessions = list(user.get_sessions_generator(location_id))
    sessions = [
        session
        for session in honcho.apps.users.sessions.list(
            user_id=user.id, app_id=app.id, is_active=True, location_id=location_id
        )
    ]
    if len(sessions) > 0:
        honcho.apps.users.sessions.delete(
            app_id=app.id, user_id=user.id, session_id=sessions[0].id
        )

    msg = (
        "The conversation has been restarted."
    )
    await ctx.respond(msg)


bot.run(os.environ["BOT_TOKEN"])
