import os
import json

from utils import default
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()


FORSEN_URL = "https://api.pubg.com/shards/steam/players?filter[playerNames]=Forsenlol"

PUBG_API_KEY = os.environ["PUBG_API_KEY"]
PUBG_HEADER = {
    "Authorization": "Bearer " + PUBG_API_KEY,
    "Accept": "application/vnd.api+json",
    "Accept-Enconding": "gzip",
}

with open("./assets/dictionaries/damageCauserName.json", "r") as f:
    DAMAGE_CAUSER_NAME = json.loads(f.read())

with open("./assets/dictionaries/damageTypeCategory.json", "r") as f:
    DAMAGE_TYPE_CATEGORY = json.loads(f.read())


async def addRows(matchID):
    MATCH_URL = "https://api.pubg.com/shards/steam/matches/{}".format(matchID)

    MATCH_STAT = await default.requestAio(MATCH_URL, PUBG_HEADER)

    forsenDied = False
    attackId = 0

    ASSET_ID = MATCH_STAT["data"]["relationships"]["assets"]["data"][0]["id"]
    for i in MATCH_STAT["included"]:
        if i["type"] == "asset" and i["id"] == ASSET_ID:
            TELEMETRY_URL = i["attributes"]["URL"]

    TELEMETRY_DATA = await default.requestAio(TELEMETRY_URL, PUBG_HEADER)

    for i in TELEMETRY_DATA:
        if i["_T"] == "LogPlayerKillV2":
            if i["victim"]["name"] == "Forsenlol":
                if i["finisher"] is not None:
                    killer = i["finisher"]["name"]
                    health = i["finisher"]["health"]
                    location_x = float(i["finisher"]["location"]["x"])
                    location_y = float(i["finisher"]["location"]["y"])
                    location_z = float(i["finisher"]["location"]["z"])
                    location = [location_x, location_y, location_z]
                else:
                    killer = None
                    health = None
                    location = None
                if i["finishDamageInfo"]["damageTypeCategory"] is not None:
                    weapon = DAMAGE_TYPE_CATEGORY[i["finishDamageInfo"]["damageTypeCategory"]]
                else:
                    weapon = None
                if i["finishDamageInfo"]["distance"] is not None:
                    distance = i["finishDamageInfo"]["distance"]
                else:
                    distance = None
                causer = DAMAGE_CAUSER_NAME[i["finishDamageInfo"]["damageCauserName"]]
                date = i["_D"]

                print(killer)
                print(weapon)
                print(causer)
                print(distance)
                print(health)
                print(location)
                print(date)
                print(matchID)

                killsQuery = """INSERT INTO kills (NAME, WEAPON, CAUSER, DISTANCE, HEALTH, LOCATION, DATE, MATCH_ID) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
                killsInsert = (
                    killer,
                    weapon,
                    causer,
                    distance,
                    health,
                    location,
                    date,
                    matchID,
                )
                await default.connectDB(killsQuery, killsInsert)

                if i["finisher"] is not None:
                    statsQuery = """INSERT INTO stats (NAME, KILLS, DEATHS, DAMAGE_DEALT, SNIPAS_KILLED, DISTANCE_TRAVELLED, SUICIDES, SCORE, RANKING, BOUNTY) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (NAME) DO UPDATE SET KILLS=STATS.KILLS+%s"""
                    statsInsert = (killer, 1, 0, 0, 0, [0, 0, 0, 0, 0], 0, 0, 0, 0, 1)
                    await default.connectDB(statsQuery, statsInsert)

                with open("./assets/dictionaries/scoreTable.json", "r") as f:
                    scoreTable = json.loads(f.read())

                score = scoreTable[causer]
                print(causer)
                print(score)

                if i["finisher"] is not None:
                    scoreQuery = """UPDATE stats SET SCORE=STATS.SCORE+%s WHERE NAME LIKE %s"""
                    scoreInsert = (score, killer)
                    await default.connectDB(scoreQuery, scoreInsert)

                rankingQuery = """WITH cte AS (SELECT name, DENSE_RANK() OVER(ORDER BY score DESC) ranking FROM stats) UPDATE stats SET ranking = cte.ranking FROM cte WHERE stats.name LIKE cte.name"""
                await default.connectDB(rankingQuery)

    # break

    snipaQuery = """SELECT name FROM stats WHERE NAME NOT IN ('Forsenlol') GROUP BY name"""
    snipaNames = await default.connectDB(snipaQuery)
    snipaNames = [r[0] for r in snipaNames]

    bountyQuery = """SELECT name, bounty FROM stats WHERE NAME NOT IN ('Forsenlol') GROUP BY name HAVING bounty > 0"""
    bountyNames = await default.connectDB(bountyQuery)

    for i in TELEMETRY_DATA:
        if i["_T"] == "LogPlayerKillV2":
            if forsenDied is False or i["attackId"] == attackId:
                if i["victim"]["name"] == "Forsenlol":
                    attackId = i["attackId"]
                    forsenDied = True

                if i["victim"]["name"] in snipaNames or i["victim"]["name"] == "Forsenlol":
                    deaths = 0
                    snipasKilled = 0
                    suicides = 0

                    distanceOnFoot = i["victimGameResult"]["stats"]["distanceOnFoot"]
                    distanceOnSwim = i["victimGameResult"]["stats"]["distanceOnSwim"]
                    distanceOnVehicle = i["victimGameResult"]["stats"]["distanceOnVehicle"]
                    distanceOnParachute = i["victimGameResult"]["stats"]["distanceOnParachute"]
                    distanceOnFreefall = i["victimGameResult"]["stats"]["distanceOnFreefall"]
                    distanceTravelled = [
                        distanceOnFoot,
                        distanceOnSwim,
                        distanceOnVehicle,
                        distanceOnParachute,
                        distanceOnFreefall,
                    ]

                    if i["finisher"] is not None and i["finisher"]["name"] == "Forsenlol":
                        deaths = 1

                    if i["isSuicide"] is True:
                        suicides = 1

                    statsQuery = """UPDATE stats SET DEATHS=STATS.DEATHS+%s,DISTANCE_TRAVELLED[1]=STATS.DISTANCE_TRAVELLED[1]+%s, DISTANCE_TRAVELLED[2]=STATS.DISTANCE_TRAVELLED[2]+%s,
                    DISTANCE_TRAVELLED[3]=STATS.DISTANCE_TRAVELLED[3]+%s,DISTANCE_TRAVELLED[4]=STATS.DISTANCE_TRAVELLED[4]+%s,DISTANCE_TRAVELLED[5]=STATS.DISTANCE_TRAVELLED[5]+%s,
                    SUICIDES=STATS.SUICIDES+%s WHERE NAME LIKE %s"""
                    statsInsert = (
                        deaths,
                        distanceTravelled[0],
                        distanceTravelled[1],
                        distanceTravelled[2],
                        distanceTravelled[3],
                        distanceTravelled[4],
                        suicides,
                        i["victim"]["name"],
                    )
                    await default.connectDB(statsQuery, statsInsert)

                    # break

                    if (
                        i["finisher"] is not None
                        and i["finisher"]["name"] in snipaNames
                        and i["victim"]["name"] != "Forsenlol"
                    ):
                        snipasKilled = 1
                        statsQuery = """UPDATE stats SET SNIPAS_KILLED=STATS.SNIPAS_KILLED+%s WHERE NAME LIKE %s"""
                        statsInsert = (snipasKilled, i["finisher"]["name"])
                        await default.connectDB(statsQuery, statsInsert)

                for bounty in bountyNames:
                    if (
                        i["finisher"] is not None
                        and bounty[0] == i["victim"]["name"]
                        and i["finisher"]["name"] in snipaNames
                    ):
                        statsQuery = """UPDATE stats SET SCORE=STATS.SCORE+%s WHERE NAME LIKE %s"""
                        statsInsert = (bounty[1], i["finisher"]["name"])
                        await default.connectDB(statsQuery, statsInsert)
                        break

        if i["_T"] == "LogPlayerTakeDamage":
            if forsenDied is False or i["attackId"] == attackId:
                if i["victim"]["name"] == "Forsenlol":
                    attacker = i["attacker"]
                    if attacker is not None:
                        attacker = i["attacker"]["name"]
                        damageDealt = i["damage"]

                        statsQuery = """UPDATE stats SET DAMAGE_DEALT=STATS.DAMAGE_DEALT+%s WHERE NAME LIKE %s"""
                        statsInsert = (damageDealt, attacker)
                        await default.connectDB(statsQuery, statsInsert)

    # break
