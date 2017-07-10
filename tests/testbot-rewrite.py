import discord
import asyncio
import logging

discord.http.Route.BASE = 'https://litecord.memework.org/api/v6'
#discord.http.Route.BASE = 'http://0.0.0.0:8000/api'
logging.basicConfig(level=logging.DEBUG)

client = discord.Client()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

client.run('litecord_UaHqNdtGmxprmE4tO3NxieEYfcebJbZj9TZ-lQQd1SNFwgU6Vr0uEPL7tHhbmoZaGx1H4cYMCHBbgiNYk7yxtg')
#client.run('litecord_V00yci0oqnSpcor-HZqA_FZIBGwknysHbCYChZIuQ1QJUKaBW_HqEtZWB2MGLnVlK8zymdW5pchBDZOPtPhIbQ')
