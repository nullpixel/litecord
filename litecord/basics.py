import json

GATEWAY_VERSION = 69

OP = {
    'DISPATCH': 0,
    'HEARTBEAT': 1,
    'IDENTIFY': 2,
    'STATUS_UPDATE': 3,
    'RESUME': 6,
    'RECONNECT': 7,
    'INVALID_SESSION': 9,
    'HELLO': 10,
    'HEARTBEAT_ACK': 11,
}
