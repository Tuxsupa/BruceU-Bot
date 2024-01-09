import os
# import logging
import asyncio
import discord
import sys

from dotenv import load_dotenv

from utils import default

def main():

    load_dotenv()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


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
