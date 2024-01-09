import discord
from discord.ext import commands

import utils.checks as checks
from utils import default


class Mod(commands.Cog):
    def __init__(self, client: default.DiscordBot):
        self.client = client
        self.db = client.db
        self.description = "Moderation commands"

    # Needs to check if command is "admin only" or not | Needs a forward slash choice with all commands possible
    @commands.check(checks.check_permissions)
    @commands.hybrid_command(description="Bans someone from using commands (Admin only)")
    async def ban(self, ctx: commands.Context, command, mention: discord.Member):
        command = next((i for i in self.client.commands if i.name == command.lower() or command.lower() in i.aliases), None)

        if not command:
            await self.client.embed_message(ctx, description="Invalid command")
            return

        if checks.check_permissions in command.checks:
            await self.client.embed_message(ctx, description="I can't ban admin commands")
            return

        query = """SELECT 1 FROM command_bans WHERE command_name=$1 AND user_id=$2 AND guild_id=$3"""
        values = (command.name, mention.id, ctx.guild.id)
        is_banned = await self.db.connect_db(query, values)

        if is_banned:
            await self.client.embed_message(ctx, description=f"{mention} is already banned from using this command")
            return

        query = """INSERT INTO command_bans (command_name, user_id, guild_id) VALUES ($1,$2,$3)"""
        values = (command.name, mention.id, ctx.guild.id)
        await self.db.connect_db(query, values)
        
        await self.client.embed_message(ctx, description=f"User {mention} banned from using command {command}")

    @commands.check(checks.check_permissions)
    @commands.hybrid_command(description="Unbans someone from using commands (Admin only)")
    async def unban(self, ctx: commands.Context, command, mention: discord.Member):
        command = next((i for i in self.client.commands if i.name == command.lower() or command.lower() in i.aliases), None)

        if not command:
            await self.client.embed_message(ctx, description="Invalid command")
            return

        if checks.check_permissions in command.checks:
            await self.client.embed_message(ctx, description="I can't unban admin commands")
            return

        query = """SELECT 1 FROM command_bans WHERE command_name=$1 AND user_id=$2 AND guild_id=$3"""
        values = (command.name, mention.id, ctx.guild.id)
        is_banned = await self.db.connect_db(query, values)

        if not is_banned:
            await self.client.embed_message(ctx, description=f"{mention} is not banned from using this command")
            return

        query = """DELETE FROM command_bans WHERE command_name=$1 AND user_id=$2 AND guild_id=$3"""
        values = (command.name, mention.id, ctx.guild.id)
        await self.db.connect_db(query, values)

        await self.client.embed_message(ctx, description=f"User {mention} unbanned from using command {command}")


async def setup(client: default.DiscordBot):
    await client.add_cog(Mod(client))
