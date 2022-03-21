from unicodedata import name
import discord
from discord.ext import commands, tasks
import math
import requests, re, random, time, datetime
from time import sleep as s
from requests_html import HTMLSession
import json
import psycopg2
from config import config
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
GUILD_ID = os.getenv('GUILD_ID')

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
        # {discord_id : [bet_amount, bet_side]}
        self.cur_bet = None
        self.betting_pool = 0
        self.bets_is_allowed = False
        self.streamer_id = None
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
            to_string = f'{i + 1}. {name} with {points}\n'
            to_strings += (to_string)
        await ctx.channel.send('```\n' + to_strings + '\n```')
        cur.close()

    @commands.command(name='payout_bet', help='Payout the current bet.')
    async def payout_bet(self, ctx, result: int):
        print(ctx.author.id)
        print(self.streamer_id)
        if int(ctx.author.id) == int(self.streamer_id) and self.is_bet_active:
            for user, bet in self.bets.items():
                if (bet[1] == result):
                    # change payout value here
                    payout = math.floor(0.8 * bet[0])
                else:
                    payout = -1 * bet[0]
                cur = conn.cursor()
                command = f"UPDATE \"ChannelPoints\" SET total_points = total_points + {payout} WHERE discord_id = '{user}';"
                cur.execute(command)
                conn.commit()
                cur.close()
            self.is_bet_active = False
            self.bets.clear()
            self.cur_bet = None
            self.streamer_id = None
            self.betting_pool = 0
            ctx.channel.send('Bets have been payed out.')
        else:
            await ctx.channel.send('Error paying out bet, either you are not the streamer or there is no bet active.')

    @payout_bet.error
    async def payout_bet_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            await ctx.channel.send('Forgot to include payout result (1 = Yes, 2 = No).')

    @commands.command(name='start_bet', help='Start a bet')
    async def start_bet(self, ctx, streamer_id_input, *bet):
        bet_identity = bet

        if (self.is_bet_active):
            await ctx.channel.send(f'Bet is currently active, please payout before making a new one')
        else:
            streamer_id = streamer_id_input.lstrip("<@!")
            streamer_id = streamer_id.rstrip(">")
            self.streamer_id = streamer_id
            self.is_bet_active = True
            self.bets_is_allowed = True
            self.bets = {}
            self.betting_pool = 0
            to_string = ""
            for word in bet_identity:
                to_string += word + " "
            self.cur_bet = to_string
            await ctx.channel.send(f'Starting bet now: {to_string}, you have 20 seconds to bet.')
            await ctx.channel.send(f'Remember: Command goes !join_bet <amount> <yes = 1/no = 2>')
            await asyncio.sleep(10)
            await ctx.channel.send(f'10 seconds left to bet')
            await asyncio.sleep(10)
            await ctx.channel.send(f'Bets are now closed')
            self.bets_is_allowed = False

    @start_bet.error
    async def start_bet_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            await ctx.channel.send(
                'Some error in starting bet, make sure you are doing !start_bet <@streamer> <what is the bet?>.')

    @commands.command(name='get_bet', help='Get the current bet')
    async def get_bet(self, ctx):
        if self.is_bet_active:
            await ctx.channel.send(f'{self.cur_bet}')
            person = self.client.get_user(int(self.streamer_id))
            await ctx.channel.send(f'Current streamer: {person}')
        else:
            await ctx.channel.send('No bets are currently active')

    @commands.command(name='join_bet', help='Join a bet')
    async def join_bet(self, ctx, amount: int, side: int):
        if self.bets_is_allowed:
            bet_amount = amount
            discord_id = ctx.author.id
            at_user = f'<@{discord_id}>'
            if (amount <= 0):
                ctx.channel.send(f'{at_user} Invalid bet: You cannot bet a negative amount.')

            elif side != 1 or side != 2:
                ctx.channel.send(f'{at_user} Invalid bet: The side can only be 1 or 2.')

            else:
                cur = conn.cursor()
                command = (f"SELECT total_points FROM \"ChannelPoints\" WHERE discord_id = \'{discord_id}\'")
                cur.execute(command)
                point_count = cur.fetchone()[0]
                cur.execute(command)
                cur.close()
                if (not discord_id in self.bets):
                    if (point_count >= bet_amount):
                        print('bet is valid')
                        self.bets[discord_id] = [bet_amount, side]
                        await ctx.channel.send(f'Sucessfully created a bet of {bet_amount} for {at_user}.')
                    else:
                        await ctx.channel.send(f'{at_user} Invalid bet: you bet more points than you have')
                else:
                    if (point_count >= bet_amount + self.bets[discord_id][0]):
                        print('bet is valid')
                        self.bets[discord_id][0] += bet_amount
                        await ctx.channel.send(
                            f'Sucessfully increased bet of {at_user} to a total of {self.bets[discord_id]}')
                    else:
                        await ctx.channel.send(f'{at_user} Invalid bet: you bet more points than you have')
        else:
            await ctx.channel.send('Sorry, bets are currently closed.')

    @join_bet.error
    async def join_bet_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            await ctx.channel.send('Forgot to include a bet amount or side of the bet (1 or 2)')

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
    async def get_streams(self, ctx):
        await ctx.channel.send(self.stream_list)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, prev, cur):
        if (cur.channel == None):
            if member.name in self.stream_list:
                self.stream_id_list.remove(member.id)
                self.stream_list.remove(member.name)

        if prev.channel and cur.channel:  # If a user is connected before and after the update
            if prev.self_stream != cur.self_stream:
                # cur.self_stream will return True whether they're currently streaming
                print("User's self-stream updated!")

                if cur.self_stream:
                    # currently started streaming
                    print('currently streaming')
                    self.someone_streaming = True
                    self.stream_list.append(member.name)
                    self.stream_id_List.append(member.id)

                else:
                    # stopped steraming
                    print('stopped streaming')
                    self.stream_id_List.remove(member.id)
                    self.stream_list.remove(member.name)
                    if (len(self.stream_list) == 0):
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
                if (len(self.stream_list) == 0):
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
                        if discord_id in self.league_accounts:
                            playing(self.league_accounts[discord_id], "NA")
                        if discord_id in accepted_users:
                            command = f"UPDATE \"ChannelPoints\" SET total_points = total_points + 10 WHERE discord_id = '{discord_id}';"
                            cur.execute(command)
                            conn.commit()
                    cur.close()


