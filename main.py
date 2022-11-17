import logging
import json
import discord
from discord.ext import commands, tasks
from discord import app_commands
import psycopg
import datetime
import validators
from PIL import Image, ImageFont, ImageDraw
from collections import Counter
import os
from dotenv import load_dotenv
import math
from psycopg import sql
import aiohttp
from howlongtobeatpy import HowLongToBeat
from fake_useragent import UserAgent
import time
import random
import re


load_dotenv()

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)

intent = discord.Intents.all()
client = commands.Bot(command_prefix="$", help_command=None, case_insensitive=True, intents=intent)


FORSEN_URL = "https://api.pubg.com/shards/steam/players?filter[playerNames]=Forsenlol"

PUBG_API_KEY = os.environ["PUBG_API_KEY"]
PUBG_HEADER = {
    "Authorization": "Bearer " + PUBG_API_KEY,
    "Accept": "application/vnd.api+json",
    "Accept-Enconding": "gzip",
}

with open("./assets/dictionaries/damageCauserName.json", "r") as f:
    DAMAGE_CAUSER_NAME = json.loads(f.read())

with open("./assets/dictionaries/damageTypeCategory.json", "r") as f:
    DAMAGE_TYPE_CATEGORY = json.loads(f.read())

try:
    DATABASE_URL = os.environ["DATABASE_URL"]
    CONNECTION = psycopg.connect(DATABASE_URL, sslmode="require")
    CURSOR = CONNECTION.cursor()
    print("Connected to PostgreSQL")

except (Exception, psycopg.Error) as error:
    print(error)


@tasks.loop(hours=1)
async def hourlyOER():
    print("Hourly Update")
    async with aiohttp.ClientSession() as session:
        hourlyOER.rates = await session.get(
            "https://openexchangerates.org/api/latest.json?app_id=" + os.environ["OPEN_EXCHANGE_RATES_ID"]
        )
        hourlyOER.rates = await hourlyOER.rates.json()


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


