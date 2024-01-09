import os
import json
import math
import asyncio
import contextlib
from datetime import datetime
from collections import Counter
from PIL import Image, ImageFont, ImageDraw
from dotenv import load_dotenv

import discord
from discord.ext import commands
from utils import default

import logging
logger = logging.getLogger("discord")

load_dotenv()

class PubgData():
    FORSEN_ID = "account.9f8afe4c244e4290abb265d6864eac3e"
    FORSEN_URL = f"https://api.pubg.com/shards/steam/players/{FORSEN_ID}"

    HEADER = {
        "Authorization": f"Bearer {os.environ['PUBG_API_KEY']}",
        "Accept": "application/vnd.api+json",
        "Accept-Enconding": "gzip",
    }

    with open("./assets/dictionaries/damageCauserName.json", "r", encoding="utf-8") as f:
        DAMAGE_CAUSER_NAME = json.loads(f.read())

    with open("./assets/dictionaries/damageTypeCategory.json", "r", encoding="utf-8") as f:
        DAMAGE_TYPE_CATEGORY = json.loads(f.read())

    with open("./assets/dictionaries/scoreTable.json", "r", encoding="utf-8") as f:
        SCORE_TABLE = json.loads(f.read())

    def __init__(self, client: default.DiscordBot):
        self.client = client
        self.db = client.db

    async def compare_times(self, first_date, second_date):
        first_date = datetime.fromisoformat(first_date.replace("Z", "+00:00"))
        second_date = datetime.fromisoformat(second_date.replace("Z", "+00:00"))

        return (second_date - first_date).total_seconds()

    async def check_values_json(self, event):
        damage_info = event["finishDamageInfo"]

        try:
            self.DAMAGE_TYPE_CATEGORY[damage_info["damageTypeCategory"]]
        except KeyError as e:
            logger.error(f"{e} doesn't exist in DAMAGE_TYPE_CATEGORY")
            raise KeyError from e

        try:
            causer = self.DAMAGE_CAUSER_NAME[damage_info["damageCauserName"]]
        except KeyError as e:
            logger.error(f"{e} doesn't exist in DAMAGE_CAUSER_NAME")
            raise KeyError from e

        try:
            self.SCORE_TABLE[causer]
        except KeyError as e:
            logger.error(f"{e} doesn't exist in SCORE_TABLE")
            raise KeyError from e

    async def process_target_kill(self, event, match_id):
        killer = None
        health = None
        location = None
        killer_id = None

        if finisher := event.get("finisher"):
            killer = finisher.get("name")
            health = finisher.get("health")
            location = [float(finisher.get("location") and finisher["location"].get(coord)) for coord in ["x", "y", "z"]]
            killer_id = finisher.get("accountId")

        damage_info = event["finishDamageInfo"]
        weapon = self.DAMAGE_TYPE_CATEGORY[damage_info["damageTypeCategory"]]
        distance = damage_info["distance"]
        causer = self.DAMAGE_CAUSER_NAME[damage_info["damageCauserName"]]
        self.kill_date = event["_D"]

        # Insert kill into the database
        query = """INSERT INTO kills (name, weapon, causer, distance, health, location, date, map, players_ids, account_id, match_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)"""
        values = (killer, weapon, causer, distance, health, location, self.kill_date, self.map, self.players_ids.keys(), killer_id, match_id)
        await self.db.connect_db(query, values)

        if killer is not None:
            # Give kill to killer | If killer doesn't exist create a row for them
            query = """INSERT INTO stats (name, kills, account_id) VALUES ($1,$2,$3) ON CONFLICT (account_id) DO UPDATE SET kills=stats.kills+$4"""
            values = (killer, 1, killer_id, 1)
            await self.db.connect_db(query, values)

            # Update score for the killer
            score = self.SCORE_TABLE[causer]
            query = """UPDATE stats SET score=stats.score+$1 WHERE account_id LIKE $2"""
            values = (score, killer_id)
            await self.db.connect_db(query, values)

        # Update rankings
        query = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
        await self.db.connect_db(query)

    async def process_snipa_data(self, event, snipa_ids, bounties):
        victim_id = event["victim"]["accountId"]
        finisher_id = event.get("finisher") and event["finisher"].get("accountId")
        
        if victim_id == self.FORSEN_ID:
            self.forsen_died = True

        if victim_id in snipa_ids or victim_id == self.FORSEN_ID:
            deaths = 1 if finisher_id == self.FORSEN_ID else 0
            suicides = 1 if event["isSuicide"] is True else 0

            stats_victim = event["victimGameResult"]["stats"]

            # Update stats for snipa
            query = """UPDATE stats SET deaths=stats.deaths+$1,distance_travelled[1]=stats.distance_travelled[1]+$2, distance_travelled[2]=stats.distance_travelled[2]+$3,
            distance_travelled[3]=stats.distance_travelled[3]+$4,distance_travelled[4]=stats.distance_travelled[4]+$5,distance_travelled[5]=stats.distance_travelled[5]+$6,
            suicides=stats.suicides+$7 WHERE account_id LIKE $8"""
            values = (
                deaths,
                stats_victim["distanceOnFoot"],
                stats_victim["distanceOnSwim"],
                stats_victim["distanceOnVehicle"],
                stats_victim["distanceOnParachute"],
                stats_victim["distanceOnFreefall"],
                suicides,
                victim_id
            )
            await self.db.connect_db(query, values)

            if finisher_id in snipa_ids or finisher_id == self.FORSEN_ID:
                query = """UPDATE stats SET snipas_killed=stats.snipas_killed+$1 WHERE account_id LIKE $2"""
                values = (1, finisher_id)
                await self.db.connect_db(query, values)

        if finisher_id in snipa_ids and victim_id in bounties:
            query = """UPDATE stats SET score=stats.score+$1 WHERE account_id LIKE $2"""
            values = (bounties[victim_id], finisher_id)
            await self.db.connect_db(query, values)

    async def process_damage_dealt(self, event):
        if attacker := event["attacker"]:
            attacker_id = attacker["accountId"]
            damage_dealt = event["damage"]

            query = """UPDATE stats SET damage_dealt=stats.damage_dealt+$1 WHERE account_id LIKE $2"""
            values = (damage_dealt, attacker_id)
            await self.db.connect_db(query, values)

    async def process_telemetry_data(self, matchID): # Main function
        TELEMETRY_DATA = None

        # While loop to prevent losing data because of maxing out requests per minute on PUBG API
        while not TELEMETRY_DATA:
            MATCH_URL = f"https://api.pubg.com/shards/steam/matches/{matchID}"
            MATCH_STAT = await self.client.request_aio(MATCH_URL, self.HEADER)

            self.forsen_died = False

            # Find telemetry data of the match
            for i in MATCH_STAT["included"]:
                if i["type"] == "asset":
                    TELEMETRY_URL = i["attributes"]["URL"]
                    break

            TELEMETRY_DATA = await self.client.request_aio(TELEMETRY_URL, self.HEADER)
            
            if not TELEMETRY_DATA:
                await asyncio.sleep(10)

        # Process target kill data
        for event in TELEMETRY_DATA:
            if event["_T"] == "LogMatchStart":
                self.map = event["mapName"]
                self.players_ids = {character["character"]["accountId"]: character["character"]["name"] for character in event["characters"]}

            if event["_T"] == "LogPlayerKillV2" and event["victim"]["accountId"] == self.FORSEN_ID:
                try:
                    await self.check_values_json(event)
                except KeyError:
                    return

                await self.process_target_kill(event, matchID)
                break

        query = """SELECT players_ids FROM kills WHERE players_ids IS NOT NULL"""
        all_players_ids = await self.db.connect_db(query)

        all_ids = [id for players_ids in all_players_ids for id in players_ids]
        id_counts = Counter(all_ids)

        query = """SELECT account_id FROM stats WHERE account_id NOT LIKE $1 ORDER BY name"""
        snipa_ids: list = await self.db.connect_db(query, (self.FORSEN_ID,))
        MATCHES_REQUIRED = 5

        for id, count in id_counts.items():
            if not id.startswith("account") or id == self.FORSEN_ID or id in snipa_ids or count < MATCHES_REQUIRED:
                continue

            if self.players_ids.get(id):
                name = self.players_ids[id]
            else:
                player_data = await self.client.request_aio(f"https://api.pubg.com/shards/steam/players/{id}", self.HEADER)
                name = player_data["data"]["attributes"]["name"]
            
            query = """INSERT INTO stats (name, matches, account_id) VALUES ($1,$2,$3) ON CONFLICT (account_id) DO NOTHING"""
            values = (name, MATCHES_REQUIRED-1, id)
            await self.db.connect_db(query, values)
            snipa_ids.append(id)

        logged_out_in_time = []

        for event in TELEMETRY_DATA:
            if event["_T"] == "LogMatchStart":
                for character in event["characters"]:
                    if character["character"]["accountId"] not in snipa_ids:
                        continue

                    query = """UPDATE stats SET matches=stats.matches+$1 WHERE account_id LIKE $2"""
                    values = (1, character["character"]["accountId"])
                    await self.db.connect_db(query, values)

            if event["_T"] == "LogPlayerLogout" and event["accountId"] in snipa_ids and \
            await self.compare_times(event["_D"], self.kill_date) <= 30:
                logged_out_in_time.append(event["accountId"])

        query = """SELECT account_id, bounty FROM stats WHERE account_id NOT LIKE $1 AND bounty > 0 ORDER BY name"""
        bounties = await self.db.connect_db(query, (self.FORSEN_ID,))
        bounties = {bounty[0]: bounty[1] for bounty in bounties}

        for event in TELEMETRY_DATA:
            if event["_T"] == "LogPlayerKillV2" and (not self.forsen_died or event["victim"]["accountId"] in logged_out_in_time):
                await self.process_snipa_data(event, snipa_ids, bounties)

            if event["_T"] == "LogPlayerTakeDamage" and event["victim"]["accountId"] == self.FORSEN_ID:
                await self.process_damage_dealt(event)


