import logging
import json
import asyncio

from aiohttp import web

from .utils import _err, _json
from .err import RequestCheckError

log = logging.getLogger(__name__)

async def user_from_request(server, request):
    try:
        token, user_id = await server.check_request(request)
    except RequestCheckError as err:
        return err.args[0]

    user = server.get_user(user_id)
    if user is None:
        return web.Response(status=401, text='Unauthorized [user not found]')

    return user

async def do(handler, *args):
    try:
        return await handler(*args)
    except Exception as err:
        log.error('Errored in a handler', exc_info=True)
        return _err(f'Error: {err!r}')

def admin_endpoint(handler):
    """Declare an Admin Endpoint.

    Admin Endpoints in Litecord are endpoints that can only be accessed by
    users who have administrator powers.

    To make a user an admin, set the `admin` field in the raw user
    object to boolean `true`.
    """
    async def inner_handler(endpoint, request):
        server = endpoint.server

        user = await user_from_request(server, request)
        if isinstance(user, web.Response):
            return user

        # pretty easy lol
        if not user.admin:
            log.warning(f"{user!s} tried to use an admin endpoint")
            return _err(errno=40001)

        return await do(handler, endpoint, request, user)

    inner_handler.__doc__ = handler.__doc__

    return inner_handler

def auth_route(handler):
    """Declare a route that needs authentication to be used."""
    async def inner_handler(endpoint, request):
        server = endpoint.server

        user = await user_from_request(server, request)
        if isinstance(user, web.Response):
            return user

        return await do(handler, endpoint, request, user)

    inner_handler.__doc__ = handler.__doc__

    return inner_handler
