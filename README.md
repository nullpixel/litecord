dicexual
=========

An implementation of Discord's backend.

This has real shitty code, good luck

# Usage

wow you *really* want to use it?

ok then.


```bash
# Pỳthon 3.6
# something along those lines
sudo pip3.6 install -U aiohttp websockets
```

Then you just run `dicexual.py`, simple.
It will fire up 2 servers, a REST one and a WS one:
 * REST runs at `http://0.0.0.0:8000`
 * WS runs at `ws://0.0.0.0:12000`

For now the REST API can give you the address to the WS one through the `/api/gateway` endpoint,
so you just need to change your gateway path(in your preferred library).

Check [this](https://git.memework.org/lnmds/dicexual/issues/2) for the list of implemented things in `dicexual`
Also, don't issue `"there is no voice"` things. There won't be.
