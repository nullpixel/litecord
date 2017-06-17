import json

class JSONConnection:
    """Represents a Websocket connection that uses JSON as its payloads."""
    def __init__(self, ws):
        self.ws = ws

    async def send(self, payload: dict):
        """Send a payload, it needs to be JSON Serializable"""
        await self.ws.send(json.dumps(payload))

    async def recv(self) -> dict:
        """Receive a JSON payload."""
        data = await self.ws.recv()
        return json.loads(data)

