import discord
import random
import datetime
import time
import aiohttp
import math

from utils import default
from discord.ext import commands
from discord import app_commands

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

        await  default.embedMessage(ctx, title="Roll", description=f"{roll}% chance of {message}")

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
            await  default.embedMessage(ctx, title="Time left until Dark and Darker", description=text)


    @commands.hybrid_command(description="List of emotes the bot has access to")
    async def emotes(self, ctx):
        embed = discord.Embed(title="Emotes", description="", color=0x000000)

        lenghtText = ""
        for emote in self.client.emojis:
            lenghtText = lenghtText + str(emote) + " `:" + emote.name + ":`\n"

        emoteText_Array = []
        while len(emoteText_Array)<6:
            emoteText = lenghtText[:1000]
            emoteText = emoteText.rsplit('\n', 1)
            emoteText_Array.append(emoteText[0])

            lenghtText = lenghtText.replace(emoteText[0]+"\n", "")


        for emoteText in emoteText_Array:
            embed.add_field(
                name="\u200b", value=emoteText
            )

        try:
            await ctx.author.send(embed=embed)
        except:
            await ctx.send(content="Couldn't DM you (blocked/DM's closed")


class Bingo_Command(commands.Cog):
    def __init__(self, client):
        self.client = client


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
                await  default.embedMessage(ctx, description="You opted-in auto bingo card sent to your DM's")
                return
            elif choice.lower() == "opt-out":
                user_settingsQuery = """INSERT INTO user_settings (id, autobingo_dm) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET autobingo_dm=%s"""
                user_settingsInsert = (ctx.author.id, False, False)
                await default.connectDB(user_settingsQuery, user_settingsInsert)
                await  default.embedMessage(ctx, description="You opted-out auto bingo card sent to your DM's")
                return

            elif ctx.message.mentions:
                file, embed = await default.create_bingo_card(user=ctx.message.mentions[0])
                await ctx.send(file=file, embed=embed)
                return

        if self.client.twitch.isIntro == True:
            file, embed = await default.create_bingo_card(user=ctx.author)
            await ctx.send(file=file, embed=embed)


class Game_Command(commands.Cog):
    def __init__(self, client):
        self.client = client


    @commands.hybrid_command(aliases=["g"], description="Shows info about a game")
    async def game(self, ctx, *, game):
        discordSelectQuery = """SELECT pubg_name, image, banned_commands from discord_profiles WHERE id = %s"""
        discordSelectInsert = (ctx.author.id,)
        discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)

        if not discordSelect or discordSelect[0][2][2] is False:
            await ctx.defer()

            async with aiohttp.ClientSession() as session:
                resIGDB = await default.get_IGDB(game, session)

                if resIGDB is not None and len(resIGDB) > 0:
                    game = resIGDB[0]["name"]

                    if "first_release_date" in resIGDB[0]:
                        year = time.localtime(int(resIGDB[0]["first_release_date"])).tm_year

                    resRAWG = await default.get_RAWG(game, session)

                    if "first_release_date" in resIGDB[0]:
                        resHLTB = await default.get_HLTB(game, session, year)
                    else:
                        resHLTB = []
                else:
                    resRAWG = await default.get_RAWG(game, session)

                    if resRAWG is not None and len(resRAWG) > 0 and len(resRAWG["results"]):
                        game = resRAWG["results"][0]["name"]
                        year = resRAWG["results"][0]["released"].split("-", 1)[0]

                        resIGDB = await default.get_IGDB(game, session, where=f"& release_dates.y = {year}")

                        resHLTB = await default.get_HLTB(game, session, year)
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
                    await  default.embedMessage(ctx, description="Game doesn't exist")
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
            await  default.embedMessage(ctx, description="You are banned from using the command game")


async def setup(client):
    await client.add_cog(Misc_Commands(client))
    await client.add_cog(Bingo_Command(client))
    await client.add_cog(Game_Command(client))
