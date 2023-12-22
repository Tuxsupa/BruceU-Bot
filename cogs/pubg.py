import typing
import validators

import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice

import utils.checks as checks
from utils import default, pubg

class Pubg(commands.Cog):
    def __init__(self, client: default.DiscordBot):
        self.client = client
        self.db = client.db
        self.description = "PUBG commands"

        self.pubg = client.pubg

    async def check_link(self, ctx: commands.Context, link: str):
        if validators.url(link):
            return True
        await self.client.embed_message(ctx, description="No link present")
        return False

    async def check_discord_name(self, ctx: commands.Context, name):
        return await pubg.get_member(ctx, name) if name else ctx.author

    @commands.check(checks.check_permissions)
    @commands.hybrid_command(aliases=["fi"], description="Force inserts an image to someone's profile (Admin only)")
    async def forceimage(self, ctx: commands.Context, mention: discord.Member, link: str):
        if not await self.check_link(ctx, link):
            return

        query = """INSERT INTO discord_profiles (id, image) VALUES ($1,$2) ON CONFLICT (id) DO UPDATE SET image=$3"""
        values = (mention.id, link, link)
        await self.db.connect_db(query, values)

        await self.client.embed_message(ctx, description=f"Image added for {mention}!")

    @commands.hybrid_command(aliases=["i"], description="Adds your PUBG character to your profile")
    async def image(self, ctx: commands.Context, link: str):        
        if not await self.check_link(ctx, link):
            return
        
        query = """SELECT image FROM discord_profiles WHERE id = $1"""
        values = (ctx.author.id,)
        discord_user = await self.db.connect_db(query, values)

        query = """INSERT INTO discord_profiles (id, image) VALUES ($1,$2) ON CONFLICT (id) DO UPDATE SET image=$3"""
        values = (ctx.author.id, link, link)
        await self.db.connect_db(query, values)
        
        if not discord_user:
            await self.client.embed_message(ctx, description="Image added!")
            return 
        
        await self.client.embed_message(ctx, description="Image replaced!")

    @commands.check(checks.check_permissions)
    @commands.hybrid_command(
        aliases=["fa"], description="Force create/replaces a PUBG and Discord name to someones profile (Admin only)")
    async def forceadd(self, ctx: commands.Context, mention: discord.Member, pubg_name: str):
        query = """SELECT pubg_name FROM discord_profiles WHERE id = $1"""
        values = (ctx.author.id,)
        current_pubg_name = await self.db.connect_db(query, values)

        if current_pubg_name == pubg_name:
            await self.client.embed_message(ctx, description=f"This name is already {mention}'s PUBG name")
            return

        SNIPA_URL = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={pubg_name}"
        player_stat = await self.client.request_aio(SNIPA_URL, self.pubg.HEADER)

        if not player_stat or "errors" in player_stat:
            await self.client.embed_message(ctx, description="Nickname doesn't exist in PUBG")
            return

        query = """INSERT INTO discord_profiles (id, pubg_name) VALUES ($1,$2) ON CONFLICT (id) DO UPDATE SET pubg_name=$3"""
        values = (mention.id, pubg_name, pubg_name)
        await self.db.connect_db(query, values)

        query = """INSERT INTO stats (name, account_id) VALUES ($1,$2) ON CONFLICT (account_id) DO NOTHING"""
        values = (pubg_name, player_stat["data"][0]["id"])
        await self.db.connect_db(query, values)

        query = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
        await self.db.connect_db(query)

        if current_pubg_name:
            await self.client.embed_message(ctx, description=f"PUBG name {current_pubg_name} replaced with {pubg_name}")
            return

        await self.client.embed_message(ctx, description=f"PUBG name {pubg_name} added to the snipa list")

    @commands.hybrid_command(
        aliases=["a"], description="Adds your name to the snipa list or add/replace PUBG name in profile")
    async def add(self, ctx: commands.Context, pubg_name: str):
        query = """SELECT pubg_name FROM discord_profiles WHERE id = $1"""
        values = (ctx.author.id,)
        current_pubg_name = await self.db.connect_db(query, values)
        
        if current_pubg_name == pubg_name:
            await self.client.embed_message(ctx, description="This name is already your PUBG name")
            return
        
        query = """SELECT 1 FROM discord_profiles WHERE LOWER(pubg_name) LIKE LOWER($1)"""
        values = (pubg_name,)
        name_taken = await self.db.connect_db(query, values)

        if name_taken:
            await self.client.embed_message(ctx, description="Name already taken! If it's yours ask the mods to remove it from the person who took it")
            return

        SNIPA_URL = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={pubg_name}"
        player_stat = await self.client.request_aio(SNIPA_URL, self.pubg.HEADER)

        if not player_stat or "errors" in player_stat:
            await self.client.embed_message(ctx, description="Nickname doesn't exist in PUBG. (Case Sensitive)")
            return

        query = """INSERT INTO discord_profiles (id, pubg_name) VALUES ($1,$2) ON CONFLICT (id) DO UPDATE SET pubg_name=$3"""
        values = (ctx.author.id, pubg_name, pubg_name)
        await self.db.connect_db(query, values)

        query = """INSERT INTO stats (name, account_id) VALUES ($1,$2) ON CONFLICT (account_id) DO NOTHING"""
        values = (pubg_name, player_stat["data"][0]["id"])
        await self.db.connect_db(query, values)

        query = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
        await self.db.connect_db(query)

        if current_pubg_name:
            await self.client.embed_message(ctx, description=f"PUBG name {current_pubg_name} replaced with {pubg_name}")
            return

        await self.client.embed_message(ctx, description=f"PUBG name {pubg_name} added to the snipa list")

    @commands.check(checks.check_permissions)
    @commands.hybrid_command(aliases=["b"], description="Adds or removes bounty to someone (Admin only)")
    @app_commands.choices(choice=[
        Choice(name="Add", value="add"), Choice(name="Remove", value="remove")
    ])
    async def bounty(self, ctx: commands.Context, choice: str, bounty: int, pubg_name: str):        
        all_choices = ctx.command.app_command.parameters[0].choices
        all_choices = [choices.value for choices in all_choices]
        
        if choice.lower() not in all_choices:
            await self.client.embed_message(ctx, description="Invalid choice, check help command or use forward slash instead")
            return

        SNIPA_URL = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={pubg_name}"
        player_stat = await self.client.request_aio(SNIPA_URL, self.pubg.HEADER)

        if not player_stat or "errors" in player_stat:
            await self.client.embed_message(ctx, description="Nickname doesn't exist in PUBG")
            return
        
        if choice.lower() == "add":
            query = """INSERT INTO stats (name, bounty, account_id) VALUES ($1,$2,$3) ON CONFLICT (account_id) DO UPDATE SET bounty=stats.bounty+$4"""
            values = (pubg_name, bounty, player_stat["data"][0]["id"], bounty)
            await self.db.connect_db(query, values)

            query = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
            await self.db.connect_db(query)

            await self.client.embed_message(ctx, description=f"Bounty {bounty} added to {pubg_name}")
            return
        
        # Else
        query = """SELECT 1 FROM stats WHERE name LIKE $1"""
        values = (pubg_name,)
        name_exists = await self.db.connect_db(query, values)
        if not name_exists:
            await self.client.embed_message(ctx, description="PUBG name not in database")
            return

        query = """UPDATE stats SET bounty = stats.bounty-$1 WHERE LOWER(name) LIKE LOWER($2)"""
        values = (bounty, pubg_name)
        await self.db.connect_db(query, values)
        await self.client.embed_message(ctx, description=f"Bounty {bounty} deducted from {pubg_name}")

    @commands.check(checks.check_permissions)
    @commands.hybrid_command(description="Deletes image/PUBG name from someone's profile (Admin only)")
    @app_commands.choices(choice=[
        Choice(name="Image", value="image"), Choice(name="PUBG Name", value="name")
    ])
    async def delete(self, ctx: commands.Context, choice, mention: discord.Member):        
        all_choices = ctx.command.app_command.parameters[0].choices
        all_choices = [choices.value for choices in all_choices]
        
        if choice.lower() not in all_choices:
            await self.client.embed_message(ctx, description="Invalid choice, check help command or use forward slash instead")
            return
        
        query = """SELECT 1 FROM discord_profiles WHERE id = $1"""
        values = (mention.id,)
        has_profile = await self.db.connect_db(query, values)
        if not has_profile:
            await self.client.embed_message(ctx, description="User not found in database")
            return
        
        if choice.lower() == "image":
            query = """UPDATE discord_profiles SET image = NULL WHERE id = $1"""
            values = (mention.id,)
            await self.db.connect_db(query, values)
            await self.client.embed_message(ctx, description=f"Image deleted from user {mention}")
            return
        
        # Else
        query = """UPDATE discord_profiles SET pubg_name = NULL WHERE id = $1"""
        values = (mention.id,)
        await self.db.connect_db(query, values)
        await self.client.embed_message(ctx, description=f"PUBG name deleted from user {mention}")

    @commands.hybrid_command(aliases=["p"], description="Shows yours or someones else profile")
    async def profile(self, ctx: commands.Context, *, name=None):
        member_name = None
        member_avatar = None

        member = await self.check_discord_name(ctx, name)

        # Find member
        if not member: # Might be PUBG name
            query = """SELECT id FROM discord_profiles WHERE LOWER(pubg_name) LIKE LOWER($1)"""
            values = (name,)
            member_id = await self.db.connect_db(query, values)
            
            if not member_id:
                await self.client.embed_message(ctx, description="Name used does not exist in the database, if it's yours use $add or $image")
                return
            
            member = name
        else:
            member_id = member.id
            member_name = member.name
            member_avatar = member.display_avatar.url

        # Check if profile exists
        query = """SELECT 1 FROM discord_profiles WHERE id = $1"""
        values = (member_id,)
        has_name = await self.db.connect_db(query, values)
        if not has_name:
            await self.client.embed_message(ctx, description=f"PUBG name from {member} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list")
            return

        # Send embed with data found
        query = """SELECT image, pubg_name FROM discord_profiles WHERE id = $1"""
        values = (member_id,)
        image, pubg_name = await self.db.connect_db(query, values)

        embed = discord.Embed(title="Profile", description="", color=0x000000, timestamp=ctx.message.created_at)
        embed.set_thumbnail(url=member_avatar)
        embed.add_field(name="Discord Name", value=member_name, inline=True)
        embed.add_field(name="PUBG Name", value=pubg_name, inline=True)
        if image:
            embed.set_image(url=image)
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.client.DEV.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=["r"], description="Shows your or someones else stats")
    async def report(self, ctx: commands.Context, *, name=None):
        util = pubg.Report(self.client)

        member = await self.check_discord_name(ctx, name)
        report = await util.generate_report(ctx, name, member)
        
        report_path = "./assets/images/reportResult.png"
        report.save(report_path)
        await ctx.send(file=discord.File(report_path))

    @commands.hybrid_command(aliases=["lb"], description="Shows the Leaderboard")
    async def leaderboard(self, ctx: commands.Context, *, value=None):
        util = pubg.Leaderboard(self.client)
        await util.generate_leaderboard(ctx, value)

    @commands.hybrid_command(aliases=["cb"], description="Shows the Customboard")
    async def customboard(self, ctx: commands.Context, choice: typing.Literal[
        "kills", "deaths", "kd", "damage", "snipakills", "distance", "suicides", "matches", "bounty"], *, value=None
    ):            
        util = pubg.Customboard(self.client)
        await util.generate_customboard(ctx, choice, value)

    @commands.hybrid_command(aliases=["st"], description="Shows the Scoretable")
    async def scoretable(self, ctx: commands.Context, *, value=None):
        util = pubg.Scoretable(self.client)
        await util.generate_scoretable(ctx, value)


async def setup(client: default.DiscordBot):
    await client.add_cog(Pubg(client))
