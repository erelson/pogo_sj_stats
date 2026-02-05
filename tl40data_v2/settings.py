# Standard library
import json
import os


# sqlite3/sqlalchemy - defaults
LOCAL_DB_DIR = os.path.abspath(os.curdir)  # may need to modify this path depending on hosting provider setup
LOCAL_DB_FILENAME = "pogo_sj.db"
LOCAL_DB_SPECIFIER_BASE = "sqlite+pysqlite:///"
LOCAL_DB_OPTIONS = "?mode=rw"

# Load per-deployment overrides from settings.json (if it exists)
# See settings.json.example for available keys.
_settings_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
if os.path.isfile(_settings_json_path):
    with open(_settings_json_path) as _f:
        _overrides = json.load(_f)
    if "LOCAL_DB_DIR" in _overrides:
        LOCAL_DB_DIR = _overrides["LOCAL_DB_DIR"]
    if "LOCAL_DB_FILENAME" in _overrides:
        LOCAL_DB_FILENAME = _overrides["LOCAL_DB_FILENAME"]

# Allow environment variable to override database location (highest priority)
# Usage: DB_LOCATION=/path/to/database.db python3 script.py
if os.environ.get('DB_LOCATION'):
    _db_path = os.path.abspath(os.environ['DB_LOCATION'])
    LOCAL_DB_SPECIFIER = LOCAL_DB_SPECIFIER_BASE + _db_path + LOCAL_DB_OPTIONS
else:
    LOCAL_DB_SPECIFIER = (LOCAL_DB_SPECIFIER_BASE
                          + os.path.join(LOCAL_DB_DIR, LOCAL_DB_FILENAME)
                          + LOCAL_DB_OPTIONS)

TEST_USER = "test_user"
PLOT_DIR = LOCAL_DB_DIR

def local_db_specifier_from_file(filepath):
    """Returns a DB specifier to use instead of the default LOCAL_DB_SPECIFIER
    """
    db_specifier = (LOCAL_DB_SPECIFIER_BASE
                    + os.path.abspath(filepath)  # TODO check if this is robust for various scenarios
                    + LOCAL_DB_OPTIONS)
    return db_specifier
