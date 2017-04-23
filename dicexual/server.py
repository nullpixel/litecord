import json
import logging
import os
import base64
import hashlib

from aiohttp import web
from .snowflake import get_raw_token

log = logging.getLogger(__name__)

def _err(msg):
    return web.Response(text=json.dumps({
        'error': msg
    }))

def _json(obj):
    return web.Response(text=json.dumps(obj))

def get_random_salt(size=32):
    return base64.b64encode(os.urandom(size)).decode()

def pwd_hash(plain, salt):
    return hashlib.sha256(f'{plain}{salt}'.encode()).hexdigest()

class DicexualServer:
    def __init__(self):
        self.db_paths = None
        self.db = {}

    def db_init_all(self):
        for database_id in self.db_paths:
            db_path = self.db_paths[database_id]
            try:
                self.db[database_id] = json.load(open(db_path, 'r'))
                if hasattr(self, f'dbload_{database_id}'):
                    getattr(self, f'dbload_{database_id}')()
            except:
                log.error(f"Error loading database {database_id} at {db_path}", exc_info=True)
                return False

        return True

    def db_save(self, list_db):
        for database_id in list_db:
            path = self.db_paths[database_id]
            db_object = self.db[database_id]
            json.dump(db_object, open(path, 'w'))

    def dbload_users(self):
        users = self.db['users']
        for user_email in users:
            user = users[user_email]
            pwd = user['password']

            if len(pwd['salt']) < 1:
                pwd['salt'] = get_random_salt()

            if len(pwd['hash']) < 1 and len(pwd['salt']) > 0:
                pwd['hash'] = pwd_hash(pwd['plain'], pwd['salt'])
                pwd['plain'] = None

        self.db_save(['users'])

    async def login(self, request):
        try:
            json = await request.json()
        except Exception as err:
            # error parsing json
            return _err("error parsing")

        email = json.get('email')
        password = json.get('password')
        if email is None or password is None:
            return _err("malformed packet")

        users = self.db['users']
        if email not in users:
            return _err("fail on login")

        user = users[email]
        pwd = user['password']
        if pwd_hash(password, pwd['salt']) != pwd['hash']:
            return _err("fail on login")

        tokens = self.db['tokens']
        account_id = user['id']

        # check if there is already a token related to the user
        _old_token = None
        for token in tokens:
            if tokens[token] == account_id:
                _old_token = token

        # make a new one
        _token = await get_raw_token()
        while _token in tokens:
            _token = await get_raw_token()

        # overwrite the previous one if any
        if _old_token is not None:
            tokens.pop(_old_token)

        tokens[_token] = account_id
        self.db_save(['tokens'])

        return _json({"token": _token})

    def init(self):
        if not self.db_init_all():
            return False
        return True
