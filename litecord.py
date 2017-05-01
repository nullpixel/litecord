#!/usr/bin/env python3
import logging
from aiohttp import web
import asyncio
import json

import aiohttp
import litecord

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('init')

app = web.Application()

DATABASES = {
    'users': 'db/users.json',
    'guilds': 'db/guilds.json',
    'messages': 'db/messages.json',
    'tokens': 'db/tokens.json',
}

async def give_gateway(request):
    return web.Response(text=json.dumps({"url": "ws://0.0.0.0:12000"}))

async def index(request):
    return web.Response(text=json.dumps({"goto": "/api/gateway"}))

app.router.add_get('/', index)
app.router.add_get('/api/gateway', give_gateway)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    log.info("Starting gateway")

    gateway_task = loop.create_task(litecord.gateway_server(app, DATABASES))
    web.run_app(app, port=8000)
    gateway_task.cancel()
    loop.close()
