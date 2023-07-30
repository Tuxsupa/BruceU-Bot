import os
import re
import textwrap
import datetime
import asyncio
import psycopg
import aiohttp
import discord

from discord.ext.commands import Bot
from discord.ext import commands, tasks

from PIL import Image, ImageFont, ImageDraw
from psycopg.types.json import Json
from fake_useragent import UserAgent
from dotenv import load_dotenv

from utils import pubgData, twitchAPI
from utils import twitchAPI_Test

load_dotenv()


class DiscordBot(Bot):
    def __init__(self, *args, prefix=None, loop: asyncio.AbstractEventLoop = None, isTest: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = prefix
        self.loop = loop
        self.isTest = isTest

    async def setup_hook(self):
        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                name = file[:-3]
                if name != "memes":
                    await self.load_extension(f"cogs.{name}")

        if not hourlyOER.is_running():
            hourlyOER.start()

        if not updateEverything.is_running():
            updateEverything.start()

        self.DEV = await self.fetch_user(os.environ["OWNER_ID"])

        if self.isTest is False:
            self.twitch = twitchAPI.TwitchAPI(client=self, loop=self.loop)
        else:
            self.twitch = twitchAPI_Test.TwitchAPI(client=self, loop=self.loop)

        self.loop.create_task(self.twitch.main())

        await self.tree.sync()

    async def on_message(self, ctx: discord.Message):
        await self.emoteFunction(ctx=ctx)

        await self.markovFunction(ctx=ctx)

        await self.process_commands(ctx)

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
        channel = await self.fetch_channel(1097639586458505336)
        await channel.send(f"reaction: {reaction} | user: {user}")

    async def on_command_error(self, message, error):
        print(error)
        if isinstance(error, commands.MissingRole):
            await embedMessage(client=self, ctx=message, description=error)
        elif isinstance(error, commands.BadArgument):
            await embedMessage(client=self, ctx=message, description=error)
        elif isinstance(error, commands.MissingRequiredArgument):
            await embedMessage(client=self, ctx=message, description=error)
        elif isinstance(error, commands.CommandInvokeError):
            error = error.original
            if isinstance(error, discord.errors.Forbidden):
                await embedMessage(client=self, ctx=message, description="Error " + error)

    @commands.bot_has_permissions(manage_messages=True, manage_webhooks=True)
    async def emoteFunction(self, ctx: discord.Message):
        if ctx.author.bot is False:
            result = ctx.content

            checkEmotes = re.findall("((?:(?!<:|<a:):)(?:(?!\w{1,64}:\d{17,18})\w{1,64})(?:(?!>):))", result)
            checkEmotes = [emote.lower() for emote in checkEmotes]

            findEmotes = []

            if checkEmotes:
                findEmotes = [str(e.split(":")[1].replace(":", "")) for e in checkEmotes]

            if findEmotes:
                _findEmotes = []
                for [existsNumber, textEmoji] in enumerate(findEmotes):
                    for emoji in self.emojis:
                        if emoji.name.lower() == textEmoji.lower():
                            if emoji not in [item[0] for item in _findEmotes]:
                                _findEmotes.append([emoji, existsNumber])

                findEmotes = _findEmotes

                if findEmotes and not all(i[0] is None for i in findEmotes):
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

                    finalEmotes = []

                    for [numberCheck, checkEmote] in enumerate(checkEmotes):
                        for [findEmote, numberFind] in findEmotes:
                            if numberCheck==numberFind:
                                finalEmotes.append([findEmote, checkEmote])
                                break

                    checkEmotes = [*set(checkEmotes)]

                    for finalEmote, finalText in finalEmotes:
                        if finalEmote:
                            test = re.compile(re.escape(finalText), re.IGNORECASE)
                            result = test.sub(str(finalEmote), result)

                            # result = re.sub(
                            #     "((?:(?!<:|<a:):)(?:(?!\w{1,64}:\d{17,18})\w{1,64})(?:(?!>):))", str(emote), result, 1
                            # )


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

                    await botWebhook.send(
                        str(result),
                        username=ctx.author.display_name,
                        avatar_url=ctx.author.display_avatar.url,
                        allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=True),
                        embeds=embeds,
                    )

                    await ctx.delete()

    # @commands.check()
    async def markovFunction(self, ctx: discord.Message):
        if ctx.author.bot is False:
            if "markov" in ctx.content.lower() and ctx.author.id != 988995123851456532:
                if ctx.channel.id == 1066008114324844645:
                    channel = await self.fetch_channel(1059283666217484338)
                    await channel.send(
                        content=ctx.content,
                        allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)
                    )

        if ctx.channel.id == 1059283666217484338 and ctx.author.id == 1058138354199318610:
            channel = await self.fetch_channel(1066008114324844645)
            await channel.send(
                content=ctx.content,
                allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)
            )


