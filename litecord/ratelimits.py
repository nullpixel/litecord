from aiohttp import web


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
        async def inner_func(self, request):
            #if not self.server.flags.get('ratelimit_enabled', False):
            #    return

            return (await func(self, request))
        return inner_func

    return decorator

def ws_ratelimit(requests=120, seconds=60, special_bucket=False):
    """Declare a ratelimited WS function.

    TODO: actual ratelimits
    """

    def decorator(func):
        async def inner_func(self, data):
            #if not self.server.flags.get('ratelimit_enabled', False):
            #    return

            return (await func(self, data))
        return inner_func

    return decorator
