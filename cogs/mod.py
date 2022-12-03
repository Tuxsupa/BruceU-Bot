from utils import default
from discord.ext import commands
from discord import app_commands


class Mod_Commands(commands.Cog):
    def __init__(self, client):
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
    async def ban(self, ctx, command, mention):
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
                            member.id,
                            bannedCommands,
                            bannedCommands,
                        )
                        await default.connectDB(discordSelectQuery, discordSelectInsert)
                        await default.embedMessage(
                            self,
                            ctx,
                            f"User {member} banned from using command {command}",
                        )
                    else:
                        await  default.embedMessage(ctx, description="Mention member not found")
                else:
                    await  default.embedMessage(ctx, description="Invalid Argument, please use mentions")
            else:
                await  default.embedMessage(ctx, description="Invalid command")
        else:
            await  default.embedMessage(ctx, description="You do not have permission to use this command")

    @commands.hybrid_command(description="Unbans someone from using commands (Admin only)")
    async def unban(self, ctx, command, mention):
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
                            discordSelectInsert = (bannedCommands, member.id)
                            await default.connectDB(discordSelectQuery, discordSelectInsert)
                            await default.embedMessage(
                                self,
                                ctx,
                                f"User {member} unbanned from using command {command}",
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


async def setup(client):
    await client.add_cog(Mod_Commands(client))
