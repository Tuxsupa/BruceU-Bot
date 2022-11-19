import discord
import os
import logging

from utils import default
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)

intent = discord.Intents.all()


client = default.DiscordBot(
    command_prefix="$", help_command=None, case_insensitive=True, intents=intent, owner_id=270224083684163584
)


# TOKEN = os.environ["BOT_TEST_TOKEN"]
TOKEN = os.environ["BOT_TOKEN"]
client.run(TOKEN)
