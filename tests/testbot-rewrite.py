import discord
import asyncio
import logging

discord.http.Route.BASE = 'http://litecord.memework.org:8000/api/v6'
#discord.http.Route.BASE = 'http://0.0.0.0:8000/api'
discord.http.Route.BASE = 'http://163.172.191.166:8000/api'
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

client.run('litecord_Prt3FEpPfiUFT4nwkFbgUSHF872sOjQWOjyE3m9PBTz0jlt2QsS-Oa2DEXuYUODxg4ONDmpd92J5112J7MbMnQ')
