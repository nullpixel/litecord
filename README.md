# Litecord
An implementation of Discord's backend.

This has real shitty code, good luck

With litecord you can run your own "Discord", locally, by yourself, but with limitations
 * You can't use the official discord client with it, use [Atomic Discord](https://git.memework.org/heatingdevice/atomic-discord) instead.
 * Not very good code, expect the unexpected when running your server or accessing one.
 * Voice doesn't work nor is planned to be implemented into Litecord.
 * This is written in Python and it wasn't made to be resilient, don't DDoS a Litecord server
 * Ratelimits doesn't exist, yet.

## Installation

Make sure you have [MongoDB](https://www.mongodb.com/) installed and running.

```bash
# Clone the repo
git clone ssh://git@git.memework.org:2222/lnmds/litecord.git
# Open the freshly cloned copy
cd litecord

# Create a virtual enviroment and install dependencies in it
# Make sure your python is 3.6+
python3 -m venv py_litecord/
py_litecord/bin/python3 -m pip install -r requirements.txt
```

Then you just run `./run_litecord.sh`, simple.

## Libraries that are known to work with Litecord
 - `discord.js`, used by Atomic Discord.
 - `discord.py`, both the `async` and `rewrite` branches.
  - Tip: edit `discord.http.Route.BASE` in `rewrite` to your litecord instance.
 - `Discordie`
  - Tip: `lib/Constants.js`, around lines 814 for API base,
    line 816 for cdn endpoint(`/images`)
 - `Eris`
  - Tip: `node_modules/eris/lib/rest/RequestHandler.js`, line 133

## Libraries that are known to not work with Litecord
 - `discord.io`

## Usage
When you run `litecord.py` it will fire up 2 servers, a REST one and a WS one:
 * REST runs at `http://0.0.0.0:8000`
 * WS runs at `ws://0.0.0.0:12000`

You'll need to change the "base URL" or whatever it is called in your preffered Discord library.

Check [this](https://git.memework.org/lnmds/litecord/issues/2) for the list of implemented things in `litecord`
Also, don't create an issue for `"there is no voice"`. There won't be.

## Updating
```bash
# Fetch changes
git fetch
# Merge the changes from origin
git pull
```
That's it! Just make sure to restart `litecord.py` when you're done!

## Folder structure
 * `/litecord` contains the actual litecord server code.
 * `/utils` has utilities to use with a litecord server.
 * `/docs` has documentation on how the server actually does its stuff.
 * `/boilerplate_data`, [read this](https://git.memework.org/lnmds/litecord/src/master/boilerplate_data/README.md)
 * Depending on your installation, you might have a `/py_litecord` directory,
 **DON'T MESS WITH IT.**, don't install other libraries unless otherwise specified(pls don't break your server instance).