async def addRows(matchID):
    MATCH_URL = "https://api.pubg.com/shards/steam/matches/{}".format(matchID)

    MATCH_STAT = await requestAio(MATCH_URL, PUBG_HEADER)

    forsenDied = False
    attackId = 0

    ASSET_ID = MATCH_STAT["data"]["relationships"]["assets"]["data"][0]["id"]
    for i in MATCH_STAT["included"]:
        if i["type"] == "asset" and i["id"] == ASSET_ID:
            TELEMETRY_URL = i["attributes"]["URL"]

    TELEMETRY_DATA = await requestAio(TELEMETRY_URL, PUBG_HEADER)

    for i in TELEMETRY_DATA:
        if i["_T"] == "LogPlayerKillV2":
            if i["victim"]["name"] == "Forsenlol":
                if i["finisher"] is not None:
                    killer = i["finisher"]["name"]
                    health = i["finisher"]["health"]
                    location_x = float(i["finisher"]["location"]["x"])
                    location_y = float(i["finisher"]["location"]["y"])
                    location_z = float(i["finisher"]["location"]["z"])
                    location = [location_x, location_y, location_z]
                else:
                    killer = None
                    health = None
                    location = None
                if i["finishDamageInfo"]["damageTypeCategory"] is not None:
                    weapon = DAMAGE_TYPE_CATEGORY[i["finishDamageInfo"]["damageTypeCategory"]]
                else:
                    weapon = None
                if i["finishDamageInfo"]["distance"] is not None:
                    distance = i["finishDamageInfo"]["distance"]
                else:
                    distance = None
                causer = DAMAGE_CAUSER_NAME[i["finishDamageInfo"]["damageCauserName"]]
                date = i["_D"]

                print(killer)
                print(weapon)
                print(causer)
                print(distance)
                print(health)
                print(location)
                print(date)
                print(matchID)

                killsQuery = """INSERT INTO kills (NAME, WEAPON, CAUSER, DISTANCE, HEALTH, LOCATION, DATE, MATCH_ID) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
                killsInsert = (
                    killer,
                    weapon,
                    causer,
                    distance,
                    health,
                    location,
                    date,
                    matchID,
                )
                await connectDB(killsQuery, killsInsert)

                if i["finisher"] is not None:
                    statsQuery = """INSERT INTO stats (NAME, KILLS, DEATHS, DAMAGE_DEALT, SNIPAS_KILLED, DISTANCE_TRAVELLED, SUICIDES, SCORE, RANKING, BOUNTY) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (NAME) DO UPDATE SET KILLS=STATS.KILLS+%s"""
                    statsInsert = (killer, 1, 0, 0, 0, [0, 0, 0, 0, 0], 0, 0, 0, 0, 1)
                    await connectDB(statsQuery, statsInsert)

                with open("./assets/dictionaries/scoreTable.json", "r") as f:
                    scoreTable = json.loads(f.read())

                score = scoreTable[causer]
                print(causer)
                print(score)

                if i["finisher"] is not None:
                    scoreQuery = """UPDATE stats SET SCORE=STATS.SCORE+%s WHERE NAME LIKE %s"""
                    scoreInsert = (score, killer)
                    await connectDB(scoreQuery, scoreInsert)

                rankingQuery = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
                await connectDB(rankingQuery)

    # break

    snipaQuery = """SELECT name FROM stats WHERE NAME NOT IN ('Forsenlol') GROUP BY name"""
    snipaNames = await connectDB(snipaQuery)
    snipaNames = [r[0] for r in snipaNames]

    bountyQuery = """SELECT name, bounty FROM stats WHERE NAME NOT IN ('Forsenlol') GROUP BY name HAVING bounty > 0"""
    bountyNames = await connectDB(bountyQuery)

    for i in TELEMETRY_DATA:
        if i["_T"] == "LogPlayerKillV2":
            if forsenDied is False or i["attackId"] == attackId:
                if i["victim"]["name"] == "Forsenlol":
                    attackId = i["attackId"]
                    forsenDied = True

                if i["victim"]["name"] in snipaNames or i["victim"]["name"] == "Forsenlol":
                    deaths = 0
                    snipasKilled = 0
                    suicides = 0

                    distanceOnFoot = i["victimGameResult"]["stats"]["distanceOnFoot"]
                    distanceOnSwim = i["victimGameResult"]["stats"]["distanceOnSwim"]
                    distanceOnVehicle = i["victimGameResult"]["stats"]["distanceOnVehicle"]
                    distanceOnParachute = i["victimGameResult"]["stats"]["distanceOnParachute"]
                    distanceOnFreefall = i["victimGameResult"]["stats"]["distanceOnFreefall"]
                    distanceTravelled = [
                        distanceOnFoot,
                        distanceOnSwim,
                        distanceOnVehicle,
                        distanceOnParachute,
                        distanceOnFreefall,
                    ]

                    if i["finisher"] is not None and i["finisher"]["name"] == "Forsenlol":
                        deaths = 1

                    if i["isSuicide"] is True:
                        suicides = 1

                    statsQuery = """UPDATE stats SET DEATHS=STATS.DEATHS+%s,DISTANCE_TRAVELLED[1]=STATS.DISTANCE_TRAVELLED[1]+%s, DISTANCE_TRAVELLED[2]=STATS.DISTANCE_TRAVELLED[2]+%s,
                    DISTANCE_TRAVELLED[3]=STATS.DISTANCE_TRAVELLED[3]+%s,DISTANCE_TRAVELLED[4]=STATS.DISTANCE_TRAVELLED[4]+%s,DISTANCE_TRAVELLED[5]=STATS.DISTANCE_TRAVELLED[5]+%s,
                    SUICIDES=STATS.SUICIDES+%s WHERE NAME LIKE %s"""
                    statsInsert = (
                        deaths,
                        distanceTravelled[0],
                        distanceTravelled[1],
                        distanceTravelled[2],
                        distanceTravelled[3],
                        distanceTravelled[4],
                        suicides,
                        i["victim"]["name"],
                    )
                    await connectDB(statsQuery, statsInsert)

                    # break

                    if (
                        i["finisher"] is not None
                        and i["finisher"]["name"] in snipaNames
                        and i["victim"]["name"] != "Forsenlol"
                    ):
                        snipasKilled = 1
                        statsQuery = """UPDATE stats SET SNIPAS_KILLED=STATS.SNIPAS_KILLED+%s WHERE NAME LIKE %s"""
                        statsInsert = (snipasKilled, i["finisher"]["name"])
                        await connectDB(statsQuery, statsInsert)

                for bounty in bountyNames:
                    if (
                        i["finisher"] is not None
                        and bounty[0] == i["victim"]["name"]
                        and i["finisher"]["name"] in snipaNames
                    ):
                        statsQuery = """UPDATE stats SET SCORE=STATS.SCORE+%s WHERE NAME LIKE %s"""
                        statsInsert = (bounty[1], i["finisher"]["name"])
                        await connectDB(statsQuery, statsInsert)
                        break

        if i["_T"] == "LogPlayerTakeDamage":
            if forsenDied is False or i["attackId"] == attackId:
                if i["victim"]["name"] == "Forsenlol":
                    attacker = i["attacker"]
                    if attacker is not None:
                        attacker = i["attacker"]["name"]
                        damageDealt = i["damage"]

                        statsQuery = """UPDATE stats SET DAMAGE_DEALT=STATS.DAMAGE_DEALT+%s WHERE NAME LIKE %s"""
                        statsInsert = (damageDealt, attacker)
                        await connectDB(statsQuery, statsInsert)

    # break


@tasks.loop(minutes=3)
async def updateEverything():
    player_stat = await requestAio(FORSEN_URL, PUBG_HEADER)

    match_id_list = player_stat["data"][0]["relationships"]["matches"]["data"]

    matchIDQuery = """SELECT match_id FROM kills"""
    matchIDs = await connectDB(matchIDQuery)
    matchIDs = [r[0] for r in matchIDs]

    print("Starting updating")
    for match in match_id_list:
        if match["id"] not in matchIDs:
            await addRows(match["id"])
            matchIDs.append(match["id"])

    print("Stopping updating")


@client.event
async def on_ready():
    if not hourlyOER.is_running():
        hourlyOER.start()

    if not updateEverything.is_running():
        updateEverything.start()

    await client.tree.sync()


@client.event
async def on_message(ctx):
    if ctx.author.bot is False:
        result = ctx.content

        checkEmotes = re.findall("((?:(?!<:|<a:):)(?:(?!\w{1,64}:\d{17,18})\w{1,64})(?:(?!>):))", result)
        findEmotes = []

        if checkEmotes:
            findEmotes = [str(e.split(":")[1].replace(":", "")) for e in checkEmotes]

        if findEmotes:
            findEmotes = [discord.utils.get(client.emojis, name=e) for e in findEmotes]

            if findEmotes and not all(i is None for i in findEmotes):
                webhooks = await ctx.channel.webhooks()
                if not any(webhook.user.id == client.user.id for webhook in webhooks):
                    print("Created Webhooks")
                    await ctx.channel.create_webhook(name="BruceU-1")
                    await ctx.channel.create_webhook(name="BruceU-2")
                    webhooks = await ctx.channel.webhooks()

                for webhook in webhooks:
                    if webhook.user.id == client.user.id:
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
                            description="📂 " + "[" + attachment.filename + "](" + attachment.proxy_url + ")", color=0x000000
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

    await client.process_commands(ctx)


""" @client.tree.context_menu(name="Delete Message")
async def deleteEmoteMessage(interaction: discord.Interaction, message: discord.Message):
    if interaction.user.id == message.author.id:
        print("test")
    await interaction.responde.send_message(content="test", ephemeral=True) """


async def embedMessage(ctx, text=None):
    DEV = await client.fetch_user(270224083684163584)
    embed = discord.Embed(title=None, description=text, color=0x000000, timestamp=ctx.message.created_at)
    embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text="Bot made by Tuxsuper", icon_url=DEV.display_avatar.url)
    await ctx.send(embed=embed)


@client.hybrid_command(description="Time left until Dark and Darker next playtest")
async def dnd(ctx):
    DEV = await client.fetch_user(270224083684163584)

    text = None
    timeLeft = datetime.datetime(2022, 12, 16, 11) - datetime.datetime.now()
    if timeLeft.total_seconds() <= 0:
        text = "Dark and Darker is out MUGA"
    else:
        days = divmod(timeLeft.total_seconds(), 86400)
        hours = divmod(days[1], 3600)
        minutes = divmod(hours[1], 60)
        seconds = divmod(minutes[1], 1)
        text = "{} days {} hours {} minutes {} seconds left until Dark and Darker".format(
            int(days[0]), int(hours[0]), int(minutes[0]), int(seconds[0])
        )

    if text is not None:
        embed = discord.Embed(
            title="Time left until Dark and Darker",
            description=text,
            color=0x000000,
            timestamp=ctx.message.created_at,
        )
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=DEV.display_avatar.url)
        await ctx.send(embed=embed)


@client.hybrid_command(description="Rolls a chance")
async def roll(ctx, *, message):
    DEV = await client.fetch_user(270224083684163584)

    roll = random.randint(0, 100)

    embed = discord.Embed(
        title="Roll",
        description=str(roll) + "% chance of " + str(message),
        color=0x000000,
        timestamp=ctx.message.created_at,
    )
    embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text="Bot made by Tuxsuper", icon_url=DEV.display_avatar.url)
    await ctx.send(embed=embed)


@client.hybrid_command(description="Shows memes")
async def lm(ctx, *, meme):
    discordSelectQuery = """SELECT name, content, upvotes, downvotes FROM memes WHERE name = LOWER(%s) AND name !~* 'the_'"""
    discordSelectInsert = (meme,)
    discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)
    if discordSelect and len(discordSelect) > 0:
        discordUpdateQuery = """UPDATE memes SET views[1] = memes.views[1]+%s WHERE name = %s"""
        discordUpdateInsert = (1, discordSelect[0][0])
        await connectDB(discordUpdateQuery, discordUpdateInsert)

        votes = len(discordSelect[0][2]) - len(discordSelect[0][3])
        text = "({}) Meme '{}': {}".format(votes, discordSelect[0][0], discordSelect[0][1])
        reaction = await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
        await reaction.add_reaction("⬆️")
        await reaction.add_reaction("⬇️")


@client.hybrid_command(description="Shows random memes")
@commands.cooldown(1, 10, commands.BucketType.channel)
async def rm(ctx):
    discordSelectQuery = (
        """SELECT name, content, upvotes, downvotes FROM memes WHERE name !~* 'the_' ORDER BY random() LIMIT 1"""
    )
    discordSelect = await connectDB(discordSelectQuery)
    if discordSelect and len(discordSelect) > 0:
        discordUpdateQuery = """UPDATE memes SET views[2] = memes.views[2]+%s WHERE name = %s"""
        discordUpdateInsert = (1, discordSelect[0][0])
        await connectDB(discordUpdateQuery, discordUpdateInsert)

        votes = len(discordSelect[0][2]) - len(discordSelect[0][3])
        text = "({}) Meme '{}': {}".format(votes, discordSelect[0][0], discordSelect[0][1])
        reaction = await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
        await reaction.add_reaction("⬆️")
        await reaction.add_reaction("⬇️")


@client.command(description="About Meme")
async def am(ctx):
    DEV = await client.fetch_user(270224083684163584)

    # rankingQuery = sql.SQL("SELECT name, ROW_NUMBER() OVER (ORDER BY damage_dealt DESC, name) AS rows from stats")

    # discordSelectQuery = """SELECT name, views, upvotes, downvotes, id, created_at FROM memes WHERE name = LOWER(%s)"""
    # discordSelectInsert = (meme,)
    # discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)

    embed = discord.Embed(
        title="Meme Leaderboard",
        description=None,
        color=0x000000,
        timestamp=ctx.message.created_at,
    )

    discordSelectQuery = """SELECT name, upvotes, downvotes FROM memes ORDER BY (array_length(upvotes, 1)-array_length(downvotes, 1)) DESC NULLS LAST LIMIT 10"""
    discordSelect = await connectDB(discordSelectQuery)

    if discordSelect and len(discordSelect) > 0:
        text = ""
        counter = 1
        for meme in discordSelect:
            votes = len(meme[1]) - len(meme[2])
            text = text + "#{} {} - ({}) votes\n".format(counter, meme[0], votes)
            counter = counter + 1

        embed.add_field(name="Top 10 Best", value=text, inline=True)

    discordSelectQuery = """SELECT name, upvotes, downvotes FROM memes ORDER BY (array_length(upvotes, 1)-array_length(downvotes, 1)) ASC NULLS LAST LIMIT 10"""
    discordSelect = await connectDB(discordSelectQuery)

    if discordSelect and len(discordSelect) > 0:
        text = ""
        counter = 1
        for meme in discordSelect:
            votes = len(meme[1]) - len(meme[2])
            text = text + "#{} {} - ({}) votes\n".format(counter, meme[0], votes)
            counter = counter + 1

        embed.add_field(name="Top 10 Worst", value=text, inline=True)

    embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text="Bot made by Tuxsuper", icon_url=DEV.display_avatar.url)
    await ctx.send(embed=embed)


@client.event
async def on_reaction_add(reaction, user):
    if user.bot is False:
        if reaction.message.author.id == client.user.id:
            if ") Meme '" in reaction.message.content:
                splitted = reaction.message.content.split(") Meme '", 1)[1]
                splitted = splitted.split("': ", 1)
                name = splitted[0]
                discordSelectQuery = """SELECT upvotes, downvotes FROM memes WHERE name = %s"""
                discordSelectInsert = (name,)
                discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)

                if reaction.emoji == "⬆️":
                    if user.id not in discordSelect[0][0]:
                        if user.id in discordSelect[0][1]:
                            discordUpdateQuery = (
                                """UPDATE memes SET downvotes = array_remove(downvotes, %s) WHERE name = %s"""
                            )
                            discordUpdateInsert = (user.id, name)
                            await connectDB(discordUpdateQuery, discordUpdateInsert)

                        discordUpdateQuery = """UPDATE memes SET upvotes = upvotes || %s WHERE name = %s"""
                        discordUpdateInsert = (user.id, name)
                        await connectDB(discordUpdateQuery, discordUpdateInsert)

                elif reaction.emoji == "⬇️":
                    if user.id not in discordSelect[0][1]:
                        if user.id in discordSelect[0][0]:
                            discordUpdateQuery = """UPDATE memes SET upvotes = array_remove(upvotes, %s) WHERE name = %s"""
                            discordUpdateInsert = (user.id, name)
                            await connectDB(discordUpdateQuery, discordUpdateInsert)

                        discordUpdateQuery = """UPDATE memes SET downvotes = downvotes || %s WHERE name = %s"""
                        discordUpdateInsert = (user.id, name)
                        await connectDB(discordUpdateQuery, discordUpdateInsert)


@client.hybrid_command(aliases=["g"], description="Shows info about a game")
async def game(ctx, *, game):
    discordSelectQuery = """SELECT pubg_name, image, banned_commands from discord_profiles WHERE id = %s"""
    discordSelectInsert = (ctx.author.id,)
    discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)
    if not discordSelect or discordSelect[0][2][2] is False:
        DEV = await client.fetch_user(270224083684163584)
        ua = UserAgent()

        await ctx.defer()

        async with aiohttp.ClientSession() as session:
            resIGDB = await session.post(
                "https://id.twitch.tv/oauth2/token?client_id="
                + os.environ["TWITCH_ID"]
                + "&client_secret="
                + os.environ["TWITCH_SECRET"]
                + "&grant_type=client_credentials"
            )

            resIGDB = await resIGDB.json()

            resIGDB = await session.post(
                "https://api.igdb.com/v4/games/",
                data='fields name,url,game_modes.name,external_games.*,cover.url,total_rating_count,first_release_date,release_dates.*; where name ~ "{}";'.format(
                    game
                ),
                headers={
                    "Accept": "application/json",
                    "Client-ID": os.environ["TWITCH_ID"],
                    "Authorization": "Bearer " + resIGDB["access_token"],
                },
            )

            resIGDB = await resIGDB.json()

            if resIGDB is not None and len(resIGDB) > 0:
                game = resIGDB[0]["name"]
                if "first_release_date" in resIGDB[0]:
                    year = time.localtime(int(resIGDB[0]["first_release_date"])).tm_year

                resRAWG = await session.get(
                    "https://api.rawg.io/api/games?key=" + os.environ["RAWG_API_KEY"] + "&search={}".format(game),
                )

                resRAWG = await resRAWG.json()

                if "first_release_date" in resIGDB[0]:
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

                    resHLTB = await resHLTB.json()
                else:
                    resHLTB = []
            else:
                resRAWG = await session.get(
                    "https://api.rawg.io/api/games?key=" + os.environ["RAWG_API_KEY"] + "&search={}".format(game),
                )

                resRAWG = await resRAWG.json()

                if resRAWG is not None and len(resRAWG) > 0 and len(resRAWG["results"]):
                    game = resRAWG["results"][0]["slug"].replace("-", " ")
                    year = resRAWG["results"][0]["released"].split("-", 1)[0]

                    resIGDB = await session.post(
                        "https://id.twitch.tv/oauth2/token?client_id="
                        + os.environ["TWITCH_ID"]
                        + "&client_secret="
                        + os.environ["TWITCH_SECRET"]
                        + "&grant_type=client_credentials"
                    )

                    resIGDB = await resIGDB.json()

                    resIGDB = await session.post(
                        "https://api.igdb.com/v4/games/",
                        data='fields name,url,game_modes.name,external_games.*,cover.url,total_rating_count,first_release_date; where name ~ "{}" & release_dates.y = {};'.format(
                            game, year
                        ),
                        headers={
                            "Accept": "application/json",
                            "Client-ID": os.environ["TWITCH_ID"],
                            "Authorization": "Bearer " + resIGDB["access_token"],
                        },
                    )

                    resIGDB = await resIGDB.json()

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

                    resHLTB = await resHLTB.json()
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
                await embedMessage(ctx, "Game doesn't exist")
                return

            embed = discord.Embed(title=game, description=None, color=0x000000, url=url, timestamp=ctx.message.created_at)
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
                        amount = i[1] / hourlyOER.rates["rates"][i[0]]
                        result = round(amount * hourlyOER.rates["rates"]["EUR"], 2)
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
            embed.set_footer(text="Bot made by Tuxsuper", icon_url=DEV.display_avatar.url)
            await ctx.send(embed=embed)
    else:
        await embedMessage(ctx, "You are banned from using the command game")


@client.hybrid_command(aliases=["fi"], description="Force inserts an image to someones profile (Admin only)")
async def forceimage(ctx, mention, link):
    if ctx.author.guild_permissions.kick_members or ctx.author.id == 270224083684163584:
        if mention.startswith("<@") is True:
            mention = mention.replace("<@", "")
            mention = mention.replace(">", "")
            member = await ctx.guild.fetch_member(mention)
            if member is not None:
                if validators.url(link):
                    discordQuery = (
                        """INSERT INTO discord_profiles (ID, IMAGE) VALUES (%s,%s) ON CONFLICT (ID) DO UPDATE SET IMAGE=%s"""
                    )
                    discordInsert = (member.id, link, link)
                    await connectDB(discordQuery, discordInsert)
                    await embedMessage(ctx, "Image added for {}!".format(mention))
                else:
                    await embedMessage(ctx, "No link present")
            else:
                await embedMessage(ctx, "Mention member not found")
        else:
            await embedMessage(ctx, "Invalid Argument, please use mentions")
    else:
        await embedMessage(ctx, "You don't have permission to use this command")


@client.hybrid_command(
    aliases=["fa"], description="Force create/replaces a PUBG and Discord name to someones profile (Admin only)"
)
async def forceadd(ctx, mention, pubgname=None):
    if ctx.author.guild_permissions.kick_members or ctx.author.id == 270224083684163584:
        if mention.startswith("<@") is True:
            mention = mention.replace("<@", "")
            mention = mention.replace(">", "")
            member = await ctx.guild.fetch_member(mention)
            if member is not None:
                if pubgname is not None:
                    SNIPA_URL = "https://api.pubg.com/shards/steam/players?filter[playerNames]={}".format(pubgname)

                    player_stat = await requestAio(SNIPA_URL, PUBG_HEADER)

                    if "errors" in player_stat:
                        await embedMessage(ctx, "Nickname doesn't exist in PUBG")
                        return
                    elif "data" in player_stat:
                        discordInsertQuery = """INSERT INTO discord_profiles (ID, PUBG_NAME) VALUES (%s,%s) ON CONFLICT (ID) DO UPDATE SET PUBG_NAME=%s"""
                        discordInsertValues = (member.id, pubgname, pubgname)
                        await connectDB(discordInsertQuery, discordInsertValues)

                        statsInsertQuery = """INSERT INTO stats (NAME, KILLS, DEATHS, DAMAGE_DEALT, SNIPAS_KILLED, DISTANCE_TRAVELLED, SUICIDES, SCORE, RANKING, BOUNTY) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (NAME) DO NOTHING"""
                        statsInsertValues = (pubgname, 0, 0, 0, 0, [0, 0, 0, 0, 0], 0, 0, 0, 0)
                        await connectDB(statsInsertQuery, statsInsertValues)

                        rankingQuery = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
                        await connectDB(rankingQuery)

                        await embedMessage(ctx, "PUBG name {} added to the snipa list".format(pubgname))
                    else:
                        print("UNKNOWN")
                        await embedMessage(ctx, "Uknown error idk kev KUKLE")
                else:
                    await embedMessage(ctx, "No PUBG name mentioned")
            else:
                await embedMessage(ctx, "Mention member not found")
        else:
            await embedMessage(ctx, "Invalid Argument, please use mentions")
    else:
        await embedMessage(ctx, "You don't have permission to use this command")


@client.hybrid_command(aliases=["b"], description="Adds or removes bounty to someone (Admin only)")
@app_commands.choices(
    choice=[app_commands.Choice(name="Add", value="add"), app_commands.Choice(name="Remove", value="remove")]
)
async def bounty(ctx, choice, value: int, name):
    checkChoices = ctx.command.app_command.parameters[0].choices
    listChoices = []
    for choices in checkChoices:
        listChoices.append(choices.value)

    if ctx.author.guild_permissions.kick_members or ctx.author.id == 270224083684163584:
        if choice in listChoices:
            SNIPA_URL = "https://api.pubg.com/shards/steam/players?filter[playerNames]={}".format(name)

            player_stat = await requestAio(SNIPA_URL, PUBG_HEADER)

            if "errors" in player_stat:
                await embedMessage(ctx, "Nickname {} doesn't exist in PUBG".format(name))
                return
            elif "data" in player_stat:
                if choice == "add":
                    statsQuery = """INSERT INTO stats (NAME, KILLS, DEATHS, DAMAGE_DEALT, SNIPAS_KILLED, DISTANCE_TRAVELLED, SUICIDES, SCORE, RANKING, BOUNTY) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (NAME) DO UPDATE SET bounty=STATS.bounty+%s"""
                    statsInsert = (
                        name,
                        0,
                        0,
                        0,
                        0,
                        [0, 0, 0, 0, 0],
                        0,
                        0,
                        0,
                        value,
                        value,
                    )
                    await connectDB(statsQuery, statsInsert)

                    rankingQuery = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
                    await connectDB(rankingQuery)
                    await embedMessage(ctx, "Bounty {} added to {}".format(value, name))
                elif choice == "remove":
                    statsQuery = """SELECT name FROM stats WHERE NAME LIKE %s"""
                    statsInsert = (name,)
                    statsSelect = await connectDB(statsQuery, statsInsert)
                    if statsSelect:
                        statsQuery = """UPDATE stats SET bounty = stats.bounty-%s WHERE LOWER(name) LIKE LOWER(%s)"""
                        statsInsert = (value, name)
                        await connectDB(statsQuery, statsInsert)
                        await embedMessage(
                            ctx,
                            "Bounty {} deducted from {}".format(value, name),
                        )
                    else:
                        await embedMessage(ctx, "Name not in database")
                        return
        else:
            await embedMessage(ctx, "Invalid command")
    else:
        await embedMessage(ctx, "You do not have permission to use this command")


@client.hybrid_command(description="Deletes image from someones profile (Admin only)")
@app_commands.choices(
    choice=[app_commands.Choice(name="Image", value="image"), app_commands.Choice(name="PUBG Name", value="name")]
)
async def delete(ctx, choice, name=None):
    checkChoices = ctx.command.app_command.parameters[0].choices
    listChoices = []
    for choices in checkChoices:
        listChoices.append(choices.value)

    if ctx.author.guild_permissions.kick_members or ctx.author.id == 270224083684163584:
        if choice in listChoices:
            if name.startswith("<@") is True:
                name = name.replace("<@", "")
                name = name.replace(">", "")
                member = await ctx.guild.fetch_member(name)
                if member is not None:
                    discordSelectQuery = """SELECT id from discord_profiles WHERE id = %s"""
                    discordSelectInsert = (member.id,)
                    discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)
                    if discordSelect:
                        if choice == "image":
                            discordSelectQuery = """UPDATE discord_profiles SET image = NULL WHERE id = %s"""
                            discordSelectInsert = (member.id,)
                            await connectDB(discordSelectQuery, discordSelectInsert)
                            await embedMessage(ctx, "Image deleted from user {}".format(member))
                        else:
                            discordSelectQuery = """UPDATE discord_profiles SET pubg_name = NULL WHERE id = %s"""
                            discordSelectInsert = (member.id,)
                            await connectDB(discordSelectQuery, discordSelectInsert)
                            await embedMessage(
                                ctx,
                                "PUBG name deleted from user {}".format(member),
                            )
                    else:
                        await embedMessage(ctx, "User not found")
                else:
                    await embedMessage(ctx, "Mention member not found")
            else:
                await embedMessage(ctx, "Invalid Argument, please use mentions")
        else:
            await embedMessage(ctx, "Invalid command")
    else:
        await embedMessage(ctx, "You do not have permission to use this command")


allCommands = [
    app_commands.Choice(name="All Commands", value="all"),
    app_commands.Choice(name="Meme Commands", value="memes"),
]

for command in client.commands:
    allCommands.append(app_commands.Choice(name=command.name, value=command.name))


@client.hybrid_command(description="Bans someone from using commands (Admin only)")
# @app_commands.choices(choice=allCommands)
async def ban(ctx, command, mention):
    if ctx.author.guild_permissions.kick_members or ctx.author.id == 270224083684163584:
        if command is not None:
            command = command.lower()

        if command == "image" or command == "add" or command == "game":
            if mention.startswith("<@") is True:
                mention = mention.replace("<@", "")
                mention = mention.replace(">", "")
                member = await ctx.guild.fetch_member(mention)
                if member is not None:
                    discordSelectQuery = """SELECT id, banned_commands from discord_profiles WHERE id = %s"""
                    discordSelectInsert = (member.id,)
                    discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)
                    if discordSelect:
                        bannedCommands = discordSelect[0][1]
                    else:
                        bannedCommands = [False, False, False]

                    match command:
                        case "image":
                            bannedCommands[0] = True
                        case "add":
                            bannedCommands[1] = True
                        case "game":
                            bannedCommands[2] = True
                    discordSelectQuery = """INSERT INTO discord_profiles (ID, BANNED_COMMANDS) VALUES (%s,%s) ON CONFLICT (ID) DO UPDATE SET banned_commands=%s"""
                    discordSelectInsert = (
                        member.id,
                        bannedCommands,
                        bannedCommands,
                    )
                    await connectDB(discordSelectQuery, discordSelectInsert)
                    await embedMessage(
                        ctx,
                        "User {} banned from using command {}".format(member, command),
                    )
                else:
                    await embedMessage(ctx, "Mention member not found")
            else:
                await embedMessage(ctx, "Invalid Argument, please use mentions")
        else:
            await embedMessage(ctx, "Invalid command")
    else:
        await embedMessage(ctx, "You do not have permission to use this command")


@client.hybrid_command(description="Unbans someone from using commands (Admin only)")
async def unban(ctx, command, mention):
    if ctx.author.guild_permissions.kick_members or ctx.author.id == 270224083684163584:
        if command is not None:
            command = command.lower()

        if command == "image" or command == "add" or command == "game":
            if mention.startswith("<@") is True:
                mention = mention.replace("<@", "")
                mention = mention.replace(">", "")
                member = await ctx.guild.fetch_member(mention)
                if member is not None:
                    discordSelectQuery = """SELECT id, banned_commands from discord_profiles WHERE id = %s"""
                    discordSelectInsert = (member.id,)
                    discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)
                    if discordSelect:
                        bannedCommands = discordSelect[0][1]
                        match command:
                            case "image":
                                bannedCommands[0] = False
                            case "add":
                                bannedCommands[1] = False
                            case "game":
                                bannedCommands[2] = False

                        discordSelectQuery = """UPDATE discord_profiles SET banned_commands = %s WHERE id = %s"""
                        discordSelectInsert = (bannedCommands, member.id)
                        await connectDB(discordSelectQuery, discordSelectInsert)
                        await embedMessage(
                            ctx,
                            "User {} unbanned from using command {}".format(member, command),
                        )
                    else:
                        await embedMessage(ctx, "User not found")
                else:
                    await embedMessage(ctx, "Mention member not found")
            else:
                await embedMessage(ctx, "Invalid Argument, please use mentions")
        else:
            await embedMessage(ctx, "Invalid command")
    else:
        await embedMessage(ctx, "You do not have permission to use this command")


@client.hybrid_command(aliases=["i"], description="Adds your PUBG character to your profile")
async def image(ctx, link):
    if validators.url(link):
        discordSelectQuery = """SELECT pubg_name, image, banned_commands from discord_profiles WHERE id = %s"""
        discordSelectInsert = (ctx.author.id,)
        discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)
        discordSelect = discordSelect[0]
        if discordSelect[2][0] is False:
            discordQuery = """ INSERT INTO discord_profiles (ID, IMAGE, PUBG_NAME) VALUES (%s,%s,%s) ON CONFLICT (ID) DO UPDATE SET IMAGE=%s"""
            discordInsert = (ctx.author.id, link, "", link)
            await connectDB(discordQuery, discordInsert)
            if discordSelect[1] is None:
                await embedMessage(ctx, "Image added!")
            else:
                await embedMessage(ctx, "Image replaced!")
        else:
            await embedMessage(ctx, "You are banned from adding images")
    else:
        await embedMessage(ctx, "No link present")


@client.hybrid_command(aliases=["a"], description="Adds your name to the snipa list and add/replace PUBG name in profile")
async def add(ctx, pubgname):
    SNIPA_URL = "https://api.pubg.com/shards/steam/players?filter[playerNames]={}".format(pubgname)

    player_stat = await requestAio(SNIPA_URL, PUBG_HEADER)

    if "errors" in player_stat:
        await embedMessage(ctx, "Nickname doesn't exist in PUBG")
        return
    elif "data" in player_stat:
        discordSelectQuery = """SELECT pubg_name, banned_commands from discord_profiles WHERE id = %s"""
        discordSelectInsert = (ctx.author.id,)
        discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)
        if discordSelect:
            discordSelect = discordSelect[0]
        if not discordSelect or discordSelect[1][1] is False:
            discordCheckQuery = """SELECT pubg_name from discord_profiles WHERE LOWER(pubg_name) LIKE LOWER(%s)"""
            discordCheckInsert = (pubgname,)
            discordCheck = await connectDB(discordCheckQuery, discordCheckInsert)
            if not (discordCheck):
                discordInsertQuery = """INSERT INTO discord_profiles (ID, PUBG_NAME) VALUES (%s,%s) ON CONFLICT (ID) DO UPDATE SET PUBG_NAME=%s"""
                discordInsertValues = (ctx.author.id, pubgname, pubgname)
                await connectDB(discordInsertQuery, discordInsertValues)

                statsInsertQuery = """INSERT INTO stats (NAME, KILLS, DEATHS, DAMAGE_DEALT, SNIPAS_KILLED, DISTANCE_TRAVELLED, SUICIDES, SCORE, RANKING, BOUNTY) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (NAME) DO NOTHING"""
                statsInsertValues = (pubgname, 0, 0, 0, 0, [0, 0, 0, 0, 0], 0, 0, 0, 0)
                await connectDB(statsInsertQuery, statsInsertValues)

                rankingQuery = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
                await connectDB(rankingQuery)

                if discordSelect:
                    await embedMessage(
                        ctx,
                        "PUBG name {} replaced with {}".format(discordSelect[0], pubgname),
                    )
                else:
                    await embedMessage(ctx, "PUBG name {} added to the snipa list".format(pubgname))
            else:
                await embedMessage(
                    ctx,
                    "Name already taken! If it's yours ask the mods to remove it from the person who took it",
                )
        else:
            await embedMessage(ctx, "You are banned from adding names to snipa list")
    else:
        print("UNKNOWN")


@client.hybrid_command(aliases=["p"], description="Shows your or someones else profile")
async def profile(ctx, *, name=None):
    DEV = await client.fetch_user(270224083684163584)
    if name is None:
        firstName = ctx.author.name
        member = ctx.author
    elif name.startswith("<@") is True:
        firstName = name
        name = name.replace("<@", "")
        name = name.replace(">", "")
        member = await ctx.guild.fetch_member(name)
    else:
        firstName = name
        await ctx.guild.query_members(name)
        member = discord.utils.get(ctx.guild.members, name=name)

    if name is not None and member is None:
        discordQuery = (
            """SELECT id, image, pubg_name, banned_commands from discord_profiles WHERE LOWER(pubg_name) LIKE LOWER(%s)"""
        )
        discordInsert = (name,)
        discordSelect = await connectDB(discordQuery, discordInsert)
        if discordSelect:
            await ctx.guild.query_members(name)
            member = discord.utils.get(ctx.guild.members, name=name)
            if member is None:
                urlProfile = ""
            else:
                urlProfile = member.display_avatar.url
        if not (discordSelect):
            await embedMessage(
                ctx,
                "No profile found for {}. Use {}image or {}add first!".format(firstName, ctx.prefix, ctx.prefix),
            )
            return

    else:
        discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
        discordInsert = (member.id,)
        discordSelect = await connectDB(discordQuery, discordInsert)
        if discordSelect:
            urlProfile = member.display_avatar.url
            discordQuery = """SELECT id, image, pubg_name, banned_commands from discord_profiles WHERE id = %s"""
            discordInsert = (member.id,)
            discordSelect = await connectDB(discordQuery, discordInsert)
        else:
            await embedMessage(
                ctx,
                "PUBG name from {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                    firstName, ctx.prefix
                ),
            )
            return

    member = await ctx.guild.fetch_member(discordSelect[0][0])

    embed = discord.Embed(title="Profile", description="", color=0x000000, timestamp=ctx.message.created_at)
    embed.set_thumbnail(url=urlProfile)
    embed.add_field(name="Discord Name", value=member.name, inline=True)
    embed.add_field(name="PUBG Name", value=discordSelect[0][2], inline=True)
    if discordSelect[0][1] is not None:
        embed.set_image(url=discordSelect[0][1])
    embed.set_footer(text="Bot made by Tuxsuper", icon_url=DEV.display_avatar.url)
    await ctx.send(embed=embed)


@client.hybrid_command(aliases=["r"], description="Shows your or someones else stats")
async def report(ctx, *, name=None):
    if name is None:  # No name used
        firstName = ctx.author.name
        member = ctx.author
    elif name.startswith("<@") is True:  # Mention used
        firstName = name
        name = name.replace("<@", "")
        name = name.replace(">", "")
        member = await ctx.guild.fetch_member(name)
    else:  # Discord name used
        firstName = name
        await ctx.guild.query_members(name)
        member = discord.utils.get(ctx.guild.members, name=name)

    if name is not None and member is None:  # PUBG name used
        discordQuery = """SELECT pubg_name from discord_profiles WHERE LOWER(pubg_name) LIKE LOWER(%s)"""
        discordInsert = (name,)
        discordSelect = await connectDB(discordQuery, discordInsert)
        if discordSelect:
            discordSelect = discordSelect[0][0]
            name = discordSelect
        else:
            discordQuery = """SELECT name from stats WHERE LOWER(name) LIKE LOWER(%s)"""
            discordInsert = (name,)
            discordSelect = await connectDB(discordQuery, discordInsert)
            if discordSelect:
                discordSelect = discordSelect[0][0]
                name = discordSelect
            else:
                await embedMessage(
                    ctx,
                    "PUBG name {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                        firstName, ctx.prefix
                    ),
                )
                return

    else:  # Discord, no name or Mention used
        discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
        discordInsert = (member.id,)
        discordSelect = await connectDB(discordQuery, discordInsert)
        if discordSelect:
            discordSelect = discordSelect[0][0]
            name = discordSelect
        else:
            await embedMessage(
                ctx,
                "PUBG name from {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                    firstName, ctx.prefix
                ),
            )
            return

    name = name.lower()

    playerSelectQuery = """SELECT * from kills WHERE LOWER(name) LIKE LOWER(%s)"""
    playerSelectInsert = (name,)
    playerSelect = await connectDB(playerSelectQuery, playerSelectInsert)

    statsSelectQuery = """SELECT * from stats WHERE LOWER(name) LIKE LOWER(%s)"""
    statsSelectInsert = (name,)
    statsSelect = await connectDB(statsSelectQuery, statsSelectInsert)
    statsSelect = statsSelect[0]

    if statsSelect[2] == 0:
        kd = statsSelect[1]
    else:
        kd = statsSelect[1] / statsSelect[2]
    distanceTravelledTotal = (statsSelect[5][0] + statsSelect[5][1] + statsSelect[5][2]) / 1000

    with open("./assets/dictionaries/typeKill.json", "r") as f:
        typeKill = json.loads(f.read())

    with open("./assets/dictionaries/simpleCause.json", "r") as f:
        simpleCause = json.loads(f.read())

    for index, playerKills in enumerate(playerSelect):
        replace = list(playerKills)
        replace[2] = simpleCause[replace[2]]
        playerSelect[index] = tuple(replace)

    counter = Counter(playerKills[2] for playerKills in playerSelect)
    print(counter)

    for kill in counter:
        typeKill[kill] = typeKill[kill] + counter[kill]

    if typeKill["Gun"] > 0:
        badge = Image.open("./assets/images/badgehaHAA.png")
    elif statsSelect[8] <= 10:
        if statsSelect[8] == 1:
            badge = Image.open("./assets/images/badgeBruceU.png")
        else:
            badge = Image.open("./assets/images/badgeCommando.png")
    else:
        badge = Image.open("./assets/images/badgeZULUL.png")

    basicReport = Image.open("./assets/images/report.png")
    title_font = ImageFont.truetype("./assets/fonts/Myriad Pro Bold.ttf", 60)
    counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
    reportCard = ImageDraw.Draw(basicReport)
    reportCard.text(
        (2000 / 2, 60),
        statsSelect[0],
        (255, 255, 255),
        font=title_font,
        anchor="ma",
        align="center",
    )

    reportCard.text((205, 273), "x {}".format(typeKill["Punch"]), (255, 255, 255), font=counter_font)
    reportCard.text(
        (205, 481),
        "x {}".format(typeKill["Vehicle"]),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text(
        (205, 689),
        "x {}".format(typeKill["Grenade"]),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text(
        (205, 897),
        "x {}".format(typeKill["Panzerfaust"]),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text((205, 1105), "x {}".format(typeKill["C4"]), (255, 255, 255), font=counter_font)
    reportCard.text(
        (205, 1313),
        "x {}".format(typeKill["Glider"]),
        (255, 255, 255),
        font=counter_font,
    )

    reportCard.text(
        (558, 273),
        "x {}".format(typeKill["Melee Weapon"]),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text(
        (558, 481),
        "x {}".format(typeKill["Melee Throw"]),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text(
        (558, 689),
        "x {}".format(typeKill["Molotov"]),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text(
        (558, 897),
        "x {}".format(typeKill["Crossbow"]),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text(
        (558, 1104),
        "x {}".format(typeKill["Mortar"]),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text((558, 1313), "x {}".format(typeKill["Gun"]), (255, 0, 0), font=counter_font)

    reportCard.text((852, 262), "Killed Forsen", (255, 255, 255), font=counter_font)
    reportCard.text((852, 378), "Died to Forsen", (255, 255, 255), font=counter_font)
    reportCard.text((852, 491), "K/D", (255, 255, 255), font=counter_font)
    reportCard.text((852, 605), "Damage Dealt", (255, 255, 255), font=counter_font)
    reportCard.text((852, 721), "Snipas Killed", (255, 255, 255), font=counter_font)
    reportCard.text((852, 842), "Distance Travelled", (255, 255, 255), font=counter_font)
    reportCard.text((852, 958), "Suicides", (255, 255, 255), font=counter_font)

    reportCard.text((1322, 262), "{}".format(statsSelect[1]), (255, 255, 255), font=counter_font)
    reportCard.text((1322, 378), "{}".format(statsSelect[2]), (255, 255, 255), font=counter_font)
    reportCard.text((1322, 491), "{}".format(round(kd, 3)), (255, 255, 255), font=counter_font)
    reportCard.text(
        (1322, 605),
        "{}".format(round(statsSelect[3], 2)),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text((1322, 721), "{}".format(statsSelect[4]), (255, 255, 255), font=counter_font)
    reportCard.text(
        (1322, 842),
        "{} km".format(round(distanceTravelledTotal, 2)),
        (255, 255, 255),
        font=counter_font,
    )
    reportCard.text((1322, 958), "{}".format(statsSelect[6]), (255, 255, 255), font=counter_font)

    reportCard.text((852, 1123), "Score", (255, 255, 255), font=counter_font)
    reportCard.text((852, 1239), "Ranking", (255, 255, 255), font=counter_font)
    reportCard.text((852, 1355), "Bounty", (255, 255, 255), font=counter_font)

    reportCard.text((1152, 1123), "{}".format(statsSelect[7]), (255, 255, 255), font=counter_font)
    reportCard.text((1152, 1239), "#{}".format(statsSelect[8]), (255, 255, 255), font=counter_font)
    reportCard.text(
        (1152, 1355),
        "{} pts".format(statsSelect[9]),
        (255, 255, 255),
        font=counter_font,
    )

    basicReport.paste(badge, (1563, 1113), badge)
    basicReport.save("./assets/images/reportResult.png")

    await ctx.send(file=discord.File("./assets/images/reportResult.png"))


@client.hybrid_command(aliases=["lb"], description="Shows the Leaderboard")
async def leaderboard(ctx, *, value=None):
    if value is None:  # No name used
        page = 0
        offset = 0
    elif value.isdigit():  # Number used
        if int(value) > 999:
            await embedMessage(ctx, "Please type numbers less than 1000")
            return
        else:
            page = int(value) - 1
            offset = page * 10

    elif value.startswith("<@") is True:  # Mention used
        firstName = value
        value = value.replace("<@", "")
        value = value.replace(">", "")
        member = await ctx.guild.fetch_member(value)
        value = firstName
    else:  # Discord name used
        firstName = value
        await ctx.guild.query_members(value)
        member = discord.utils.get(ctx.guild.members, name=value)

    if value is not None and not value.isdigit():
        if member is None:  # PUBG name used
            discordQuery = """SELECT name from stats WHERE LOWER(name) LIKE LOWER(%s)"""
            discordInsert = (value,)
            discordSelect = await connectDB(discordQuery, discordInsert)
            if discordSelect:
                discordSelect = discordSelect[0][0]
                value = discordSelect
            else:
                await embedMessage(
                    ctx,
                    "PUBG name {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                        firstName, ctx.prefix
                    ),
                )
                return

        else:  # Discord, no name or Mention used
            discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
            discordInsert = (member.id,)
            discordSelect = await connectDB(discordQuery, discordInsert)
            if discordSelect:
                discordSelect = discordSelect[0][0]
                value = discordSelect
            else:
                await embedMessage(
                    ctx,
                    "PUBG name from {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                        firstName, ctx.prefix
                    ),
                )
                return

        statsSelectQuery = """SELECT name, ROW_NUMBER() OVER (ORDER BY ranking ASC, name) AS rows from stats"""
        statsSelect = await connectDB(statsSelectQuery)
        for stats in statsSelect:
            if stats[0] == value:
                row = stats[1]
                break

        page = math.floor((row - 1) / 10)
        offset = page * 10

        print(row)
        print(page)
        print(offset)

    statsSelectQuery = (
        """SELECT ranking, name, score, kills, deaths from stats ORDER BY ranking ASC, name LIMIT 10 OFFSET %s"""
    )
    statsSelectInsert = (offset,)
    statsSelect = await connectDB(statsSelectQuery, statsSelectInsert)

    xArray = [87, 221, 874, 1224, 1574]
    yArray = [326, 442, 558, 674, 790, 906, 1022, 1136, 1254, 1370]

    basicReport = Image.open("./assets/images/leaderboard.png")
    counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
    reportCard = ImageDraw.Draw(basicReport)
    reportCard.text((1751, 57), "Page {}".format(page + 1), (255, 255, 255), font=counter_font)

    for index, user in enumerate(statsSelect):
        if value is not None and not value.isdigit():
            if user[1].lower() == value.lower():
                color = (255, 255, 0)
            else:
                color = (255, 255, 255)
        else:
            color = (255, 255, 255)

        reportCard.text(
            (xArray[0], yArray[index]),
            "#{}".format(user[0]),
            color,
            font=counter_font,
            align="center",
        )
        reportCard.text((xArray[1], yArray[index]), "{}".format(user[1]), color, font=counter_font)
        reportCard.text(
            (xArray[2], yArray[index]),
            "{} pts".format(user[2]),
            color,
            font=counter_font,
        )
        reportCard.text((xArray[3], yArray[index]), "{}".format(user[3]), color, font=counter_font)
        reportCard.text((xArray[4], yArray[index]), "{}".format(user[4]), color, font=counter_font)

    basicReport.save("./assets/images/leaderboardResult.png")

    await ctx.send(file=discord.File("./assets/images/leaderboardResult.png"))


customboardArray = {
    "kills": "kills",
    "deaths": "deaths",
    "kd": "KD",
    "damage": "damage",
    "snipakills": "snipas_killed",
    "distance": "distance",
    "suicides": "suicides",
    "bounty": "bounty",
}
customboardChoices = []
for command in customboardArray:
    customboardChoices.append(app_commands.Choice(name=command, value=command))


@client.hybrid_command(aliases=["cb"], description="Shows the Customboard")
@app_commands.choices(choice=customboardChoices)
async def customboard(ctx, choice, *, value=None):
    if choice is not None:
        choice = choice.lower()

    valueArray = {
        "kills": "kills",
        "deaths": "deaths",
        "kd": "kills/CASE WHEN deaths = 0 THEN 1 ELSE deaths END::real AS KD",
        "damage": "ROUND(damage_dealt::numeric,2) AS damage",
        "snipakills": "snipas_killed",
        "distance": "(distance_travelled[1]+distance_travelled[2]+distance_travelled[3])/1000 AS distance",
        "suicides": "suicides",
        "bounty": "bounty",
    }
    if choice in customboardArray:
        if value is None:  # No name used
            page = 1
            offset = 0
        elif value.isdigit():  # Number used
            if int(value) > 999:
                await embedMessage(ctx, "Please type numbers less than 1000")
                return
            else:
                page = int(value)
                offset = (page - 1) * 20

        elif value.startswith("<@") is True:  # Mention used
            firstName = value
            value = value.replace("<@", "")
            value = value.replace(">", "")
            member = await ctx.guild.fetch_member(value)
            value = firstName
        else:  # Discord name used
            firstName = value
            await ctx.guild.query_members(value)
            member = discord.utils.get(ctx.guild.members, name=value)

        if value is not None and not value.isdigit():
            if member is None:  # PUBG name used
                discordQuery = """SELECT name from stats WHERE LOWER(name) LIKE LOWER(%s)"""
                discordInsert = (value,)
                discordSelect = await connectDB(discordQuery, discordInsert)
                if discordSelect:
                    discordSelect = discordSelect[0][0]
                    value = discordSelect
                else:
                    await embedMessage(
                        ctx,
                        "PUBG name {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                            firstName, ctx.prefix
                        ),
                    )
                    return

            else:  # Discord, no name or Mention used
                discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
                discordInsert = (member.name,)
                discordSelect = await connectDB(discordQuery, discordInsert)
                if discordSelect:
                    discordSelect = discordSelect[0][0]
                    value = discordSelect
                else:
                    await embedMessage(
                        ctx,
                        "PUBG name from {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                            firstName, ctx.prefix
                        ),
                    )
                    return

            match choice:
                case "kd":
                    rankingQuery = sql.SQL(
                        "SELECT name, ROW_NUMBER() OVER (ORDER BY kills/CASE WHEN deaths = 0 THEN 1 ELSE deaths END::real DESC, name) AS rows from stats"
                    )
                case "damage":
                    rankingQuery = sql.SQL(
                        "SELECT name, ROW_NUMBER() OVER (ORDER BY damage_dealt DESC, name) AS rows from stats"
                    )
                case "distance":
                    rankingQuery = sql.SQL(
                        "SELECT name, ROW_NUMBER() OVER (ORDER BY (distance_travelled[1]+distance_travelled[2]+distance_travelled[3])/1000 DESC, name) AS rows from stats"
                    )
                case _:
                    rankingQuery = sql.SQL(
                        "SELECT name, ROW_NUMBER() OVER (ORDER BY {} DESC, name) AS rows from stats"
                    ).format(sql.Identifier(customboardArray[choice]))
            CURSOR.execute(rankingQuery)
            rankingRows = CURSOR.fetchall()

            for stats in rankingRows:
                if stats[0] == value:
                    row = stats[1]
                    break

            page = math.ceil((row) / 20)
            offset = (page - 1) * 20

        match choice:
            case "kd":
                statsSelectQuery = sql.SQL(
                    "SELECT name, ROUND(kills/CASE WHEN deaths = 0 THEN 1 ELSE deaths END::numeric, 2) AS KD, DENSE_RANK() OVER(ORDER BY kills/CASE WHEN deaths = 0 THEN 1 ELSE deaths END::real DESC) rank FROM stats ORDER BY rank, name LIMIT 20 OFFSET %s"
                )
            case "damage":
                statsSelectQuery = sql.SQL(
                    "SELECT name, ROUND(damage_dealt::numeric,2) AS damage, DENSE_RANK() OVER(ORDER BY damage_dealt DESC) rank FROM stats ORDER BY rank, name LIMIT 20 OFFSET %s"
                )
            case "distance":
                statsSelectQuery = sql.SQL(
                    "SELECT name, ROUND(((distance_travelled[1]+distance_travelled[2]+distance_travelled[3])/1000)::numeric,2) AS distance, DENSE_RANK() OVER(ORDER BY (distance_travelled[1]+distance_travelled[2]+distance_travelled[3]) DESC) rank FROM stats ORDER BY rank, name LIMIT 20 OFFSET %s"
                )
            case "bounty":
                statsSelectQuery = sql.SQL(
                    "SELECT name, {}, DENSE_RANK() OVER(ORDER BY {} DESC) rank FROM stats GROUP BY name HAVING bounty > 0 ORDER BY rank, name  LIMIT 20 OFFSET %s"
                ).format(
                    sql.Identifier(valueArray[choice]),
                    sql.Identifier(customboardArray[choice]),
                )
            case _:
                statsSelectQuery = sql.SQL(
                    "SELECT name, {}, DENSE_RANK() OVER(ORDER BY {} DESC) rank FROM stats ORDER BY rank, name LIMIT 20 OFFSET %s"
                ).format(
                    sql.Identifier(valueArray[choice]),
                    sql.Identifier(customboardArray[choice]),
                )

        statsSelectInsert = (offset,)
        CURSOR.execute(statsSelectQuery, statsSelectInsert)
        statsSelect = CURSOR.fetchall()

        limit = page * 20
        counter = 0
        otherCounter = 0

        xArray = [87, 221, 764, 1026, 1160, 1703]
        yArray = [326, 442, 558, 674, 790, 906, 1022, 1136, 1254, 1370]
        titleArray = {
            "kills": "Kills",
            "deaths": "Deaths",
            "kd": "K/D",
            "damage": "Damage",
            "snipakills": "Snipa Kills",
            "distance": "Distance",
            "suicides": "Suicides",
            "bounty": "Bounty",
        }

        basicReport = Image.open("./assets/images/customboard.png")
        counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
        reportCard = ImageDraw.Draw(basicReport)
        reportCard.text((1750, 57), "Page {}".format(page), (255, 255, 255), font=counter_font)
        reportCard.text((xArray[1], 210), "Username", (255, 255, 255), font=counter_font)
        reportCard.text(
            (xArray[2], 210),
            "{}".format(titleArray[choice]),
            (255, 255, 255),
            font=counter_font,
        )
        reportCard.text((xArray[4], 210), "Username", (255, 255, 255), font=counter_font)
        reportCard.text(
            (xArray[5], 210),
            "{}".format(titleArray[choice]),
            (255, 255, 255),
            font=counter_font,
        )

        for index, user in enumerate(statsSelect):
            if index == limit:
                break

            # valueArray = {"kills":user[2],"deaths":user[3],"damage":round(user[4],2),"snipakills":user[5],"suicides":user[6],"bounty":user[7]}
            if value is not None and not value.isdigit():
                if user[0].lower() == value.lower():
                    color = (255, 255, 0)
                else:
                    color = (255, 255, 255)
            else:
                color = (255, 255, 255)

            if counter >= 10:
                counter = 0
            if otherCounter < 10:
                reportCard.text(
                    (xArray[0], yArray[counter]),
                    "#{}".format(user[2]),
                    color,
                    font=counter_font,
                    align="center",
                )
                reportCard.text(
                    (xArray[1], yArray[counter]),
                    "{}".format(user[0]),
                    color,
                    font=counter_font,
                )
                reportCard.text(
                    (xArray[2], yArray[counter]),
                    "{}".format(user[1]),
                    color,
                    font=counter_font,
                )
            else:
                reportCard.text(
                    (xArray[3], yArray[counter]),
                    "#{}".format(user[2]),
                    color,
                    font=counter_font,
                    align="center",
                )
                reportCard.text(
                    (xArray[4], yArray[counter]),
                    "{}".format(user[0]),
                    color,
                    font=counter_font,
                )
                reportCard.text(
                    (xArray[5], yArray[counter]),
                    "{}".format(user[1]),
                    color,
                    font=counter_font,
                )

            counter += 1
            otherCounter += 1

        basicReport.save("./assets/images/customboardResult.png")

        await ctx.send(file=discord.File("./assets/images/customboardResult.png"))


@client.hybrid_command(aliases=["st"], description="Shows the Scoretable")
async def scoretable(ctx, *, value=None):
    with open("./assets/dictionaries/scoreTable.json", "r") as f:
        scoreTable = json.loads(f.read())

    if value is None:
        page = 1
    elif value.isdigit():  # Number used
        if int(value) > 999:
            await embedMessage(ctx, "Please type numbers less than 1000")
            return
        else:
            page = int(value)
    else:  # Weapon name used
        page = -1
        for index, value in enumerate(scoreTable):
            if value.lower() == value.lower():
                page = math.ceil((index + 1) / 20)
                break
        if page == -1:
            await embedMessage(ctx, "Weapon {} does not exist in the scoretable".format(value))
            return

    limit = page * 20
    counter = 0
    otherCounter = 0

    xArray = [102, 748, 930, 1576]
    yArray = [326, 442, 558, 674, 790, 906, 1022, 1136, 1254, 1370]

    basicReport = Image.open("./assets/images/scoreTable.png")
    counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
    reportCard = ImageDraw.Draw(basicReport)
    reportCard.text((1538, 57), "Page {}".format(page), (255, 255, 255), font=counter_font)

    for index, score in enumerate(scoreTable):
        if index == limit:
            break

        if index < limit and index >= limit - 20:
            if value is not None and not value.isdigit():
                if score.lower() == value.lower():
                    color = (255, 255, 0)
                else:
                    color = (255, 255, 255)
            else:
                color = (255, 255, 255)

            if counter >= 10:
                counter = 0
            if otherCounter < 10:
                reportCard.text(
                    (xArray[0], yArray[counter]),
                    "{}".format(score),
                    color,
                    font=counter_font,
                )
                reportCard.text(
                    (xArray[1], yArray[counter]),
                    "{}".format(scoreTable[score]),
                    color,
                    font=counter_font,
                )
            else:
                reportCard.text(
                    (xArray[2], yArray[counter]),
                    "{}".format(score),
                    color,
                    font=counter_font,
                )
                reportCard.text(
                    (xArray[3], yArray[counter]),
                    "{}".format(scoreTable[score]),
                    color,
                    font=counter_font,
                )
            counter += 1
            otherCounter += 1

    basicReport.save("./assets/images/scoreTableResult.png")

    await ctx.send(file=discord.File("./assets/images/scoreTableResult.png"))


@client.hybrid_command(aliases=["h"], description="List of commands")
async def help(ctx):
    DEV = await client.fetch_user(270224083684163584)
    embed = discord.Embed(title="Commands", description="", color=0x000000, timestamp=ctx.message.created_at)
    embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
    for command in client.commands:
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

    embed.set_footer(text="Bot made by Tuxsuper", icon_url=DEV.display_avatar.url)
    await ctx.send(embed=embed)


@client.event
async def on_command_error(message, error):
    print(error)
    if isinstance(error, commands.MissingRole):
        await embedMessage(message, "Role required missing")
    if isinstance(error, commands.BadArgument):
        await embedMessage(message, "Wrong value for the parameter")
    if isinstance(error, commands.MissingRequiredArgument):
        await embedMessage(message, error.param.name.capitalize() + " parameter is required")


TOKEN = os.environ["BOT_TEST_TOKEN"]
# TOKEN = os.environ["BOT_TOKEN"]
client.run(TOKEN)
