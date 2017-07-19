import logging, asyncio, websockets, aiohttp

logging.basicConfig(level=logging.DEBUG)
loop = asyncio.get_event_loop()

BASE = 'http://localhost:8000/api'
sess = aiohttp.ClientSession()

async def main():
    gateway = None
    async with sess.get(f'{BASE}/gateway') as r:
        gateway = await r.json()

    logging.info('gateway: %r', gateway)
    ws = await websockets.connect('ws://localhost:12000')
    try:
        while True: await ws.recv()
    except KeyboardInterrupt:
        await ws.close()

loop.run_until_complete(main())

