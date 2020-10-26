import discord
import youtube_dl
from discord.ext import commands

youtube_dl.utils.bug_reports_message = lambda: ''

YTDL_FORMAT_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'options' : '-vn',
}

ytdl = youtube_dl.YoutubeDL(YTDL_FORMAT_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def open_stream(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)


class Music(commands.Cog):

    def __init__(self, client):
        self.client = client
    
    @commands.command(name='play')
    async def play(self, ctx, *, url):
        #Plays the audio from a given youtube url
        guild = ctx.message.guild
        voice_client = guild.voice_client
        
        async with ctx.typing():
            player = await YTDLSource.open_stream(url, loop=self.client.loop)
            voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
        await ctx.send('Now playing: {}'.format(player.title))
        await self.client.change_presence(
            activity=discord.Activity(
                name=f'{player.title}', 
                type=discord.ActivityType.listening
            )
        )

    @commands.command(name='stop')
    async def stop(self, ctx):
        #Stops the current voice client
        guild = ctx.message.guild
        voice_client = guild.voice_client
        channel = ctx.message.guild.voice_client
        voice_client.stop()
        await ctx.send(f'Stopped playing')

    @commands.command(name='pause')
    async def pause(self, ctx):
        #Pauses the currently playing song
        guild = ctx.message.guild
        voice_client = guild.voice_client

        if voice_client.is_playing():
            voice_client.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resume')
    async def resume(self, ctx):
        #Resumes a paused song
        guild = ctx.message.guild
        voice_client = guild.voice_client

        if voice_client.is_paused():
            voice_client.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='connect')
    async def connect(self, ctx):
        #Connects to the user's voice channel
        channel = ctx.author.voice.channel
        await channel.connect()
        print(f'Connected to {channel.name}')

    @commands.command(name='disconnect')
    async def disconnect(self, ctx):
        #Disconnects a bot from its current voice channel
        voice_channel = ctx.message.guild.voice_client
        await voice_channel.disconnect()


def setup(client):
    client.add_cog(Music(client))