#! /usr/bin/env python3

# NOTE: adapted from copy of db_editor.py 3-2025

"""This script is hopefully a one off that helps deal with the pokedex update
in Pokemon Go circa 2-2025.  Two updates occured about a month apart, resulting in
surveys needing to handle the following scenarios:
    - The old way: 3* and other dexes
    - The incomplete new way: Game failed to report the counts for the various dexes
    - The new way: 3* and other dexes removed; XXL/XXS dexes added; and dex counts
      working again.
When surveys were filled out in the second scenario, the entries for all dex entries
were left off the survey, resulting in 0 values for these stats in the DB.
When the dex counts were working again with the third scenario, we wanted to avoid
artificial large stat increases. (also large decreases for the changes from the
first scenario to second scenario's zeroes)

This script implements a one-time solution for that:
    - Run after surveys in scenario 2 were done, and after scenario 3 was live, but before
    the subsequent month's survey...
    - Take the non-zero values from "two months" ago, i.e. the first scenario,
      and update any 0 values recorded in the second scenario. (What this script does)
    - (Not done by this script) Save and push the modified DB live.
"""

# Standard library
from argparse import ArgumentParser
import datetime

# Third party
from fuzzywuzzy import process
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm.exc import NoResultFound, UnmappedInstanceError

# Local
from tables import Stat, Response, Trainer
from settings import LOCAL_DB_SPECIFIER, local_db_specifier_from_file


def load_entries_from_db(session):
    """Read survey responses... TODO

    Returns: TODO
        trainers_lookup
        response_refs
    """
    # Get our trainer name:id lookup from the DB
    trainers = session.query(Trainer).all()
    trainers_lookup = {trainer.name: trainer.id for trainer in trainers}

    # Read all responses
    responses = session.query(Response).all()
    response_refs = {response.id: {"trainer_id": response.trainer_id,
                                   "month": report_month_year(response.timestamp)} for
                     response in responses}

    stat_table = session.query(Stat).all()
    # Get list of stats that make up the survey responses.
    stat_keys = [[item.name, item.order_idx] for item in stat_table]
    return trainers_lookup, response_refs, stat_keys

class Editor():
    def __init__(self, db_filepath=None):

        # Open DB
        if db_filepath:
            db_specifier = local_db_specifier_from_file(db_filepath)
        else:
            db_specifier = LOCAL_DB_SPECIFIER
        engine = create_engine(db_specifier)
        self.session = Session(engine)

        self.changed = False
        self.trainers_lookup, self.response_refs, self.stat_keys = load_entries_from_db(self.session)

    def get_trainer(self):
        while True:
            trainer = None
            trainer_list = self.trainers_lookup.keys()
            inp = None
            while not inp:
                inp = input("\nWhat trainer do you want to look at? (q to abort) ")
                if inp == 'q' or inp == 'abort':
                    print("Done for now")
                    return
            result = process.extract(inp, trainer_list, limit=3)
            # Check first selection
            if result[0][0] == inp or \
                    (result[0][1] > result[1][1] and prompt_confirm(f"Is '{result[0][0]}' correct? (y/n): ")):
                trainer = result[0][0]
            else:
                trainer = prompt_confirm_selection([x[0] for x in result])

            if not trainer:
                continue
                print("Done for now")
                return
            trainer_id = self.trainers_lookup[trainer]
            self.get_and_update_surveys(trainer_id)

    def get_and_update_surveys(self, trainer_id):
        """
        Args:
            trainer_id (int): DB index of the selected trainer.
        """
        # List of [response_id, month/year] pairs for trainer_id
        trainer_surveys = [[response, data["month"]] for response, data in self.response_refs.items()
                            if data["trainer_id"] == trainer_id]
        # grab 2 most recent surveys for trainer, most recent first
        surveys = trainer_surveys[-1:-3:-1]
        print("Loaded last two surveys")
        self.update_newest_from_previous_survey(surveys)

    def update_newest_from_previous_survey(self, surveys):
        """
        Args:
            surveys: List of two survey IDs [newest, second-newest]
        """
        assert(len(surveys) == 2)
        # Load all stat values from the surveys
        print(surveys)
        surveyLatest = self.session.query(Response).filter(Response.id == surveys[0][0]).first()
        surveyPrev = self.session.query(Response).filter(Response.id == surveys[1][0]).first()
        # TODO remove the self. from stats?
        # self.stats is dict {stat_name : {"value": value}, ...}
        statsLatest = Stat.unpack_strdata(surveyLatest.strdata, self.session, pad_data=True)
        statsPrev = Stat.unpack_strdata(surveyPrev.strdata, self.session, pad_data=True)
        changes = {}
        for stat_name, val in statsLatest.items():
            val = val["value"]
            if val == 0:
                prev_val = statsPrev[stat_name]["value"]
                if prev_val != 0:
                    statsLatest[stat_name]["value"] = prev_val
                    changes[stat_name] = prev_val
        # Confirm with user the changes being made:
        print("The following changes would be made for this trainer's survey:")
        for k in changes:
            print('\t', changes[k], "\t-", k)

        if prompt_confirm("Go ahead and apply changes? (y/n)"):
            stats_strdata = Stat.repack_strdata(statsLatest)
            surveyLatest.strdata = stats_strdata

            print("Writing to DB...")
            self.session.add(surveyLatest)  # A response object
            self.session.flush()
            self.session.commit()
            self.changed = False


