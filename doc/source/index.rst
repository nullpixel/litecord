.. Litecord documentation master file, created by
   sphinx-quickstart on Wed May 24 14:03:37 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Litecord
====================================

.. _Atomic-Discord: https://git.memework.org/heatingdevice/atomic-discord

Litecord is an async server that (tries) to comply with Discord's Gateway and REST APIs.

**DISCLAIMER: LITECORD IS NOT DISCORD. WE DON'T PLAN TO BE 100% DISCORD.
THIS IS AN EXPERIMENT IN LEARNING HOW DISCORD WORKS. PLS DON'T SUE US**

Features:
 - Implemented APIs:
    - REST (30% implemented)
      - OAuth2, Bearer tokens (0% implemented)
    - Gateway (90% implemented)
 - MongoDB for storage
 - Admin users for server operation in runtime

Limitations:
 - Use the Atomic-Discord_ client to access a litecord server.
   - It isn't recommended to use the official client, because that requires
      modification to the client source code, which is against Discord's ToS. don't do it

 - No hot reloading or whatever you call it.
 - Don't expect good code, expect the unexpected when running your server or accessing one.
 - A bare voice implementation is planned, but no "actual" working voice is planned.
 - Litecord is made using Python and it wasn't designed to be resilient, **don't DDoS a Litecord server**
 - Ratelimits doesn't exist, yet.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   connecting
   api/index
   server
   guild
   presence
   objects
   config
   embeds
   enums
   ws

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
