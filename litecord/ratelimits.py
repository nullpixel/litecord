import logging
import json
import asyncio

from aiohttp import web

from .utils import _err, _json

log = logging.getLogger(__name__)

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


async def gl_ratelimit_task(conn):
    try:
        _flags = conn.server.flags
        while True:
            conn.request_counter = 0
            await asyncio.sleep(_flags['ratelimits']['global_ws'][1])
    except asyncio.CancelledError:
        pass


def ws_ratelimit(special_bucket=None, requests=5, seconds=60):
    """Declare a ratelimited WS handler.

    TODO: make special_bucket + requests + seconds functional
    """

    def decorator(func):
        async def inner_func(conn, data):
            server = conn.server
            if not server.flags['ratelimits'].get('ws', False):
                return (await func(conn, data))

            default = [120, 60]
            global_requests = server.flags['ratelimits'].get('global_ws', default)[0]
            global_seconds = server.flags['ratelimits'].get('global_ws', default)[1]

            if conn.ratelimit_tasks.get('global') is None:
                conn.ratelimit_tasks['global'] = server.loop.create_task(gl_ratelimit_task(conn))

            ratelimits = server.ws_ratelimits
            max_requests = global_requests

            if conn.request_counter > max_requests:
                log.info(f"[ratelimit] Closing {conn!r} from WS ratelimiting.")
                await conn.ws.close(4008, 'You are being ratelimited.')
                return False

            res = (await func(conn, data))
            conn.request_counter += 1
            return res
        return inner_func

    return decorator
