import discord

from discord.ext import commands
from discord import app_commands
from utils import default


class Mod_Commands(commands.Cog):
    def __init__(self, client: default.DiscordBot):
        self.client = client

    async def getCommands(self):
        allCommands = [
            app_commands.Choice(name="All Commands", value="all"),
            app_commands.Choice(name="Meme Commands", value="memes"),
        ]

        for command in self.client.commands:
            allCommands.append(app_commands.Choice(name=command.name, value=command.name))

    @commands.hybrid_command(description="Bans someone from using commands (Admin only)")
    # @app_commands.choices(choice=allCommands)
    async def ban(self, ctx: commands.Context, command, mention: discord.Member):
        if await default.check_permissions(self.client, ctx):
            if command is not None:
                command = command.lower()

            if command == "image" or command == "add" or command == "game":
                discordSelectQuery = """SELECT id, banned_commands from discord_profiles WHERE id = %s"""
                discordSelectInsert = (mention.id,)
                discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)
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
                    mention.id,
                    bannedCommands,
                    bannedCommands,
                )
                await default.connectDB(discordSelectQuery, discordSelectInsert)
                await default.embedMessage(
                    client=self.client,
                    ctx=ctx,
                    description=f"User {mention} banned from using command {command}",
                )
            else:
                await default.embedMessage(client=self.client, ctx=ctx, description="Invalid command")

    @commands.hybrid_command(description="Unbans someone from using commands (Admin only)")
    async def unban(self, ctx: commands.Context, command, mention: discord.Member):
        if await default.check_permissions(self.client, ctx):
            if command is not None:
                command = command.lower()

            if command == "image" or command == "add" or command == "game":
                discordSelectQuery = """SELECT id, banned_commands from discord_profiles WHERE id = %s"""
                discordSelectInsert = (mention.id,)
                discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)
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
                    discordSelectInsert = (bannedCommands, mention.id)
                    await default.connectDB(discordSelectQuery, discordSelectInsert)
                    await default.embedMessage(
                        client=self.client,
                        ctx=ctx,
                        description=f"User {mention} unbanned from using command {command}",
                    )
                else:
                    await default.embedMessage(client=self.client, ctx=ctx, description="User not found")
            else:
                await default.embedMessage(client=self.client, ctx=ctx, description="Invalid command")


async def setup(client: default.DiscordBot):
    await client.add_cog(Mod_Commands(client))
