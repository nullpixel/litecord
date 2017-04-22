import time
import hashlib

process_id = 0

def get_token():
    global process_id
    now = int(time.time())
    _str = f'{now}{process_id}'
    process_id += 1
    token = hashlib.md5(_str.encode()).hexdigest()
    return f'memework_{token}'

def get_snowflake():
    # TODO: this
    raise NotImplemented
