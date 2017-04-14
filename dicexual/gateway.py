import json
import websockets
import logging

from .basics import OP

log = logging.getLogger(__name__)

class Connection:
    def __init__(self, ws, path):
        self.ws = ws
        self.path = path

    def basic_hello(self):
        return {
            'op': OP["HELLO"],
            'd': {
                'heartbeat_interval': 40000,
                '_trace': [],
            }
        }

    async def run(self):
        # send OP HELLO
        log.info("Sending OP HELLO")
        await self.ws.send(json.dumps(self.basic_hello()))
        self.ws.close(1000, 'Exited?')

async def gateway_server():
    async def hello(websocket, path):
        log.info("Got new client, opening connection")
        connection = Connection(websocket, path)
        await connection.run()
        log.info("Stopped connection")

    log.info("Starting websocket server")
    start_server = websockets.serve(hello, '0.0.0.0', 12000)
    await start_server
    log.info("Finished gateway")
