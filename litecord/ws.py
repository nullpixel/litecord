"""
ws - Websocket server
    This implements a basic websocket server
    that follows Discord's format in packets
    
    The `WebsocketServer` class implements checking of payloads
    and disconnects with proper error codes.

    `Connection` and `VoiceConnection` inherit from this class.
"""

import inspect

class StopConnection(Exception):
    pass

class PayloadLengthExceeded(Exception):
    pass

class Handler:
    """Describes a handler for a specific OP code."""
    def __init__(self, op, func):
        self.op = op
        self.func = func

    def is_mine(self, payload):
        return self.op == payload['op']

    def __repr__(self):
        return f'Handler({self.op}, {self.func})'

    async def run(self, payload):
        await self.func()

def handler(op):
    h = Handler(op)
    def inner(conn, payload):
        await a
    return inner

class WebsocketConnection:
    def __init__(self, ws):
        self.ws = ws

        self._handlers = {}
        self._register()

    def _register(self):
        """Register all handlers"""
        methods = inspect.getmembers(predicate=inspect.ismethod)

        for method_id, method in methods:
            if isinstance(method, Handler):
                log.debug(f'[ws] Adding handler {handler!r}')
                self._handlers.append(method)

    @property
    def is_compressable(self):
        """Used in :meth:`Connection` to check for discord.js
        since it doesn't like compression.
        """
        return True

    async def send(self, anything, compress=False) -> int:
        """Send anything through the websocket, if its a payload(dict)
        it gets encoded and processed.

        Parameters
        ----------
        anything: any
            Anything.
        compress: bool
            If thie payload will be compressed with ZLIB before sending.

        Returns
        -------
        int
            The amount of bytes transmitted.
        """
        if isinstance(anything, dict):
            anything = await self._encoder(anything)
            if compress and self.is_compressable:
                anything = zlib.compress(anything)

        await self.ws.send(anything)
        return len(anything)

    async def send_op(self, op, data=None):
        """Send a payload with an OP code.

        Parameters
        ----------
        op: int
            OP code to be sent.
        data: any
            OP code data.
        """
        if data is None:
            data = {}

        return await self.send({
            'op': op,
            'd': data,
        })

    async def recv(self):
        """Receive a payload from the websocket.
        Will be decoded.
        """
        raw = await self.ws.recv()
        if len(raw) > 4096:
            raise PayloadLengthExceeded()

        return await self._decoder(raw)

    async def process(self, payload):
        """Process a payload
        This checks for the payload's OP code
        and checks if a handler exists for that OP code.
        """
        for handler in self._handlers:
            if handler.is_mine(payload):
                await handler.run(self, payload['d'])

    async def _run(self):
        """Enter an infinite loop waiting for websocket packets"""
        try:
            while True:
                payload = await self.recv()
                await self.process(payload)
        except asyncio.CancelledError:
            log.info('[ws] Run task was cancelled')
            await self.ws.close(1006, 'Task was cancelled')
            self.clean()
        except StopConnection as sc:
            log.info('[ws] StopConnection: {sc!r}')
            await self.ws.close(sc.args[0], sc.args[1])
            self.clean()
        except websockets.ConnectionClosed as err:
            log.info('[ws] Closed with {err.code!r}, {err.reason!r}')
            self.clean()
        except Exception as err:
            log.error('Error while running', exc_info=True)
            await self.ws.close(4000, f'Unexpected error: {err!r}')
            self.clean()

        await self.ws.close(1000)

    async def run(self):
        """Can be overridden by classes to
        do anything before listening for payloads."""
        await self._run()
