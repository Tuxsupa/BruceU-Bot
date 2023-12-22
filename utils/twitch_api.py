import asyncio
import os
from datetime import datetime
from typing import Union

import discord
import tweepy
from tweepy.asynchronous import AsyncClient
from dotenv import load_dotenv

from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.object.eventsub import ChannelUpdateEvent, StreamOnlineEvent, StreamOfflineEvent

from utils import default
from utils.bingo import Bingo
from utils.game import Game

load_dotenv()


class TwitchAPI():
    GANGSTALKERS = "<@&1033103133959786556>"
    SNIPA = "<@&829458674543099954>"

    def __init__(self, client: default.DiscordBot, loop: asyncio.AbstractEventLoop):
        self.client = client
        self.loop = loop
        self.is_intro = False
        
        self.bingo = Bingo(self.client)

    async def main(self):
        twitterAuth = tweepy.OAuth1UserHandler(
            consumer_key = os.environ["TWITTER_CONSUMER_KEY"],
            consumer_secret = os.environ["TWITTER_CONSUMER_SECRET"],
            access_token = os.environ["TWITTER_ACCESS_TOKEN"],
            access_token_secret = os.environ["TWITTER_ACCESS_SECRET"]
        )

        self.twitterAPI_v1 = tweepy.API(twitterAuth)

        self.twitterAPI_v2 = AsyncClient(
            consumer_key = os.environ["TWITTER_CONSUMER_KEY"],
            consumer_secret = os.environ["TWITTER_CONSUMER_SECRET"],
            access_token = os.environ["TWITTER_ACCESS_TOKEN"],
            access_token_secret = os.environ["TWITTER_ACCESS_SECRET"]
        )

        self.TWITCH = await Twitch(os.environ["TWITCH_ID"], os.environ["TWITCH_SECRET"])

        self.user = await first(self.TWITCH.get_users(logins="forsen"))
        self.stream = await first(self.TWITCH.get_streams(user_id=[self.user.id]))
        self.channel = await self.TWITCH.get_channel_information(self.user.id)

        SNIPA_CHANNEL = 1081602472516276294
        self.discord_channel = (self.client.get_channel(SNIPA_CHANNEL) or await self.client.fetch_channel(SNIPA_CHANNEL))

        self.is_online = self.stream is not None
        self.title = self.channel[0].title
        self.game = self.channel[0].game_name

        print(f"Online: {self.is_online}")
        print(f"Channel name: {self.user.display_name}")
        print(f"Channel title: {self.title}")
        print(f"Channel game: {self.game}")
        
        # Currently playing PUBG
        await self.check_pubg()

        event_sub = EventSubWebhook(os.environ["HOST"], 8080, self.TWITCH)
        event_sub.wait_for_subscription_confirm = False

        await event_sub.unsubscribe_all()

        event_sub.start()

        await event_sub.listen_channel_update(self.user.id, self.on_update)
        await event_sub.listen_stream_online(self.user.id, self.on_online)
        await event_sub.listen_stream_offline(self.user.id, self.on_offline)
        
    async def check_pubg(self):
        if self.is_online and self.game == "PUBG: BATTLEGROUNDS":
            self.client.update_pubg_stats.change_interval(minutes=5)
            return
        
        self.client.update_pubg_stats.change_interval(hours=24)

    async def update_event(self, data: ChannelUpdateEvent):
        print("Update")

        event = data.event
        title = event.title
        game = event.category_name
        user = event.broadcaster_user_name
        link = f"https://twitch.tv/{event.broadcaster_user_login}"
        GAME = await first(self.TWITCH.get_games(game_ids=[event.category_id]))

        if self.is_online:
            util = Game(self.client)
            util.TWITCH_TOKEN = await util.get_twitch_token()
            util.embed = discord.Embed(title=None, color=0x000000, timestamp=datetime.now())
            embed = util.embed

            hltb_data = await util.get_HLTB(game)
            game_data = await util.get_IGDB(game)

            # Get twitter data
            twitter_changed = ""

            if self.title != title:
                embed.title = f"{user} changed title!"
                embed.add_field(name="New Title ", value=title, inline=False)

                twitter_changed += f"New Title:\n{title}\n\n"

            if self.game != game:
                embed.title = f"{user} changed category!"
                embed.add_field(name="New Category ", value=game, inline=False)

                twitter_changed += f"New Category:\n{game}\n\n"

            if self.title != title and self.game != game:
                embed.title = f"{user} changed title and category!"


            game_time = await util.get_game_time(hltb_data)

            if game_time:
                twitter_changed += f"Main Story:\n{game_time}hours\n\n"

            twitter = f"{embed.title}\n\n{twitter_changed}{link}"

            if game_data and game_data[0]:
                game_data = next((i_game_data for i_game_data in game_data for i in i_game_data.get("external_games", []) if i.get("category") == 14 and i.get("uid") == event.category_id), game_data[0])
                igdb_steam = next((i for i in game_data.get("external_games", []) if i.get("category") == 1), None)
                original_prices_str = await util.set_steam_data(igdb_steam)

                await util.add_embed_indentation(game_time, igdb_steam)
                await util.get_price_details(original_prices_str)
                
                got_game_modes = False
                if igdb_steam:
                    got_game_modes = await util.get_game_modes_steam(igdb_steam["uid"])

                if not got_game_modes:
                    await util.get_game_modes_igdb(game_data)

            pings = self.GANGSTALKERS
            if game == "PUBG: BATTLEGROUNDS" and self.game != game:
                pings += self.SNIPA

            embed.set_thumbnail(url=GAME.box_art_url.format(width=144, height=192))
            embed.set_author(name=user, icon_url=self.user.profile_image_url, url=link)
            embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.client.DEV.display_avatar.url)
            await self.discord_channel.send(content=pings, embed=embed)

            await self.twitterAPI_v2.create_tweet(text=twitter)

            if self.game != game:
                self.is_intro = False
        else:
            await self.went_online(data)

        self.title = title
        self.game = game

        await self.check_pubg()

    async def online_event(self, data: StreamOnlineEvent):
        print("Online Event")

        if not self.is_online:
            print("Went live without changing the title")
            await self.went_online(data)

        self.is_actually_online = True

    async def went_online(self, data: Union[ChannelUpdateEvent, StreamOnlineEvent]):
        print("Online")

        event = data.event
        user = event.broadcaster_user_name
        link = f"https://twitch.tv/{event.broadcaster_user_login}"

        self.is_online = True
        self.is_actually_online = False

        embed = discord.Embed(
            title=f"{user} just went live!",
            color=0x000000,
            timestamp=datetime.now(),
        )
        embed.set_author(name=user, icon_url=self.user.profile_image_url, url=link)
        embed.set_image(url="https://media.discordapp.net/attachments/103642197076742144/865277316136566794/tenor_16.gif")
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.client.DEV.display_avatar.url)

        await self.discord_channel.send(embed=embed)

        mediaID = self.twitterAPI_v1.media_upload("./assets/images/mrPresident.gif")
        await self.twitterAPI_v2.create_tweet(
            text=f"{user} just went live!\n\n{link}", media_ids=[mediaID.media_id]
        )

        await self.bingo.bingo_online_event()

        self.is_intro = True

        self.loop.create_task(self.check_if_actually_online())

    async def check_if_actually_online(self):
        await asyncio.sleep(5 * 60)

        if not self.is_actually_online:
            print("Changed title but didn't go online after 5 minutes")

            self.is_online = False
            await self.check_pubg()

    async def offline_event(self, data: StreamOfflineEvent):
        print("Offline")
        self.is_online = False
        event = data.event

        embed = discord.Embed(
            title=f'{event.broadcaster_user_name} just went offline... Now what...',
            color=0x000000,
            timestamp=datetime.now(),
        )
        embed.set_author(
            name=event.broadcaster_user_name,
            icon_url=self.user.profile_image_url,
            url=f'https://twitch.tv/{event.broadcaster_user_login}',
        )
        # embed.set_image(url="https://cdn.discordapp.com/attachments/1002241010115559464/1025614839118307398/unknown.png")
        # embed.set_image(url="https://cdn.discordapp.com/attachments/988994875234082829/1061429150818242662/tenor_2.gif")
        embed.set_image(url="https://cdn.discordapp.com/attachments/1002241010115559464/1167256446447132744/forsenSmug.webp")
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.client.DEV.display_avatar.url)
        await self.discord_channel.send(embed=embed)

        # mediaID = self.twitterAPI_v1.media_upload("./assets/images/forsenDespair.png")
        # mediaID = self.twitterAPI_v1.media_upload("./assets/images/minecraft.gif")
        mediaID = self.twitterAPI_v1.media_upload("./assets/images/forsenSmug.webp")
        await self.twitterAPI_v2.create_tweet(text="Forsen just went offline... Now what...", media_ids=[mediaID.media_id])

        await self.bingo.bingo_offline_event()
        self.loop.create_task(self.pubg_offline())

        self.is_intro = False

    # Only change back to 24 hours after 30 minutes
    async def pubg_offline(self):
        await asyncio.sleep(45 * 60)
        self.client.update_pubg_stats.change_interval(hours=24)

    async def on_update(self, data: ChannelUpdateEvent):
        self.loop.create_task(self.update_event(data))

    async def on_online(self, data: StreamOnlineEvent):
        self.loop.create_task(self.online_event(data))

    async def on_offline(self, data: StreamOfflineEvent):
        self.loop.create_task(self.offline_event(data))
