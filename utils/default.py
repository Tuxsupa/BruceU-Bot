import discord
import os
import psycopg
import aiohttp
import re

from utils import pubgData
from discord.ext.commands import Bot
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()


class DiscordBot(Bot):
    def __init__(self, *args, prefix=None, loop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = prefix
        self.loop = loop

    async def setup_hook(self):
        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                name = file[:-3]
                await self.load_extension(f"cogs.{name}")

        if not hourlyOER.is_running():
            hourlyOER.start()

        if not updateEverything.is_running():
            updateEverything.start()

        await self.tree.sync()

        global DEV
        DEV = await self.fetch_user(self.owner_id)

    async def on_message(self, ctx):
        if ctx.author.bot is False:
            result = ctx.content

            checkEmotes = re.findall("((?:(?!<:|<a:):)(?:(?!\w{1,64}:\d{17,18})\w{1,64})(?:(?!>):))", result)
            findEmotes = []

            if checkEmotes:
                findEmotes = [str(e.split(":")[1].replace(":", "")) for e in checkEmotes]

            if findEmotes:
                findEmotes = [discord.utils.get(self.emojis, name=e) for e in findEmotes]

                if findEmotes and not all(i is None for i in findEmotes):
                    webhooks = await ctx.channel.webhooks()
                    if not any(webhook.user.id == self.user.id for webhook in webhooks):
                        print("Created Webhooks")
                        await ctx.channel.create_webhook(name="BruceU-1")
                        await ctx.channel.create_webhook(name="BruceU-2")
                        webhooks = await ctx.channel.webhooks()

                    for webhook in webhooks:
                        if webhook.user.id == self.user.id:
                            botWebhook = webhook
                            break

                    animated = ""

                    for emote in findEmotes:
                        if emote:
                            if emote.animated is True:
                                animated = "a"
                            emoteString = "<" + animated + ":" + emote.name + ":" + str(emote.id) + ">"
                            result = re.sub(
                                "((?:(?!<:|<a:):)(?:(?!\w{1,64}:\d{17,18})\w{1,64})(?:(?!>):))", emoteString, result, 1
                            )

                    embeds = []

                    if ctx.reference:
                        embed = discord.Embed(
                            description="**[Reply to:](" + ctx.reference.jump_url + ")** " + ctx.reference.resolved.content,
                            color=0x000000,
                        )
                        embed.set_author(
                            name=ctx.reference.resolved.author.display_name,
                            icon_url=ctx.reference.resolved.author.display_avatar,
                        )
                        embeds.append(embed)

                    if ctx.attachments:
                        for attachment in ctx.attachments:
                            embed = discord.Embed(
                                description="📂 " + "[" + attachment.filename + "](" + attachment.proxy_url + ")",
                                color=0x000000,
                            )
                            embed.set_image(url=attachment.proxy_url)
                            embeds.append(embed)

                    messageSent = await botWebhook.send(
                        str(result),
                        username=ctx.author.display_name,
                        avatar_url=ctx.author.display_avatar.url,
                        allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=True),
                        embeds=embeds,
                    )
                    # messageSent.realID = ctx.author.id

                    await ctx.delete()

        await self.process_commands(ctx)

    async def on_command_error(self, message, error):
        print(error)
        if isinstance(error, commands.MissingRole):
            await embedMessage(self, message, description="Role required missing")
        if isinstance(error, commands.BadArgument):
            await embedMessage(self, message, description="Wrong value for the field")
        if isinstance(error, commands.MissingRequiredArgument):
            await embedMessage(self, message, description=error.param.name.capitalize() + " field is required")

    """ async def on_ready(self):
        global DEV
        DEV = await self.client.fetch_user(self.client.owner_id) """


async def embedMessage(self, ctx, title=None, description=None):
    embed = discord.Embed(title=title, description=description, color=0x000000, timestamp=ctx.message.created_at)
    embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text="Bot made by Tuxsuper", icon_url=DEV.display_avatar.url)
    await ctx.send(embed=embed)


try:
    DATABASE_URL = os.environ["DATABASE_URL"]
    CONNECTION = psycopg.connect(DATABASE_URL, sslmode="require")
    CURSOR = CONNECTION.cursor()
    print("Connected to PostgreSQL")

except (Exception, psycopg.Error) as error:
    print(error)


async def connectDB(query="", values=None, isSelect=False):
    try:
        print(query)

        if values is not None:
            CURSOR.execute(query, values)
        else:
            CURSOR.execute(query)

        if query.startswith("SELECT") is False:
            CONNECTION.commit()

        if query.startswith("SELECT") is True or isSelect is True:
            return CURSOR.fetchall()

    except (Exception, psycopg.Error) as error:
        print("Failed to select record from the table", error)


async def requestAio(url="", header=None, type=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=header) as r:
            if r.status == 200:
                print("Successfully Connected!")
                if type == None:
                    return await r.json()
                elif type == "content":
                    return await r.read()
            else:
                print("Failed to Connect")
                return


@tasks.loop(hours=1)
async def hourlyOER():
    print("Hourly Update")
    async with aiohttp.ClientSession() as session:
        hourlyOER.rates = await session.get(
            "https://openexchangerates.org/api/latest.json?app_id=" + os.environ["OPEN_EXCHANGE_RATES_ID"]
        )
        hourlyOER.rates = await hourlyOER.rates.json()


@tasks.loop(minutes=3)
async def updateEverything():
    player_stat = await requestAio(pubgData.FORSEN_URL, pubgData.PUBG_HEADER)

    match_id_list = player_stat["data"][0]["relationships"]["matches"]["data"]

    matchIDQuery = """SELECT match_id FROM kills"""
    matchIDs = await connectDB(matchIDQuery)
    matchIDs = [r[0] for r in matchIDs]

    print("Starting updating")
    for match in match_id_list:
        if match["id"] not in matchIDs:
            await pubgData.addRows(match["id"])
            matchIDs.append(match["id"])

    print("Stopping updating")


""" @client.tree.context_menu(name="Find Author")
async def findEmoteAuthor(interaction: discord.Interaction, message: discord.Message):
    async for checkMessage in message.channel.history(limit=5, before=message):
        if checkMessage == message:
            print("KUKE")

    await interaction.responde.send_message(content="test", ephemeral=True) """


""" @client.tree.context_menu(name="Delete Message")
async def deleteEmoteMessage(interaction: discord.Interaction, message: discord.Message):
    if interaction.user.id == message.author.id:
        print("test")
    await interaction.responde.send_message(content="test", ephemeral=True) """
