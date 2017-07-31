import asyncio
import urllib.parse as urlparse
import logging

import websockets

from litecord.ws import WebsocketConnection, handler, StopConnection, get_data_handlers
from litecord.basics import OP

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class Connection(WebsocketConnection):
    """An example on how WebsocketConnection will look.
    
    Attributes
    ----------
    ws: websocket
        the actual websocket
    """
    def __init__(self, ws, **kwargs):
        super().__init__(ws)
        self.config = kwargs['config']
        self._encoder, self._decoder = get_data_handlers(self.config[1])
        self.hb_interval = 1000

    async def heartbeat_canceller(self):
        """Wait the interval and close the connection."""
        try:
            await asyncio.sleep((self.hb_interval / 1000) + 3)
            raise StopConnection(4000, 'Heartbeat period expired.')
        except asyncio.CancelledError:
            pass

    @handler(OP.HEARTBEAT)
    async def heartbeat_handler(self, data):
        """Handle OP 1 Heartbeat packets. sends OP 11 Heartbeat ACK."""
        print('RECV HEARTBEAT')
        try:
            self.wait_task.cancel()
        except AttributeError: pass

        try:
            self.events['recv_seq'] = data
        except AttributeError: pass

        await self.send_op(OP.HEARTBEAT_ACK, {})
        self.wait_task = self.loop.create_task(self.heartbeat_canceller())

    async def run(self):
        """Starts an infinite loop waiting for paylods,
        since this is Discord, we modify this function to
        send an OP 10 Hello payload before actuallly
        listening to payloads.
        """
        await self.send_op(OP.HELLO, {'heartbeat_interval': self.hb_interval})

        # this is from WebsocketConnection
        await self._run()

async def henlo(ws, path):
    """Called on a new connection."""
    log.info('[ws] henlo')

    # first, we parse the URL
    params = urlparse.parse_qs(urlparse.urlparse(path).query)

    gw_version = params.get('v', [6])[0]
    encoding = params.get('encoding', ['json'])[0]

    try:
        gw_version = int(gw_version)
    except ValueError:
        gw_version = 6

    if encoding not in ('json', 'etf'):
        await ws.close(4000, f'encoding not supported: {encoding!r}')
        return

    if gw_version != 6:
        await ws.close(4000, f'gw version not supported: {gw_version}')
        return

    conn = Connection(ws, config=(gw_version, encoding))

    # this starts an infinite loop waiting for payloads from the client
    await conn.run()

if __name__ == '__main__':
    logging.info('starting')
    loop = asyncio.get_event_loop()
    ws_server = websockets.serve(henlo, host='0.0.0.0', port=8000)
    loop.create_task(ws_server)
    loop.run_forever()
    loop.close()
    logging.info('end')

