import discord

from utils import default
from discord.ext import commands


class Meme_Commands(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.hybrid_command(description="Shows memes")
    async def lm(self, ctx, *, meme):
        discordSelectQuery = (
            """SELECT name, content, upvotes, downvotes FROM memes WHERE name = LOWER(%s) AND name !~* 'the_'"""
        )
        discordSelectInsert = (meme,)
        discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)
        if discordSelect and len(discordSelect) > 0:
            discordUpdateQuery = """UPDATE memes SET views[1] = memes.views[1]+%s WHERE name = %s"""
            discordUpdateInsert = (1, discordSelect[0][0])
            await default.connectDB(discordUpdateQuery, discordUpdateInsert)

            votes = len(discordSelect[0][2]) - len(discordSelect[0][3])
            text = "({}) Meme '{}': {}".format(votes, discordSelect[0][0], discordSelect[0][1])
            reaction = await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
            await reaction.add_reaction("⬆️")
            await reaction.add_reaction("⬇️")

    @commands.hybrid_command(description="Shows random memes")
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def rm(self, ctx):
        discordSelectQuery = (
            """SELECT name, content, upvotes, downvotes FROM memes WHERE name !~* 'the_' ORDER BY random() LIMIT 1"""
        )
        discordSelect = await default.connectDB(discordSelectQuery)
        if discordSelect and len(discordSelect) > 0:
            discordUpdateQuery = """UPDATE memes SET views[2] = memes.views[2]+%s WHERE name = %s"""
            discordUpdateInsert = (1, discordSelect[0][0])
            await default.connectDB(discordUpdateQuery, discordUpdateInsert)

            votes = len(discordSelect[0][2]) - len(discordSelect[0][3])
            text = "({}) Meme '{}': {}".format(votes, discordSelect[0][0], discordSelect[0][1])
            reaction = await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
            await reaction.add_reaction("⬆️")
            await reaction.add_reaction("⬇️")

    @commands.command(description="Meme Leaderboard")
    async def ml(self, ctx):
        # rankingQuery = sql.SQL("SELECT name, ROW_NUMBER() OVER (ORDER BY damage_dealt DESC, name) AS rows from stats")

        # discordSelectQuery = """SELECT name, views, upvotes, downvotes, id, created_at FROM memes WHERE name = LOWER(%s)"""
        # discordSelectInsert = (meme,)
        # discordSelect = await connectDB(discordSelectQuery, discordSelectInsert)

        embed = discord.Embed(
            title="Meme Leaderboard",
            description=None,
            color=0x000000,
            timestamp=ctx.message.created_at,
        )

        discordSelectQuery = """SELECT name, upvotes, downvotes FROM memes ORDER BY (array_length(upvotes, 1)-array_length(downvotes, 1)) DESC NULLS LAST LIMIT 10"""
        discordSelect = await default.connectDB(discordSelectQuery)

        if discordSelect and len(discordSelect) > 0:
            text = ""
            counter = 1
            for meme in discordSelect:
                votes = len(meme[1]) - len(meme[2])
                text = text + "#{} {} - ({}) votes\n".format(counter, meme[0], votes)
                counter = counter + 1

            embed.add_field(name="Top 10 Best", value=text, inline=True)

        discordSelectQuery = """SELECT name, upvotes, downvotes FROM memes ORDER BY (array_length(upvotes, 1)-array_length(downvotes, 1)) ASC NULLS LAST LIMIT 10"""
        discordSelect = await default.connectDB(discordSelectQuery)

        if discordSelect and len(discordSelect) > 0:
            text = ""
            counter = 1
            for meme in discordSelect:
                votes = len(meme[1]) - len(meme[2])
                text = text + "#{} {} - ({}) votes\n".format(counter, meme[0], votes)
                counter = counter + 1

            embed.add_field(name="Top 10 Worst", value=text, inline=True)

        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Bot made by Tuxsuper", icon_url=default.DEV.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot is False:
            if reaction.message.author.id == self.client.user.id:
                if ") Meme '" in reaction.message.content:
                    splitted = reaction.message.content.split(") Meme '", 1)[1]
                    splitted = splitted.split("': ", 1)
                    name = splitted[0]
                    discordSelectQuery = """SELECT upvotes, downvotes FROM memes WHERE name = %s"""
                    discordSelectInsert = (name,)
                    discordSelect = await default.connectDB(discordSelectQuery, discordSelectInsert)

                    if reaction.emoji == "⬆️":
                        if user.id not in discordSelect[0][0]:
                            if user.id in discordSelect[0][1]:
                                discordUpdateQuery = (
                                    """UPDATE memes SET downvotes = array_remove(downvotes, %s) WHERE name = %s"""
                                )
                                discordUpdateInsert = (user.id, name)
                                await default.connectDB(discordUpdateQuery, discordUpdateInsert)

                            discordUpdateQuery = """UPDATE memes SET upvotes = upvotes || %s WHERE name = %s"""
                            discordUpdateInsert = (user.id, name)
                            await default.connectDB(discordUpdateQuery, discordUpdateInsert)

                    elif reaction.emoji == "⬇️":
                        if user.id not in discordSelect[0][1]:
                            if user.id in discordSelect[0][0]:
                                discordUpdateQuery = (
                                    """UPDATE memes SET upvotes = array_remove(upvotes, %s) WHERE name = %s"""
                                )
                                discordUpdateInsert = (user.id, name)
                                await default.connectDB(discordUpdateQuery, discordUpdateInsert)

                            discordUpdateQuery = """UPDATE memes SET downvotes = downvotes || %s WHERE name = %s"""
                            discordUpdateInsert = (user.id, name)
                            await default.connectDB(discordUpdateQuery, discordUpdateInsert)


async def setup(client):
    await client.add_cog(Meme_Commands(client))
