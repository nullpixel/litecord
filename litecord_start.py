#!/usr/bin/env python3
import logging
import asyncio
import json
import sys

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

import aiohttp
from aiohttp import web

import litecord

logging.basicConfig(level=logging.DEBUG, \
    format='[%(levelname)7s] [%(name)s] %(message)s')

loggers_to_info = ['websockets.protocol']

log = logging.getLogger('litecord')

handler = logging.FileHandler('litecord.log')
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - [%(levelname)s] [%(name)s] %(message)s')
handler.setFormatter(formatter)

log.addHandler(handler)

app = web.Application()

async def index(request):
    return web.Response(text='beep boop this is litecord!')

def shush_loggers():
    """Set some specific loggers to `INFO` level."""
    for logger in loggers_to_info:
        logging.getLogger(logger).setLevel(logging.INFO)

def main():    
    try:
        config_path = sys.argv[1]
    except IndexError:
        config_path = 'litecord_config.json'

    try:
        cfgfile = open(config_path, 'r')
    except FileNotFoundError:
        cfgfile = open('litecord_config.sample.json', 'r')

    shush_loggers()
    loop = asyncio.get_event_loop()
    flags = json.load(open(config_path, 'r'))
    app.router.add_get('/', index)

    litecord.init_server(app, flags, loop)

    try:
        loop.run_until_complete(litecord.start_all(app))
        server = app.litecord_server
        server.compliance()

        log.debug('Running servers')
        server.http_server = loop.run_until_complete(server.http_server)
        server.ws_server = loop.run_until_complete(server.ws_server)

        log.debug('Running server sentry')
        loop.create_task(litecord.server_sentry(server))

        log.debug('Running loop')
        loop.run_forever()
    except KeyboardInterrupt:
        log.info('Exiting from a CTRL-C...')
    except:
        log.exception('Oh no! We received an error. Exiting.')
    finally:
        app.litecord_server.shutdown()

    return 0

if __name__ == "__main__":
    sys.exit(main())
