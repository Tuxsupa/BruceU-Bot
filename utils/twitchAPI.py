import discord
import asyncio
import os
import aiohttp
import datetime

from utils import default
from dotenv import load_dotenv

from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
from twitchAPI.eventsub import EventSub

import tweepy
from tweepy.asynchronous import AsyncClient 

load_dotenv()


class TwitchAPI(object):
    def __init__(self, client, loop):
        self.client = client
        self.loop = loop
        self.isIntro=False
        

    async def main(self):
        twitterAuth = tweepy.OAuth1UserHandler(
        os.environ["TWITTER_API"], os.environ["TWITTER_SECRET"], os.environ["TWITTER_ACCESS_TOKEN"], os.environ["TWITTER_ACCESS_SECRET"]
        )

        self.twitterAPI_v1 = tweepy.API(twitterAuth)

        self.twitterAPI_v2 = AsyncClient(
            os.environ["TWITTER_ACCESS_TOKEN"], os.environ["TWITTER_API"], os.environ["TWITTER_SECRET"], os.environ["TWITTER_ACCESS_TOKEN"], os.environ["TWITTER_ACCESS_SECRET"]
        )

        self.TWITCH = await Twitch(os.environ["TWITCH_ID"], os.environ["TWITCH_SECRET"])

        self.user = await first(self.TWITCH.get_users(logins="forsen"))
        self.channel = await self.TWITCH.get_channel_information(self.user.id)
        self.discordChannel = self.client.get_channel(979091569678364693)
        self.discordChannel_Logs = self.client.get_channel(1044664235365502996)

        try:
            self.stream = await first(self.TWITCH.get_streams(user_id=[self.user.id]))
            self.onlineCheck = True
        except:
            self.onlineCheck = False

        self.title = self.channel[0].title
        self.game = self.channel[0].game_name


        print(f"Online: {self.onlineCheck}")
        print(f"Channel name: {self.user.display_name}")
        print(f"Channel title: {self.title}")
        print(f"Channel game: {self.game}")

        await self.discordChannel_Logs.send(content=f"Online: {self.onlineCheck}\nChannel name: {self.user.display_name}\nChannel title: {self.title}\nChannel game: {self.game}")

        event_sub = EventSub(os.environ["HOST"], os.environ["TWITCH_ID"], 8080, self.TWITCH)

        await event_sub.unsubscribe_all()

        event_sub.start()

        await event_sub.listen_channel_update(self.user.id, self.on_update)

        await event_sub.listen_stream_online(self.user.id, self.on_online)

        await event_sub.listen_stream_offline(self.user.id, self.on_offline)

    async def checkIfActuallyOnline(self):
        await asyncio.sleep(5 * 60)
        if self.onlineEvent_checked is False:
            print("Changed title but didn't go online after 5 minutes")
            await self.discordChannel_Logs.send(content="Changed title but didn't go online after 5 minutes")

            self.onlineCheck = False

    async def isOnline(self, data: dict):
        print("Online")
        await self.discordChannel_Logs.send(content="Online")

        self.onlineCheck = True
        self.onlineEvent_checked = False

        embed = discord.Embed(
            title=f'{data["event"]["broadcaster_user_name"]} just went live!',
            color=0x000000,
            timestamp=datetime.datetime.now(),
        )
        embed.set_author(
            name=data["event"]["broadcaster_user_name"],
            icon_url=self.user.profile_image_url,
            url=f'https://twitch.tv/{data["event"]["broadcaster_user_login"]}',
        )
        embed.set_image(url="https://media.discordapp.net/attachments/103642197076742144/865277316136566794/tenor_16.gif")
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=default.DEV.display_avatar.url)

        await self.discordChannel.send(embed=embed)

        mediaID = self.twitterAPI_v1.media_upload("./assets/images/mrPresident.gif")

        await self.twitterAPI_v2.create_tweet(text="Forsen just went live!\n\nhttps://www.twitch.tv/forsen", media_ids=[mediaID.media_id])

        await default.onlineEvent(client=self.client)

        self.isIntro = True
        
        self.loop.create_task(self.checkIfActuallyOnline())

    async def updateEvent(self, data: dict):
        print("Update")
        await self.discordChannel_Logs.send(content="Update")

        GAME = await first(self.TWITCH.get_games(game_ids=[data["event"]["category_id"]]))  # 31376

        if self.onlineCheck:

            async with aiohttp.ClientSession() as session:
                resHLTB = await default.get_HLTB(game=data["event"]["category_name"], session=session)

                resIGDB = await default.get_IGDB(game=data["event"]["category_name"], session=session)

                embed = discord.Embed(title=None, color=0x000000, timestamp=datetime.datetime.now())
                embed.set_author(
                    name=data["event"]["broadcaster_user_name"],
                    icon_url=self.user.profile_image_url,
                    url=f'https://twitch.tv/{data["event"]["broadcaster_user_login"]}',
                )
                embed.set_thumbnail(url=GAME.box_art_url.format(width=144, height=192))

                if self.title != data["event"]["title"] and self.game != data["event"]["category_name"]:
                    embed.title = f'{data["event"]["broadcaster_user_name"]} changed title and category!'
                    embed.add_field(name="New Title ", value=data["event"]["title"], inline=False)
                    embed.add_field(name="New Category ", value=data["event"]["category_name"], inline=False)

                    twitterText = (
                        f"Forsen changed title and category!\n\n"
                        + f"New Title:\n{data['event']['title']}\n\n"
                        + f"New Category:\n{data['event']['category_name']}\n\n"
                    )
                elif self.title != data["event"]["title"]:
                    embed.title = f'{data["event"]["broadcaster_user_name"]} changed title!'
                    embed.add_field(name="New Title ", value=data["event"]["title"], inline=False)

                    twitterText = f"Forsen changed title!\n\n" + f"New Title:\n{data['event']['title']}\n\n"
                elif self.game != data["event"]["category_name"]:
                    embed.title = f'{data["event"]["broadcaster_user_name"]} changed category!'
                    embed.add_field(name="New Category ", value=data["event"]["category_name"], inline=False)

                    twitterText = f"Forsen changed category!\n\n" + f"New Category:\n{data['event']['category_name']}\n\n"
                else:
                    twitterText = ""

                if resHLTB and len(resHLTB["data"]) > 0:
                    gameData = resHLTB["data"][0]
                    gameTime = round(gameData["comp_main"] / 3600, 3)
                    if gameTime > 0:
                        embed.add_field(name="Main Story", value=f"{gameTime} hours", inline=True)
                        twitterText = twitterText + f"Main Story:\n{gameTime}hours\n\n"

                if resIGDB:
                    resData = resIGDB[0]
                    gameModes = ""
                    appID = None

                    if "game_modes" in resData:
                        for gameModesData in resData["game_modes"]:
                            gameModes = gameModes + gameModesData["name"] + "\n"

                    if "external_games" in resData:
                        for externalGamesData in resData["external_games"]:
                            if externalGamesData["category"] == 1:
                                appID = externalGamesData["uid"]
                                linkSteam = "https://steamdb.info/app/" + appID

                                embed.add_field(name="Link", value="[SteamDB](" + linkSteam + ")", inline=True)
                                break

                    COUNTRYCODES = ["se", "ar", "tr"]
                    originalPrices = []
                    originalPricesText = ""
                    convertedPricesText = ""

                    for countryCode in COUNTRYCODES:
                        resSteam = None

                        if appID:
                            resSteam = await default.get_Steam(appID=appID, countryCode=countryCode, session=session)

                        if resSteam and len(resSteam[appID]["data"]) > 0:
                            PRICE_OVERVIEW = resSteam[appID]["data"]["price_overview"]

                            originalPrices.append([PRICE_OVERVIEW["currency"], PRICE_OVERVIEW["final"] / 100])

                            originalPricesText = originalPricesText + PRICE_OVERVIEW["final_formatted"] + "\n"

                    if originalPrices:
                        for prices in originalPrices:
                            amount = prices[1] / default.hourlyOER.rates["rates"][prices[0]]
                            result = round(amount * default.hourlyOER.rates["rates"]["EUR"], 2)
                            convertedPricesText = f"{convertedPricesText}{result}€\n"

                        if len(resHLTB) == 0 or len(resHLTB["data"]) == 0 or resHLTB["data"][0]["comp_main"] == 0:
                            embed.add_field(name="\u200B", value="\u200B", inline=True)

                        embed.add_field(name="\u200B", value="\u200B", inline=True)
                        embed.add_field(name="Prices ", value=originalPricesText, inline=True)
                        embed.add_field(name="Converted ", value=convertedPricesText, inline=True)

                    else:
                        if len(resHLTB) > 0 and len(resHLTB["data"]) > 0 and resHLTB["data"][0]["comp_main"] != 0:
                            embed.add_field(name="\u200B", value="\u200B", inline=True)
                            embed.add_field(name="\u200B", value="\u200B", inline=True)

                    if gameModes:
                        embed.add_field(name="Game Modes ", value=gameModes, inline=True)

                embed.set_footer(text="Bot made by Tuxsuper", icon_url=default.DEV.display_avatar.url)

                await self.discordChannel.send(content="<@&1033103133959786556>", embed=embed)

                twitterText = twitterText + "https://www.twitch.tv/forsen"

                await self.twitterAPI_v2.create_tweet(text=twitterText)

                self.isIntro = False
        else:
            await self.isOnline(data)

        self.title = data["event"]["title"]
        self.game = data["event"]["category_name"]

    async def onlineEvent(self, data: dict):
        print("Online Event")
        await self.discordChannel_Logs.send(content="Online Event")

        if self.onlineCheck is False:
            print("Went live without changing the title")
            await self.isOnline(data)

        self.onlineEvent_checked = True

    async def offlineEvent(self, data: dict):
        print("Offline")
        await self.discordChannel_Logs.send(content="Offline")

        self.onlineCheck = False

        embed = discord.Embed(
            title=f'{data["event"]["broadcaster_user_name"]} just went offline... Now what...',
            color=0x000000,
            timestamp=datetime.datetime.now(),
        )
        embed.set_author(
            name=data["event"]["broadcaster_user_name"],
            icon_url=self.user.profile_image_url,
            url=f'https://twitch.tv/{data["event"]["broadcaster_user_login"]}',
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1002241010115559464/1025614839118307398/unknown.png")
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=default.DEV.display_avatar.url)

        await self.discordChannel.send(embed=embed)

        mediaID = self.twitterAPI_v1.media_upload("./assets/images/forsenDespair.png")

        await self.twitterAPI_v2.create_tweet(text="Forsen just went offline... Now what...", media_ids=[mediaID.media_id])

        await default.offlineEvent()

        self.isIntro = False

    async def on_update(self, data: dict):
        self.loop.create_task(self.updateEvent(data))

    async def on_online(self, data: dict):
        self.loop.create_task(self.onlineEvent(data))

    async def on_offline(self, data: dict):
        self.loop.create_task(self.offlineEvent(data))
