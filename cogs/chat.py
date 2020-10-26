import discord
from discord.ext import commands

class Chat(commands.Cog):
    
    def __init__(self,client):
        self.client = client

    @commands.command(name='wipe', help='Clears specified amount.  If no number given, clears 5.')
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount=6):
        await ctx.channel.purge(limit=amount)

def setup(client):
    client.add_cog(Chat(client))