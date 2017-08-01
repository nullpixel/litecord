
class ConnectionState:
    """State of a connection to the gateway over websockets
    
    Attributes
    ----------
    session_id: str
        Session ID this state refers to.

    events: `collections.deque`[dict]
        Deque of sent events to the connection. Used for resuming
        This is filled up when the connection receives a dispatched event
    """
    def __init__(self, session_id):
        self.session_id = session_id

    def clean(self):
        del self.session_id

