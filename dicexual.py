import logging
from aiohttp import web
import asyncio
import json

import aiohttp
import dicexual

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('init')

app = web.Application()

async def give_gateway(request):
    log.info('Giving gateway URL')
    return web.Response(text=json.dumps({"url": "ws://0.0.0.0:12000"}))

async def index(request):
    return web.Response(text=json.dumps({"goto": "/api/gateway"}))

app.router.add_get('/', index)
app.router.add_get('/api/gateway', give_gateway)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    log.info("Starting gateway")

    gateway_task = loop.create_task(dicexual.gateway_server())
    web.run_app(app, port=8000)
    gateway_task.cancel()
    loop.close()
