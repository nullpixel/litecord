
class MockEndpoints:
    """Mocked endpoints gathered from the official client"""
    def __init__(self, server):
        self.server = server
        self.register()

    def register(self):
        self.server.add_get('api/', self.h_update_mock)

