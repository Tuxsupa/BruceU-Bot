import os
import logging
import asyncio
import discord

from dotenv import load_dotenv

from utils import default



load_dotenv()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)

# database = default.Database(loop=loop)

intent = discord.Intents.all()


client = default.DiscordBot(
    command_prefix="$", help_command=None, case_insensitive=True, intents=intent, owner_id=270224083684163584, loop=loop
)


TOKEN = os.environ["BOT_TOKEN"]
# TOKEN = os.environ["BOT_TEST_TOKEN"]


loop.create_task(client.run(TOKEN))
loop.run_forever()
