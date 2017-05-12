#!/usr/bin/env python3
import logging
from aiohttp import web
import asyncio
import json

import aiohttp
import litecord

logging.basicConfig(level=logging.DEBUG, \
    format='[%(levelname)7s] [%(name)s] %(message)s')

log = logging.getLogger('litecord')

app = web.Application()

async def give_gateway(request):
    return web.Response(text=json.dumps({"url": "ws://0.0.0.0:12000"}))

async def index(request):
    return web.Response(text=json.dumps({"goto": "/api/gateway"}))

def main():
    app.router.add_get('/', index)
    app.router.add_get('/api/gateway', give_gateway)

    loop = asyncio.get_event_loop()

    log.debug("[main] starting ws task")
    gateway_task = loop.create_task(litecord.gateway_server(app))

    log.debug("[main] starting http")
    web.run_app(app, port=8000)

    log.info("Exiting...")
    gateway_task.cancel()
    loop.close()

if __name__ == "__main__":
    main()
