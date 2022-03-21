from unicodedata import name
import discord
from discord.ext import commands, tasks
import requests
import json
import psycopg2
from config import config
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
GUILD_ID = os.getenv('GUILD_ID')

print(POSTGRES_PASSWORD)

accepted_users = []

try:
    params = config()
    print('Connecting to the PostgreSQL database...')
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    command = (f"SELECT discord_id FROM \"ChannelPoints\"")
    cur.execute(command)
    values = cur.fetchall()
    print(values)
    for val in values:
        accepted_users.append(int(val[0]))
    cur.close()
except (Exception, psycopg2.DatabaseError) as error:
    print(error)

class Points(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.stream_list = []
        self.stream_id_List = []
        self.someone_streaming = False
        self.bets = {}
        self.betting_pool = 0
        self.is_bet_active = False
        self.give_points.start()

    
    @commands.command(name='reg', help='Add a user to the channel points list.')
    @commands.has_permissions(kick_members=True)
    async def reg(self, ctx, desired_name):
        print(desired_name)
        cur = conn.cursor()
        my_id = str(ctx.author.id)
        print(my_id)
        command = (f'SELECT discord_id FROM \"ChannelPoints\";')
        cur.execute(command)
        active_chatters = cur.fetchall()
        found = False
        for chatter in active_chatters:
            print(chatter)
            if my_id in chatter:
                found = True
        at_user = f'<@{my_id}>'

        if found:
            await ctx.channel.send(f'{at_user} is already registered.')
        else:
            command = f'INSERT INTO \"ChannelPoints\" (discord_id, name, total_points) VALUES(\'{my_id}\', \'{desired_name}\', 0);'
            print(command)
            cur.execute(command)
            conn.commit()
            await ctx.channel.send(f'{at_user} is now registered.')
        cur.close()

    @reg.error
    async def reg_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            await ctx.channel.send('Forgot to include a name to go by.')

    @commands.command(name='point_leaders', help='List the top 3 point leaders.')
    async def point_leaders(self, ctx):
        cur = conn.cursor()
        command = (f"SELECT * FROM \"ChannelPoints\" ORDER BY total_points DESC LIMIT 2;")
        cur.execute(command)
        point_leaders = cur.fetchall()

        to_strings = ""
        for i in range(2):
            name = point_leaders[i][1]
            points = point_leaders[i][2]
            to_string = f'{i+1}. {name} with {points}\n'
            to_strings += (to_string)
        await ctx.channel.send('```\n' + to_strings + '\n```')
        cur.close()

    @commands.command(name='update_streams', help='Manually update stream status.')
    @commands.has_permissions(kick_members=True)
    async def update_streams(self, ctx):
        print(ctx.guild.id)
        if ctx.author.voice.channel:
            for member in ctx.author.voice.channel.members:
                if member.voice.self_stream and member.name not in self.stream_list:
                    self.stream_list.append(member.name)
                    self.stream_id_list.append(member.id)
                    self.someone_streaming = True
    
    @commands.command(name='get_streams', help='List the current users streaming.')
    async def get_streams(self,ctx):
        await ctx.channel.send(self.stream_list)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, prev, cur):
        if(cur.channel == None):
            if member.name in self.stream_list:
                self.stream_id_list.remove(member.id)
                self.stream_list.remove(member.name)

        if prev.channel and cur.channel:  # If a user is connected before and after the update
            if prev.self_stream != cur.self_stream:
                # cur.self_stream will return True whether they're currently streaming
                print("User's self-stream updated!")

                if cur.self_stream:
                    #currently started streaming
                    print('currently streaming')
                    self.someone_streaming = True
                    self.stream_list.append(member.name)
                    self.stream_id_List.append(member.id)

                else:
                    # stopped steraming
                    print('stopped streaming')
                    self.stream_id_List.remove(member.id)
                    self.stream_list.remove(member.name)
                    if(len(self.stream_list) == 0):
                        self.someone_streaming = False

    @tasks.loop(seconds=10)
    async def give_points(self):
        print(self.someone_streaming)
        print(self.stream_list)

        guild = self.client.get_guild(int(GUILD_ID))

        self.someone_streaming = bool(self.stream_list)
        for member_id in self.stream_id_List:
            is_still_streaming = False
            for channel in guild.voice_channels:
                for member in channel.members:
                    if member_id == member.id:
                        is_still_streaming = True
                    if member.voice.self_stream and member.name not in self.stream_list:
                        self.stream_list.append(member.name)
                        self.stream_id_list.append(member.id)
                        self.someone_streaming = True
            if not is_still_streaming:
                member = self.client.get_user(member_id).name
                self.stream_list.remove(member)
                self.stream_id_list.remove(member_id)
                if(len(self.stream_list) == 0):
                    self.someone_streaming = False

        if self.someone_streaming:
            for channel in guild.voice_channels:
                channel_has_stream = False
                for user in channel.members:
                    if user.voice.self_stream:
                        channel_has_stream = True
                        break
                if channel_has_stream:
                    cur = conn.cursor()
                    for user in channel.members:
                        discord_id = user.id
                        if discord_id in accepted_users:
                            command = f"UPDATE \"ChannelPoints\" SET total_points = total_points + 10 WHERE discord_id = '{discord_id}';"
                            cur.execute(command)
                            conn.commit()
                    cur.close()


def setup(client):
    client.add_cog(Points(client))
