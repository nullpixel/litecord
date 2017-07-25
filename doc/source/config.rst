
Configuration file
=====================

Litecord needs a configuration file to run, that file specifies
where the server will create its smaller servers(WS and HTTP),
defines if ratelimiting is enabled and customizes it,
and enables or disables boilerplate data overwrites.

You can see an example configuration file at ``litecord_config.json``.

 - ``"server"``
   - Defines where Litecord will start its servers.
     - More specifically: Gateway and Voice(Websockets) and the REST API(HTTP)
 - ``"ratelimits"``
   - Defines how Litecord will handle ratelimitng
     - If they are enabled, and what rate of requests will be allowed on them
     - Currently, there isn't a way to define the specific ratelimits(like the ones in `IDENTIFY` and `PRESENCE_UPDATE`).
 - ``"boilerplate.update"``
   - Says if Litecord will overwrite existing user/guild data with the boilerplate user/guild data.

