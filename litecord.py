#!/usr/bin/env python3
import logging
from aiohttp import web
import asyncio
import json

import aiohttp
import litecord

import litecord_config as config

logging.basicConfig(level=logging.DEBUG, \
    format='[%(levelname)7s] [%(name)s] %(message)s')

log = logging.getLogger('litecord')

handler = logging.FileHandler('litecord.log')
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - [%(levelname)s] [%(name)s] %(message)s')
handler.setFormatter(formatter)

log.addHandler(handler)

app = web.Application()

async def give_gateway(request):
    ws = config.flags['server']['ws']
    if len(ws) == 2:
        return web.Response(text=json.dumps({"url": f"ws://{ws[0]}:{ws[1]}"}))
    elif len(ws) == 3:
        return web.Response(text=json.dumps({"url": f"ws://{ws[2]}:{ws[1]}"}))

async def index(request):
    return web.Response(text=json.dumps({"goto": "/api/gateway"}))

def main():
    app.router.add_get('/', index)
    app.router.add_get('/api/gateway', give_gateway)

    loop = asyncio.get_event_loop()

    log.debug("[main] starting ws task")
    gateway_task = loop.create_task(litecord.gateway_server(app, config.flags))

    log.debug("[main] starting http")
    http_task = loop.create_task(litecord.http_server(app, config.flags))

    try:
        loop.run_forever()
    except:
        log.info("Exiting...")
        gateway_task.cancel()
        loop.close()

if __name__ == "__main__":
    main()
