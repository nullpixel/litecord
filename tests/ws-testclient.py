import logging, asyncio, websockets, aiohttp

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()
loop = asyncio.get_event_loop()

BASE = 'http://localhost:8000/api'
BASE = 'https://litecord.memework.org:8000/api'

async def main():
    sess = aiohttp.ClientSession()
    gateway = None

    log.info(f'requesting {BASE}/gateway')
    async with sess.get(f'{BASE}/gateway') as r:
        gateway = await r.json()

    log.info('gateway: %r', gateway)
    ws = await websockets.connect(gateway['url'])
    log.info('in loop')
    try:
        while True:
            d = await ws.recv()
            log.info('data: %s', d)
    except KeyboardInterrupt:
        await ws.close()

loop.run_until_complete(main())

