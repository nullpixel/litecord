"""
enums.py - Various Enums used by litecord
"""
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
    GUILD_SYNC = 12

class CloseCodes:
    """Websocket close codes used by the gateway."""
    UNKNOWN_ERROR = 4000
    UNKNOWN_OP = 4001
    DECODE_ERROR = 4002

    NOT_AUTH = 4003
    AUTH_FAILED = 4004
    ALREADY_AUTH = 4005
    INVALID_SEQ = 4007
    RATE_LIMITED = 4008
    SESSION_TIMEOUT = 4009

    INVALID_SHARD = 4010
    SHARDING_REQUIRED = 4011

CloseReasons = {
    CloseCodes.UNKNOWN_OP: 'Unknown OP code',
    CloseCodes.NOT_AUTH: 'Not authenticated',
    CloseCodes.AUTH_FAILED: 'Failed to authenticate',
    CloseCodes.ALREADY_AUTH: 'Already identified',
    CloseCodes.INVALID_SEQ: 'Invalid sequence',
    CloseCodes.RATE_LIMITED: 'Rate limited',
    CloseCodes.SESSION_TIMEOUT: 'Session timed out',
    CloseCodes.INVALID_SHARD: 'Invalid Shard',
    CloseCodes.SHARDING_REQUIRED: 'Sharding required',
}

class VoiceOP:
    """Voice OP codes.
    
    These OP codes are used in the Voice Websocket.
    """
    IDENTIFY = 0
    SELECT_PROTOCOL = 1
    READY = 2

    HEARTBEAT = 3
    SESSION_DESCRIPTION = 4
    SPEAKING = 5
    HEARTBEAT_ACK = 6
    RESUME = 7

    HELLO = 8
    RESUMED = 9
    CLIENT_DISCONNECT = 13

class VoiceWSCloseCodes:
    """Close codes used by the Voice WebSocket."""
    UNKNOWN_OP = 4001
    NOT_AUTH = 4003
    AUTH_FAILED = 4004
    ALREADY_AUTH = 4005
    INVALID_SESSION = 4006
    SESSION_TIMEOUT = 4009

    SERVER_NOT_FOUND = 4011
    UNKNOWN_PROTOCOL = 4012

    DISCONNECTED = 4014
    SERVER_CRASH = 4015
    UNKNOWN_ENC_MODE = 4016

class AppType:
    """Application Type."""
    BOT = 0

class ChannelType:
    """Channel Type."""
    GUILD_TEXT = 0
    DM = 1
    GUILD_VOICE = 2
    GROUP_DM = 3
    GUILD_CATEGORY = 4

class MessageType:
    """Message Type.
    
    ``DEFAULT`` is the one that users can usually send.
    The rest are system messages.
    """
    DEFAULT = 0
    RECIPIENT_ADD = 1
    RECIPIENT_REMOVE = 2
    CALL = 3
    CHANNEL_NAME_CHANGE = 4
    CHANNEL_ICON_CHANGE = 5
    CHANNEL_PINNED_MESSAGE = 6
    GUILD_MEMBER_JOIN = 7