async def embedMessage(client: DiscordBot, ctx: commands.Context, title: str = None, description: str = None):
    embed = discord.Embed(title=title, description=description, color=0x000000, timestamp=ctx.message.created_at)
    embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text="Bot made by Tuxsuper", icon_url=client.DEV.display_avatar.url)
    await ctx.send(embed=embed)


# print("HELLO!")


# class Database():
#     def __init__(self, loop: asyncio.AbstractEventLoop):
#         self.pool = loop.create_task(self.createDB())

#     async def createDB(self):
#         try:
#             DATABASE_URL = os.environ["DATABASE_URL"]
#             pool = await asyncpg.create_pool(dsn=DATABASE_URL)
#             print("Connected to PostgreSQL")
#             return pool
#         except Exception as e:
#             print(f"Failed to create connection to PostgreSQL: {e}")

#     async def connectDB(self, query, values=None):
#         try:
#             async with self.pool.acquire() as conn:
#                 stmt = await conn.prepare(query)
#                 if query.startswith("SELECT") or query.get_type() == "SELECT":
#                     return await stmt.fetch(values)
#                 else:
#                     return await stmt.execute(values)
#         except Exception as e:
#             print(f"Failed to connect to PostgreSQL: {e}")

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


async def requestAio(url: str = "", header=None, typeJson=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=header) as r:
            if r.status == 200:
                print("Successfully Connected!")
                if typeJson is None:
                    return await r.json()
                elif typeJson == "content":
                    return await r.read()
            else:
                print("Failed to Connect")
                return


