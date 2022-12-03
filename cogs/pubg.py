import discord
import json
import math
import validators

from PIL import Image, ImageFont, ImageDraw
from collections import Counter
from psycopg import sql

from utils import default, pubgData
from discord.ext import commands
from discord import app_commands


class PUBG_Commands(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.hybrid_command(aliases=["fi"], description="Force inserts an image to someones profile (Admin only)")
    async def forceimage(self, ctx, mention, link):
        if ctx.author.guild_permissions.kick_members or ctx.author.id == 270224083684163584:
            if mention.startswith("<@") is True:
                mention = mention.replace("<@", "")
                mention = mention.replace(">", "")
                member = await ctx.guild.fetch_member(mention)
                if member is not None:
                    if validators.url(link):
                        discordQuery = """INSERT INTO discord_profiles (ID, IMAGE) VALUES (%s,%s) ON CONFLICT (ID) DO UPDATE SET IMAGE=%s"""
                        discordInsert = (member.id, link, link)
                        await default.connectDB(discordQuery, discordInsert)
                        await  default.embedMessage(ctx, description="Image added for {}!".format(mention))
                    else:
                        await  default.embedMessage(ctx, description="No link present")
                else:
                    await  default.embedMessage(ctx, description="Mention member not found")
            else:
                await  default.embedMessage(ctx, description="Invalid Argument, please use mentions")
        else:
            await  default.embedMessage(ctx, description="You don't have permission to use this command")

    @commands.hybrid_command(
        aliases=["fa"], description="Force create/replaces a PUBG and Discord name to someones profile (Admin only)"
    )
    async def forceadd(self, ctx, mention, pubgname=None):
        if ctx.author.guild_permissions.kick_members or ctx.author.id == 270224083684163584:
            if mention.startswith("<@") is True:
                mention = mention.replace("<@", "")
                mention = mention.replace(">", "")
                member = await ctx.guild.fetch_member(mention)
                if member is not None:
                    if pubgname is not None:
                        SNIPA_URL = "https://api.pubg.com/shards/steam/players?filter[playerNames]={}".format(pubgname)

                        player_stat = await default.requestAio(SNIPA_URL, pubgData.PUBG_HEADER)

                        if "errors" in player_stat:
                            await  default.embedMessage(ctx, description="Nickname doesn't exist in PUBG")
                            return
                        elif "data" in player_stat:
                            discordInsertQuery = """INSERT INTO discord_profiles (ID, PUBG_NAME) VALUES (%s,%s) ON CONFLICT (ID) DO UPDATE SET PUBG_NAME=%s"""
                            discordInsertValues = (member.id, pubgname, pubgname)
                            await default.connectDB(discordInsertQuery, discordInsertValues)

                            statsInsertQuery = """INSERT INTO stats (NAME, KILLS, DEATHS, DAMAGE_DEALT, SNIPAS_KILLED, DISTANCE_TRAVELLED, SUICIDES, SCORE, RANKING, BOUNTY) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (NAME) DO NOTHING"""
                            statsInsertValues = (pubgname, 0, 0, 0, 0, [0, 0, 0, 0, 0], 0, 0, 0, 0)
                            await default.connectDB(statsInsertQuery, statsInsertValues)

                            rankingQuery = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
                            await default.connectDB(rankingQuery)

                            await default.embedMessage(
                                self, ctx, description="PUBG name {} added to the snipa list".format(pubgname)
                            )
                        else:
                            print("UNKNOWN")
                            await  default.embedMessage(ctx, description="Uknown error idk kev KUKLE")
                    else:
                        await  default.embedMessage(ctx, description="No PUBG name mentioned")
                else:
                    await  default.embedMessage(ctx, description="Mention member not found")
            else:
                await  default.embedMessage(ctx, description="Invalid Argument, please use mentions")
        else:
            await  default.embedMessage(ctx, description="You don't have permission to use this command")

    @commands.hybrid_command(aliases=["b"], description="Adds or removes bounty to someone (Admin only)")
    @app_commands.choices(
        choice=[app_commands.Choice(name="Add", value="add"), app_commands.Choice(name="Remove", value="remove")]
    )
    async def bounty(self, ctx, choice, value: int, name):
        checkChoices = ctx.command.app_command.parameters[0].choices
        listChoices = []
        for choices in checkChoices:
            listChoices.append(choices.value)

        if ctx.author.guild_permissions.kick_members or ctx.author.id == 270224083684163584:
            if choice in listChoices:
                SNIPA_URL = "https://api.pubg.com/shards/steam/players?filter[playerNames]={}".format(name)

                player_stat = await default.requestAio(SNIPA_URL, pubgData.PUBG_HEADER)

                if "errors" in player_stat:
                    await  default.embedMessage(ctx, description="Nickname {} doesn't exist in PUBG".format(name))
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
                        await  default.embedMessage(ctx, description="Bounty {} added to {}".format(value, name))
                    elif choice == "remove":
                        statsQuery = """SELECT name FROM stats WHERE NAME LIKE %s"""
                        statsInsert = (name,)
                        statsSelect = await default.connectDB(statsQuery, statsInsert)
                        if statsSelect:
                            statsQuery = """UPDATE stats SET bounty = stats.bounty-%s WHERE LOWER(name) LIKE LOWER(%s)"""
                            statsInsert = (value, name)
                            await default.connectDB(statsQuery, statsInsert)
                            await default.embedMessage(
                                self,
                                ctx,
                                "Bounty {} deducted from {}".format(value, name),
                            )
                        else:
                            await  default.embedMessage(ctx, description="Name not in database")
                            return
            else:
                await  default.embedMessage(ctx, description="Invalid command")
        else:
            await  default.embedMessage(ctx, description="You do not have permission to use this command")

    @commands.hybrid_command(description="Deletes image from someones profile (Admin only)")
    @app_commands.choices(
        choice=[app_commands.Choice(name="Image", value="image"), app_commands.Choice(name="PUBG Name", value="name")]
    )
    async def delete(self, ctx, choice, name=None):
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
                        discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)
                        if discordSelect:
                            if choice == "image":
                                discordSelectQuery = """UPDATE discord_profiles SET image = NULL WHERE id = %s"""
                                discordSelectInsert = (member.id,)
                                await default.connectDB(discordSelectQuery, discordSelectInsert)
                                await default.embedMessage(
                                    self, ctx, description="Image deleted from user {}".format(member)
                                )
                            else:
                                discordSelectQuery = """UPDATE discord_profiles SET pubg_name = NULL WHERE id = %s"""
                                discordSelectInsert = (member.id,)
                                await default.connectDB(discordSelectQuery, discordSelectInsert)
                                await default.embedMessage(
                                    self,
                                    ctx,
                                    "PUBG name deleted from user {}".format(member),
                                )
                        else:
                            await  default.embedMessage(ctx, description="User not found")
                    else:
                        await  default.embedMessage(ctx, description="Mention member not found")
                else:
                    await  default.embedMessage(ctx, description="Invalid Argument, please use mentions")
            else:
                await  default.embedMessage(ctx, description="Invalid command")
        else:
            await  default.embedMessage(ctx, description="You do not have permission to use this command")

    @commands.hybrid_command(aliases=["i"], description="Adds your PUBG character to your profile")
    async def image(self, ctx, link):
        if validators.url(link):
            discordSelectQuery = """SELECT pubg_name, image, banned_commands from discord_profiles WHERE id = %s"""
            discordSelectInsert = (ctx.author.id,)
            discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)
            discordSelect = discordSelect[0]
            if discordSelect[2][0] is False:
                discordQuery = """ INSERT INTO discord_profiles (ID, IMAGE, PUBG_NAME) VALUES (%s,%s,%s) ON CONFLICT (ID) DO UPDATE SET IMAGE=%s"""
                discordInsert = (ctx.author.id, link, "", link)
                await default.connectDB(discordQuery, discordInsert)
                if discordSelect[1] is None:
                    await  default.embedMessage(ctx, description="Image added!")
                else:
                    await  default.embedMessage(ctx, description="Image replaced!")
            else:
                await  default.embedMessage(ctx, description="You are banned from adding images")
        else:
            await  default.embedMessage(ctx, description="No link present")

    @commands.hybrid_command(
        aliases=["a"], description="Adds your name to the snipa list and add/replace PUBG name in profile"
    )
    async def add(self, ctx, pubgname):
        SNIPA_URL = "https://api.pubg.com/shards/steam/players?filter[playerNames]={}".format(pubgname)

        player_stat = await default.requestAio(SNIPA_URL, pubgData.PUBG_HEADER)

        if "errors" in player_stat:
            await  default.embedMessage(ctx, description="Nickname doesn't exist in PUBG")
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
                if not (discordCheck):
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
                            self,
                            ctx,
                            "PUBG name {} replaced with {}".format(discordSelect[0], pubgname),
                        )
                    else:
                        await default.embedMessage(
                            self, ctx, description="PUBG name {} added to the snipa list".format(pubgname)
                        )
                else:
                    await default.embedMessage(
                        self,
                        ctx,
                        "Name already taken! If it's yours ask the mods to remove it from the person who took it",
                    )
            else:
                await  default.embedMessage(ctx, description="You are banned from adding names to snipa list")
        else:
            print("UNKNOWN")

    @commands.hybrid_command(aliases=["p"], description="Shows your or someones else profile")
    async def profile(self, ctx, *, name=None):
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
            discordQuery = """SELECT id, image, pubg_name, banned_commands from discord_profiles WHERE LOWER(pubg_name) LIKE LOWER(%s)"""
            discordInsert = (name,)
            discordSelect = await default.connectDB(discordQuery, discordInsert)
            if discordSelect:
                await ctx.guild.query_members(name)
                member = discord.utils.get(ctx.guild.members, name=name)
                if member is None:
                    urlProfile = ""
                else:
                    urlProfile = member.display_avatar.url
            if not (discordSelect):
                await default.embedMessage(
                    self,
                    ctx,
                    "No profile found for {}. Use {}image or {}add first!".format(firstName, ctx.prefix, ctx.prefix),
                )
                return

        else:
            discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
            discordInsert = (member.id,)
            discordSelect = await default.connectDB(discordQuery, discordInsert)
            if discordSelect:
                urlProfile = member.display_avatar.url
                discordQuery = """SELECT id, image, pubg_name, banned_commands from discord_profiles WHERE id = %s"""
                discordInsert = (member.id,)
                discordSelect = await default.connectDB(discordQuery, discordInsert)
            else:
                await default.embedMessage(
                    self,
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
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=default.DEV.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=["r"], description="Shows your or someones else stats")
    async def report(self, ctx, *, name=None):
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
                        self,
                        ctx,
                        "PUBG name {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                            firstName, ctx.prefix
                        ),
                    )
                    return

        else:  # Discord, no name or Mention used
            discordQuery = """SELECT pubg_name from discord_profiles WHERE id = %s"""
            discordInsert = (member.id,)
            discordSelect = await default.connectDB(discordQuery, discordInsert)
            if discordSelect:
                discordSelect = discordSelect[0][0]
                name = discordSelect
            else:
                await default.embedMessage(
                    self,
                    ctx,
                    "PUBG name from {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                        firstName, ctx.prefix
                    ),
                )
                return

        name = name.lower()

        playerSelectQuery = """SELECT * from kills WHERE LOWER(name) LIKE LOWER(%s)"""
        playerSelectInsert = (name,)
        playerSelect = await default.connectDB(playerSelectQuery, playerSelectInsert)

        statsSelectQuery = """SELECT * from stats WHERE LOWER(name) LIKE LOWER(%s)"""
        statsSelectInsert = (name,)
        statsSelect = await default.connectDB(statsSelectQuery, statsSelectInsert)
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

    @commands.hybrid_command(aliases=["lb"], description="Shows the Leaderboard")
    async def leaderboard(self, ctx, *, value=None):
        if value is None:  # No name used
            page = 0
            offset = 0
        elif value.isdigit():  # Number used
            if int(value) > 999:
                await  default.embedMessage(ctx, description="Please type numbers less than 1000")
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
                        self,
                        ctx,
                        "PUBG name {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                            firstName, ctx.prefix
                        ),
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
                        self,
                        ctx,
                        "PUBG name from {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                            firstName, ctx.prefix
                        ),
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

    @commands.hybrid_command(aliases=["cb"], description="Shows the Customboard")
    @app_commands.choices(choice=customboardChoices)
    async def customboard(self, ctx, choice, *, value=None):
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
        if choice in pubgData.customboardValues.customboardArray:
            if value is None:  # No name used
                page = 1
                offset = 0
            elif value.isdigit():  # Number used
                if int(value) > 999:
                    await  default.embedMessage(ctx, description="Please type numbers less than 1000")
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
                            self,
                            ctx,
                            "PUBG name {} is not on the database use {}add to add your PUBG name to the snipa list".format(
                                firstName, ctx.prefix
                            ),
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
                            self,
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
                        ).format(sql.Identifier(pubgData.customboardValues.customboardArray[choice]))
                default.CURSOR.execute(rankingQuery)
                rankingRows = default.CURSOR.fetchall()

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
                        sql.Identifier(pubgData.customboardValues.customboardArray[choice]),
                    )
                case _:
                    statsSelectQuery = sql.SQL(
                        "SELECT name, {}, DENSE_RANK() OVER(ORDER BY {} DESC) rank FROM stats ORDER BY rank, name LIMIT 20 OFFSET %s"
                    ).format(
                        sql.Identifier(valueArray[choice]),
                        sql.Identifier(pubgData.customboardValues.customboardArray[choice]),
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

    @commands.hybrid_command(aliases=["st"], description="Shows the Scoretable")
    async def scoretable(self, ctx, *, value=None):
        with open("./assets/dictionaries/scoreTable.json", "r") as f:
            scoreTable = json.loads(f.read())

        if value is None:
            page = 1
        elif value.isdigit():  # Number used
            if int(value) > 999:
                await  default.embedMessage(ctx, description="Please type numbers less than 1000")
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
                await  default.embedMessage(ctx, description="Weapon {} does not exist in the scoretable".format(value))
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


async def setup(client):
    await client.add_cog(PUBG_Commands(client))
