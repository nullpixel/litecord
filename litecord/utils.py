import json
import datetime
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

date_handler = lambda obj: (
    obj.isoformat()
    if isinstance(obj, datetime.datetime)
    or isinstance(obj, datetime.date)
    else None
)

def dt_to_json(dt):
    return json.dumps(dt, default=date_handler)

def _json(obj):
    return web.Response(text=json.dumps(obj))

# Modification of https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
def chunk_list(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]