@tasks.loop(hours=1)
async def hourlyOER():
    print("Hourly Update")
    async with aiohttp.ClientSession() as session:
        hourlyOER.rates = await session.get(
            f"https://openexchangerates.org/api/latest.json?app_id={os.environ['OPEN_EXCHANGE_RATES_ID']}"
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


async def get_IGDB(game: str, session: aiohttp.ClientSession, where=""):
    resIGDB = await session.post(
        f'https://id.twitch.tv/oauth2/token?client_id={os.environ["TWITCH_ID"]}&client_secret={os.environ["TWITCH_SECRET"]}&grant_type=client_credentials'
    )

    resIGDB = await resIGDB.json()

    resIGDB = await session.post(
        "https://api.igdb.com/v4/games/",
        data=f'fields name,url,game_modes.name,external_games.*,cover.url,total_rating_count,first_release_date,release_dates.*; where name ~ "{game}" {where};"',
        headers={
            "Accept": "application/json",
            "Client-ID": os.environ["TWITCH_ID"],
            "Authorization": "Bearer " + resIGDB["access_token"],
        },
    )

    return await resIGDB.json()


async def get_RAWG(game: str, session: aiohttp.ClientSession):
    resRAWG = await session.get(f'https://api.rawg.io/api/games?key={os.environ["RAWG_API_KEY"]}&search={game}')

    return await resRAWG.json()


async def get_HLTB(game: str, session: aiohttp.ClientSession, year=0):
    ua = UserAgent()

    resHLTB = await session.post(
        "https://www.howlongtobeat.com/api/search",
        json={
            "searchType": "games",
            "searchTerms": game.split(),
            "searchPage": 1,
            "size": 20,
            "searchOptions": {
                "games": {
                    "userId": 0,
                    "platform": "",
                    "sortCategory": "popular",
                    "rangeCategory": "main",
                    "rangeTime": {"min": 0, "max": 0},
                    "gameplay": {"perspective": "", "flow": "", "genre": ""},
                    "rangeYear": {"min": year, "max": year},
                    "modifier": "",
                },
                "users": {"sortCategory": "postcount"},
                "filter": "",
                "sort": 0,
                "randomizer": 0,
            },
        },
        headers={
            "content-type": "application/json",
            "accept": "*/*",
            "User-Agent": ua.random,
            "referer": "https://howlongtobeat.com/",
        },
    )

    return await resHLTB.json()


async def get_Steam(appID, countryCode, session):
    resSteam = await session.get(
        f"https://store.steampowered.com/api/appdetails?appids={appID}&cc={countryCode}&filters=price_overview"
    )

    return await resSteam.json()


async def create_bingo_card(client: DiscordBot, user: discord.Member):
    timeNow = datetime.date.today()
    dayOfWeek = timeNow.isoweekday()

    if dayOfWeek != 5:  # Not Friday
        emote = Image.open("./assets/images/forsenJoy.png")
    else:  # It's Friday
        emote = Image.open("./assets/images/RebeccaBlack.png")

    emote = emote.resize((200, 200))

    bingoQuery = """SELECT lines from cache_bingo WHERE owner_id=%s"""
    bingoInsert = (user.id,)
    bingoSelect = await connectDB(bingoQuery, bingoInsert)

    if bingoSelect:
        bingoSelect = bingoSelect[0][0]
    else:
        bingoQuery = """SELECT line from bingo ORDER BY random() LIMIT 25"""
        bingoSelect = await connectDB(bingoQuery)
        bingoSelect = [r[0] for r in bingoSelect]

        lineJson = {line: 0 for line in bingoSelect}

        cache_bingoQuery = """INSERT INTO cache_bingo (owner_id, lines) VALUES (%s, %s)"""
        cache_bingoInsert = (user.id, Json(lineJson))
        await connectDB(cache_bingoQuery, cache_bingoInsert)

    basicBingo = Image.open("./assets/images/bingo.png")
    counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
    bingoCard = ImageDraw.Draw(basicBingo)

    xCount = 0
    yCount = 0

    for line in bingoSelect:
        if xCount > 4:
            xCount = 0
            yCount = yCount + 1

        if not (xCount == 2 and yCount == 2):
            text = textwrap.fill(text=line, width=10)

            bingoCard.text(
                (150 + (300 * xCount), 150 + (300 * yCount)),
                f"{text}",
                color=(255, 255, 255),
                font=counter_font,
                anchor="mm",
                align="center",
            )

        xCount = xCount + 1

    if emote.mode == "RGB":
        basicBingo.paste(emote, (645, 645))
    else:
        basicBingo.paste(emote, (645, 645), emote)

    basicBingo.save("./assets/images/bingoResult.png")

    file = discord.File("./assets/images/bingoResult.png", filename="bingoResult.png")
    embed = discord.Embed(title=user.display_name + "'s bingo card", color=0x000000, timestamp=datetime.datetime.now())
    embed.set_image(url="attachment://bingoResult.png")
    embed.set_author(name=user, icon_url=user.display_avatar.url)
    embed.set_footer(text="Bot made by Tuxsuper", icon_url=client.DEV.display_avatar.url)

    return file, embed


async def onlineEvent(client: DiscordBot):
    user_settingsQuery = """SELECT user_id, autobingo_dm from user_settings"""
    user_settingsSelect = await connectDB(user_settingsQuery)

    for userArray in user_settingsSelect:
        if userArray[1] is True:
            user = client.get_user(userArray[0])

            if user:
                try:
                    file, embed = await create_bingo_card(client=client, user=user)
                    embed.description = (
                        f"You can use {client.command_prefix}bingo opt-out to stop getting automatic bingo cards"
                    )
                    await user.send(file=file, embed=embed)
                except discord.Forbidden:
                    print("Couldn't send DM with bingo")


async def offlineEvent():
    cache_bingoQuery = """TRUNCATE TABLE cache_bingo"""
    await connectDB(cache_bingoQuery)


async def predictionEvent(client: DiscordBot, embed: discord.Embed):
    user_settingsQuery = """SELECT user_id, bets_dm from user_settings"""
    user_settingsSelect = await connectDB(user_settingsQuery)

    for userArray in user_settingsSelect:
        if userArray[1] is True:
            user = client.get_user(userArray[0])

            if user:
                try:
                    embed.description = embed.description[:embed.description.rfind('\n\n')]
                    embed.description = f'{embed.description}\n\n Use $bets opt-out to stop getting bets in DMs'
                    await user.send(embed=embed)
                except discord.Forbidden:
                    print("Couldn't send DM with bet")


async def check_permissions(client: DiscordBot, ctx: commands.Context):
    if ctx.author.guild_permissions.kick_members or ctx.author.id == client.DEV.id:
        return True
    else:
        await embedMessage(client=client, ctx=ctx, description="You don't have permission to use this command")
        return False
