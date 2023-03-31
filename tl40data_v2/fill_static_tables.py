#! /usr/bin/env python3

# Standard library
from argparse import ArgumentParser
import json
import os
from tables import Stat, Trainer, Response

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
    except OperationalError as e:
        existing_stat_lookup = {}

    static_stat_info = json.load(open("stats.json", 'r'))  # dict
    stat_names = static_stat_info["key"]  # list
    stat_vals = static_stat_info["data"]  # dict
    for cnt, stat_name in enumerate(stat_vals):
        #print(dir(stat_name))
        #print((stat_name))
        #if stat_name.name in existing_stat_lookup:
        if stat_name in existing_stat_lookup:
            # TODO verify this doesn't break when we add it?
            stat = existing_stat_data[cnt]
            #print(dir(stat))
            #print(stat.keys())
            if stat.order_idx != cnt:
                changed = True
            stat.order_idx = cnt
        else:
            stat = Stat(name=stat_name, order_idx=cnt,
                        **dict(zip(stat_names, stat_vals[stat_name])))
            changed = True

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


if __name__ == '__main__':
    parser = ArgumentParser("Fill in non-user-submitted data to a db")
    args = parser.parse_args()
    main(args)
