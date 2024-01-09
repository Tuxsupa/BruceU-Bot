import random
import datetime
import time
import json
import asyncio

import discord
import aiohttp

from discord.ext import commands, tasks
from discord import app_commands

from dotenv import load_dotenv

from utils import default

load_dotenv()


class Misc_Commands(commands.Cog):
    def __init__(self, client: default.DiscordBot):
        self.client = client

        self.dndTime = datetime.datetime(2023, 4, 14, 0)
        # self.my_task.start()

    @commands.hybrid_command(aliases=["h"], description="List of commands")
    async def help(self, ctx: commands.Context):
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

        embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.client.DEV.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Rolls a chance")
    async def roll(self, ctx: commands.Context, *, message: str):
        roll = random.randint(0, 100)

        await default.embedMessage(client=self.client, ctx=ctx, title="Roll", description=f"{roll}% chance of {message}")

    @commands.hybrid_command(description="Time left until Dark and Darker next playtest")
    async def dnd(self, ctx: commands.Context):
        text = None
        timeLeft = self.dndTime - datetime.datetime.now()
        if timeLeft.total_seconds() <= 0:
            text = "DARK AND DARKER IS OUT <:MUGA:844690515966689291>"
            # text = "Now what <:TrollDespair:867414306580856832>"
        else:
            days = divmod(timeLeft.total_seconds(), 86400)
            hours = divmod(days[1], 3600)
            minutes = divmod(hours[1], 60)
            seconds = divmod(minutes[1], 1)
            text = f"{int(days[0])} days {int(hours[0])} hours {int(minutes[0])} minutes {int(seconds[0])} seconds left until Dark and Darker"
            # text = "DARK AND DARKER IS OUT <:MUGA:844690515966689291>"

        if text is not None:
            await default.embedMessage(
                client=self.client, ctx=ctx, title="Time left until Dark and Darker", description=text
            )

    @commands.hybrid_command(description="List of emotes the bot has access to")
    async def emotes(self, ctx: commands.Context):
        embed = discord.Embed(title="Emotes", description="", color=0x000000)

        lenghtText = ""
        for emote in self.client.emojis:
            lenghtText = lenghtText + str(emote) + " `:" + emote.name + ":`\n"

        emoteText_Array = []
        while len(emoteText_Array) < 6:
            emoteText = lenghtText[:1000]
            emoteText = emoteText.rsplit("\n", 1)
            emoteText_Array.append(emoteText[0])

            lenghtText = lenghtText.replace(emoteText[0] + "\n", "")

        for emoteText in emoteText_Array:
            embed.add_field(name="\u200b", value=emoteText)

        try:
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(content="Couldn't DM you (blocked/DM's closed)")


    # @commands.command(description="Turns markov on/off")
    # async def test(self, ctx: commands.Context):
    #     jsonCommands = {}

    #     print(self.client.commands)
    #     for command in self.client.commands:
    #         print(command)
    #         jsonCommands.update({command.name: False})

    #     print(jsonCommands)
    #     jsonCommands=json.dumps(jsonCommands)
    #     print(jsonCommands)

    #     user_settingsQuery = """INSERT INTO user_settings (user_id, autobingo_dm) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET autobingo_dm=%s"""
    #     user_settingsInsert = (ctx.author.id, True, True)
    #     await default.connectDB(user_settingsQuery, user_settingsInsert)


    # @tasks.loop(hours=1)
    # async def my_task(self):
    #     timeLeft = self.dndTime - datetime.datetime.now()
    #     hours = round(timeLeft.total_seconds()/3600)

    #     channel = await self.client.fetch_channel(1035515030445232188) #1035515030445232188
    #     if hours>1:
    #         await channel.send(f"{hours} HOURS LEFT UNTIL DARK AND DARKER <:MUGA:844690515966689291>")
    #     elif hours==1:
    #         await channel.send(f"{hours} HOUR LEFT UNTIL DARK AND DARKER <:MUGA:844690515966689291>")
    #     else:
    #         await channel.send(f"DARK AND DARKER IS OUUUUUUUUUUUUUUUT LET'S FUCKING GOOOOOOOOOOOO <:MUGA:844690515966689291>")
    #         self.my_task.stop()


    # @my_task.before_loop
    # async def time_check(self):
    #     await self.client.wait_until_ready()
    #     now = datetime.datetime.now()
    #     future = self.dndTime

    #     timeLeft = future-now
    #     if round(timeLeft.total_seconds()/3600) > 24:
    #         delta = datetime.timedelta(days=1)
    #         await asyncio.sleep(((future-delta) - now).seconds)
    #     elif round(timeLeft.total_seconds()/3600) >= 0:
    #         delta = datetime.timedelta(hours=1)
    #         now = datetime.datetime.now()
    #         next_hour = (now + delta).replace(microsecond=0, second=0, minute=0)
    #         await asyncio.sleep((next_hour - now).seconds)
    #     else:
    #         self.my_task.cancel()

