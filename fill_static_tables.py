#! /usr/bin/env python3

# Standard library
from argparse import ArgumentParser
import json
from tables import Stat, Trainer, TrainerStatMetrics, Response

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
            print(f"Adding '{stat_name}' to 'stats' table...")
            stat = Stat(name=stat_name, order_idx=new_stat_order_idx,
                        **dict(zip(json_stat_names, json_stat_vals[stat_name])))
            changed = True
            new_stat_order_idx += 1  # increment idx for the next new stat

        session.add(stat)

    return changed

# No static trainer or response data, unless we're testing something


def fill_trainer_metrics(session: Session):
    """Calculate metrics for trainers who don't already have them.

    This is intended for converting old databases to the new schema with
    trainer_stat_metrics table. Only generates metrics for trainers who:
    - Don't already have metrics in the database
    - Have at least 2 survey responses

    For updating existing metrics after manual corrections, use db_editor.py
    which automatically recalculates metrics after edits.

    Args:
        session: SQLAlchemy session

    Returns:
        dict: Statistics about the operation
    """
    print("\nFilling missing trainer metrics...")

    # Get all trainers
    try:
        all_trainers = session.query(Trainer).all()
    except OperationalError as e:
        print(f"ERROR: Cannot read trainers table: {e}")
        return {'error': True}

    total_trainers = len(all_trainers)
    print(f"  Found {total_trainers} trainers")

    stats = {
        'total': total_trainers,
        'processed': 0,
        'skipped_no_responses': 0,
        'skipped_has_metrics': 0,
        'errors': 0
    }

    # Process each trainer
    for trainer in all_trainers:
        # Check if trainer already has metrics
        existing_metrics_count = session.query(TrainerStatMetrics).filter(
            TrainerStatMetrics.trainer_id == trainer.id
        ).count()

        if existing_metrics_count > 0:
            stats['skipped_has_metrics'] += 1
            continue

        # Get response count
        response_count = session.query(Response).filter(
            Response.trainer_id == trainer.id
        ).count()

        # Need at least 2 responses to calculate metrics
        if response_count < 2:
            stats['skipped_no_responses'] += 1
            continue

        # Calculate metrics for this trainer (who has no existing metrics)
        try:
            TrainerStatMetrics.update_metrics_for_trainer(session, trainer)
            stats['processed'] += 1
        except Exception as e:
            print(f"  Warning: Error processing {trainer.name}: {e}")
            stats['errors'] += 1
            session.rollback()
            continue

    # Print summary
    print(f"  Processed: {stats['processed']} trainers (new metrics created)")
    print(f"  Skipped: {stats['skipped_has_metrics']} (already have metrics)")
    print(f"  Skipped: {stats['skipped_no_responses']} (insufficient responses)")
    if stats['errors'] > 0:
        print(f"  Errors: {stats['errors']}")

    return stats


def main(args):
    ran_ok = True
    changed = False

    db_specifier = LOCAL_DB_SPECIFIER
    #engine = get_engine(db_specifier)
    engine = create_engine(db_specifier)
    session = Session(engine, autoflush=True)

    # Fill static stat data
    changed = fill_stats(session) or changed
    try:
        session.commit()
    except OperationalError as e:
        print("ERROR: Did you run tables.py to create the tables first?")
        print(e)
        ran_ok = False

    # Calculate trainer metrics (unless skipped)
    if ran_ok and not args.skip_metrics:
        try:
            metrics_stats = fill_trainer_metrics(session)
            session.commit()
            if metrics_stats.get('error'):
                print("WARNING: Metrics calculation had errors")
        except OperationalError as e:
            print(f"WARNING: Could not calculate trainer metrics: {e}")
            print("  (This is expected for new/empty databases)")
    elif ran_ok and args.skip_metrics:
        print("\nSkipping trainer metrics calculation (--skip-metrics)")

    session.flush()
    session.close()

    if ran_ok:
        if changed:
            print("\nSuccess!")
        else:
            print("\nNOTE!: No changes needed to be made to the DB...")

        print("You can inspect the (presumably new, mostly empty) DB with:")
        print(f"\tsqlite3 {LOCAL_DB_FILENAME} .dump")
        print("Or if this is an updated db, browse in a more controlled manner with")
        print(f"\tsqlitebrowser {LOCAL_DB_FILENAME}")


if __name__ == '__main__':
    parser = ArgumentParser("Fill in non-user-submitted data to a db. Can be re-run to add new survey rows.")
    parser.add_argument(
        '--skip-metrics',
        action='store_true',
        help='Skip calculating trainer metrics (faster for testing/new DBs)'
    )
    args = parser.parse_args()
    main(args)
