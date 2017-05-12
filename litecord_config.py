"""
config.py - basic configuration file for a litecord instance.
"""

flags = {
    'ratelimits': {
        'rest': True,
        'ws': True,

        'global_ws': [120, 60],
        'global_rest': [50, 1],
    },
    'images': {
        'local': True,
    }
}