class Report():
    WHITE = (255, 255, 255)

    with open("./assets/dictionaries/simpleCause.json", "r", encoding="utf-8") as f:
        SIMPLE_CAUSE = json.loads(f.read())

    def __init__(self, client: default.DiscordBot):
        self.client = client
        self.db = client.db

    async def start_report(self):
        self.report = Image.open("./assets/images/report.png")
        self.title_font = ImageFont.truetype("./assets/fonts/Myriad Pro Bold.ttf", 60)
        self.counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
        self.report_draw = ImageDraw.Draw(self.report)
        
    async def get_pubg_name(self, ctx, name, member):
        if member is None: # Might be PUBG name
            query = """SELECT pubg_name FROM discord_profiles WHERE LOWER(pubg_name) LIKE LOWER($1)"""
            values = (name,)
            self.pubg_name = await self.db.connect_db(query, values)

            query = """SELECT name FROM stats WHERE LOWER(name) LIKE LOWER($1)"""
            values = (name,)
            pubg_name = await self.db.connect_db(query, values)
            
            if not self.pubg_name and pubg_name:
                self.pubg_name = pubg_name

            if not self.pubg_name or not pubg_name:
                await self.client.embed_message(ctx, description=f"PUBG name {name} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list")
                raise StopIteration

        else: # Is discord name | Might need to put it above the if?
            query = """SELECT pubg_name FROM discord_profiles WHERE id = $1"""
            values = (member.id,)
            self.pubg_name = await self.db.connect_db(query, values)
            if not self.pubg_name:
                await self.client.embed_message(ctx, description=f"PUBG name from {member} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list")
                raise StopIteration

    async def write_header(self):
        IMAGE_WIDTH = 2000
        
        self.report_draw.text(
            (IMAGE_WIDTH/2, 60),
            self.pubg_name,
            self.WHITE,
            font=self.title_font,
            anchor="ma",
            align="center",
        )

    async def convert_to_array(self, data):
        if isinstance(data, str):
            return [data]
        elif isinstance(data, list):
            return data
        else:
            raise ValueError("Input must be a string or a list")

    async def write_kill_causes(self):
        query = """SELECT causer FROM kills WHERE LOWER(name) LIKE LOWER($1)"""
        values = (self.pubg_name,)
        causer = await self.db.connect_db(query, values)
        causer = await self.convert_to_array(causer)

        try:
            self.counter = Counter([self.SIMPLE_CAUSE[cause] for cause in causer])
        except KeyError as e:
            logger.error("Error in report: ", e)
            raise StopIteration
        
        Y_START = 273
        xAxis = 200
        yAxis = Y_START
        color = self.WHITE
        type_kill = [
            "Punch",
            "Vehicle",
            "Grenade",
            "Panzerfaust",
            "C4",
            "Glider",
            "Melee Weapon",
            "Melee Throw",
            "Molotov",
            "Crossbow",
            "Mortar",
            "Gun",
        ]

        for index, kill in enumerate(type_kill):
            if kill == "Gun":
                color = (255, 0, 0)

            if index == len(type_kill)/2: # Half way point
                xAxis += 350
                yAxis = Y_START

            self.report_draw.text(
                (xAxis, yAxis),
                f"x {self.counter.get(kill, 0)}",
                color,
                font=self.counter_font,
            )

            yAxis += 208
            
    async def write_stats_data(self):        
        query = """SELECT kills, deaths, damage_dealt, snipas_killed, distance_travelled, suicides, score, ranking, bounty FROM stats WHERE LOWER(name) LIKE LOWER($1)"""
        values = (self.pubg_name,)
        kills, deaths, damage_dealt, snipas_killed, distance_travelled, suicides, score, self.ranking, self.bounty = await self.db.connect_db(query, values)

        data_labels = [
            "Killed Forsen",
            "Died to Forsen",
            "K/D",
            "Damage Dealt",
            "Snipas Killed",
            "Distance Travelled",
            "Suicides",
            "Score",
            "Ranking",
            "Bounty",
        ]
        
        xAxis = 852
        yAxis = 262
        xExtra = 470
        ROW_HEIGHT = 116
        
        data_values = [
            f"{kills}",
            f"{deaths}",
            f"{round(kills if deaths == 0 else kills / deaths, 3)}",
            f"{round(damage_dealt, 2)}",
            f"{snipas_killed}",
            f"{round((distance_travelled[0] + distance_travelled[1] + distance_travelled[2])/1000, 2)} km",
            f"{suicides}",
            f"{score}",
            f"#{self.ranking}",
            f"{self.bounty} pts",
        ]
        
        for label, value in zip(data_labels, data_values):
            if label == "Score":
                yAxis += 50
                xExtra -= 170
                
            self.report_draw.text((xAxis, yAxis), label, self.WHITE, font=self.counter_font)
            self.report_draw.text((xAxis + xExtra, yAxis), value, self.WHITE, font=self.counter_font)
            
            yAxis += ROW_HEIGHT
    
    async def write_badge(self):
        if "Gun" in self.counter or self.bounty > 0:
            badge = "badgehaHAA"
        elif self.ranking == 1:
            badge = "badgeBruceU"
        elif self.ranking <= 10:
            badge = "badgeCommando"
        else:
            badge = "badgeZULUL"
        
        badge = Image.open(f"./assets/images/{badge}.png")

        BADGE_POSITION = (1563, 1113)
        self.report.paste(badge, BADGE_POSITION, badge)
        
    async def generate_report(self, ctx: commands.Context, name, member):
        try:
            await self.start_report()
            await self.get_pubg_name(ctx, name, member)
            await self.write_header()
            await self.write_kill_causes()
            await self.write_stats_data()
            await self.write_badge()
        except StopIteration:
            return
        
        return self.report


