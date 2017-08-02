import discord
import asyncio
import logging

#discord.http.Route.BASE = 'https://memework.org:8000/api'
discord.http.Route.BASE = 'http://localhost:8000/api'
logging.basicConfig(level=logging.DEBUG)

client = discord.Client()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    #await client.ws.close(4000)
    #await asyncio.sleep(3)
    chan = client.get_channel(150501171201)
    print(chan)

    async for message in chan.history():
        print(message)

@client.event
async def on_message(message):
    if message.content.startswith('%bye'):
        await message.channel.send('nNNOOOOOoOOoOoOoOoOOOOOOOoOoOoOoOOoooo')
        await client.ws.close(4000)

    if message.content.startswith('%hello'):
        await message.channel.send('asd')

# sexhouse
#client.run('MTQ5MjYwMDQ2MzM3.DGDbFw.oJBJSHHFQEk3UUNy8GGdFlBDpw8')

# local
client.run('MTQ5MjYwMDQ2MzM3.DFUWag.15nCARMffeCulxwbrM2uy5eUbF4')
