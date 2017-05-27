import discord
import asyncio
import logging
import json

logging.basicConfig(level=logging.DEBUG)

client = discord.Client()

@client.event
async def on_ready():
    print('Connected!')
    print('Username: ' + client.user.name)
    print('ID: ' + client.user.id)

    for i in range(130):
        await client.ws.send(json.dumps({
            'op': 1,
            'd': 0,
        }))
    print("Finished ratelimiting")

@client.event
async def on_message(message):
    if message.content.startswith('!editme'):
        msg = await client.send_message(message.channel, '10')
        await asyncio.sleep(3)
        await client.edit_message(msg, '40')

@client.event
async def on_message_edit(before, after):
    fmt = '**{0.author}** edited their message:\n{1.content}'
    await client.send_message(after.channel, fmt.format(after, before))

client.run('litecord_RLoWjnc45pDX2shufGjijfyPbh2kV0sYGz2EwARhIAs=')
