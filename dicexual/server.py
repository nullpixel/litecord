import json
import logging
from aiohttp import web

from .snowflake import get_raw_token

log = logging.getLogger(__name__)

def _err(msg):
    return web.Response(text=json.dumps({
        'error': msg
    }))

def _json(obj):
    return web.Response(text=json.dumps(obj))

class DicexualServer:
    def __init__(self):
        self.db_paths = None
        self.db = {}

    def db_init_all(self):
        for database_id in self.db_paths:
            db_path = self.db_paths[database_id]
            try:
                self.db[database_id] = json.load(open(db_path, 'r'))
            except:
                log.error(f"Error loading database {database_id} at {db_path}", exc_info=True)
                return False

        return True

    def db_save(self, list_db):
        for database_id in list_db:
            path = self.db_paths[database_id]
            db_object = self.db[database_id]
            json.dump(db_object, open(path, 'w'))

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
        if password != user['password']['plain']:
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
