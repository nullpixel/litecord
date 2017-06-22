GATEWAY_VERSION = 69

class OP:
    """Gateway OP codes."""
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    STATUS_UPDATE = 3

    VOICE_STATE_UPDATE = 4
    VOICE_SERVER_PING = 5

    RESUME = 6
    RECONNECT = 7
    REQUEST_GUILD_MEMBERS = 8
    INVALID_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11

    # Undocumented OP code
    GUILD_SYNC = 12

class VOICE_OP:
    """Voice OP codes.
    
    These OP codes are used in the Voice Websocket.
    """
    IDENTIFY = 0
    SELECT_PROTOCOL = 1
    READY = 2
    HEARTBEAT = 3
    SESSION_DESCRIPTION = 4
    SPEAKING = 5

CHANNEL_TO_INTEGER = {
    'text': 0,
    'private': 1,
    'voice': 2,
    'group': 3,
}
