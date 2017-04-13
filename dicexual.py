from sanic import Sanic
from sanic.response import json
import dicexual
import logging
import asyncio

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('init')

app = Sanic()

@app.route("/api/gateway")
async def give_gateway(request):
    log.info('Giving gateway URL')
    return json({"url": "ws://0.0.0.0:6969"})

@app.route("/")
async def index(response):
    return json({"goto": "/api/gateway"})

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    log.info("Starting gateway")
    gateway_task = loop.create_task(dicexual.gateway_server())

    app.run(host="0.0.0.0", port=8000)

    gateway_task.cancel()
    loop.close()
