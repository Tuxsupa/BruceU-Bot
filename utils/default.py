import os
import asyncio

import asyncpg
import aiohttp
import discord
import regex as re
from dotenv import load_dotenv

from discord.ext.commands import Bot
from discord.ext import commands, tasks
from utils import checks, emotes
from utils.reposter import Reposter

load_dotenv()


class DiscordBot(Bot):
    def __init__(self, *args, prefix=None, loop: asyncio.AbstractEventLoop = None, isTest: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = prefix
        self.loop = loop
        self.isTest = isTest        

        from utils import twitch_api
        self.twitch: twitch_api.TwitchAPI = None
        
        self.db = Database()
        self.webhook_emotes = WebhookEmotes(self)
        
        from utils import pubg
        self.pubg = pubg.PubgData(self)

    async def setup_hook(self):
        await checks.setup(self)
        
        await self.db.create_db()
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(force_close=True))

        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                name = file[:-3]
                if name not in ('memes'):
                    await self.load_extension(f"cogs.{name}")

        if not self.OER.is_running():
            self.OER.start()

        if not self.isTest and not self.update_pubg_stats.is_running():
            self.update_pubg_stats.start()

        self.DEV = await self.fetch_user(os.environ["OWNER_ID"])

        reposter = Reposter(self)
        self.loop.create_task(reposter.start(os.environ["DISCORD_TOKEN"]))

        if self.isTest is False:
            from utils import twitch_api
            self.twitch = twitch_api.TwitchAPI(client=self, loop=self.loop)
        else:
            from utils import twitch_api_test
            self.twitch = twitch_api_test.TwitchAPI(client=self, loop=self.loop)

        self.loop.create_task(self.twitch.main())

        await self.tree.sync()

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
        REACTION_CHANNEL = 1097639586458505336
        channel = (self.get_channel(REACTION_CHANNEL) or await self.fetch_channel(REACTION_CHANNEL))
        await channel.send(f"reaction: {reaction} | user: {user}")

    async def on_command_error(self, message, error):
        print(error)
        if isinstance(error, (commands.MissingRole, commands.BadArgument, commands.MissingRequiredArgument)):
            await self.embed_message(message, description=error)
        elif isinstance(error, commands.CommandInvokeError):
            error = error.original
            if isinstance(error, discord.errors.Forbidden):
                await self.embed_message(message, description=f"Error {error}")

    async def markov(self, ctx: discord.Message):
        BOT_ID = 988995123851456532
        MARKOV_ID = 1058138354199318610
        MARKOV_BOT_CHANNEL = 1059283666217484338
        MARKOV_CHANNEL = 1066008114324844645

        if not ctx.author.bot and ("markov" in ctx.content.lower() and ctx.author.id != BOT_ID) and ctx.channel.id == MARKOV_CHANNEL:
            channel = (self.get_channel(MARKOV_BOT_CHANNEL) or await self.fetch_channel(MARKOV_BOT_CHANNEL))
            await channel.send(
                content=ctx.content,
                allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)
            )

        if ctx.channel.id == MARKOV_BOT_CHANNEL and ctx.author.id == MARKOV_ID:
            channel = (self.get_channel(MARKOV_CHANNEL) or await self.fetch_channel(MARKOV_CHANNEL))
            await channel.send(
                content=ctx.content,
                allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)
            )

    async def on_message(self, ctx: discord.Message):
        await self.webhook_emotes.start(ctx)
        await self.markov(ctx)
        await self.process_commands(ctx)

    @tasks.loop(hours=12)
    async def OER(self):
        print("OER Update")

        OER_URL = f"https://openexchangerates.org/api/latest.json?app_id={os.environ['OPEN_EXCHANGE_RATES_ID']}"
        self.oer_rates = await self.request_aio(OER_URL)

    @tasks.loop(hours=24)
    async def update_pubg_stats(self):
        player_stat = await self.request_aio(self.pubg.FORSEN_URL, self.pubg.HEADER)

        pubg_match_ids = None
        if player_stat and player_stat.get("data") and player_stat["data"].get("relationships") and player_stat["data"]["relationships"].get("matches"):
            pubg_match_ids = player_stat["data"]["relationships"]["matches"]["data"]

        if not pubg_match_ids:
            return

        query = """SELECT match_id FROM kills"""
        db_match_ids:list = await self.db.connect_db(query)

        print("Starting the PUBG data update")
        for match in pubg_match_ids:
            if match["id"] not in db_match_ids:
                await self.pubg.process_telemetry_data(match["id"])
                db_match_ids.append(match["id"])

        print("Stopping the PUBG data update")

    async def embed_message(self, ctx: commands.Context, title: str = None, description: str = None):
        embed = discord.Embed(title=title, description=description, color=0x000000, timestamp=ctx.message.created_at)
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.DEV.display_avatar.url)
        await ctx.send(embed=embed)

    async def request_aio(self, url: str = "", headers=None, data=None, json=None, method="GET"):
        async with getattr(self.session, method.lower())(url, headers=headers, data=data, json=json) as r:
            if r.status == 200:
                print(f"Successfull {method} request")
                return await r.json()
            else:
                print(f"Failed to {method} request")
                return