class Leaderboard():
    WHITE = (255, 255, 255)
    PAGE_SIZE = 10

    def __init__(self, client: default.DiscordBot):
        self.client = client
        self.db = client.db

    async def start_leaderboard(self, value):
        self.value = value
        self.page = 1
        self.offset = 0
        
        self.leaderboard = Image.open("./assets/images/leaderboard.png")
        self.counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
        self.lb_draw = ImageDraw.Draw(self.leaderboard)
    
    async def get_player_data(self, ctx, member):
        if member is None:  # PUBG name used
            query = """SELECT name FROM stats WHERE LOWER(name) LIKE LOWER($1)"""
            values = (self.value,)
            self.pubg_name = await self.db.connect_db(query, values)

            if not self.pubg_name:
                await self.client.embed_message(ctx, description=f"PUBG name {self.value} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list")
                raise StopIteration

        else:  # Discord, no name or Mention used
            query = """SELECT pubg_name FROM discord_profiles WHERE id = $1"""
            values = (member.id,)
            self.pubg_name = await self.db.connect_db(query, values)

            if not self.pubg_name:
                await self.client.embed_message(ctx, description=f"PUBG name from {self.value} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list")
                raise StopIteration

        query = """SELECT name, ROW_NUMBER() OVER (ORDER BY ranking ASC, name) AS rows FROM stats"""
        ranking_order = await self.db.connect_db(query)
        
        ranking = next((ranking for name, ranking in ranking_order if name == self.pubg_name), 0)

        self.page = math.ceil(ranking/self.PAGE_SIZE)
        self.offset = (self.page-1)*self.PAGE_SIZE
    
    async def write_leaderboard(self):
        xArray = [87, 221, 874, 1224, 1574]
        yAxis = 326
        ROW_HEIGHT = 116
        color = self.WHITE
        
        query = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
        await self.db.connect_db(query)

        query = """SELECT ranking, name, score, kills, deaths FROM stats ORDER BY ranking ASC, name LIMIT 10 OFFSET $1"""
        values = (self.offset,)
        ranked_stats = await self.db.connect_db(query, values)

        for rank, name, score, kills, deaths in ranked_stats:
            if self.value and not self.value.isdigit():
                color = (255, 255, 0) if name == self.pubg_name else self.WHITE

            self.lb_draw.text((xArray[0], yAxis), f"#{rank}", color, font=self.counter_font, align="center")
            self.lb_draw.text((xArray[1], yAxis), f"{name}", color, font=self.counter_font)
            self.lb_draw.text((xArray[2], yAxis), f"{score} pts", color, font=self.counter_font)
            self.lb_draw.text((xArray[3], yAxis), f"{kills}", color, font=self.counter_font)
            self.lb_draw.text((xArray[4], yAxis), f"{deaths}", color, font=self.counter_font)
            
            yAxis += ROW_HEIGHT
        
    async def generate_leaderboard(self, ctx: commands.Context, value):
        await self.start_leaderboard(value)

        member = await get_member(ctx, self.value)

        try:
            if self.value:
                if self.value.isdigit(): # Is a page number
                    self.page = int(self.value)
                    self.offset = (self.page-1)*self.PAGE_SIZE

                else:
                    await self.get_player_data(ctx, member)
        except StopIteration:
            return

        query = """SELECT count(*) FROM stats"""
        row_count = await self.db.connect_db(query)
        max_page = math.ceil(row_count/self.PAGE_SIZE)

        if self.value and self.value.isdigit() and self.page > max_page:
            await self.client.embed_message(ctx, description="Page number can't be higher than number of pages")
            return

        self.lb_draw.text((1935, 57), f"Page {self.page}/{max_page}", self.WHITE, font=self.counter_font, anchor="ra")

        await self.write_leaderboard()

        lb_path = "./assets/images/leaderboardResult.png"
        self.leaderboard.save(lb_path)
        await ctx.send(file=discord.File(lb_path))