class Bingo_Command(commands.Cog):
    def __init__(self, client: default.DiscordBot):
        self.client = client

    @commands.hybrid_command(description="Random Bingo Card when forsen is doing reactions")
    @app_commands.choices(
        choice=[app_commands.Choice(name="Opt-In", value="opt-in"), app_commands.Choice(name="Opt-Out", value="opt-out")]
    )
    async def bingo(self, ctx: commands.Context, choice=None):
        if choice:
            if choice.lower() == "opt-in":
                user_settingsQuery = """INSERT INTO user_settings (user_id, autobingo_dm) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET autobingo_dm=%s"""
                user_settingsInsert = (ctx.author.id, True, True)
                await default.connectDB(user_settingsQuery, user_settingsInsert)
                await default.embedMessage(
                    client=self.client, ctx=ctx, description="You opted-in auto bingo card sent to your DM's"
                )
                return
            elif choice.lower() == "opt-out":
                user_settingsQuery = """INSERT INTO user_settings (user_id, autobingo_dm) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET autobingo_dm=%s"""
                user_settingsInsert = (ctx.author.id, False, False)
                await default.connectDB(user_settingsQuery, user_settingsInsert)
                await default.embedMessage(
                    client=self.client, ctx=ctx, description="You opted-out auto bingo card sent to your DM's"
                )
                return

        if self.client.twitch.isIntro is True:
            user = ctx.author
            if ctx.message.mentions:
                user = ctx.message.mentions[0]

            file, embed = await default.create_bingo_card(client=self.client, user=user)
            embed.description = f"You can use {ctx.prefix}bingo opt-in to get automatic bingo cards"
            await ctx.send(file=file, embed=embed)


class Bets_Command(commands.Cog):
    def __init__(self, client: default.DiscordBot):
        self.client = client

    @commands.hybrid_command(description="Opt-in or out of recieving notifications when streamer starts bets")
    @app_commands.choices(
        choice=[app_commands.Choice(name="Opt-In", value="opt-in"), app_commands.Choice(name="Opt-Out", value="opt-out")]
    )
    async def bets(self, ctx: commands.Context, choice: str):
        if choice:
            if choice.lower() == "opt-in":
                user_settingsQuery = """INSERT INTO user_settings (user_id, bets_dm) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET bets_dm=%s"""
                user_settingsInsert = (ctx.author.id, True, True)
                await default.connectDB(user_settingsQuery, user_settingsInsert)
                await default.embedMessage(
                    client=self.client, ctx=ctx, description="You opted-in for bets sent to your DM's"
                )
                return
            elif choice.lower() == "opt-out":
                user_settingsQuery = """INSERT INTO user_settings (user_id, bets_dm) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET bets_dm=%s"""
                user_settingsInsert = (ctx.author.id, False, False)
                await default.connectDB(user_settingsQuery, user_settingsInsert)
                await default.embedMessage(
                    client=self.client, ctx=ctx, description="You opted-out for bets sent to your DM's"
                )
                return

class Game_Command(commands.Cog):
    def __init__(self, client: default.DiscordBot):
        self.client = client

    @commands.hybrid_command(aliases=["g"], description="Shows info about a game")
    async def game(self, ctx: commands.Context, *, game: str):
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
                    await default.embedMessage(client=self.client, ctx=ctx, description="Game doesn't exist")
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
                                for i in enumerate(countryCodes):
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
                embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.client.DEV.display_avatar.url)
                await ctx.send(embed=embed)
        else:
            await default.embedMessage(client=self.client, ctx=ctx, description="You are banned from using the command game")


async def setup(client: default.DiscordBot):
    await client.add_cog(Misc_Commands(client))
    await client.add_cog(Bingo_Command(client))
    await client.add_cog(Bets_Command(client))
    await client.add_cog(Game_Command(client))
