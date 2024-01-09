from discord.ext import commands

async def setup(client):
    allowed_dm_commands = ["help", "emotes", "bingo"]

    @client.check
    async def check_command_ban(ctx: commands.Context):
        if not ctx.guild:
            return True

        query = """SELECT 1 FROM command_bans WHERE command_name=$1 AND user_id=$2 AND guild_id=$3"""
        values = (ctx.command.name, ctx.author.id, ctx.guild.id)
        banned = await client.db.connect_db(query, values)

        if not banned:
            return True

        await client.embed_message(ctx, description="You are banned from using this command")
        return False

    @client.check
    async def block_dm_commands(ctx: commands.Context):
        if ctx.guild or ctx.command.name.lower() in allowed_dm_commands:
            return True

        await ctx.channel.send("Commands are not allowed in DMs.")
        return False

async def check_permissions(ctx: commands.Context):
    #if ctx.author.guild_permissions.kick_members or ctx.author.id == self.DEV.id:
    if ctx.author.id == ctx.bot.DEV.id:
        return True

    await ctx.bot.embed_message(ctx, description="You don't have permission to use this command")
    return False
