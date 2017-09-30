"""
ws - Websocket server
    This implements a basic websocket server
    that follows Discord's format in packets
    
    The `WebsocketServer` class implements checking of payloads
    and disconnects with proper error codes.

    `Connection` and `VoiceConnection` inherit from this class.
"""

import json
import inspect
import logging
import asyncio
import zlib
import pprint

import websockets

try:
    import earl
except ImportError:
    print('Running without ETF support')

from .err import InvalidateSession
from .enums import CloseReasons, CloseCodes

log = logging.getLogger(__name__)

class StopConnection(Exception):
    pass

class PayloadLengthExceeded(Exception):
    pass

class Handler:
    """Describes a handler for a specific OP code."""
    def __init__(self, op):
        self.op = op
        self.func = None

    def is_mine(self, payload):
        return self.op == payload['op']

    def __call__(self, func):
        self.func = func
        self.__doc__ = func.__doc__
        return self

    def __repr__(self):
        return f'Handler({self.op}, {self.func})'

    async def run(self, conn, payload):
        await self.func(conn, payload)


def handler(op):
    return Handler(op)


async def decode_dict(data):
    """Decode a dictionary that all strings are in `bytes` type.
    
    Returns
    -------
    dict
        The decoded dictionary with all strings in UTF-8.
    """
    if isinstance(data, bytes):
        return str(data, 'utf-8')
    elif isinstance(data, dict):
        _copy = dict(data)
        for key in _copy:
            data[await decode_dict(key)] = await decode_dict(data[key])
        return data
    else:
        return data


async def json_encoder(obj):
    return json.dumps(obj)

async def json_decoder(raw_data):
    return json.loads(raw_data)

async def etf_encoder(obj):
    return earl.pack(obj)

async def etf_decoder(raw_data):
    data = earl.unpack(raw_data)

    # Earl makes all keys and values bytes object.
    # We convert them into UTF-8
    if isinstance(data, dict):
        data = await decode_dict(data)

    return data


def get_data_handlers(name):
    if name == 'json':
        return json_encoder, json_decoder
    elif name == 'etf':
        return etf_encoder, etf_decoder


class WebsocketConnection:
    def __init__(self, ws):
        self.ws = ws
        self.loop = ws.loop

        self._handlers = [] 
        self._register()

    def _register(self):
        """Register all handlers"""
        methods = inspect.getmembers(self)

        for method_id, method in methods:
            if isinstance(method, Handler):
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
        log.debug('[ws:send] %s', pprint.pformat(anything))
        anything = await self._encoder(anything)

        if compress and self.is_compressable:
            anything = zlib.compress(anything.encode())

        try:
            await self.ws.send(anything)
        except Exception: return 0

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

        Returns
        -------
        any
        """
        raw = await self.ws.recv()
        if len(raw) > 4096:
            raise PayloadLengthExceeded()

        payload = await self._decoder(raw)
        log.debug('[ws:recv] %s', pprint.pformat(payload))
        return payload

    async def _process(self, payload):
        """Process a payload
        This checks for the payload's OP code
        and checks if a handler exists for that OP code.
        """
        for handler in self._handlers:
            if handler.is_mine(payload):
                log.debug('Handling OP %d', payload['op'])
                await handler.run(self, payload.get('d'))
                return

        raise StopConnection(4001, f'opcode not found: {payload["op"]}')
    
    async def process(self, payload):
        """Can be overwritten."""
        return await self._process(payload)

    async def _clean(self):
        """Search for a cleanup method and call it"""
        if hasattr(self, 'cleanup'):
            await self.cleanup()

    async def _run(self):
        """Enter an infinite loop waiting for websocket packets"""
        try:
            while True:
                payload = await self.recv()
                await self.process(payload)
        except (PayloadLengthExceeded, earl.DecodeError, json.JSONDecodeError):
            await self.ws.close(CloseCodes.DECODE_ERROR, 'Decoding Error')
        except asyncio.CancelledError:
            log.info('[ws] Run task was cancelled')
            await self.ws.close(1006, 'Task was cancelled')
        except StopConnection as sc:
            log.info('[ws] StopConncection: %r', sc)

            sc_args = sc.args
            c_code = sc.args[0]
            if len(sc_args) == 1:
                await self.ws.close(c_code, reason=CloseReasons.get(c_code))
            elif len(sc_args) == 2:
                await self.ws.close(c_code, reason=sc.args[1])

        except websockets.ConnectionClosed as err:
            log.info('[ws] Closed with %d, %r', err.code, err.reason)
        except InvalidateSession as err:
            resumable = err.args[0]
            if not resumable:
                await self._clean()
            pass
        except Exception as err:
            log.error('Error while running', exc_info=True)
            await self.ws.close(4000, f'Unexpected error: {err!r}')
            await self._clean()
            return

        await self._clean()
        if self.ws.open:
            await self.ws.close(1000)

    async def clean(self):
        log.debug('cleaning')

    async def run(self):
        """Can be overridden by classes to
        do anything before listening for payloads."""
        await self._run()



