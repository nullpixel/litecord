import logging
import json
import asyncio

from aiohttp import web

from .utils import _err, _json

log = logging.getLogger(__name__)


class GatewayRatelimitModes:
    CLOSE = 0
    IGNORE_PACKET = 1


"""

Handy ratelimit table:


REST:
        POST Message |  5/5s    | per-channel
      DELETE Message |  5/1s    | per-channel
 PUT/DELETE Reaction |  1/0.25s | per-channel
        PATCH Member |  10/10s  | per-guild
   PATCH Member Nick |  1/1s    | per-guild
      PATCH Username |  2/3600s | per-account
      |All Requests| |  50/1s   | per-account
WS:
     Gateway Connect |   1/5s   | per-account
     Presence Update |   5/60s  | per-session
 |All Sent Messages| | 120/60s  | per-session
"""

def ratelimit(requests=50, seconds=1, special_bucket=False):
    """Declare a ratelimited REST route.

    TODO: actual ratelimits.
    """

    # NOTE: ratelimits here are the same as discord's
    #  per-user, per-route, etc.
    #  However I don't know how do we do per-user, do we do per-IP?
    #  Needs more thinking.

    def decorator(func):
        async def inner_func(endpoint, request):
            server = endpoint.server
            if not server.flags.get('rest_ratelimits', False):
                return (await func(endpoint, request))

            ratelimits = endpoint.server.rest_ratelimits
            peername = request.transport.get_extra_info('peername')
            if peername is not None:
                host, port = peername
            else:
                log.warning("Request without client IP")

            return (await func(endpoint, request))
        return inner_func

    return decorator


class WSBucket:
    """Websocket ratelimiting Bucket.
    
    With this class you can specify certain requests that will close your connection with 4000
    or if they'll just ignore your packet completly.
    """
    def __init__(self, name, **kwargs):
        self.name = name
        self.mode = kwargs.get('mode', GatewayRatelimitModes.CLOSE)

        self.requests = kwargs.get('requests', 120)
        self.seconds = kwargs.get('seconds', 60)

    async def request_task(self, conn):
        try:
            while True: 
                conn.request_counter[self.name] = 0
                await asyncio.sleep(self.seconds)
        except asyncio.CancelledError:
            pass

    async def ratelimit(self, conn):
        if self.mode == GatewayRatelimitModes.CLOSE:
            log.info(f'[bucket:{self.name}] Closing {conn!r} with 4000')
            await conn.ws.close(4000, 'You are being ratelimited.')
            return False
        elif self.mode == GatewayRatelimitModes.IGNORE_PACKET:
            log.info(f'[bucket:{self.name}] Ignoting {conn!r} packets')
            return True


def ws_ratelimit(bucket_name='all'):
    """Declare a ratelimited WS function."""

    def decorator(handler):
        async def inner_handler(conn, payload):
            server = conn.server
            ratelimits = server.flags['ratelimits']

            if not ratelimits.get('ws'):
                return await handler(conn, payload)

            bucket = server.buckets.get(bucket_name)
            if bucket is None:
                log.warning(f'Bucket {bucket_name} not found, ignoring packet')
                return True

            if bucket_name not in conn.ratelimit_tasks:
                conn.ratelimit_tasks[bucket_name] = server.loop.create_task(bucket.request_task(conn))

            if bucket_name not in conn.request_counter:
                conn.request_counter[bucket_name] = 0

            if conn.request_counter[bucket_name] > bucket.requests: 
                return await bucket.ratelimit(conn)

            result = await handler(conn, payload)

            # We duplicate this piece of code because
            # when IDENTIFYing, conn.request_counter gets overwritten
            if bucket_name not in conn.request_counter:
                conn.request_counter[bucket_name] = 0

            #log.debug(f'[bucket:{bucket_name}] Add 1 to counter, {result}')
            conn.request_counter[bucket_name] += 1

            return result
        return inner_handler
    return decorator

