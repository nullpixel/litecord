# Litecord
=========

An implementation of Discord's backend.

This has real shitty code, good luck

With litecord you can run your own "Discord", locally, by yourself, but with limitations
 * You can't use the official discord client with it, use [Atomic Discord](https://git.memework.org/heatingdevice/atomic-discord) instead.
 * Not very good code, expect the unexpected when running your server or accessing one.
 * Voice doesn't work nor is planned to be implemented into Litecord.
 * This is written in Python and it wasn't made to be resilient, don't DDoS a Litecord server
 * Ratelimits doesn't exist, yet.

# Usage

wow you *really* want to use it?

ok then.


```bash
# Pỳthon 3.6
# something along those lines
sudo pip3.6 install -U aiohttp websockets
```

Then you just run `litecord.py`, simple.
It will fire up 2 servers, a REST one and a WS one:
 * REST runs at `http://0.0.0.0:8000`
 * WS runs at `ws://0.0.0.0:12000`

For now the REST API can give you the address to the WS one through the `/api/gateway` endpoint,
so you just need to change your gateway path(in your preferred library).

Check [this](https://git.memework.org/lnmds/litecord/issues/2) for the list of implemented things in `litecord`
Also, don't issue `"there is no voice"` things. There won't be.
