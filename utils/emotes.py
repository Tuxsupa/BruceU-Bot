import discord
from discord.ext import commands
from utils import default


def get_allowed_guilds(author: discord.Member, client):
    allowed_guilds = author.mutual_guilds
    extra_guild_ids = [1042188276003504258, 1042244494814347367, 1138970372553834519]
    extra_guilds = [client.get_guild(guild_id) for guild_id in extra_guild_ids]

    for guild in extra_guilds:
        if guild not in allowed_guilds:
            allowed_guilds.append(guild)

    return allowed_guilds


class Emotes():
    MAX_LENGTH = 6
    
    def __init__(self):
        self.guild = None
        self.index = 0

    async def get_embed(self, ctx: commands.Context = None):
        if not self.guild:
            if ctx.guild:
                self.guild = ctx.guild
            else:
                allowed_guilds = get_allowed_guilds(ctx.author, ctx.bot)
                self.guild = allowed_guilds[0]

        embed = discord.Embed(title=self.guild.name, description="", color=0x000000)
        emotes = self.guild.emojis

        emote_string = "".join(
            f"{str(emote)} `:{emote.name}:`\n" for emote in emotes
        )

        if not emotes:
            embed.description = "No emotes"
        else:
            emote_field_array = []
            while emote_string != "":
                emote_field = emote_string[:1000]
                emote_field = emote_field.rsplit("\n", 1)[0]
                emote_field_array.append(emote_field)

                emote_string = emote_string.replace(f"{emote_field}\n", "")

            self.length = len(emote_field_array)

            for emote_field in emote_field_array[self.index : self.index + self.MAX_LENGTH]:
                embed.add_field(name="\u200b", value=emote_field)

        return embed


class Button(discord.ui.Button):
    def __init__(self, ctx: commands.Context, util: Emotes, emoji=None):
        self.ctx = ctx
        self.client: default.DiscordBot = ctx.bot
        self.util = util

        super().__init__(emoji=emoji, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        if self.emoji.name == "▶️":
            if self.util.index + self.util.MAX_LENGTH < self.util.length:
                self.util.index += self.util.MAX_LENGTH
            else:
                self.util.index = self.util.length - self.util.MAX_LENGTH

        elif self.emoji.name == "◀️":
            if self.util.index - self.util.MAX_LENGTH >= 0:
                self.util.index -= self.util.MAX_LENGTH
            else:
                self.util.index = 0

        embed = await self.util.get_embed(self.ctx)
        await interaction.response.edit_message(embed=embed)


class Select(discord.ui.Select):
    def __init__(self, ctx: commands.Context, util: Emotes):
        self.ctx = ctx
        self.util = util

        allowed_guilds = get_allowed_guilds(ctx.author, ctx.bot)

        options=[
            discord.SelectOption(label=guild.name, value=guild.id, default=guild == ctx.guild)
            for guild in allowed_guilds
        ]

        super().__init__(max_values=1, min_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        guild_id = int(self.values[0])
        guild = interaction.client.get_guild(guild_id)

        if not guild:
            return

        for option in self.options:
            option.default = int(option.value) == guild_id

        self.util.guild = guild
        self.util.index = 0
        embed = await self.util.get_embed(self.ctx)  

        await interaction.response.edit_message(embed=embed, view=self.view)

class EmotesView(discord.ui.View):
    def __init__(self, ctx: commands.Context, util: Emotes):
        super().__init__()
        self.add_item(Select(ctx, util))
        
        self.add_item(Button(ctx, util, emoji="◀️"))
        self.add_item(Button(ctx, util, emoji="▶️"))
