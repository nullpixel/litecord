import logging
import json

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

def ws_ratelimit(requests=120, seconds=60, special_bucket=False):
    """Declare a ratelimited WS function.

    TODO: actual ratelimits
    """

    def decorator(func):
        async def inner_func(conn, data):
            server = conn.server
            if not server.flags.get('ws_ratelimits', False):
                return (await func(conn, data))

            ratelimits = server.ws_ratelimits
            host, port = conn.ws.remote_address

            return (await func(conn, data))
        return inner_func

    return decorator

def admin_endpoint(handler):
    """Declare an Admin Endpoint.

    Admin Endpoints in Litecord are endpoints that can only be accessed by
    users who have administrator powers.

    To make a user an admin, set the `admin` field in the raw user
    object to boolean `true`.
    """
    async def inner_handler(endpoint, request):
        server = endpoint.server

        _error = await endpoint.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        user = endpoint.server._user(_error_json['token'])

        # pretty easy actually
        if not user.admin:
            log.warning(f"{user!s} tried to use an admin endpoint")
            return _err(errno=40001)

        return (await handler(endpoint, request, user))
    return inner_handler
