import json
import logging

log = logging.getLogger(__name__)

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

    def init(self):
        if not self.db_init_all():
            return False
        return True
