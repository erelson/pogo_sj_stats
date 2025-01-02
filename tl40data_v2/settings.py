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


def local_db_specifier_from_file(filepath):
    """Returns a DB specifier to use instead of the default LOCAL_DB_SPECIFIER
    """
    db_specifier = (LOCAL_DB_SPECIFIER_BASE
                    + os.path.abspath(filepath)  # TODO check if this is robust for various scenarios
                    + LOCAL_DB_OPTIONS)
    return db_specifier