class Database():
    def __init__(self):
        self.pool: asyncpg.pool.Pool = None

    async def create_db(self):
        try:
            self.pool = await asyncpg.create_pool(os.environ["CONNECTION_URL"])
            print("Connected to PostgreSQL")

        except Exception as e:
            print(f"Failed to create connection pool to PostgreSQL: {e}")

    async def connect_db(self, query="", values=None):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                try:
                    print(query)
                    if values:
                        print(values)

                    # Fetch Data
                    if query.startswith("SELECT"):
                        # Check if values used in query
                        if values:                   
                            rows = await self.pool.fetch(query, *values)
                        else:
                            rows = await self.pool.fetch(query)

                        # Check if only one row returned
                        if len(rows) == 1:
                            return tuple(rows[0])[0] if len(rows[0]) == 1 else tuple(rows[0])

                        # Check if all rows returned are one value 
                        if all(len(row) == 1 for row in rows):
                            return [tuple(row)[0] for row in rows]

                        # Return normal tuple if none of the above
                        return [tuple(row) for row in rows]

                    # Insert/Update Data | Check if values used in query
                    if values:
                        await self.pool.execute(query, *values)
                    else:
                        await self.pool.execute(query)

                except Exception as error:
                    print("Failed to use database. Error: ", error)


class WebhookEmotes():
    def __init__(self, client: DiscordBot):
        self.client = client

    async def get_webhook(self, ctx: discord.Message):
        user = self.client.user

        if isinstance(ctx.channel, discord.Thread):
            channel = ctx.channel.parent
        else:
            channel = ctx.channel

        try:
            webhooks = await channel.webhooks()
        except discord.Forbidden:
            # await ctx.channel.send(content="Enable ""Manage Webhooks"" permission OR Turn off emote functionality")
            return

        if all(webhook.user.id != user.id for webhook in webhooks):
            print("Created Webhooks")
            await channel.create_webhook(name=f"{user.name}-1")
            await channel.create_webhook(name=f"{user.name}-2")
            webhooks = await channel.webhooks()

        # Randomize between both?
        return next((webhook for webhook in webhooks if webhook.user.id == user.id))

    async def get_embeds(self, ctx: discord.Message):
        embeds = []
        if reference := ctx.reference:
            embed = discord.Embed(description=f"**[Reply to:]({reference.jump_url})** {reference.resolved.content}", color=0x000000)
            embed.set_author(name=reference.resolved.author.display_name, icon_url=reference.resolved.author.display_avatar)
            embeds.append(embed)

        if ctx.attachments:
            for attachment in ctx.attachments:
                embed = discord.Embed(description=f"📂 [{attachment.filename}]({attachment.proxy_url})", color=0x000000)
                embed.set_image(url=attachment.proxy_url)
                embeds.append(embed)
        
        return embeds

    @commands.bot_has_permissions(manage_messages=True, manage_webhooks=True)
    async def start(self, ctx: discord.Message):
        if ctx.author.bot:
            return

        content = ctx.content

        # Find emotes in string
        emotes_array = re.findall("((?:(?!<:|<a:):)(?:(?!\w{1,64}:\d{17,18})\w{1,64})(?:(?!>):))", content)
        clean_emotes = [emote.strip(":") for emote in emotes_array]

        allowed_guilds = emotes.get_allowed_guilds(ctx.author, self.client)
        allowed_emojis = [emoji for guild in allowed_guilds for emoji in guild.emojis]

        # Find if bot has emotes and get them
        discord_emotes = [
            next((emoji for emoji in allowed_emojis if emoji.name == emote), None) or \
            next((emoji for emoji in allowed_emojis if emoji.name.lower() == emote.lower()), None)
            for emote in clean_emotes
        ]

        # Return of none emotes are found
        if not discord_emotes or all(emote is None for emote in discord_emotes):
            return

        # Substitue text of emote with discord emote in the string
        for emote_text, emote in zip(emotes_array, discord_emotes):
            if emote:
                substitute = re.compile(f'(?<!<|<a){emote_text}', re.IGNORECASE)
                content = substitute.sub(str(emote), content, 1)

        bot_webhook = await self.get_webhook(ctx)
        if not bot_webhook:
            return
        
        embeds = await self.get_embeds(ctx)

        webhook_args = {
            "content": str(content),
            "username": ctx.author.display_name,
            "avatar_url": ctx.author.display_avatar.url,
            "allowed_mentions": discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=False),
            "embeds": embeds,
        }

        if isinstance(ctx.channel, discord.Thread):
            webhook_args["thread"] = ctx.channel

        await bot_webhook.send(**webhook_args)
        await ctx.delete()
