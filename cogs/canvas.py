import discord
from discord.ext import commands
import requests
import json
import psycopg2
from config import config

URL = {
    "base" : "https://canvas.instructure.com/api/{version}/{module}",
    "courses" : "courses"
}
API_VERSION = "v1"

def select_user(user):
    conn = None
    try:
        params = config()
        print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)
        cur = conn.cursor()
        print('PostgreSQL database version:')
        command = (f"SELECT * FROM users WHERE name LIKE '{user}'")
        cur.execute(command)
        values = cur.fetchone()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
    return values

class CanvasAPI(object):
    def __init__(self, access_token):
        self.access_token = access_token
        self.api_version = API_VERSION
    
    def __request(self, module, params={}):
        args = {'access_token' : self.access_token}
        for key, value in params.items():
            if key not in args:
                args[key] = value

        response = requests.get(URL['base'].format(module=module, version=self.api_version), params=args)
        print(response.url)
        return response.json()
    
    def get_courses(self):
        return self.__request('courses')

class Canvas(commands.Cog):

    def __init__(self, client):
        self.client = client
    
    @commands.command(name='classes', help='List the classes for a given user.')
    async def list_classes(self, ctx, user):
        values = select_user(user)
        for value in values:
            print(f'{value}')

        access_token = values[2]
        api = CanvasAPI(access_token)
        r = api.get_courses()
        for course in r:
            await ctx.send(course['name'])


def setup(client):
    client.add_cog(Canvas(client))