def setup(client):
    client.add_cog(Points(client))

ua_list = []
userList = re.sub('\r\n', '\n', str(requests.get('http://pastebin.com/raw/VtUHCwE6').text)).splitlines()
for x in userList:ua_list.append(x)
random.shuffle(ua_list)


def get_userAgent():
    return str(random.choice(ua_list))


pers_UA=get_userAgent()
headers={'user-agent': pers_UA,'accept-language': 'en-US,en;q=0.9',}
sess = requests.Session()


def check_playing(Region, Username):
    if 'is not in an active game' in sess.get('https://'+Region+'.op.gg/summoner/spectator/userName='+Username.replace(' ','+'), headers={'x-requested-with': 'XMLHttpRequest','user-agent': pers_UA,'accept-language': 'en-US,en;q=0.9',}).text:
        return 0
    else:
        return 1

def playing(Username, Region):
    while True:
        check = check_playing(Region, Username)
        if check == 0:
            opgg_website = sess.get('https://'+Region+'.op.gg/summoner/userName='+Username.replace(' ','+'), headers=headers)
            try:
                global r, session, current_time, possible_update
                session = HTMLSession()
                r = session.get('https://'+Region+'.op.gg/summoner/userName='+Username.replace(' ','+'), headers=headers)
                r.html.render(timeout=20)
                website = str(r.html.html)
                opgg_update = sess.post('https://'+Region+'.op.gg/summoner/ajax/renew.json/', headers=headers, data={'summonerId': re.findall(r'Id=[0-9]+', str(opgg_website.content))[0].strip('Id=')})
                if opgg_update.status_code == 200:
                    current_time = time.time()
                    possible_update=int(current_time)+180
                    game_history = []
                    x_val = 1
                    game_history.append(r.html.find('#SummonerLayoutContent > div.tabItem.Content.SummonerLayoutContent.summonerLayout-summary > div.RealContent > div > div.Content > div.GameItemList > div:nth-child('+str(x_val)+') > div > div.Content > div.GameStats > div.TimeStamp > span', first=True).text+':'+r.html.find('#SummonerLayoutContent > div.tabItem.Content.SummonerLayoutContent.summonerLayout-summary > div.RealContent > div > div.Content > div.GameItemList > div:nth-child('+str(x_val)+') > div > div.Content > div.GameStats > div.GameResult', first=True).text)
                    whitelist = ['1 minute','2 minutes','3 minutes','4 minutes']
                    filtered_stats = [f for f in game_history if all([word in f for word in whitelist])]
                    matches = []
                    for j in filtered_stats:
                        matches.append(j.split(':'))
                    stats_today = []
                    for i in range(len(matches)):
                        stats_today.append(matches[i][0])
                        stats_today.append(matches[i][1])
                    counted_today_dict = {i: stats_today.count(i) for i in stats_today}
                    try:
                        try:
                            wins = str(counted_today_dict['Victory'])
                        except:
                            print(Username + "did not win")
                            wins = 0
                        try:
                            lose = str(counted_today_dict['Defeat'])
                        except:
                            print(Username + "did not lose")
                            lose = 0
                            if lose == wins:
                                print("The game resulted in a remake")
                            elif lose > wins:
                                print(Username + " Lost")
                            else:
                                print(Username + " Won")
                    except Exception as e:
                        print('Bad request, verify playername and op.gg status...')
                elif opgg_update.status_code == 418 or 504:
                    current_time = time.time()
                    possible_update=int(re.search(r"e='(.*)' data-t", r.text)[1])+180
                    print('Player rate limited: '+Username+' | waiting until next possible Update @ '+datetime.datetime.fromtimestamp(possible_update).strftime('%H:%M:%S')+' ; relaying on older stats now')
                    s(possible_update-current_time)
                else:
                    print('\n'+opgg_update.text)
                    print('\nERROR: Op.gg responded unexpectedly (Code: '+opgg_update.status_code+'); Copy & Paste this error into Github > Issues.\n')
                    s(30)
                    exit()
            except Exception as e:
                print(e)
                pass
            r.session.close()
            r.close()
        elif check == 1:
            print('Player: '+Username+' currently ingame; will start checking for updates again once his game ends')
            s(random.uniform(8,15))