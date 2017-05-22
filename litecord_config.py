"""
config.py - basic configuration file for a litecord instance.
"""

flags = {
    'server': {
        # its a tuple (host, port)
        'http': ('0.0.0.0', 8000),
        'ws': ('0.0.0.0', 12000),
    },
    'ratelimits': {
        'rest': True,
        'ws': True,

        'global_ws': [120, 60],
        'global_rest': [50, 1],
    },
    'images': {
        'local': True,
    },
    'boilerplate.update': {
        'user': False,
        'guild': False
    },
}
