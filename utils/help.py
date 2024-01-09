import datetime
from typing import List

import discord
from discord.ext import commands
from utils import default, checks


class HelpEmbed(discord.Embed):  # Our embed with some preset attributes to avoid setting it multiple times
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.timestamp = datetime.datetime.now(datetime.timezone.utc)
        text = "Use help [command] or help [category] for more information | <> is required | [] is optional"
        self.set_footer(text=text)
        self.color = 0x000000


class Help():
    def __init__(self, client: default.DiscordBot):
        self.client = client

    def has_normal_admin_cmd(self, commands: List[commands.HybridCommand]):
        has_normal = any(not command.checks for command in commands)
        has_admin = any(checks.check_permissions in command.checks for command in commands)
        
        return has_normal, has_admin
    
    async def get_bot_help(self, ctx: commands.Context):
        embed = HelpEmbed(title=f"{ctx.me.display_name} Help")
        embed.set_thumbnail(url=ctx.me.display_avatar)

        for cog in self.client.cogs.values():
            commands = cog.get_commands()

            name = cog.qualified_name
            description = cog.description or "No description"

            embed.add_field(name=f"{name} [{len(commands)}]", value=description)

        return embed

    async def get_command_help(self, ctx: commands.Context, command: commands.HybridCommand):
        signature = command.signature
        embed = HelpEmbed(title=f"{ctx.clean_prefix}{command.qualified_name} {signature}", description=command.description or "No description found...")

        if cog := command.cog:
            embed.add_field(name="Category", value=cog.qualified_name)

        if aliases := command.aliases:
            embed.add_field(name="Aliases", value=', '.join(aliases))

        return embed

    async def get_cog_help(self, ctx: commands.Context, cog: commands.Cog, is_admin=False):
        embed = HelpEmbed(title=f"{cog.qualified_name} Category", description=cog.description or "No description found...")

        if commands := cog.get_commands():
            has_normal, has_admin = self.has_normal_admin_cmd(commands)

            for command in commands:
                if has_normal and has_admin and (not is_admin and checks.check_permissions in command.checks
                    or is_admin and not command.checks):
                    continue

                title = f"{ctx.clean_prefix}[{command.qualified_name}|{'|'.join(command.aliases)}]" if command.aliases else command.qualified_name
                title += f" {command.signature}" if command.signature else ""
                title = title.replace('"', "")
                embed.add_field(name=title, value=command.description)

        return embed

    async def main(self, ctx: commands.Context, option:str = None):
        if not option:
            embed = await self.get_bot_help(ctx)
            await ctx.send(embed=embed)
            return

        option = option.lower()

        if command := self.client.all_commands.get(option):
            embed = await self.get_command_help(ctx, command)
            await ctx.send(embed=embed)
            return

        for index, (cog_name, cog) in enumerate(self.client.cogs.items()):
            if cog_name.lower() == option:
                embed = await self.get_cog_help(ctx, cog)
                await ctx.send(embed=embed, view=ButtonView(ctx, self.client, cog, self, index))
                return


class Button(discord.ui.Button):
    def __init__(self, ctx: commands.Context, client: default.DiscordBot, cog: commands.Cog, util: Help, index=None, label=None, emoji=None):
        self.ctx = ctx
        self.client = client
        self.cog = cog
        self.util = util
        self.index = index

        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        if self.label == "Admin Commands":
            embed = await self.util.get_cog_help(self.ctx, self.cog, is_admin=True)
            self.label = "Normal Commands"
            view = self.view

        elif self.label == "Normal Commands":
            embed = await self.util.get_cog_help(self.ctx, self.cog)
            self.label = "Admin Commands"
            view = self.view

        elif self.emoji.name == "▶️":
            cogs = list(self.client.cogs.values())
            self.index = (self.index + 1) % len(cogs)
            cog = cogs[self.index]
            
            embed = await self.util.get_cog_help(self.ctx, cog)
            view = ButtonView(self.ctx, self.client, cogs[self.index], self.util, self.index)

        elif self.emoji.name == "◀️":
            cogs = list(self.client.cogs.values())
            self.index = (self.index - 1) % len(cogs)
            cog = cogs[self.index]
            
            embed = await self.util.get_cog_help(self.ctx, cog)
            view = ButtonView(self.ctx, self.client, cogs[self.index], self.util, self.index)

        await interaction.response.edit_message(embed=embed, view=view)


class ButtonView(discord.ui.View):
    def __init__(self, ctx: commands.Context, client: default.DiscordBot, cog: commands.Cog, util: Help, index: int):
        super().__init__()
        
        if commands := cog.get_commands():
            has_normal, has_admin = util.has_normal_admin_cmd(commands)
            if has_normal and has_admin:
                self.add_item(Button(ctx, client, cog, util, label="Admin Commands"))

        self.add_item(Button(ctx, client, cog, util, index, emoji="◀️"))
        self.add_item(Button(ctx, client, cog, util, index, emoji="▶️"))
