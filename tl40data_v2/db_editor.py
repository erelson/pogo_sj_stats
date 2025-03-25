#! /usr/bin/env python3

# Standard library
from argparse import ArgumentParser
import datetime

# Third party
from fuzzywuzzy import process
from sqlalchemy.orm import registry, declarative_base, relationship, Session
from sqlalchemy import create_engine, event
from sqlalchemy.orm.exc import NoResultFound, UnmappedInstanceError
import sqlite3

# Local
from tables import Stat, Response, Trainer
from settings import LOCAL_DB_SPECIFIER, local_db_specifier_from_file

# Use: Launch this from my generate-stats bash script.

# Purpose: Navigate through and edit some DB entries

# Secondary purpose? Browse DB in some interesting way

def load_entries_from_db(session):
    """Read survey responses... TODO

    Returns: TODO
        trainers_lookup
        response_refs
    """
    #entries = {}

    # Get our trainer name:id lookup from the DB
    trainers = session.query(Trainer).all()
    trainers_lookup = {trainer.name: trainer.id for trainer in trainers}

    # Read all responses
    responses = session.query(Response).all()
    #for response in responses:
    #    trainer = trainers_lookup[response.trainer_id]
    #    if trainer == "test" or trainer == "*_-#test":
    #        continue
    #    if trainer not in entries:
    #        entries[trainer] = {}

    #    # Convert from timestamp (db) to datetime (used by our code)
    #    #entry_date = datetime.datetime.fromtimestamp(float(response.timestamp), tz=timezone('US/Pacific'))
    #    # Convert from timestamp (db) to datetime.date (used by our code)
    #    entry_date = datetime.date.fromtimestamp(float(response.timestamp))#, tz=timezone('US/Pacific'))

    #    entries[trainer][entry_date] = Stat.unpack_strdata(response.strdata, session, pad_data=True)
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
                    (result[0][1] > result[1][1] and confirm(f"Is '{result[0][0]}' correct? (y/n): ")):
                trainer = result[0][0]
            else:
                trainer = prompt_confirm_selection([x[0] for x in result])

            if not trainer:
                continue
                print("Done for now")
                return
            trainer_id = self.trainers_lookup[trainer]
            self.get_survey(trainer_id)

    def get_survey(self, trainer_id):
        """
        Args:
            trainer_id (int): DB index of the selected trainer.
        """
        while True:
            # List of [response_id, month/year] pairs for trainer_id
            trainer_surveys = [[response, data["month"]] for response, data in self.response_refs.items()
                                if data["trainer_id"] == trainer_id]
            # choose from 10 most recent surveys for trainer, most recent first
            survey = prompt_survey(trainer_surveys[-1:-11:-1])
            if not survey or survey == "abort":
                return
            self.get_stat(survey)

    def get_stat(self, survey_id):
        # Load all stat values from this survey
        survey = self.session.query(Response).filter(Response.id == survey_id).first()
        # TODO remove the self. from stats?
        # self.stats is dict {stat_name : {"value": value}, ...}
        self.stats = Stat.unpack_strdata(survey.strdata, self.session, pad_data=True)
        while True:
            print("\n(To abort updating values in this survey, give empty response or say 'abort')")
            stat_name = prompt_stat(self.stats)
            if not stat_name:
                break
                #return
            # Get current value
            stat_val = self.stats[stat_name]["value"]
            # Get updated value from user
            stat_val = self.edit_stat(stat_name, stat_val)
            self.stats[stat_name]["value"] = stat_val
        # Done with edit(s) to stat values; recreate strdata value and put it in DB
        if self.changed:
            # From tables.py
            #for k, v in response_values.items():
            #    # Presently, everything but the trainername is a numeric survey value
            #    if k == "trainername":
            #        continue
            #    stat_data_dict[k] = v
            # Then make the values a single string.
            stats_strdata = Stat.repack_strdata(self.stats)
            survey.strdata = stats_strdata  # Untested

            self.session.add(survey)  # A response object
            self.session.flush()
            self.session.commit()
            self.changed = False

    def edit_stat(self, stat, stat_val):
        print(f"The current value for '{stat}' is: {stat_val}")
        while True:
            new_val = input("Enter the new value for the stat: ")
            try:
                new_val = int(new_val)  # TODO float handling? cast as float and DB-writing maybe casts the value?
            except ValueError as e:
                continue
            break
        if new_val != stat_val:
            self.changed=True  # Or do we just write the value now? i.e. not going to queue this stuff up...
                               # Might be weird if I try and re-edit the value as I don't re-read the DB? Not sure.
        return new_val


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

def confirm(prompt):
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
    ##        (result[0][1] > result[1][1] and confirm(f"Is '{result[0][0]}' correct? (y/n)")):
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

def prompt_survey(trainer_surveys):
    values, keys = zip(*trainer_surveys)
    print("\nSelect which survey to work with")
    sel = prompt_confirm_selection(keys, values)
    return sel

def prompt_stat(stat_data):
    """
    Returns a stat name as determined user interaction.
    If user gives empty input or 'abort', returns None to signal user is done.
    """
    keys, values = zip(*[[key, value["value"]] for key, value in stat_data.items()])
    #keys, values = zip(*stat_data)
    inp = None
    while not inp:
        inp = input("What stat do you want to look at? (q to abort) ").strip()
    if not inp or inp.lower() in ['abort', 'q']:
        return None
    result = process.extract(inp, keys, limit=3)  # List of [key, score]
    # Check first selection
    if result[0][1] == inp or \
            (result[0][1] > result[1][1] and confirm(f"Is '{result[0][0]}' correct? (y/n): ")):
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
