dicexual
=========

This is literally the worst shit I'm making to learn about Discord: A reimplementation of
Discord's gateway.

# Usage

wow you really want to use it?
ok
make sure you have Python 3.6, `aiohttp` and `websockets`

Then you just run dicexual.py, simple.
It will fire up 2 servers, a REST one and a WS one:
 * REST: `http://0.0.0.0:8000`
 * WS: `ws://0.0.0.0:12000`

For now the REST API can give you the address to the WS one through the `/api/gateway` endpoint,
so you just need to change your gateway path.