class Customboard():
    WHITE = (255, 255, 255)
    PAGE_SIZE = 20

    ORDER_DICT = {
        "kills": "kills",
        "deaths": "deaths",
        "kd": "kills/CASE WHEN deaths = 0 THEN 1 ELSE deaths END::real",
        "damage": "damage_dealt",
        "snipakills": "snipas_killed",
        "distance": "(distance_travelled[1]+distance_travelled[2]+distance_travelled[3])",
        "suicides": "suicides",
        "matches": "matches",
        "bounty": "bounty"
    }
    SELECT_DICT = {
        "kills": "kills",
        "deaths": "deaths",
        "kd": "ROUND(kills/CASE WHEN deaths = 0 THEN 1 ELSE deaths END::numeric, 2) AS kd",
        "damage": "ROUND(damage_dealt::numeric,2) AS damage",
        "snipakills": "snipas_killed",
        "distance": "ROUND(((distance_travelled[1]+distance_travelled[2]+distance_travelled[3])/1000)::numeric,2) AS distance",
        "suicides": "suicides",
        "matches": "matches",
        "bounty": "bounty"
    }
    TITLE_DICT = {
        "kills": "Kills",
        "deaths": "Deaths",
        "kd": "K/D",
        "damage": "Damage",
        "snipakills": "Snipa Kills",
        "distance": "Distance",
        "suicides": "Suicides",
        "matches": "Matches",
        "bounty": "Bounty"
    }

    def __init__(self, client: default.DiscordBot):
        self.client = client
        self.db = client.db

    async def start_customboard(self, choice, value):
        self.choice = choice
        self.value = value
        self.page = 1
        self.offset = 0
        
        self.customboard = Image.open("./assets/images/customboard.png")
        self.counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
        self.cb_draw = ImageDraw.Draw(self.customboard)
        
    async def get_player_data(self, ctx, member):
        if member is None: # Check if PUBG name
            query = """SELECT name FROM stats WHERE LOWER(name) LIKE LOWER($1)"""
            values = (self.value,)
            self.pubg_name = await self.db.connect_db(query, values)

            if not self.pubg_name:
                await self.client.embed_message(ctx, description=f"PUBG name {self.value} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list")
                raise StopIteration

        else:
            query = """SELECT pubg_name FROM discord_profiles WHERE id = $1"""
            values = (member.id,)
            self.pubg_name = await self.db.connect_db(query, values)

            if not self.pubg_name:
                await self.client.embed_message(ctx, description=f"PUBG name from {self.value} is not on the database use {ctx.prefix}add to add your PUBG name to the snipa list")
                raise StopIteration


        query = f"SELECT name, ROW_NUMBER() OVER (ORDER BY {self.ORDER_DICT[self.choice]} DESC, name) AS rows from stats"
        ranking_order = await self.db.connect_db(query)

        ranking = next((ranking for name, ranking in ranking_order if name == self.pubg_name), 0)

        self.page = math.ceil(ranking/self.PAGE_SIZE)
        self.offset = (self.page-1)*self.PAGE_SIZE
    
    async def write_customboard(self):
        Y_START = 326
        ROW_HEIGHT = 116

        xArray = [87, 221, 764, 1026, 1160, 1703]
        yAxis = Y_START
        color = self.WHITE

        self.cb_draw.text((xArray[1], 210), "Username", color, font=self.counter_font)
        self.cb_draw.text((xArray[2], 210), f"{self.TITLE_DICT[self.choice]}", color, font=self.counter_font)
        self.cb_draw.text((xArray[4], 210), "Username", color, font=self.counter_font)
        self.cb_draw.text((xArray[5], 210), f"{self.TITLE_DICT[self.choice]}", color, font=self.counter_font)

        query_where = "WHERE bounty > 0" if self.choice == "bounty" else ""
        query = f"SELECT name, {self.SELECT_DICT[self.choice]}, DENSE_RANK() OVER(ORDER BY {self.ORDER_DICT[self.choice]} DESC) rank FROM stats {query_where} ORDER BY rank, name LIMIT $1 OFFSET $2"
        values = (self.PAGE_SIZE, self.offset)
        ordered_stats = await self.db.connect_db(query, values)


        for index, (name, choice_value, rank) in enumerate(ordered_stats):
            if self.value and not self.value.isdigit():
                color = (255, 255, 0) if name == self.pubg_name else self.WHITE

            if index == self.PAGE_SIZE/2:
                yAxis = Y_START

            if index < self.PAGE_SIZE/2:
                self.cb_draw.text((xArray[0], yAxis), f"#{rank}", color, font=self.counter_font, align="center")
                self.cb_draw.text((xArray[1], yAxis), f"{name}", color, font=self.counter_font)
                self.cb_draw.text((xArray[2], yAxis), f"{choice_value}", color, font=self.counter_font)
            else:
                self.cb_draw.text((xArray[3], yAxis), f"#{rank}", color, font=self.counter_font, align="center")
                self.cb_draw.text((xArray[4], yAxis), f"{name}", color, font=self.counter_font)
                self.cb_draw.text((xArray[5], yAxis), f"{choice_value}", color, font=self.counter_font)

            yAxis += ROW_HEIGHT

    async def generate_customboard(self, ctx: commands.Context, choice, value):
        if not choice:
            await self.client.embed_message(ctx, description="Choose a value to show. Use help command or forward slash to check which ones exist")
            return
        
        choice = choice.lower()

        if choice not in self.TITLE_DICT.keys():
            await self.client.embed_message(ctx, description="Value doesn't exist. Use help command or forward slash to check which ones exist")
            return
        
        await self.start_customboard(choice, value)

        member = await get_member(ctx, self.value)

        try:
            if self.value:
                if self.value.isdigit(): # Is a page number
                    self.page = int(self.value)
                    self.offset = (self.page-1)*self.PAGE_SIZE

                else:
                    await self.get_player_data(ctx, member)
        except StopIteration:
            return

        query_where = "WHERE bounty > 0" if self.choice == "bounty" else ""
        query = f"""SELECT count(*) FROM stats {query_where}"""
        row_count = await self.db.connect_db(query)
        max_page = math.ceil(row_count/self.PAGE_SIZE)

        if self.value and self.value.isdigit() and self.page > max_page:
            await self.client.embed_message(ctx, description="Page number can't be higher than number of pages")
            return

        self.cb_draw.text((1935, 57), f"Page {self.page}/{max_page}", self.WHITE, font=self.counter_font, anchor="ra")

        await self.write_customboard()
        
        cb_path = "./assets/images/customboardResult.png"
        self.customboard.save(cb_path)
        await ctx.send(file=discord.File(cb_path))


