import collections


class ConnectionState:
    """State of a connection to the gateway over websockets
    
    Attributes
    ----------
    session_id: str
        Session ID this state refers to.
    token: str
        Token that this state refers to.
    user: :class:`User`
        User that this state refers to.

    shard_id: int
        Shard ID of this state.
    shard_count: int
        Shard count of this state.
    sharded: bool
        If this state refers to a shard

    events: `collections.deque`[dict]
        Deque of sent events to the connection. Used for resuming
        This is filled up when the connection receives a dispatched event

    recv_seq: int
        Last sequence number received by the client.
    sent_seq: int
        Last sequence number dispatched to the client.

    """
    def __init__(self, session_id, token, user, properties, shard_id, shard_count):
        self.session_id = session_id
        self.token = token
        self.user = user
        self.properties = properties

        self.shard_id = shard_id
        self.shard_count = shard_count
        self.sharded = shard_count > 1

        # sequence stuff
        self.recv_seq = 0
        self.sent_seq = 0

        self.events = collections.deque(maxlen=RESUME_MAX_EVENTS)

    def __repr__(self):
        return f'<ConnectionState session_id={self.session_id}>'

    def __getitem__(self, seq):
        """Return a payload from a sequence number."""
        if not isinstance(seq, int):
            raise TypeError('seq is not an int')

        try:
            return self.events[seq]
        except IndexError:
            return

    def add(self, payload):
        """Add a payload to the state's queue"""
        self.events.append(payload)

    def clean(self):
        pass

