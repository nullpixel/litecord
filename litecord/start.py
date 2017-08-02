"""
start.py - things to start the server
"""

import asyncio
import logging
import ssl
import urllib.parse as urlparse

import websockets

from .basics import GATEWAY_VERSION
from .server import LitecordServer
from .gateway import Connection

log = logging.getLogger(__name__)

async def server_sentry(server):
    log.info('Starting sentry')
    try:
        while True:
            log.debug('ws sockets: %s', server.ws_server.websockets)

            check_data = await server.check()

            if not check_data.get('good', False):
                log.warning('[sentry] we are NOT GOOD.')

            log.info(f"[sentry] Mongo ping: {check_data['mongo_ping']}msec")

            #log.info(f"[sentry] HTTP throughput: {check_data['http_throughput']}requests/s")
            #log.info(f"[sentry] WS throughput: {check_data['ws_throughput']}packets/s")

            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    except Exception:
        log.error('fug', exc_info=True)


def init_server(app, flags, loop=None):
    """Load the LitecordServer instance."""
    try:
        server = LitecordServer(flags, loop)
    except Exception:
        log.error('Error while loading server', exc_info=True)

    asyncio.ensure_future(server.init(app))
    app.litecord_server = server
    return True


async def on_connection(server, ws, path):
    log.info(f'[ws] New client at {path!r}')
    if not server.accept_clients:
        await ws.close(1000, 'Server is not accepting new clients.')
        return

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

    if gw_version != GATEWAY_VERSION:
        await ws.close(4000, f'gw version not supported: {gw_version}')
        return

    conn = Connection(ws, config=(gw_version, encoding), server=server)

    # this starts an infinite loop waiting for payloads from the client
    await conn.run()

async def start_all(app):
    """Start Gateway and HTTP."""

    server = app.litecord_server
    flags = server.flags

    await server.good.wait()

    async def henlo(ws, path):
        return await on_connection(server, ws, path)

    # we gotta get that SSL right
    # or else we are doomed
    context = None
    f_ssl = flags['ssl']
    ssl_on = f_ssl['on']
    if ssl_on:
        log.info('[ssl] creating context')

        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        certfile = f_ssl['certfile']
        keyfile = f_ssl['keyfile']
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        server.ssl_cxt = context

        log.info('[ssl] done, cert_store=%r', context.cert_store_stats())
    else:
        log.info('[ssl] context not enabled')

    # start HTTP
    http = server.flags['server']['http']

    handler = app.make_handler()
    if ssl_on:
        server.http_server = app.loop.create_server(handler, host=http[0], \
            port=http[1], ssl=context)
    else:
        server.http_server = app.loop.create_server(handler, \
            host=http[0], port=http[1])

    log.info(f'[http] http://{http[0]}:{http[1]}')

    # start ws
    ws = flags['server']['ws']

    if ssl_on:
        server.ws_server = websockets.serve(henlo, host=ws[0], \
            port=ws[1], ssl=context)
    else:
        server.ws_server = websockets.serve(henlo, \
            host=ws[0], port=ws[1])

    log.info(f'[ws] ws://{ws[0]}:{ws[1]} {f"-> ws://{ws[2]}:{ws[1]}" if len(ws) > 2 else ""}')

    return True
