"""
config.py - configuration file for a litecord instance.
"""

flags = {
    'server': {
        # its a tuple (host, port)
        'http': ('0.0.0.0', 8000),
        'ws': ('0.0.0.0', 12000),
        'voice_ws': ('0.0.0.0', 6969),
    },
    'ratelimits': {
        'rest': True,
        'ws': True,

        # [requests, period of seconds]
        'global_ws': [120, 60],
        'global_rest': [50, 1],
    },
    'images': {
        # keep this as True
        'local': True,
    },
    'boilerplate.update': {
        # Those only need to be true if you see changes happening over
        #  boilerplate_data, if there is, mark one or both depending on the situation
        #  and restart your Litecord isntance.
        'user': False,
        'guild': False
    },
}
