import os
# import logging
import asyncio
import discord

from dotenv import load_dotenv

from utils import default

def main():

    load_dotenv()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # logger = logging.getLogger("discord")
    # logger.setLevel(logging.DEBUG)
    # handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
    # handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
    # logger.addHandler(handler)

    # database = default.Database(loop=loop)


    isTest = False


    intent = discord.Intents.all()

    client = default.DiscordBot(
        command_prefix="$", help_command=None, case_insensitive=True, intents=intent, loop=loop, isTest = isTest
    )

    TOKEN = os.environ["BOT_TEST_TOKEN"] if isTest else os.environ["BOT_TOKEN"]
    loop.create_task(client.run(TOKEN))
    loop.run_forever()

if __name__ == "__main__":
    main()
