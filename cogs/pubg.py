import json
import math
import re
from collections import Counter
import discord
import validators

from PIL import Image, ImageFont, ImageDraw

from psycopg import sql

from discord.ext import commands
from discord import app_commands
from utils import default, pubgData


class PUBG_Commands(commands.Cog):
    def __init__(self, client: default.DiscordBot):
        self.client = client

    async def check_mention(self, ctx: commands.Context):
        if ctx.message.mentions:
            return True
        await default.embedMessage(client=self.client, ctx=ctx, description="Invalid Argument, please use mentions")
        return False

    async def check_link(self, ctx: commands.Context, link: str):
        if validators.url(link):
            return True
        await default.embedMessage(client=self.client, ctx=ctx, description="No link present")
        return False

    @commands.hybrid_command(aliases=["fi"], description="Force inserts an image to someones profile (Admin only)")
    async def forceimage(self, ctx: commands.Context, mention: discord.Member, link: str):
        if await default.check_permissions(self.client, ctx) and await self.check_link(ctx, link):
            discordQuery = (
                """INSERT INTO discord_profiles (ID, IMAGE) VALUES (%s,%s) ON CONFLICT (ID) DO UPDATE SET IMAGE=%s"""
            )
            discordInsert = (mention.id, link, link)
            await default.connectDB(discordQuery, discordInsert)
            await default.embedMessage(client=self.client, ctx=ctx, description=f"Image added for {mention}!")

    @commands.hybrid_command(
        aliases=["fa"], description="Force create/replaces a PUBG and Discord name to someones profile (Admin only)"
    )
    async def forceadd(self, ctx: commands.Context, mention: discord.Member, pubgname: str):
        if await default.check_permissions(self.client, ctx):
            SNIPA_URL = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={pubgname}"

            player_stat = await default.requestAio(SNIPA_URL, pubgData.PUBG_HEADER)

            if not player_stat or "errors" in player_stat:
                await default.embedMessage(client=self.client, ctx=ctx, description="Nickname doesn't exist in PUBG")
                return
            elif "data" in player_stat:
                discordInsertQuery = """INSERT INTO discord_profiles (ID, PUBG_NAME) VALUES (%s,%s) ON CONFLICT (ID) DO UPDATE SET PUBG_NAME=%s"""
                discordInsertValues = (mention.id, pubgname, pubgname)
                await default.connectDB(discordInsertQuery, discordInsertValues)

                statsInsertQuery = """INSERT INTO stats (NAME, KILLS, DEATHS, DAMAGE_DEALT, SNIPAS_KILLED, DISTANCE_TRAVELLED, SUICIDES, SCORE, RANKING, BOUNTY) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (NAME) DO NOTHING"""
                statsInsertValues = (pubgname, 0, 0, 0, 0, [0, 0, 0, 0, 0], 0, 0, 0, 0)
                await default.connectDB(statsInsertQuery, statsInsertValues)

                rankingQuery = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
                await default.connectDB(rankingQuery)

                await default.embedMessage(
                    client=self.client, ctx=ctx, description=f"PUBG name {pubgname} added to the snipa list"
                )
            else:
                print("UNKNOWN")
                await default.embedMessage(client=self.client, ctx=ctx, description="Unknown error idk kev KUKLE")

    @commands.hybrid_command(aliases=["b"], description="Adds or removes bounty to someone (Admin only)")
    @app_commands.choices(
        choice=[app_commands.Choice(name="Add", value="add"), app_commands.Choice(name="Remove", value="remove")]
    )
    async def bounty(self, ctx: commands.Context, choice, value: int, name: str):
        checkChoices = ctx.command.app_command.parameters[0].choices
        listChoices = [choices.value for choices in checkChoices]
        if await default.check_permissions(self.client, ctx):
            if choice in listChoices:
                SNIPA_URL = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={name}"

                player_stat = await default.requestAio(SNIPA_URL, pubgData.PUBG_HEADER)

                if not player_stat or "errors" in player_stat:
                    await default.embedMessage(
                        client=self.client, ctx=ctx, description=f"Nickname {name} doesn't exist in PUBG"
                    )
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
                        await default.connectDB(statsQuery, statsInsert)

                        rankingQuery = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
                        await default.connectDB(rankingQuery)
                        await default.embedMessage(
                            client=self.client, ctx=ctx, description=f"Bounty {value} added to {name}"
                        )
                    elif choice == "remove":
                        statsQuery = """SELECT name FROM stats WHERE NAME LIKE %s"""
                        statsInsert = (name,)
                        statsSelect = await default.connectDB(statsQuery, statsInsert)
                        if statsSelect:
                            statsQuery = """UPDATE stats SET bounty = stats.bounty-%s WHERE LOWER(name) LIKE LOWER(%s)"""
                            statsInsert = (value, name)
                            await default.connectDB(statsQuery, statsInsert)
                            await default.embedMessage(
                                client=self.client, ctx=ctx, description=f"Bounty {value} deducted from {name}"
                            )
                        else:
                            await default.embedMessage(client=self.client, ctx=ctx, description="Name not in database")
                            return
            else:
                await default.embedMessage(client=self.client, ctx=ctx, description="Invalid command")

    @commands.hybrid_command(description="Deletes image from someones profile (Admin only)")
    @app_commands.choices(
        choice=[app_commands.Choice(name="Image", value="image"), app_commands.Choice(name="PUBG Name", value="name")]
    )
    async def delete(self, ctx: commands.Context, choice, mention: discord.Member):
        checkChoices = ctx.command.app_command.parameters[0].choices
        listChoices = [choices.value for choices in checkChoices]
        if await default.check_permissions(self.client, ctx):
            if choice in listChoices:
                discordSelectQuery = """SELECT id from discord_profiles WHERE id = %s"""
                discordSelectInsert = (mention.id,)
                discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)
                if discordSelect:
                    if choice == "image":
                        discordSelectQuery = """UPDATE discord_profiles SET image = NULL WHERE id = %s"""
                        discordSelectInsert = (mention.id,)
                        await default.connectDB(discordSelectQuery, discordSelectInsert)
                        await default.embedMessage(
                            client=self.client, ctx=ctx, description=f"Image deleted from user {mention}"
                        )
                    else:
                        discordSelectQuery = """UPDATE discord_profiles SET pubg_name = NULL WHERE id = %s"""
                        discordSelectInsert = (mention.id,)
                        await default.connectDB(discordSelectQuery, discordSelectInsert)
                        await default.embedMessage(
                            client=self.client, ctx=ctx, description=f"PUBG name deleted from user {mention}"
                        )
                else:
                    await default.embedMessage(client=self.client, ctx=ctx, description="User not found in database")
            else:
                await default.embedMessage(client=self.client, ctx=ctx, description="Invalid command")

    @commands.hybrid_command(aliases=["i"], description="Adds your PUBG character to your profile")
    async def image(self, ctx: commands.Context, link: str):
        if await self.check_link(ctx, link):
            discordSelectQuery = """SELECT pubg_name, image, banned_commands from discord_profiles WHERE id = %s"""
            discordSelectInsert = (ctx.author.id,)
            discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)
            discordSelect = discordSelect[0]
            if discordSelect[2][0] is False:
                discordQuery = """ INSERT INTO discord_profiles (ID, IMAGE, PUBG_NAME) VALUES (%s,%s,%s) ON CONFLICT (ID) DO UPDATE SET IMAGE=%s"""
                discordInsert = (ctx.author.id, link, "", link)
                await default.connectDB(discordQuery, discordInsert)
                if discordSelect[1] is None:
                    await default.embedMessage(client=self.client, ctx=ctx, description="Image added!")
                else:
                    await default.embedMessage(client=self.client, ctx=ctx, description="Image replaced!")
            else:
                await default.embedMessage(client=self.client, ctx=ctx, description="You are banned from adding images")

    @commands.hybrid_command(
        aliases=["a"], description="Adds your name to the snipa list or add/replace PUBG name in profile"
    )
    async def add(self, ctx: commands.Context, pubgname: str):
        SNIPA_URL = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={pubgname}"

        player_stat = await default.requestAio(SNIPA_URL, pubgData.PUBG_HEADER)

        if not player_stat or "errors" in player_stat:
            await default.embedMessage(client=self.client, ctx=ctx, description="Nickname doesn't exist in PUBG")
            return
        elif "data" in player_stat:
            discordSelectQuery = """SELECT pubg_name, banned_commands from discord_profiles WHERE id = %s"""
            discordSelectInsert = (ctx.author.id,)
            discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)
            if discordSelect:
                discordSelect = discordSelect[0]
            if not discordSelect or discordSelect[1][1] is False:
                discordCheckQuery = """SELECT pubg_name from discord_profiles WHERE LOWER(pubg_name) LIKE LOWER(%s)"""
                discordCheckInsert = (pubgname,)
                discordCheck = await default.connectDB(discordCheckQuery, discordCheckInsert)
                if not discordCheck:
                    discordInsertQuery = """INSERT INTO discord_profiles (ID, PUBG_NAME) VALUES (%s,%s) ON CONFLICT (ID) DO UPDATE SET PUBG_NAME=%s"""
                    discordInsertValues = (ctx.author.id, pubgname, pubgname)
                    await default.connectDB(discordInsertQuery, discordInsertValues)

                    statsInsertQuery = """INSERT INTO stats (NAME, KILLS, DEATHS, DAMAGE_DEALT, SNIPAS_KILLED, DISTANCE_TRAVELLED, SUICIDES, SCORE, RANKING, BOUNTY) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (NAME) DO NOTHING"""
                    statsInsertValues = (pubgname, 0, 0, 0, 0, [0, 0, 0, 0, 0], 0, 0, 0, 0)
                    await default.connectDB(statsInsertQuery, statsInsertValues)

                    rankingQuery = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
                    await default.connectDB(rankingQuery)

                    if discordSelect:
                        await default.embedMessage(
                            client=self.client, ctx=ctx, description=f"PUBG name {discordSelect[0]} replaced with {pubgname}"
                        )
                    else:
                        await default.embedMessage(
                            client=self.client, ctx=ctx, description=f"PUBG name {pubgname} added to the snipa list"
                        )
                else:
                    await default.embedMessage(
                        client=self.client,
                        ctx=ctx,
                        description="Name already taken! If it's yours ask the mods to remove it from the person who took it",
                    )
            else:
                await default.embedMessage(
                    client=self.client, ctx=ctx, description="You are banned from adding names to snipa list"
                )
        else:
            print("UNKNOWN")

    @commands.hybrid_command(aliases=["p"], description="Shows your or someones else profile")
    async def profile(self, ctx: commands.Context, *, name=None):
        if name is None:
            member = ctx.author
        elif name.startswith("<@"):
            result = re.findall("\d+", name)
            member = self.client.get_user(int(result[0]))
        else:
            member = discord.utils.get(ctx.guild.members, name=name)

        if member:
            discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
            discordInsert = (member.id,)
            discordSelect = await default.connectDB(discordQuery, discordInsert)
            if discordSelect:
                discordQuery = """SELECT id, image, pubg_name, banned_commands from discord_profiles WHERE id = %s"""
                discordInsert = (member.id,)
                discordSelect = await default.connectDB(discordQuery, discordInsert)
            else:
                await default.embedMessage(
                    client=self.client,
                    ctx=ctx,
                    description=f"PUBG name from {member} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list",
                )
                return

            embed = discord.Embed(title="Profile", description="", color=0x000000, timestamp=ctx.message.created_at)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Discord Name", value=member.name, inline=True)
            embed.add_field(name="PUBG Name", value=discordSelect[0][2], inline=True)
            if discordSelect[0][1] is not None:
                embed.set_image(url=discordSelect[0][1])
            embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.client.DEV.display_avatar.url)
            await ctx.send(embed=embed)

        else:
            await default.embedMessage(
                client=self.client, ctx=ctx, description="Name used does not exist"
            )
            return

    @commands.hybrid_command(aliases=["r"], description="Shows your or someones else stats")
    async def report(self, ctx: commands.Context, *, name=None):
        if name is None:
            member = ctx.author
        elif name.startswith("<@"):
            result = re.findall("\d+", name)
            member = self.client.get_user(int(result[0]))
        else:
            member = discord.utils.get(ctx.guild.members, name=name)

        if member is None:  # PUBG name used
            discordQuery = """SELECT pubg_name from discord_profiles WHERE LOWER(pubg_name) LIKE LOWER(%s)"""
            discordInsert = (name,)
            discordSelect = await default.connectDB(discordQuery, discordInsert)
            if discordSelect:
                discordSelect = discordSelect[0][0]
                name = discordSelect
            else:
                discordQuery = """SELECT name from stats WHERE LOWER(name) LIKE LOWER(%s)"""
                discordInsert = (name,)
                discordSelect = await default.connectDB(discordQuery, discordInsert)
                if discordSelect:
                    discordSelect = discordSelect[0][0]
                    name = discordSelect
                else:
                    await default.embedMessage(
                        client=self.client,
                        ctx=ctx,
                        description=f"PUBG name {name} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list",
                    )
                    return

        else:  # The rest
            discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
            discordInsert = (member.id,)
            discordSelect = await default.connectDB(discordQuery, discordInsert)
            if discordSelect:
                discordSelect = discordSelect[0][0]
                name = discordSelect
            else:
                await default.embedMessage(
                    client=self.client,
                    ctx=ctx,
                    description=f"PUBG name from {member} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list",
                )
                return

        playerSelectQuery = """SELECT name, weapon, causer, distance, health, location, date, match_id from kills WHERE LOWER(name) LIKE LOWER(%s)"""
        playerSelectInsert = (name,)
        playerSelect = await default.connectDB(playerSelectQuery, playerSelectInsert)

        statsSelectQuery = """SELECT name, kills, deaths, damage_dealt, snipas_killed, distance_travelled, suicides, score, ranking, bounty from stats WHERE LOWER(name) LIKE LOWER(%s)"""
        statsSelectInsert = (name,)
        statsSelect = await default.connectDB(statsSelectQuery, statsSelectInsert)
        statsSelect = statsSelect[0]

        kd = statsSelect[1] if statsSelect[2] == 0 else statsSelect[1] / statsSelect[2]
        distanceTravelledTotal = (
            statsSelect[5][0] + statsSelect[5][1] + statsSelect[5][2]
        ) / 1000  # Sum all movement stats and convert them to Km

        with open("./assets/dictionaries/simpleCause.json", "r", encoding="utf-8") as f:
            simpleCause = json.loads(f.read())

        for index, playerKills in enumerate(playerSelect):
            replace = list(playerKills)
            replace[2] = simpleCause[replace[2]]
            playerSelect[index] = tuple(replace)

        counter = Counter(playerKills[2] for playerKills in playerSelect)
        print(counter)

        if "Gun" in counter:  # If you have a Gun Kill
            badge = Image.open("./assets/images/badgehaHAA.png")
        elif statsSelect[8] <= 10:  # Else if you are top 10
            if statsSelect[8] == 1:  # If you are top 1
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

        xAxis = 205
        yAxis = 273
        color = (255, 255, 255)
        typeKill_Order = [
            "Punch",
            "Vehicle",
            "Grenade",
            "Panzerfaust",
            "C4",
            "Glider",
            "Melee Weapon",
            "Melee Throw",
            "Molotov",
            "Crossbow",
            "Mortar",
            "Gun",
        ]

        for index, kill in enumerate(typeKill_Order):
            if index == 11:
                color = (255, 0, 0)

            elif index == 6:
                xAxis = 558
                yAxis = 273

            reportCard.text(
                (xAxis, yAxis),
                f"x {counter.get(kill, 0)}",
                color,
                font=counter_font,
            )

            yAxis = yAxis + 208

        reportCard.text((852, 262), "Killed Forsen", (255, 255, 255), font=counter_font)
        reportCard.text((852, 378), "Died to Forsen", (255, 255, 255), font=counter_font)
        reportCard.text((852, 491), "K/D", (255, 255, 255), font=counter_font)
        reportCard.text((852, 605), "Damage Dealt", (255, 255, 255), font=counter_font)
        reportCard.text((852, 721), "Snipas Killed", (255, 255, 255), font=counter_font)
        reportCard.text((852, 842), "Distance Travelled", (255, 255, 255), font=counter_font)
        reportCard.text((852, 958), "Suicides", (255, 255, 255), font=counter_font)

        reportCard.text((1322, 262), f"{statsSelect[1]}", (255, 255, 255), font=counter_font)
        reportCard.text((1322, 378), f"{statsSelect[2]}", (255, 255, 255), font=counter_font)
        reportCard.text((1322, 491), f"{round(kd, 3)}", (255, 255, 255), font=counter_font)
        reportCard.text(
            (1322, 605),
            f"{round(statsSelect[3], 2)}",
            (255, 255, 255),
            font=counter_font,
        )
        reportCard.text((1322, 721), f"{statsSelect[4]}", (255, 255, 255), font=counter_font)
        reportCard.text(
            (1322, 842),
            f"{round(distanceTravelledTotal, 2)} km",
            (255, 255, 255),
            font=counter_font,
        )
        reportCard.text((1322, 958), f"{statsSelect[6]}", (255, 255, 255), font=counter_font)

        reportCard.text((852, 1123), "Score", (255, 255, 255), font=counter_font)
        reportCard.text((852, 1239), "Ranking", (255, 255, 255), font=counter_font)
        reportCard.text((852, 1355), "Bounty", (255, 255, 255), font=counter_font)

        reportCard.text((1152, 1123), f"{statsSelect[7]}", (255, 255, 255), font=counter_font)
        reportCard.text((1152, 1239), f"#{statsSelect[8]}", (255, 255, 255), font=counter_font)
        reportCard.text(
            (1152, 1355),
            f"{statsSelect[9]} pts",
            (255, 255, 255),
            font=counter_font,
        )

        basicReport.paste(badge, (1563, 1113), badge)
        basicReport.save("./assets/images/reportResult.png")

        await ctx.send(file=discord.File("./assets/images/reportResult.png"))

    @commands.hybrid_command(aliases=["lb"], description="Shows the Leaderboard")
    async def leaderboard(self, ctx: commands.Context, *, value=None):
        if value is None:  # No name used
            page = 0
            offset = 0
        elif value.isdigit():  # Number used
            if int(value) > 999:
                await default.embedMessage(client=self.client, ctx=ctx, description="Please type numbers less than 1000")
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
                discordSelect = await default.connectDB(discordQuery, discordInsert)
                if discordSelect:
                    discordSelect = discordSelect[0][0]
                    value = discordSelect
                else:
                    await default.embedMessage(
                        client=self.client,
                        ctx=ctx,
                        description=f"PUBG name {firstName} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list",
                    )
                    return

            else:  # Discord, no name or Mention used
                discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
                discordInsert = (member.id,)
                discordSelect = await default.connectDB(discordQuery, discordInsert)
                if discordSelect:
                    discordSelect = discordSelect[0][0]
                    value = discordSelect
                else:
                    await default.embedMessage(
                        client=self.client,
                        ctx=ctx,
                        description=f"PUBG name from {firstName} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list",
                    )
                    return

            statsSelectQuery = """SELECT name, ROW_NUMBER() OVER (ORDER BY ranking ASC, name) AS rows from stats"""
            statsSelect = await default.connectDB(statsSelectQuery)
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
        statsSelect = await default.connectDB(statsSelectQuery, statsSelectInsert)

        xArray = [87, 221, 874, 1224, 1574]
        yArray = [326, 442, 558, 674, 790, 906, 1022, 1136, 1254, 1370]

        basicReport = Image.open("./assets/images/leaderboard.png")
        counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
        reportCard = ImageDraw.Draw(basicReport)
        reportCard.text((1751, 57), f"Page {page + 1}", (255, 255, 255), font=counter_font)

        for index, user in enumerate(statsSelect):
            if value is not None and not value.isdigit():
                color = (255, 255, 0) if user[1].lower() == value.lower() else (255, 255, 255)
            else:
                color = (255, 255, 255)

            reportCard.text(
                (xArray[0], yArray[index]),
                f"#{user[0]}",
                color,
                font=counter_font,
                align="center",
            )
            reportCard.text((xArray[1], yArray[index]), f"{user[1]}", color, font=counter_font)
            reportCard.text(
                (xArray[2], yArray[index]),
                f"{user[2]} pts",
                color,
                font=counter_font,
            )
            reportCard.text((xArray[3], yArray[index]), f"{user[3]}", color, font=counter_font)
            reportCard.text((xArray[4], yArray[index]), f"{user[4]}", color, font=counter_font)

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

    @commands.hybrid_command(aliases=["cb"], description="Shows the Customboard")
    @app_commands.choices(choice=customboardChoices)
    async def customboard(self, ctx: commands.Context, choice, *, value=None):
        if choice is not None:
            choice = choice.lower()

        if choice in self.customboardArray:
            if value is None:  # No name used
                page = 1
                offset = 0
            elif value.isdigit():  # Number used
                if int(value) > 999:
                    await default.embedMessage(client=self.client, ctx=ctx, description="Please type numbers less than 1000")
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
                    discordSelect = await default.connectDB(discordQuery, discordInsert)
                    if discordSelect:
                        discordSelect = discordSelect[0][0]
                        value = discordSelect
                    else:
                        await default.embedMessage(
                            client=self.client,
                            ctx=ctx,
                            description=f"PUBG name {firstName} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list",
                        )
                        return

                else:  # Discord, no name or Mention used
                    discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
                    discordInsert = (member.name,)
                    discordSelect = await default.connectDB(discordQuery, discordInsert)
                    if discordSelect:
                        discordSelect = discordSelect[0][0]
                        value = discordSelect
                    else:
                        await default.embedMessage(
                            client=self.client,
                            ctx=ctx,
                            description=f"PUBG name from {firstName} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list",
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
                        ).format(sql.Identifier(self.customboardArray[choice]))
                default.CURSOR.execute(rankingQuery)
                rankingRows = default.CURSOR.fetchall()

                for stats in rankingRows:
                    if stats[0] == value:
                        row = stats[1]
                        break

                page = math.ceil((row) / 20)
                offset = (page - 1) * 20

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
                        sql.Identifier(self.customboardArray[choice]),
                    )
                case _:
                    statsSelectQuery = sql.SQL(
                        "SELECT name, {}, DENSE_RANK() OVER(ORDER BY {} DESC) rank FROM stats ORDER BY rank, name LIMIT 20 OFFSET %s"
                    ).format(
                        sql.Identifier(valueArray[choice]),
                        sql.Identifier(self.customboardArray[choice]),
                    )

            statsSelectInsert = (offset,)
            default.CURSOR.execute(statsSelectQuery, statsSelectInsert)
            statsSelect = default.CURSOR.fetchall()

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
            reportCard.text((1750, 57), f"Page {page}", (255, 255, 255), font=counter_font)
            reportCard.text((xArray[1], 210), "Username", (255, 255, 255), font=counter_font)
            reportCard.text(
                (xArray[2], 210),
                f"{titleArray[choice]}",
                (255, 255, 255),
                font=counter_font,
            )
            reportCard.text((xArray[4], 210), "Username", (255, 255, 255), font=counter_font)
            reportCard.text(
                (xArray[5], 210),
                f"{titleArray[choice]}",
                (255, 255, 255),
                font=counter_font,
            )

            for index, user in enumerate(statsSelect):
                if index == limit:
                    break

                # valueArray = {"kills":user[2],"deaths":user[3],"damage":round(user[4],2),"snipakills":user[5],"suicides":user[6],"bounty":user[7]}
                if value is not None and not value.isdigit():
                    color = (255, 255, 0) if user[0].lower() == value.lower() else (255, 255, 255)
                else:
                    color = (255, 255, 255)

                if counter >= 10:
                    counter = 0
                if otherCounter < 10:
                    reportCard.text(
                        (xArray[0], yArray[counter]),
                        f"#{user[2]}",
                        color,
                        font=counter_font,
                        align="center",
                    )
                    reportCard.text(
                        (xArray[1], yArray[counter]),
                        f"{user[0]}",
                        color,
                        font=counter_font,
                    )
                    reportCard.text(
                        (xArray[2], yArray[counter]),
                        f"{user[1]}",
                        color,
                        font=counter_font,
                    )
                else:
                    reportCard.text(
                        (xArray[3], yArray[counter]),
                        f"#{user[2]}",
                        color,
                        font=counter_font,
                        align="center",
                    )
                    reportCard.text(
                        (xArray[4], yArray[counter]),
                        f"{user[0]}",
                        color,
                        font=counter_font,
                    )
                    reportCard.text(
                        (xArray[5], yArray[counter]),
                        f"{user[1]}",
                        color,
                        font=counter_font,
                    )

                counter += 1
                otherCounter += 1

            basicReport.save("./assets/images/customboardResult.png")

            await ctx.send(file=discord.File("./assets/images/customboardResult.png"))

    @commands.hybrid_command(aliases=["st"], description="Shows the Scoretable")
    async def scoretable(self, ctx: commands.Context, *, value=None):
        with open("./assets/dictionaries/scoreTable.json", "r", encoding="utf-8") as f:
            scoreTable = json.loads(f.read())

        if value is None:
            page = 1
        elif value.isdigit():  # Number used
            if int(value) > 999:
                await default.embedMessage(client=self.client, ctx=ctx, description="Please type numbers less than 1000")
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
                await default.embedMessage(
                    client=self.client, ctx=ctx, description=f"Weapon {value} does not exist in the scoretable"
                )
                return

        limit = page * 20
        counter = 0
        otherCounter = 0

        xArray = [102, 748, 930, 1576]
        yArray = [326, 442, 558, 674, 790, 906, 1022, 1136, 1254, 1370]

        basicReport = Image.open("./assets/images/scoreTable.png")
        counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
        reportCard = ImageDraw.Draw(basicReport)
        reportCard.text((1538, 57), f"Page {page}", (255, 255, 255), font=counter_font)

        for index, score in enumerate(scoreTable):
            if index == limit:
                break

            if index < limit and index >= limit - 20:
                if value is not None and not value.isdigit():
                    color = (255, 255, 0) if score.lower() == value.lower() else (255, 255, 255)
                else:
                    color = (255, 255, 255)

                if counter >= 10:
                    counter = 0
                if otherCounter < 10:
                    reportCard.text(
                        (xArray[0], yArray[counter]),
                        f"{score}",
                        color,
                        font=counter_font,
                    )
                    reportCard.text(
                        (xArray[1], yArray[counter]),
                        f"{scoreTable[score]}",
                        color,
                        font=counter_font,
                    )
                else:
                    reportCard.text(
                        (xArray[2], yArray[counter]),
                        f"{score}",
                        color,
                        font=counter_font,
                    )
                    reportCard.text(
                        (xArray[3], yArray[counter]),
                        f"{scoreTable[score]}",
                        color,
                        font=counter_font,
                    )
                counter += 1
                otherCounter += 1

        basicReport.save("./assets/images/scoreTableResult.png")

        await ctx.send(file=discord.File("./assets/images/scoreTableResult.png"))


async def setup(client: default.DiscordBot):
    await client.add_cog(PUBG_Commands(client))
