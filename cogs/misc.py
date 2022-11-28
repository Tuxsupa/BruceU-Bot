import discord
import os
import random
import datetime
import time
import aiohttp
import textwrap
import json

from utils import default
from discord.ext import commands
from discord import app_commands

from PIL import Image, ImageFont, ImageDraw
from psycopg.types.json import Jsonb
from fake_useragent import UserAgent
from dotenv import load_dotenv

load_dotenv()


class Misc_Commands(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.hybrid_command(aliases=["h"], description="List of commands")
    async def help(self, ctx):
        embed = discord.Embed(title="Commands", description="", color=0x000000, timestamp=ctx.message.created_at)
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        for command in self.client.commands:
            paramText = ""

            if command.params and len(command.params):
                for param in command.params:
                    if command.params[param].required is True:
                        paramText = paramText + " [" + command.params[param].name + "]"
                    else:
                        paramText = paramText + " <" + command.params[param].name + ">"

            embed.add_field(
                name=ctx.prefix + command.name + paramText,
                value=command.description,
                inline=False,
            )

        embed.set_footer(text="Bot made by Tuxsuper", icon_url=default.DEV.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Rolls a chance")
    async def roll(self, ctx, *, message):
        roll = random.randint(0, 100)

        await default.embedMessage(self, ctx, title="Roll", description=f"{roll}% chance of {message}")

    @commands.hybrid_command(description="Time left until Dark and Darker next playtest")
    async def dnd(self, ctx):
        text = None
        timeLeft = datetime.datetime(2022, 12, 16, 11) - datetime.datetime.now()
        if timeLeft.total_seconds() <= 0:
            text = "Dark and Darker is out MUGA"
        else:
            days = divmod(timeLeft.total_seconds(), 86400)
            hours = divmod(days[1], 3600)
            minutes = divmod(hours[1], 60)
            seconds = divmod(minutes[1], 1)
            text = f"{int(days[0])} days {int(hours[0])} hours {int(minutes[0])} minutes {int(seconds[0])} seconds left until Dark and Darker"

        if text is not None:
            await default.embedMessage(self, ctx, title="Time left until Dark and Darker", description=text)


class Bingo_Command(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def create_bingo_card(self, ctx, owner_id=None):
        if not owner_id:
            owner_id = ctx.author.id

        timeNow = datetime.date.today()
        dayOfWeek = timeNow.isoweekday()

        if dayOfWeek != 5:  # Not Friday
            emote = Image.open("./assets/images/forsenJoy.png")
        else:  # It's Friday
            emote = Image.open("./assets/images/RebeccaBlack.png")

        emote = emote.resize((200, 200))

        bingoQuery = """SELECT lines from cache_bingo WHERE owner_id=%s"""
        bingoInsert = (owner_id,)
        bingoSelect = await default.connectDB(bingoQuery, bingoInsert)

        if bingoSelect:
            bingoSelect = bingoSelect[0][0]
        else:
            bingoQuery = """SELECT line from bingo ORDER BY random() LIMIT 25"""
            bingoSelect = await default.connectDB(bingoQuery)
            bingoSelect = [r[0] for r in bingoSelect]

            lineJson = {line: 0 for line in bingoSelect}

            cache_bingoQuery = """INSERT INTO cache_bingo (owner_id, lines) VALUES (%s, %s)"""
            cache_bingoInsert = (owner_id, Jsonb(lineJson))
            await default.connectDB(cache_bingoQuery, cache_bingoInsert)

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
        embed = discord.Embed(title=ctx.author.display_name + "'s bingo card", color=0x000000, timestamp=ctx.created_at)
        embed.set_image(url="attachment://bingoResult.png")
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=default.DEV.display_avatar.url)

        return file, embed

    @commands.Cog.listener()
    async def on_message(self, ctx):
        if ctx.channel.id == 1044664235365502996:
            async for message in ctx.channel.history(limit=1):
                if message.embeds:
                    if message.embeds[0].title == "forsen just went offline... Now what...":
                        cache_bingoQuery = """TRUNCATE TABLE cache_bingo"""
                        await default.connectDB(cache_bingoQuery)
                        break

                    if message.embeds[0].title == "forsen just went live!":
                        user_settingsQuery = """SELECT * from user_settings"""
                        user_settingsSelect = await default.connectDB(user_settingsQuery)
                        for user in user_settingsSelect:
                            if user[2] is True:
                                file, embed = await self.create_bingo_card(ctx)

                                user = self.client.get_user(user[0])
                                await user.send(file=file, embed=embed)

    @commands.hybrid_command(description="Random Bingo Card when forsen is doing reactions")
    @app_commands.choices(
        choice=[app_commands.Choice(name="Opt-In", value="opt-in"), app_commands.Choice(name="Opt-Out", value="opt-out")]
    )
    async def bingo(self, ctx, choice=None):
        if choice:
            if choice.lower() == "opt-in":
                user_settingsQuery = """INSERT INTO user_settings (id, autobingo_dm) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET autobingo_dm=%s"""
                user_settingsInsert = (ctx.author.id, True, True)
                await default.connectDB(user_settingsQuery, user_settingsInsert)
                await default.embedMessage(self, ctx, description="You opted-in auto bingo card sent to your DM's")
                return
            elif choice.lower() == "opt-out":
                user_settingsQuery = """INSERT INTO user_settings (id, autobingo_dm) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET autobingo_dm=%s"""
                user_settingsInsert = (ctx.author.id, False, False)
                await default.connectDB(user_settingsQuery, user_settingsInsert)
                await default.embedMessage(self, ctx, description="You opted-out auto bingo card sent to your DM's")
                return

            elif ctx.message.mentions:
                await self.create_bingo_card(ctx.message, ctx.message.mentions[0].id)
                return

        channel = self.client.get_channel(1044664235365502996)
        async for message in channel.history(limit=1):
            if message.embeds:
                if message.embeds[0].title == "forsen just went live!":
                    file, embed = await self.create_bingo_card(ctx.message)
                    await ctx.send(file=file, embed=embed)


class Game_Command(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def get_IGDB(self, game, session, where=""):
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

    async def get_RAWG(self, game, session):
        resRAWG = await session.get(f'https://api.rawg.io/api/games?key={os.environ["RAWG_API_KEY"]}&search={game}')

        return await resRAWG.json()

    async def get_HLTB(self, game, session, year):
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

    @commands.hybrid_command(aliases=["g"], description="Shows info about a game")
    async def game(self, ctx, *, game):
        discordSelectQuery = """SELECT pubg_name, image, banned_commands from discord_profiles WHERE id = %s"""
        discordSelectInsert = (ctx.author.id,)
        discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)

        if not discordSelect or discordSelect[0][2][2] is False:
            await ctx.defer()

            async with aiohttp.ClientSession() as session:
                resIGDB = await self.get_IGDB(game, session)

                if resIGDB is not None and len(resIGDB) > 0:
                    game = resIGDB[0]["name"]

                    if "first_release_date" in resIGDB[0]:
                        year = time.localtime(int(resIGDB[0]["first_release_date"])).tm_year

                    resRAWG = await self.get_RAWG(game, session)

                    if "first_release_date" in resIGDB[0]:
                        resHLTB = await self.get_HLTB(game, session, year)
                    else:
                        resHLTB = []
                else:
                    resRAWG = await self.get_RAWG(game, session)

                    if resRAWG is not None and len(resRAWG) > 0 and len(resRAWG["results"]):
                        game = resRAWG["results"][0]["name"]
                        year = resRAWG["results"][0]["released"].split("-", 1)[0]

                        resIGDB = await self.get_IGDB(game, session, where=f"& release_dates.y = {year}")

                        resHLTB = await self.get_HLTB(game, session, year)
                    else:
                        resHLTB = []

                if resIGDB is not None and len(resIGDB) > 0:
                    resType = "IGDB"
                    game = resIGDB[0]["name"]
                    url = resIGDB[0]["url"]
                elif resRAWG is not None and len(resRAWG) > 0 and len(resRAWG["results"]):
                    resType = "RAWG"
                    game = resRAWG["results"][0]["name"]
                    url = "https://rawg.io/games/" + resRAWG["results"][0]["slug"]
                elif len(resHLTB) > 0 and len(resHLTB["data"]) > 0:
                    resType = "HLTB"
                    game = resHLTB["data"][0]["game_name"]
                    if "game_web_link" in resHLTB["data"][0]:
                        url = resHLTB["data"][0]["game_web_link"]
                else:
                    await default.embedMessage(self, ctx, description="Game doesn't exist")
                    return

                embed = discord.Embed(
                    title=game, description=None, color=0x000000, url=url, timestamp=ctx.message.created_at
                )
                if resType == "IGDB" and "cover" in resIGDB[0]:
                    url = str(resIGDB[0]["cover"]["url"])
                    embed.set_thumbnail(url="https:" + url.replace("t_thumb", "t_cover_big"))
                elif resType == "RAWG" and "background_image" in resRAWG["results"][0]:
                    url = str(resRAWG["results"][0]["background_image"])
                    embed.set_thumbnail(url=url)

                if len(resHLTB) > 0 and len(resHLTB["data"]) > 0:
                    gameTime = round((resHLTB["data"][0]["comp_main"] / 3600), 3)
                    if gameTime != 0:
                        embed.add_field(name="Main Story", value=str(gameTime) + " hours", inline=True)

                if resIGDB:
                    resData = resIGDB[0]
                    gameModes = ""

                    if "game_modes" in resData:
                        for i in resData["game_modes"]:
                            gameModes = gameModes + i["name"] + "\n"

                    if "external_games" in resData:
                        for i in resData["external_games"]:
                            if i["category"] == 1:
                                linkSteam = "https://steamdb.info/app/" + i["uid"]
                                appID = i["uid"]
                                break

                    countryCodes = ["se", "ar", "tr"]
                    originalPrices = []
                    originalPricesText = ""
                    convertedPricesText = ""

                    if "external_games" in resData:
                        for i in resData["external_games"]:
                            if i["category"] == 1:
                                for i in range(len(countryCodes)):
                                    resSteam = await session.get(
                                        "https://store.steampowered.com/api/appdetails?appids="
                                        + appID
                                        + "&cc="
                                        + countryCodes[i]
                                        + "&filters=price_overview"
                                    )

                                    resSteam = await resSteam.json()

                                    if (
                                        len(resSteam[appID]) != 0
                                        and "data" in resSteam[appID]
                                        and len(resSteam[appID]["data"]) != 0
                                    ):
                                        priceOverview = resSteam[appID]["data"]["price_overview"]
                                        originalPrices.append([priceOverview["currency"], priceOverview["final"] / 100])
                                        originalPricesText = originalPricesText + priceOverview["final_formatted"] + "\n"

                                embed.add_field(name="Link ", value="[SteamDB](" + linkSteam + ")", inline=True)

                                break

                    if originalPrices:
                        for i in originalPrices:
                            amount = i[1] / default.hourlyOER.rates["rates"][i[0]]
                            result = round(amount * default.hourlyOER.rates["rates"]["EUR"], 2)
                            convertedPricesText = convertedPricesText + str(result) + "€\n"

                        if len(resHLTB) == 0 or len(resHLTB["data"]) == 0 or resHLTB["data"][0]["comp_main"] == 0:
                            embed.add_field(name="\u200B", value="\u200B", inline=True)

                        embed.add_field(name="\u200B", value="\u200B", inline=True)
                        embed.add_field(name="Prices ", value=originalPricesText, inline=True)
                        embed.add_field(name="Converted ", value=convertedPricesText, inline=True)

                    else:
                        if len(resHLTB) > 0 and len(resHLTB["data"]) > 0 and resHLTB["data"][0]["comp_main"] != 0:
                            embed.add_field(name="\u200B", value="\u200B", inline=True)
                            embed.add_field(name="\u200B", value="\u200B", inline=True)

                    if gameModes:
                        embed.add_field(name="Game Modes ", value=gameModes, inline=True)

                embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
                embed.set_footer(text="Bot made by Tuxsuper", icon_url=default.DEV.display_avatar.url)
                await ctx.send(embed=embed)
        else:
            await default.embedMessage(self, ctx, description="You are banned from using the command game")


async def setup(client):
    await client.add_cog(Misc_Commands(client))
    await client.add_cog(Bingo_Command(client))
    await client.add_cog(Game_Command(client))