def report_month_year(timestamp):
    # Convert the timestamp to a datetime object
    date = datetime.datetime.fromtimestamp(float(timestamp))

    # Check if the day is one of the first three days
    if date.day <= 3:
        # Move to the previous month
        first_day_of_current_month = date.replace(day=1)
        last_day_of_previous_month = first_day_of_current_month - datetime.timedelta(days=1)
        month = last_day_of_previous_month.month
        year = last_day_of_previous_month.year
    else:
        month = date.month
        year = date.year

    # Convert month to a full month name
    month_name = datetime.datetime(year, month, 1).strftime("%B")

    return month_name, year

def prompt_confirm(prompt):
    """Prompt should be a string ending in (y/n)"""
    ans = None
    while ans not in ['y', 'n']:
        ans = input(prompt).lower().strip()[0]
    return ans == 'y'

def prompt_confirm_selection(options, vals=None):
    """
    """
    if vals:
        assert(len(options) == len(vals))
    for idx, x in enumerate(options):
        print(f"{idx + 1}: {x}")
    print("q: Abort")
    sel = -1
    while sel not in range(len(options)):
        sel = input("Enter the number of the desired option: ").strip()
        # User abort
        if not sel:
            continue
        elif sel[0] == 'q':
            return None
        # Regular input
        try:
            sel = int(sel) - 1
        except Exception:
            continue
        if vals:
            return vals[sel]
        else:
            return options[sel]

def main(args):
    editor = Editor(args.db)
    editor.get_trainer()

    ## return

    ## # Start:
    ## trainers_lookup, response_refs = load_entries_from_db(session)
    ## trainer_list = trainers_lookup.keys()
    ## # Prompt: What trainer do you want to look at?
    ## inp = input("What trainer do you want to look at? ")
    ## result = process.extract(inp, trainer_list, limit=3)
    ## print(result)
    ## # Check first selection
    ## if result[0][1] == inp or \
    ##        (result[0][1] > result[1][1] and prompt_confirm(f"Is '{result[0][0]}' correct? (y/n)")):
    ##     trainer = result[0][1]
    ## # Else prompt user for which of top matches to use
    ## else:
    ##     trainer = prompt_confirm_selection([x[0] for x in result])
    ## # Alternate: Abort; prompt save if diffs made
    ## # Fuzzy look-up
    ## # List surveys by month (limit to 12?)
    ## "Which survey do you want to inspect the values of?"
    ## #  Function to generate "survey month" from timestamp
    ## # Prompt select survey by index
    ## return
    ## # Alternate: q: Go back to trainer selection
    ## # Prompt: What stat do you want to inspect?
    ## inp = input("What stat do you need to check? ")
    ## result = process.extract(inp, trainer_list, limit=3)
    ## print(result)
    ## # Alternate options: q: go back to list of surveys
    ## # Fuzzy look-up
    ## # Print value
    ## # Prompt: Set different value?
    ## # Update value in DB (but don't sync?)
    ## # Prompt: Lookup another value or 'q':

def prompt_stat(stat_data):
    """
    Returns a stat name as determined user interaction.
    If user gives empty input or 'abort', returns None to signal user is done.
    """
    keys, values = zip(*[[key, value["value"]] for key, value in stat_data.items()])
    inp = None
    while not inp:
        inp = input("What stat do you want to look at? (q to abort) ").strip()
    if not inp or inp.lower() in ['abort', 'q']:
        return None
    result = process.extract(inp, keys, limit=3)  # List of [key, score]
    # Check first selection
    if result[0][1] == inp or \
            (result[0][1] > result[1][1] and prompt_confirm(f"Is '{result[0][0]}' correct? (y/n): ")):
        stat_name = result[0][0]
    # Else prompt user for which of top matches to use
    else:
        print("\nWhich stat did you want?")
        stat_name = prompt_confirm_selection([x[0] for x in result])
    return stat_name


if __name__ == '__main__':
    parser = ArgumentParser("Fill in non-user-submitted data to a db. Can be re-run to add new survey rows.")
    parser.add_argument("db", nargs='?', default="pogo_sj.db",
                        help="Database file to work with. Default: %(default)s")
    args = parser.parse_args()
    main(args)
