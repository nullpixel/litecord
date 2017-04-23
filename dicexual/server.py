import json
import logging
from aiohttp import web

from .snowflake import get_token

log = logging.getLogger(__name__)

def _err(msg):
    return web.Response(text=f'{"error": {msg!r}}')

def _json(obj):
    return web.Response(text=f'{json.dumps(obj)}')

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
        tokens[account_id] = get_token()
        self.db_save(['tokens'])

        return _json({"token": tokens[account_id]})

    def init(self):
        if not self.db_init_all():
            return False
        return True
