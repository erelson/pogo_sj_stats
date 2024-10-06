#! /usr/bin/env python3

# Standard library
from argparse import ArgumentParser
import json
from tables import Stat

# Third party
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.engine import ExceptionContext

# Local
from settings import LOCAL_DB_SPECIFIER, LOCAL_DB_FILENAME


def fill_stats(session: Session, changed: bool = False):

    try:
        #existing_stat_data = session.query(Stat.name).all()
        existing_stat_data = session.query(Stat).all()
        existing_stat_lookup = {stat.name: stat for stat in existing_stat_data}
        existing_stat_names = [stat.name for stat in existing_stat_data]  # for lookup with .index()
    except OperationalError as e:
        existing_stat_lookup = {}

    static_stat_info = json.load(open("stats.json", 'r'))  # dict
    json_stat_names = static_stat_info["key"]  # list
    json_stat_vals = static_stat_info["data"]  # dict
    # In our json files, we use a order_idx value that helps determine the
    # order of the different stats in a survey.  This survey order can be
    # changed by modifying the json.
    #
    # In the db, we have a similarly named field, but this field is the index
    # of the stat in the strdata field of a response. When we add new stat columns,
    # they get the next index in the strdata field.
    new_stat_order_idx = len(existing_stat_data)
    for stat_name in json_stat_vals:
        if stat_name in existing_stat_lookup:
            # NOTE: This doesn't do any updates of column values in the row...
            stat = existing_stat_lookup[stat_name]
            existing_stat_idx = existing_stat_names.index(stat_name)  # preserve DB's order
            # This should rarely happen? Or maybe never? Might be a relic from earlier confused coding.
            if stat.order_idx != existing_stat_idx:  # this reads poorly; should rename stat...
                print("WARNING: Updating order_idx value of", stat_name)
                changed = True
            stat.order_idx = existing_stat_idx
        else:  # add new stat in the database; its idx is essentially len(stats)
            stat = Stat(name=stat_name, order_idx=new_stat_order_idx,
                        **dict(zip(json_stat_names, json_stat_vals[stat_name])))
            changed = True
            new_stat_order_idx += 1  # increment idx for the next new stat

        session.add(stat)

    return changed

# No static trainer or response data, unless we're testing something


def main(args):
    """ Get command line args, and call the function that fill the static tables.
    """

    ran_ok = True
    changed = False

    db_specifier = LOCAL_DB_SPECIFIER
    #engine = get_engine(db_specifier)
    engine = create_engine(db_specifier)
    session = Session(engine, autoflush=True)
    changed = fill_stats(session) or changed
    try:
        session.commit()
    except OperationalError as e:
        print("ERROR: Did you run tables.py to create the tables first?")
        print(e)
        ran_ok = False
    session.flush()
    session.close()

    if ran_ok:
        if changed:
            print("Success!")
        else:
            print("NOTE!: No changes needed to be made to the DB...")

        print("You can inspect the (presumably new, mostly empty) DB with:")
        print(f"\tsqlite3 {LOCAL_DB_FILENAME} .dump")
        print("Or if this is an updated db, browse in a more controlled manner with")
        print(f"\tsqlitebrowser {LOCAL_DB_FILENAME}")


if __name__ == '__main__':
    parser = ArgumentParser("Fill in non-user-submitted data to a db. Can be re-run to add new survey rows.")
    args = parser.parse_args()
    main(args)
