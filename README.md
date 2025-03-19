# discord-python-starter

A starter template for making discord bots with
[Honcho](https//github.com/plastic-labs/honcho) that are deployed to fly.io

The main logic for the discord bot is in the `bot.py` file. It contains 2
functions.

- `on_message` — the event that is run when a message is sent to the server
  the bot is in
- `restart` — A discord slash command called restart. It is used to close the
  `session` and create a new one

The template uses [openrouter](https://openrouter.ai) for LLM inferences and
supports all the LLMs on there

## Getting Started

First, install the dependencies for the project.

```bash
uv sync
```

From here you can edit the `bot.py` file to add whatever logic you want for the
3 methods described above. Additional functionality can be added to the bot.
Refer to the [py-cord documentation](https://pycord.dev)

### Environment Variables

The repo contains a `.env.template` file that shows all the default environment
variables used by the discord bot. Make a copy of this template and fill out the
`.env` with your own values.

```bash
cp .env.template .env
```

> [!CAUTION]
> Make sure you do not push your `.env` file to GitHub or any other version
> control. These should remain secret. By default the included `.gitignore` file
> should prevent this.

### Docker

The project uses [Docker](https://www.docker.com/) for packaging the bot code
and providing a single executable to start the bot. The below commands will
build the docker image and then run the bot using a local `.env` file.

```bash
docker build -t discord-bot .
docker run --env-file .env discord-bot
```

## Deployment

To launch the bot for the first time, run `fly launch`.
This will generate a `fly.toml` file that you can use to deploy/update the bot.
Use `cat .env | fly secrets import` to add the environment variables to fly.

After launching, use `fly deploy` to update your deployment.
