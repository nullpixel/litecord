.. Litecord documentation master file, created by
   sphinx-quickstart on Wed May 24 14:03:37 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Litecord
====================================

.. _Atomic-Discord: https://git.memework.org/heatingdevice/atomic-discord

Litecord is an implementation of Discord's backend.

**DISCLAIMER: LITECORD IS NOT DISCORD. WE DON'T PLAN TO BE 100% DISCORD.
THIS IS AN EXPERIMENT IN LEARNING HOW DISCORD WORKS. PLS DON'T SUE US**

Features:
 - Websocket + REST API
 - MongoDB for storage (is that an actual feature? 🤔)
 - Presence management
 - Admin users and routes

Limitations:
 - You can't use the official discord client with it, use Atomic-Discord_ instead.
 - No module reloading.
 - Not very good code, expect the unexpected when running your server or accessing one.
 - Voice doesn't work nor is planned to be implemented into Litecord.
 - Litecord is made using Python and it wasn't made to be resilient, don't DDoS a Litecord server
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


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
