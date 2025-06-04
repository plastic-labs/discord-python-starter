# discord-python-starter

A starter template for Discord bots with [Honcho](https://github.com/plastic-labs/honcho) memory management, deployable to Fly.io.

## Features

- 🤖 **Multi-provider support**: Anthropic, OpenAI, and OpenRouter
- 🧠 **Memory management**: Persistent conversation history via Honcho
- 🎭 **Custom personalities**: System prompts and base context
- ⏰ **Rate limiting**: Global and per-channel limits
- 📁 **File-based config**: System prompts and rate limits from files
- 🔧 **Easy deployment**: Ready for Fly.io with Docker

## Quick Start

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Choose configuration:**
   ```bash
   # Anthropic
   cp .env.template .env # Populate ANTHROPIC_API_KEY
   
   # OpenAI
   cp .env.template .env # Populate OPENAI_API_KEY
   
   # OpenRouter (multiple models)
   cp .env.template # Populate the base URL & the relevant API key
   ```

3. **Set up base context: (optional)**
   ```bash
   cp base_context.example.json base_context.json
   # Edit with your agent's personality
   ```

4. **Run locally:**
   ```bash
   source .venv/bin/activate
   python src/bot.py
   ```

## Configuration

### Environment Variables

Key configuration options:

```bash
# Discord & API
BOT_TOKEN=your_discord_bot_token
API_PROVIDER=anthropic  # or "openai"
ANTHROPIC_API_KEY=your_key  # if using Anthropic
OPENAI_API_KEY=your_key     # if using OpenAI/OpenRouter
OPENAI_BASE_URL=https://openrouter.ai/api/v1  # for OpenRouter

# Model & Agent
MODEL_NAME=claude-3-5-sonnet-20241022
APP_NAME=your-unique-app-name
SYSTEM_PROMPT=You are a helpful AI assistant.
BASE_CONTEXT_FILE=base_context.json

# Rate Limiting
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_MESSAGE=⏰ Please wait before asking again.
```

### Base Context

Create conversation context that prepends all interactions:

```bash
cp base_context.example.json base_context.json
```

Example format:
```json
[
  {
    "role": "user",
    "content": "What is your role?"
  },
  {
    "role": "assistant", 
    "content": "I'm a specialized AI assistant for your team..."
  }
]
```

## Advanced Configuration

### System Prompt from File

For complex prompts, use a separate file:

```bash
# Create prompt file
cp system_prompt.example.txt system_prompt.txt

# Configure environment
SYSTEM_PROMPT_FILE=system_prompt.txt
```

### Per-Channel Rate Limits

Configure different limits for different channels:

```bash
# Create config file
cp rate_limits.example.json rate_limits.json

# Get channel IDs (Discord Developer Mode → right-click channel → Copy ID)
# Configure limits
{
  "123456789012345678": 3,   // # Channel 1
  "234567890123456789": 15,  // # Channel 2
  "345678901234567890": 5    // # Channel 3
}

# Set environment variable
RATE_LIMIT_CONFIG_FILE=rate_limits.json
```

## Discord Setup

1. **Create Discord Application:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create new application → Bot section → Add Bot
   - Copy bot token → Enable Message Content Intent

2. **Invite Bot to Server:**
   - OAuth2 → URL Generator → Select `bot` and `applications.commands`
   - Permissions: Send Messages, Use Slash Commands, Read Message History

3. **Test Bot:**
   - Mention bot: `@YourBot hello`
   - Slash commands: `/restart`, `/dialectic query`, `/document text`

## Deployment

### Fly.io Deployment

1. **Initialize:**
   ```bash
   fly launch --no-deploy
   ```

2. **Set secrets:**
   ```bash
   fly secrets set BOT_TOKEN="your_token"
   fly secrets set API_PROVIDER="anthropic"
   fly secrets set ANTHROPIC_API_KEY="your_key"
   fly secrets set MODEL_NAME="claude-3-5-sonnet-20241022"
   fly secrets set APP_NAME="my-discord-agent"
   fly secrets set SYSTEM_PROMPT="Your system prompt"
   fly secrets set RATE_LIMIT_PER_MINUTE="10"
   ```

3. **Deploy:**
   ```bash
   fly deploy
   ```

4. **Check status:**
   ```bash
   fly logs
   fly status
   ```

### Docker Deployment

```bash
docker build -t discord-bot . && docker run --env-file .env discord-bot
```

## Usage

**Bot responds to:**
- Direct mentions: `@YourBot help me debug this`
- Slash commands:
  - `/restart` - Reset conversation history
  - `/dialectic query` - Search conversation history  
  - `/document text` - Save information to knowledge base

**Rate limiting:**
- Per-channel limits (independent tracking)
- Global fallback for unconfigured channels
- Shows friendly message when limited

## Architecture

### Discord ↔ Honcho Flow

1. **Message received** → validate & sanitize
2. **Rate limit check** → per-channel limits
3. **Honcho session** → get/create user & session for channel
4. **Context assembly** → base context + history + current message
5. **API call** → Anthropic/OpenAI with full context
6. **Response & storage** → send to Discord + save to Honcho

### Memory Management

- **Per-channel sessions**: Each Discord channel = separate conversation
- **Base context**: Always included in API calls (personality/background)
- **Persistent history**: Survives bot restarts via Honcho
- **User isolation**: Each user has independent memory per channel

## Troubleshooting

**Bot not responding:**
- Check Discord permissions & bot token
- Verify API keys and model names
- Check rate limits (wait 1 minute)
- View logs: `fly logs`

**Configuration issues:**
- Validate JSON syntax for config files
- Ensure channel IDs are strings in JSON
- Check file permissions (readable by bot)
- Verify environment variables are set

**Rate limiting:**
- Adjust `RATE_LIMIT_PER_MINUTE` if too restrictive
- Use per-channel config for fine-tuning
- Monitor logs for rate limit messages

## Cost Considerations

**API Costs (per million tokens):**
- Claude 3.5 Sonnet: ~$3-15
- Claude 3 Opus: ~$15-75  
- Claude 3 Haiku: ~$0.25-1.25
- GPT-4: ~$30-60
- GPT-3.5 Turbo: ~$0.5-2

**Hosting:**
- Fly.io: ~$5-10/month

**Cost optimization:**
- Use rate limiting to control usage
- Choose appropriate models for use case
- Keep base context reasonably sized
- Monitor usage via provider dashboards

## File Structure

```
discord-python-starter/
├── src/
│   ├── bot.py                 # Main bot logic
│   └── honcho_utils.py        # Honcho utilities
├── env.template               # Credentials config
├── base_context.example.json  # Example base context
├── system_prompt.example.txt  # Example system prompt
├── rate_limits.example.json   # Example rate limits
├── Dockerfile                 # Docker configuration
├── fly.toml                   # Fly.io configuration
└── pyproject.toml            # Python dependencies
```

> [!CAUTION]
> Never commit `.env` files or API keys to version control. The included `.gitignore` prevents this.

---