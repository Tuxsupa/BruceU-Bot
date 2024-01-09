import os
import csv

from steam import Steam
from fake_useragent import UserAgent
from dotenv import load_dotenv

import discord

load_dotenv()


class Game():
    steam = Steam(os.environ["STEAM_WEB_API"])

    def __init__(self, client):
        from utils.default import DiscordBot
        self.client: DiscordBot = client

        self.TWITCH_TOKEN = None
        self.embed: discord.Embed = None

    async def get_twitch_token(self):
        url = f'https://id.twitch.tv/oauth2/token?client_id={os.environ["TWITCH_ID"]}&client_secret={os.environ["TWITCH_SECRET"]}&grant_type=client_credentials'
        response = await self.client.session.post(url)
        response = await response.json()
        return response["access_token"]

    async def get_IGDB(self, game: str, where=""):
        response = await self.client.session.post(
            "https://api.igdb.com/v4/games/",
            data=f'fields name,alternative_names,url,game_modes.name,external_games.*,cover.url,total_rating_count,first_release_date,release_dates.*; where name ~ "{game}" {where}; sort total_rating desc;',
            headers={
                "Accept": "application/json",
                "Client-ID": os.environ["TWITCH_ID"],
                "Authorization": f"Bearer {self.TWITCH_TOKEN}",
            })

        return await response.json()

    async def get_HLTB(self, game: str, year=0):
        ua = UserAgent()

        resHLTB = await self.client.session.post(
            "https://www.howlongtobeat.com/api/search",
            json={
                "searchType": "games",
                "searchTerms": game.split(),
                "searchPage": 1,
                "size": 20,
                "searchOptions": {
                    "games": {
                        "userId": 0,
                        "platform": "",
                        "sortCategory": "popular",
                        "rangeCategory": "main",
                        "rangeTime": {"min": 0, "max": 0},
                        "gameplay": {"perspective": "", "flow": "", "genre": ""},
                        "rangeYear": {"min": year, "max": year},
                        "modifier": "",
                    },
                    "users": {"sortCategory": "postcount"},
                    "filter": "",
                    "sort": 0,
                    "randomizer": 0,
                },
            },
            headers={
                "content-type": "application/json",
                "accept": "*/*",
                "User-Agent": ua.random,
                "referer": "https://howlongtobeat.com/",
            },
        )

        return await resHLTB.json()

    async def get_steam_prices(self, appID, countryCode):
        resSteam = await self.client.session.get(
            f"https://store.steampowered.com/api/appdetails?appids={appID}&cc={countryCode}&filters=price_overview"
        )

        return await resSteam.json()

    async def get_steam_game(self, game):
        steam_data = self.steam.apps.search_games(game)
        
        if not steam_data.get("apps"):
            return

        resIGDB = await self.client.session.post(
            "https://api.igdb.com/v4/games/",
            data=f'fields name,url,game_modes.name,external_games.*,cover.url,total_rating_count,first_release_date,release_dates.*; where external_games.uid = "{steam_data["apps"][0]["id"]}";"',
            headers={
                "Accept": "application/json",
                "Client-ID": os.environ["TWITCH_ID"],
                "Authorization": f"Bearer {self.TWITCH_TOKEN}",
            })

        return await resIGDB.json()

    async def get_igdb_with_hltb(self, hltb_data):
        if not hltb_data.get("data"):
            return

        alias = [hltb_data["data"][0]["game_name"]]
        alias += list(csv.reader([hltb_data["data"][0]["game_alias"]], skipinitialspace=True))[0]
        if alias:
            for title in alias:
                game_data = await self.get_IGDB(title)

                if game_data:
                    return game_data

    async def set_steam_data(self, igdb_steam):
        self.original_prices = []

        if not igdb_steam:
            return

        # Set SteamDB link
        app_id = igdb_steam["uid"]
        steamdb_link = f"https://steamdb.info/app/{app_id}"
        self.embed.add_field(name="Link ", value=f"[SteamDB]({steamdb_link})", inline=True)

        # Get converted steam prices
        COUNTRY_CODES = ["se", "ar", "tr"]
        original_prices_str = ""

        for codes in COUNTRY_CODES:
            steam_prices = await self.client.session.get(
                f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc={codes}&filters=price_overview")
            steam_prices = await steam_prices.json()

            if steam_prices.get(app_id) and steam_prices[app_id].get("data"):
                price_overview = steam_prices[app_id]["data"]["price_overview"]
                self.original_prices.append([price_overview["currency"], price_overview["final"] / 100])
                original_prices_str += f"{price_overview['final_formatted']}\n"

        return original_prices_str

    async def get_game_time(self, hltb_data):
        if not hltb_data.get("data") or hltb_data["data"][0]["comp_main"] <= 0:
            return

        game_time = round((hltb_data["data"][0]["comp_main"] / 3600), 3)
        self.embed.add_field(name="Main Story", value=f"{str(game_time)} hours", inline=True)
        return game_time

    async def add_embed_indentation(self, game_time, igdb_steam):
        if self.original_prices:
            # no main story | steam link | prices
            if not game_time:
                self.embed.add_field(name="\u200B", value="\u200B", inline=True)

            # steam link | prices
            self.embed.add_field(name="\u200B", value="\u200B", inline=True)
            return

        if game_time:
            # no steam link | main story | no prices
            if not igdb_steam:
                self.embed.add_field(name="\u200B", value="\u200B", inline=True)
                
            # main story | no prices
            self.embed.add_field(name="\u200B", value="\u200B", inline=True)

    async def get_price_details(self, original_prices_str):
        if not self.original_prices:
            return

        converted_prices_str = ""

        for region, price in self.original_prices:
            price_converted = price / self.client.oer_rates["rates"][region]
            price_converted = round(price_converted * self.client.oer_rates["rates"]["EUR"], 2)
            converted_prices_str += f"{str(price_converted)}€\n"

        self.embed.add_field(name="Prices ", value=original_prices_str, inline=True)
        self.embed.add_field(name="Converted ", value=converted_prices_str, inline=True)

    async def get_game_modes(self, data):
        if game_modes := "".join(f"{i['name']}\n" for i in data.get("game_modes", [])):
            self.embed.add_field(name="Game Modes ", value=game_modes, inline=True)
            return

        # indent if no game modes AND has prices 
        if self.original_prices:
            self.embed.add_field(name="\u200B", value="\u200B", inline=True)