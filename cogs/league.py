import discord
import requests
import json
import os

from discord.ext import commands
from dotenv import load_dotenv
from pathlib import Path

env_path = Path('discord_bot') / '.env'
load_dotenv(dotenv_path=env_path)

RIOT_API_KEY = os.getenv('RIOT_API_TOKEN')

URL = {
    'base' : 'https://{region}.api.riotgames.com/lol/{module}/{url}',
    'summoner_by_name' : 'v{version}/summoners/by-name/{name}',
    'current_game_by_name' : 'v{version}/active-games/by-summoner/{userId}'
}

API_VERSIONS = {
    'summoner' : '4',
    'spectator' : '4'
}

REGIONS = {
    'north_america' : 'na1',
    'korea' : 'kr'
}

class RiotAPI(object):

    def __init__(self, api_key, region=REGIONS['north_america']):
        self.api_key = api_key
        self.region = region
    
    def __request(self, module, api_url, params={}):
        args = {'api_key' : self.api_key}
        for key, value in params.items():
            if key not in args:
                args[key] = value

        response = requests.get(URL['base'].format(region=self.region, module=module, url=api_url), params=args)
        print(response.url)
        return response.json()

    def get_summoner_by_name(self, name):
        api_url = URL['summoner_by_name'].format(
            version=API_VERSIONS['summoner'],
            name=name
        )
        return self.__request('summoner', api_url)

    def get_current_game_by_name(self, id):
        api_url = URL['current_game_by_name'].format(
            version=API_VERSIONS['spectator'],
            userId=id
        )
        return self.__request('spectator', api_url)

    def getChamp(self, championId):
        directory = 'champion.json'
        with open(directory, encoding='utf-8') as f:
            overview = json.load(f)
        for champion_data in overview['data'].values():
            if str(championId) == champion_data['key']:
                return(champion_data['id'])


class League(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.command(name='search')
    async def search_in_game(self, ctx, *, summonerName):
        api_key = RIOT_API_KEY
        api = RiotAPI(api_key)
        r = api.get_summoner_by_name(summonerName)
        user_id = r['id']
        current_game = api.get_current_game_by_name(user_id)

        if 'status' in current_game:
            await ctx.channel.send(f'{summonerName} is not currently in a game.')
        else:
            for participant in current_game['participants']:
                if summonerName == participant['summonerName']:
                    champion = api.getChamp(participant['championId'])
                    print(f'{summonerName} is selling again on {champion}.')
                    await ctx.channel.send(f"{summonerName} is currently in game on {champion}.")


def setup(client):
    client.add_cog(League(client))