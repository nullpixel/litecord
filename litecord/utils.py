import json
from random import randint
from aiohttp import web

def strip_user_data(user):
    return {
        'id': user['id'],
        'username': user['username'],
        'discriminator': user['discriminator'],
        'avatar': user['avatar'],
        'bot': user['bot'],
        #'mfa_enabled': user['mfa_enabled'],
        'verified': user['verified'],
        'email': user['email'],
    }

def random_digits(n):
    range_start = 10**(n-1)
    range_end = (10**n)-1
    return randint(range_start, range_end)

def _err(msg):
    return web.Response(text=json.dumps({
        'code': 0,
        'message': msg
    }))

def _json(obj):
    return web.Response(text=json.dumps(obj))
