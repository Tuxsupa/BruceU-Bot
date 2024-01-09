import os
import sys
import asyncio
from dotenv import load_dotenv

import discord
from utils import default

import logging
logger = logging.getLogger("discord")

def main():

    load_dotenv()

    loop = asyncio.get_event_loop()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # discord.utils.setup_logging(level=logging.INFO, root=False)

    isTest = False

    intent = discord.Intents.all()
    client = default.DiscordBot(
        command_prefix="$", help_command=None, case_insensitive=True, intents=intent, loop=loop, isTest=isTest
    )

    TOKEN = os.environ["BOT_TEST_TOKEN"] if isTest else os.environ["BOT_TOKEN"]
    #loop.run_until_complete(client.start(TOKEN))
    loop.create_task(client.run(TOKEN))
    loop.run_forever()

if __name__ == "__main__":
    main()