class Scoretable():
    WHITE = (255, 255, 255)
    PAGE_SIZE = 20
    
    with open("./assets/dictionaries/scoreTable.json", "r", encoding="utf-8") as f:
        scoretable_json = json.loads(f.read())

    def __init__(self, client: default.DiscordBot):
        self.client = client
        self.db = client.db

    async def start_scoretable(self, value):
        self.value = value
        self.page = 1
        self.offset = 0

        self.scoretable = Image.open("./assets/images/scoreTable.png")
        self.counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
        self.st_draw = ImageDraw.Draw(self.scoretable)

    async def write_scoretable(self):
        Y_START = 326
        ROW_HEIGHT = 116

        xArray = [102, 748, 930, 1576]
        yAxis = Y_START

        color = self.WHITE
        
        items = list(self.scoretable_json.items())

        for index, score_order in enumerate(range(self.offset, min(self.offset+self.PAGE_SIZE, len(items)))):
            key, score = items[score_order]

            if self.value and not self.value.isdigit():
                color = (255, 255, 0) if self.value.lower() == key.lower() else self.WHITE

            if index == self.PAGE_SIZE/2:
                yAxis = Y_START

            if index < self.PAGE_SIZE/2:
                self.st_draw.text((xArray[0], yAxis), f"{key}", color, font=self.counter_font)
                self.st_draw.text((xArray[1], yAxis), f"{score}", color, font=self.counter_font)
            else:
                self.st_draw.text((xArray[2], yAxis), f"{key}", color, font=self.counter_font)
                self.st_draw.text((xArray[3], yAxis), f"{score}", color, font=self.counter_font)

            yAxis += ROW_HEIGHT

    async def generate_scoretable(self, ctx: commands.Context, value):        
        await self.start_scoretable(value)

        if self.value:
            if self.value.isdigit(): # Is a page number
                self.page = int(self.value)
            else:
                position = next((index for index, item in enumerate(self.scoretable_json) if item.lower() == value.lower()), None)

                if not position:
                    await self.client.embed_message(ctx, description=f"Weapon {value} does not exist in the scoretable")
                    return

                self.page = math.ceil(position/self.PAGE_SIZE)

            self.offset = (self.page-1)*self.PAGE_SIZE

        max_page = math.ceil(len(self.scoretable_json)/self.PAGE_SIZE)

        if self.value and self.value.isdigit() and self.page > max_page:
            await self.client.embed_message(ctx, description="Page number can't be higher than number of pages")
            return

        self.st_draw.text((1725, 55), f"Page {self.page}/{max_page}", self.WHITE, font=self.counter_font, anchor="ra")

        await self.write_scoretable()
        
        st_path = "./assets/images/scoreTableResult.png"
        self.scoretable.save(st_path)
        await ctx.send(file=discord.File(st_path))


async def get_member(ctx, name):
    if name:
        with contextlib.suppress(commands.errors.MemberNotFound):
                return await commands.MemberConverter().convert(ctx, name)
