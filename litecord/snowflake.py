import time
import hashlib
import os
import base64

process_id = 0

EPOCH = 1420081200
_id_in_process = 1

async def get_raw_token(prefix='litecord_'):
    """Generate a token"""
    random_stuff = hashlib.sha512(os.urandom(4096)).digest()
    token = base64.urlsafe_b64encode(random_stuff).decode().replace('=', '')
    return f'{prefix}{token}'


def sync_get_raw_token(prefix='litecord_'):
    random_stuff = hashlib.sha512(os.urandom(4096)).digest()
    token = base64.urlsafe_b64encode(random_stuff).decode().replace('=', '')
    return f'{prefix}{token}'


def get_invite_code():
    random_stuff = hashlib.sha512(os.urandom(4096)).digest()
    code = base64.urlsafe_b64encode(random_stuff).decode().replace('=', '5') \
        .replace('_', 'W').replace('-', 'm')
    return code[:6]

def _snowflake(timestamp):
    """Generate a snowflake from a specific timestamp.

    NOTE: the same timestamp won't generate the same snowflake in this function.
    """
    global _id_in_process
    since_epoch = int(timestamp - EPOCH)
    b_epoch = '{0:038b}'.format(since_epoch)

    b_id = '{0:011b}'.format(_id_in_process)
    _id_in_process += 1

    res = f'{b_epoch}{b_id}'
    return int(res[2:], 2)


def _snowflake_raw(timestamp, process_id):
    """Make a snowflake using raw data"""
    since_epoch = int(timestamp - EPOCH)
    b_epoch = '{0:038b}'.format(since_epoch)
    b_id = '{0:011b}'.format(process_id)
    res = f'{b_epoch}{b_id}'
    return int(res[2:], 2)


def snowflake_time(snowflake):
    """Get a timestamp from a specific snowflake"""
    snowflake = int(snowflake)
    b_snowflake = '{0:049b}'.format(snowflake)
    since_epoch = int(b_snowflake[:38], 2)

    timestamp = EPOCH + since_epoch
    return timestamp


def get_snowflake():
    """Generate a snowflake"""
    return _snowflake(time.time())
