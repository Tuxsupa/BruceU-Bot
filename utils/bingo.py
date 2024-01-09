from datetime import datetime

import discord
import textwrap
from PIL import Image, ImageFont, ImageDraw


class Bingo():
    def __init__(self, client):
        self.client = client
        self.db = client.db

    async def draw_emote(self):
        time_now = datetime.now()
        day_of_week = time_now.isoweekday()
        
        if day_of_week != 5: # Not Friday
            emote = Image.open("./assets/images/forsenJoy.png")
        else: # It's Friday
            emote = Image.open("./assets/images/RebeccaBlack.png")

        emote = emote.resize((200, 200))

        MIDDLE_COORDS = (645, 645)
        if emote.mode == "RGB":
            self.bingo.paste(emote, MIDDLE_COORDS)
        else:
            self.bingo.paste(emote, MIDDLE_COORDS, emote)

    async def get_bingo_data(self, user):
        query = """SELECT lines FROM cache_bingo WHERE owner_id=$1"""
        values = (user.id,)
        cache_bingo = await self.db.connect_db(query, values)

        if not cache_bingo:
            query = """SELECT line FROM bingo ORDER BY random() LIMIT 25"""
            cache_bingo = await self.db.connect_db(query)

            query = """INSERT INTO cache_bingo (owner_id, lines) VALUES ($1, $2)"""
            values = (user.id, cache_bingo)
            await self.db.connect_db(query, values)

        return cache_bingo

    async def draw_bingo(self, cache_bingo):
        xRow = 0
        yRow = 0
        WHITE = (255, 255, 255)
        ROW_WIDTH = 4

        for line in cache_bingo:
            if xRow > ROW_WIDTH:
                xRow = 0
                yRow += 1

            if xRow == ROW_WIDTH/2 and yRow == ROW_WIDTH/2:
                xRow += 1
                continue

            text = textwrap.fill(text=line, width=10)
            coords = (150+(300*xRow), 150+(300*yRow))
            self.bingo_draw.text(coords, text, color=WHITE, font=self.counter_font, anchor="mm", align="center")

            xRow += 1

    async def create_bingo_card(self, user: discord.Member):
        self.bingo = Image.open("./assets/images/bingo.png")
        self.counter_font = ImageFont.truetype("./assets/fonts/MYRIADPRO-REGULAR.ttf", 50)
        self.bingo_draw = ImageDraw.Draw(self.bingo)

        await self.draw_emote()

        cache_bingo = await self.get_bingo_data(user)

        await self.draw_bingo(cache_bingo)
        
        self.bingo.save("./assets/images/bingoResult.png")
        file = discord.File("./assets/images/bingoResult.png", filename="bingoResult.png")

        embed = discord.Embed(title=f"{user.display_name}'s bingo card", color=0x000000, timestamp=datetime.now())
        embed.set_image(url="attachment://bingoResult.png")
        embed.set_author(name=user, icon_url=user.display_avatar.url)
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=self.client.DEV.display_avatar.url)

        return file, embed

    async def auto_bingo_db(self, ctx, choice):
        choice = choice.lower()

        autobingo = choice == "opt-in"
        query = """INSERT INTO user_settings (user_id, autobingo_dm) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET autobingo_dm=$3"""
        values = (ctx.author.id, autobingo, autobingo)
        await self.client.db.connect_db(query, values)
        await self.client.embed_message(ctx, description=f"You {choice} auto bingo card sent to your DM's")

    async def bingo_online_event(self):
        query = """SELECT user_id, autobingo_dm FROM user_settings"""
        user_settings = await self.db.connect_db(query)

        for user_id, autobingo in user_settings:
            if not autobingo:
                continue

            if user := self.client.get_user(user_id):
                file, embed = await self.create_bingo_card(user)
                embed.description = (f"You can use {self.client.command_prefix}bingo opt-out to stop getting automatic bingo cards")

                try:
                    await user.send(file=file, embed=embed)
                except discord.Forbidden:
                    print("Couldn't send DM with bingo")

    async def bingo_offline_event(self):
        query = """TRUNCATE TABLE cache_bingo"""
        await self.db.connect_db(query)