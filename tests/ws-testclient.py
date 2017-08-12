import logging, asyncio, websockets, aiohttp

logging.basicConfig(level=logging.DEBUG)
loop = asyncio.get_event_loop()

BASE = 'http://localhost:8000/api'
BASE = 'http://litecord.memework.org:8000/api'

async def main():
    sess = aiohttp.ClientSession()
    gateway = None
    async with sess.get(f'{BASE}/gateway') as r:
        gateway = await r.json()

    logging.info('gateway: %r', gateway)
    ws = await websockets.connect(gateway['url'])
    try:
        while True: await ws.recv()
    except KeyboardInterrupt:
        await ws.close()

loop.run_until_complete(main())

