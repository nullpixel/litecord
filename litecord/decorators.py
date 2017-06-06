import logging
import json
import asyncio

from .utils import _err, _json

log = logging.getLogger(__name__)

def admin_endpoint(handler):
    """Declare an Admin Endpoint.

    Admin Endpoints in Litecord are endpoints that can only be accessed by
    users who have administrator powers.

    To make a user an admin, set the `admin` field in the raw user
    object to boolean `true`.
    """
    async def inner_handler(endpoint, request):
        server = endpoint.server

        _error = await server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        user = server._user(_error_json['token'])

        # pretty easy actually
        if not user.admin:
            log.warning(f"{user!s} tried to use an admin endpoint")
            return _err(errno=40001)

        return (await handler(endpoint, request, user))
    return inner_handler

def auth_route(handler):
    """Declare a route that needs authentication to be used."""
    async def inner_handler(endpoint, request):
        server = endpoint.server

        _error = await server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        user = server._user(_error_json['token'])
        try:
            return (await handler(endpoint, request, user))
        except Exception as err:
            log.error('errored in auth_route', exc_info=True)
            return _err(f'Error: {err!s}')

    # Fixes the docs
    inner_handler.__doc__ = handler.__doc__

    return inner_handler
