# Standard library
import os

# sqlite3/sqlalchemy
LOCAL_DB_DIR = os.path.abspath(os.curdir)  # may need to modify this path depending on hosting provider setup
LOCAL_DB_FILENAME = "pogo_sj.db"
LOCAL_DB_SPECIFIER_BASE = "sqlite+pysqlite:///"
LOCAL_DB_OPTIONS = "?mode=rw"
LOCAL_DB_SPECIFIER = (LOCAL_DB_SPECIFIER_BASE
                      + os.path.join(LOCAL_DB_DIR, LOCAL_DB_FILENAME)
                      + LOCAL_DB_OPTIONS)
TEST_USER = "test_user"
