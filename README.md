# discord-python-starter

A starter template for making discord bots with
[Honcho](https//github.com/plastic-labs/honcho) that are deployed to fly.io

The main logic for the discord bot is in the `bot.py` file. It contains 3
functions. 

* `on_member_join` — the event that is run when a member joins the server the bot
is in
* `on_message` — the event that is run when a message is sent to the server
the bot is in
* `restart` — A discord slash command called restart. It is used to close the
`session` and create a new one

## Getting Started

This project uses python with [poetry](https://python-poetry.org/) for
dependency management. The main two dependencies are `Honcho` and
`pycord`.

To get started, run `poetry install`

With poetry, you can start a `poetry shell` to initiate a virtual environment for
the project. 

From here you can edit the `bot.py` file to add whatever logic you want for the
3 methods described above. Additional functionality can be added to the bot.
Refer to the [py-cord documentation](https://pycord.dev)

### Docker

The project uses [Docker](https://www.docker.com/) for packaging the bot code
and providing a single executable to start the bot. The below commands will
build the docker image and then run the bot using a local `.env` file.

```bash
docker build -t discord-bot .
docker run --env-file .env discord-bot 
```

## Deployment

The project contains a generic `fly.toml` that will run a single process for the
discord bot.

To deploy the bot, run `fly deploy`
