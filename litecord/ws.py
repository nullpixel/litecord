"""
ws - Websocket server
    This implements a basic websocket server
    that follows Discord's format in packets
    
    The `WebsocketServer` class implements checking of payloads
    and disconnects with proper error codes.

    `Connection` and `VoiceConnection` inherit from this class.
"""

class WebsocketServer:
    def __init__(self):
        pass

    async def convert(self, payload):
        """Process a raw payload from the websocket
        converts to JSON if possible.
        """
        pass

    async def process(self, payload):
        """Process a payload
        This checks for the payload's OP code
        and checks if a handler exists for that OP code.
        """
        pass

    async def run(self):
        """Enter an infinite loop waiting for a websocket packet"""
        try:
            while True:
                payload = await self.ws.recv()
                j = await self.convert(payload)
                await self.process(j)
        except asyncio.CancelledError:
            self.clean()

