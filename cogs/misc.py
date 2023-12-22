import random
import time

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from utils import default
from utils.emotes import Emotes, EmotesView
from utils.bingo import Bingo
from utils.game import Game
from utils.help import Help

load_dotenv()


class Misc(commands.Cog):
    def __init__(self, client: default.DiscordBot):
        self.client = client
        self.description = "Multiple miscellaneous commands"

    @commands.cooldown(1, 10, commands.BucketType.channel)
    @commands.hybrid_command(aliases=["h"], description="List of commands")
    async def help(self, ctx: commands.Context, option = None):
        await Help(self.client).main(ctx, option)

    @commands.hybrid_command(description="List of emotes the bot has access to")
    async def emotes(self, ctx: commands.Context):
        util = Emotes()     
        embed = await util.get_embed(ctx)

        try:
            await ctx.author.send(embed=embed, view=EmotesView(ctx, util))
            if ctx.guild:
                await ctx.send(content="Check DM's...")
        except discord.Forbidden:
            await ctx.send(content="Couldn't DM you (blocked/DM's closed)")

    @commands.hybrid_command(description="Rolls a chance")
    async def roll(self, ctx: commands.Context, *, message: str):
        roll = random.randint(0, 100)

        await self.client.embed_message(ctx, title="Roll", description=f"{roll}% chance of {message}")

    @commands.hybrid_command(description="Time left until Dark and Darker playtest")
    async def dnd(self, ctx: commands.Context):
        # time_left = 0 # date - datetime.now()

        # if time_left <= 0:
        #     text = "DARK AND DARKER IS OUT <:MUGA:844690515966689291>"
        #     # text = "Now what <:TrollDespair:867414306580856832>"
        # else:
        #     days = time_left.day
        #     hours = time_left.hour
        #     minutes = time_left.minute
        #     seconds = time_left.second
        #     text = f"{days} days {hours} hours {minutes} minutes {seconds} seconds left until Dark and Darker"

        text = "DARK AND DARKER IS OUT <:MUGA:844690515966689291>"
        await self.client.embed_message(ctx, title="Time left until Dark and Darker", description=text)

    # @commands.hybrid_command(description="Pings Foxhole Mugas. (Foxhole Admins only)")
    # @commands.has_role(1117895934773313547) # 1117895934773313547
    # async def foxhole(self, ctx: commands.Context, *, message: str):
    #     FOXHOLE_ROLE = 1117904228418076732
    #     await ctx.send(content=f"<@&{FOXHOLE_ROLE}>\n\n{message}",
    #             allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=[ctx.guild.get_role(FOXHOLE_ROLE)], replied_user=False))

    #     await ctx.message.delete()

    @commands.hybrid_command(description="Reaction bingo card")
    @app_commands.choices(
        choice=[app_commands.Choice(name="Opt-In", value="opt-in"), app_commands.Choice(name="Opt-Out", value="opt-out")]
    )
    async def bingo(self, ctx: commands.Context, choice=""):
        util = Bingo(self.client)
        
        if choice:
            if choice.lower() not in ("opt-in", "opt-out"):
                await self.client.embed_message(ctx, description="Don't use anything after or choose between opt-in or opt-out")
                return
            
            await util.auto_bingo_db(ctx, choice)
            return

        if not self.client.twitch.is_intro:
            await self.client.embed_message(ctx, description="Forsen is not in intro")
            return

        user = ctx.message.mentions[0] if ctx.message.mentions else ctx.author
        file, embed = await util.create_bingo_card(user)
        embed.description = f"You can use {ctx.prefix}bingo opt-in to get automatic bingo cards"
        await ctx.send(file=file, embed=embed)

    @commands.hybrid_command(aliases=["g"], description="Shows info about a game")
    async def game(self, ctx: commands.Context, *, game: str):
        await ctx.defer()

        util = Game(self.client)
        util.TWITCH_TOKEN = await util.get_twitch_token()

        hltb_data = await util.get_HLTB(game)
        game_data = await util.get_igdb_with_hltb(hltb_data) or await util.get_steam_game(game) or await util.get_IGDB(game)

        if not game_data:
            await self.client.embed_message(ctx, description="Game doesn't exist")
            return

        data = game_data[0]
        game = data["name"]
        game_url = data["url"]
        
        util.embed = discord.Embed(title=game, description=None, color=0x000000, url=game_url, timestamp=ctx.message.created_at)

        # Get HLTB data if empty
        if not hltb_data and data.get("first_release_date"):
            release_date = data["first_release_date"]
            year = time.localtime(int(release_date)).tm_year
            hltb_data = await util.get_HLTB(game, year)

        # Set thumbnail
        if cover := data.get("cover"):
            image_url = str(cover["url"])
            util.embed.set_thumbnail(url=f"https:{image_url.replace('t_thumb', 't_cover_big')}")

        game_time = await util.get_game_time(hltb_data)

        if game_data:
            igdb_steam = next((i for i in data.get("external_games", []) if i.get("category") == 1), None)
            original_prices_str = await util.set_steam_data(igdb_steam)

            await util.add_embed_indentation(game_time, igdb_steam)
            await util.get_price_details(original_prices_str)
            await util.get_game_modes_igdb(data)

        util.embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        util.embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.client.DEV.display_avatar.url)
        await ctx.send(embed=util.embed)

async def setup(client: default.DiscordBot):
    await client.add_cog(Misc(client))
