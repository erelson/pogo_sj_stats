#! /usr/bin/env python3

# Some assumptions:
# - All dates listed on tl40 are MM/DD/YYYY regardless of locale, etc.

# Standard library
from argparse import ArgumentParser
import calendar
import csv
import datetime
import json
import os
import re

# Third party
import dominate
from dominate.tags import a, b, img, link, option, select, table, tr, td, th, div, script, meta, sup
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.engine import ExceptionContext

# Custom
from download_google_sheets_csv import main as get_csv

# Local
from tables import Stat, Response
from settings import LOCAL_DB_SPECIFIER


# Keep a list of current and past column headers tracked in the survey.
# This lets us support old submissions when a column is added and present in newer submissions.
# Could maybe refer to these as schemas?
# ASSUMPTION: first column_names file should be the most complete one
column_names_files = ["columns_11-7.json", "columns_11-7_no-types.json"]
column_names = []


REPORT_FIELDS_PATH = "report_fields_1.json"

DAY_TO_INT = dict(zip(calendar.day_name, range(7)))
SURVEY_LINK = "https://docs.google.com/forms/d/e/1FAIpQLScOSB49nQMQDIKamSqdLwCL65AddprQJF7Htm5R9J03OjOESw/viewform?usp=sf_link"

N_DEX_ENTRIES = 9
# Note that the survey ignores the regular dex count. Our "Sum of All" doesn't include this, which is rather arbitrary.
DEX_NAMES = ["Purified", "Shadow", "Perfect", "3 Stars", "Shiny 3 Stars", "Shiny", "Lucky", "Event", "Mega", "Sum of All Dex Counts"]
N_TYPE_MEDALS = 18

       # dex_data = [int(val) if val else None for val in raw_entry[3:12]]  # 9 dex entries we started recording
       # for cnt, (dex_cnt, dex_cnt2) in enumerate(zip(dex_entries[user], dex_data)):
       #     if dex_cnt2:
       #         if dex_cnt is None or dex_cnt2 > dex_cnt:
       #             dex_entries[user][cnt] = dex_cnt2

def get_column_names(filepaths=column_names_files):
    # Runs once to initialize column_names if needed.
    if column_names:
        return column_names
    for fp in filepaths:
        if not os.path.isfile(fp):
            fp = os.path.join(os.path.dirname(__file__), fp)
            if not os.path.isfile(fp):
                print("Error: Setup: Failed to find file '{fp}' for column names" )
                continue
        with open(fp, 'r') as fr:
            try:
                colnames = json.load(fr)
                if not isinstance(colnames, list):
                    raise TypeError("Json must contain a single list")
            except Exception as e:
                print(e)
                print("Error: Setup: Failed to load column names in '{fp}'" )
                continue
            column_names.append(colnames)

    column_names.sort(key=lambda x: len(x))
    return column_names


def relative_date_string_to_date(datestr, ref_date_str):
    """Return the date indicated by a relative date string like "Last Tuesday".

    While the strings include times, too, we don't parse these, since the older submissions
    reported on TL40 only have the date, not the time.

    Arguments:
        datestr (str): String starting with e.g. "Today", "Last Sunday", "Yesterday"
        ref_date_str (str): "MM/DD/YYYY HH:mm:ss" string, though only the date part is used

    Returns
        date - datetime.date:
    """
    ref_mon, ref_day, ref_year = [int(part) for part in ref_date_str.split()[0].split("/")]
    ref_date = datetime.date(ref_year, ref_mon, ref_day)
    datestr = datestr.strip()
    if datestr.startswith("Today"):
        return ref_date
    elif datestr.startswith("Yesterday"):
        return ref_date - datetime.timedelta(days=1)
    elif datestr.startswith("Last"):
        prev_dayname = datestr.split()[1]
        # day_delta should be a negative number of days
        days_delta = DAY_TO_INT[prev_dayname] - ref_date.weekday()
        while days_delta > 0:
            days_delta -= 7
        if days_delta == 0: # not verified that this occurs
            days_delta = -7
        #print(datestr, ref_date.weekday(), DAY_TO_INT[prev_dayname], days_delta)
        return ref_date + datetime.timedelta(days=days_delta)
    else:
        print(f"FAILED TO HANDLE 'datestr' with value '{datestr}'")
        return None

def raw_num_from_tl40(valstring):
    """Returns a number (int or float) as a string, or None"""
    if valstring.strip() == '---':  # Commonly seen for type medals
        return None
    try:
        int(valstring[0])
    except:
        # non-numeric values; just return the value
        return valstring
    val = valstring.split()[0] # column total value, e.g. '12345'
    val = val.replace(",", "")
    return val

def parse_csv_to_clean_submissions(session, fileobj):
    """

    Returns:
        entries: dict by user (lowercase), to subdict by "Response Date" list values.
        dex_entries: dict by user (lowercase), to subdicts by "Response Date" list values
    """
    # Load columns, if needed.
    # This feature lets us support old entries on the google form, in case tl40 adds additional columns later.
    column_names = get_column_names(column_names_files)
    print("Have column sets to match to, with lengths:")
    for colset in column_names:
        print("-", len(colset))

    raw = csv.reader(fileobj)
    raw_entries = [row for row in raw]
    entries = {}  # dict by user (lowercase), to subdicts by "Response Date" list values
    #dex_entries = {}  # dict by user (lowercase), to subdicts by "Response Date" list values  TODO

#def map_to_new_db(something):
    # TODO: something is going to be either:
    # - a single row of the google form
    # - the parsed result of a single row of the google form
    # ... TBD
    #response_dict["timestamp"] = raw_entry[0] # Nope - take it from the copy/paste blob
    # TODO might need to redeclare this after recreating response_dict...
    def add_to_response_dict(key, val):
        response_dict[key] = val

    with open("stats.json", 'r') as fr:
        stats = json.load(fr)
    field_lookup = dict([(stat, stats["data"][stat][8]) for stat in stats["data"]])
    function_lookup = {
           #0: lambda x: None # Timestamp,
           #1: lambda x: None # PoGo Name (either in-game or discord name),
           #2: parse_tl40_dump # Copy paste output parser
           3: lambda x: add_to_response_dict("pokedex_purified", x), # Purified
           4: lambda x: add_to_response_dict("pokedex_shadow", x), # Shadow
           5: lambda x: add_to_response_dict("pokedex_4star", x), # Perfect
           6: lambda x: add_to_response_dict("pokedex_3star", x), # 3 Stars
           7: lambda x: add_to_response_dict("pokedex_3star_shiny", x), # Shiny 3 Stars
           8: lambda x: add_to_response_dict("pokedex_shiny", x), # Shiny
           9: lambda x: add_to_response_dict("pokedex_lucky", x), # Lucky
           10: lambda x: add_to_response_dict("pokedex_event", x), # Event
           11: lambda x: None, # Mega - covered by "Mega/Primal Evolution Guru"
           12: lambda x: add_to_response_dict("pokedex_entries_gen9", x), #Hisui Dex/Medal Count
           13: lambda x: add_to_response_dict("pokedex_entries_gen7", x), #Alola Dex/Medal Count
           14: lambda x: add_to_response_dict("vivilloncollector", x), #Vivillon Collector
           }

    # For each copy-paste by a participant; possibly including multiple submissions to TL40.
    for lineno, raw_entry in enumerate(raw_entries[1:]):
        # raw_entry is a list of spreadsheet cell contents in the responses row. length varies
        # Sanit checks
        input_lines = raw_entry[2].splitlines()
        if len(input_lines) == 0:
            continue
        print(f"Num input lines in submission ({raw_entry[1]}):", len(input_lines))
        form_sub_time = raw_entry[0]
        trainer = raw_entry[1].lower().strip()

        # Start processing submission
        response_dict = {"trainername": trainer}  # This first loop is special, and gets the
                                                  # the additional fields from the google form

        # Handle additional survey questions in columns idx 3+
        for colidx in range(3, len(raw_entry)):
            # Call function to interpret the column's value
            function_lookup[colidx](raw_entry[colidx])

        # NOTE: dex entry counts are different from survey responses of tl40 data because there's
        # only one "row" per submission (while we might have multiple tl40 rows in one response)
        #if user not in dex_entries:
        #    dex_entries[user] = [None] * N_DEX_ENTRIES
        #dex_data = [int(val) if val else None for val in raw_entry[3:12]]  # 9 dex entries we started recording
        #for cnt, (dex_cnt, dex_cnt2) in enumerate(zip(dex_entries[user], dex_data)):
        #    if dex_cnt2:
        #        if dex_cnt is None or dex_cnt2 > dex_cnt:
        #            dex_entries[user][cnt] = dex_cnt2

        # Parse copy/pasted blob
        input_lines = [line.split("\t") for line in input_lines]
        for cnt, line in enumerate(input_lines):
            if len(line) == 1:  # 8x spaces instead of tabs?
                input_lines[cnt] = line[0].split("        ")
        # Filter out first-column things, as well as "Survey History" and leading empty strings
        for idx in range(len(input_lines)):
            #
            while input_lines[idx] and input_lines[idx][0].strip() in ["edit", "done", "warning", "verified_user", "Survey History", '']:
                input_lines[idx] = input_lines[idx][1:]
            if len(input_lines[idx]) == 0:
                continue
            while input_lines[idx][-1] == '':
                input_lines[idx] = input_lines[idx][:-1]
        # Filter out empty lines...
        input_lines = [inp for inp in input_lines if inp]

        # Toss truncated start/end lines from copy-paste variation
        if len(input_lines) > 2:
            # Remove truncated last line
            if len(input_lines[1]) > len(input_lines[-1]):
                input_lines = input_lines[:-1]
            # Remove truncated first line
            if len(input_lines[0]) < len(input_lines[-1]):
                input_lines = input_lines[1:]
            first_len = len(input_lines[0])
            # Check consistent length of remaining "full" lines
            if len(input_lines) > 1 and not all(first_len == len(line) for line in input_lines[1:]):
                print(f"Warning: for entry {raw_entry[:2]} got varying number of line parts... should investigate...")
                print(f"   had {len(input_lines)} after cleanup when checking this...")

        # Iterate over each pasted-from-TL40 submission within a google form submission
        # TODO 3-6-2023: Should I do this in reverse order for the date stuff below? Or should I just include all submissions?
        # I think I already check for newest submissions in the rendering code
        for idx, line in enumerate(input_lines):
            # Reset for each row after the first; the first is started above
            # and includes the additional fields like special dex counts.
            if idx > 0:
                response_dict = {"trainername": trainer}
            # Skip header lines - no numbers at all in them
            if not re.search("\d", "".join(line)):
                continue

            # Match lines to column sets by length, aka number of columns
            # Note: above we already remove "done" (the check mark's alt text) and similar from start of lines
            found_colset = False
            for colset in column_names:  # Iterate over known line lengths (i.e. number of columns)
                if len(line) == len(colset):
                    found_colset = True
                    break
                # TODO validate line further
            # Recovery: Possibly handle partial copying of lines, where user both did not fill in catch medal counts,
            # and selected some of those unfilled ('---') columns.
            oldline = None  # line before we drop trailing '---' columns
            if not found_colset:
                oldline = line
                while line[-1] == '---':
                    line = line[:-1]
                for colset in column_names:  # Iterate over known line lengths (i.e. number of columns)
                    if len(line) == len(colset):
                        found_colset = True
                        break
            if not found_colset:
                print(f"!!!!!!!!!!!Was unable to find colset for line {lineno+2} ({raw_entry[1]})...", len(line))  # TODO more debug output
                if oldline:
                    print("Full line parts:")
                    print(oldline)
                    print(f"Line parts after stripping '---' (resulting in {len(line)} remaining parts)")
                print(line)
                continue

            # Skipping header lines, i.e. lines that match the colset's column names
            if colset[0] == line[0].strip(): # lazy but maybe we need to fix this
                continue
            # Get the tl40 submission's time
            submission_time = line[0]  # string
            try:
                sub_mon, sub_day, sub_year = [int(part) for part in submission_time.split()[0].split("/")]
                submission_date = datetime.date(sub_year, sub_mon, sub_day)
                #submission_timestamp = datetime.datetime.strftime(submission_date, "%Y-%m-%d %H:%M:%S").timestamp()
                submission_timestamp = datetime.datetime.strptime(submission_time, "%m/%d/%Y").timestamp()
            except Exception as e:  # TODO exception types
                print("Error was", type(e), e)
                submission_date = relative_date_string_to_date(submission_time, form_sub_time)
                submission_timestamp = datetime.datetime(year=submission_date.year,
                                                         month=submission_date.month,
                                                         day=submission_date.day).timestamp()

            survey_entry_data = {field_lookup[field]: raw_num_from_tl40(val) for field, val
                                 in zip(colset, line) if field in field_lookup}
            survey_entry_data_clean = {field: val for field, val in survey_entry_data.items()
                                       if val is not None} 
            response_dict.update(survey_entry_data_clean)

            # If not a duplicate submission (based on timestamp)
            # TODO OOOOOOOOOOOOOOOOOOOOOOOOOOOOOO 2-20-2023
            if submission_on_new_date(session, trainer, submission_date):
                #print("Saving")
                Response.save_response(session, response_values=response_dict, timestamp=submission_timestamp)
            else:
                print(f"Skipped submission for {trainer} on {submission_date} as it's already in DB")

    # Nearly every column in tl40data (columns_11-7.json) matches a stat name from stats.json

    # Do this in chunks:
    #for cnt, column in enumerate(row):
        # Parse the columns from column_11-7[_no-types]

        # Parse the extra survey columns, when present
        #if cnt 

    #Response.save_response(session, response_values=response_dict)


    print("BYE!")
    return entries#, dex_entries


def submission_on_new_date(session, trainer, submission_date):

    # Get all submission dates by trainer
    dates = []  # session.

    for date in dates:
        if submission_date == date:
            return False
    # No duplicate submission recorded
    return True


def main(args, session):
    # ...
    with open(REPORT_FIELDS_PATH, 'r') as fr:
        report_fields_dict = json.load(fr)  # expect a list of strings matching field keys
    report_fields = list(report_fields_dict.keys())

    # If not given a CSV, try to get CSV by treating args.file as a keyfile
    if not args.file.endswith(".csv"):
        csvfilename = "latest_stats_responses.csv"
        try:
            get_csv(keyfile=args.file, save_file=csvfilename)
        except Exception as e:
            print("Got an exception while trying to auto-obtain .csv file:")
            print(e)
            print("Make sure you pass in either a .csv file or a keyfile for Google Docs API.")

        args.file = csvfilename

    # Read CSV file
    with open(args.file, 'r') as fr:
        #entries, dex_entries = parse_csv_to_clean_submissions(session, fr)
        parse_csv_to_clean_submissions(session, fr)

    # Calculate monthly diffs
    #add_monthly_changes(entries, list(report_fields_dict.keys()))

    #render_monthly(entries)

    # Generate HTML for each month
    #today_date = datetime.date.today()
    #starting_date = datetime.date(day=1, year=today_date.year, month=today_date.month)
    ##starting_date = datetime.date(day=1, year=2022, month=2)
    #running_totals = None  # will become a dict
    #player_platinum_tracker = None  # will become a dict
    #for n in range(-11, 1):  # last 12 months, starting from 12 months ago
    #    newmonthdate = starting_date + relativedelta(months=n, days=-1)  # e.g. 10-31-2021

    #    # Start of an HTML document
    #    doc = dominate.document(title='PoGo Stats - San Jose')
    #    with doc.head:
    #        link(rel='stylesheet', href='style.css')
    #        meta(charset='utf-8')
    #    with doc:
    #        # TODO move to func?
    #        # Top bar with linked icons, survey link, and dropdown
    #        header_box = div(cls="headerbox", id="myHeader")
    #        with header_box:
    #            with div(cls="iconsbox"):
    #                for key in report_fields:
    #                    keyname = report_fields_dict[key]
    #                    a(img(width=50, title=keyname, alt=keyname, src=f"{keyname}.png"), href=f"#{keyname}")
    #                month_selector = select(name="months", id="months_select", onchange="monthSelect()")
    #                with month_selector:
    #                    option(calendar.month_name[newmonthdate.month] + " " + str(newmonthdate.year), selected="selected")
    #                    for m in range(12):
    #                        monthdate = starting_date + relativedelta(months=-1 * m, days=-1)  # e.g. 10-31-2021
    #                        month_year_str = calendar.month_name[monthdate.month] + " " + str(monthdate.year)
    #                        opt = option(month_year_str, value=str(monthdate).rsplit("-", maxsplit=1)[0] + ".html")
    #                a("Submit survey data", href=SURVEY_LINK, cls="headerlinks")

    #        # Tables for each stat
    #        content, running_totals, player_platinum_tracker, aborted = render_monthly_html(entries,
    #                                                                                        newmonthdate,
    #                                                                                        running_totals,
    #                                                                                        player_platinum_tracker)
    #        if aborted:
    #            print(f"Skipped month ending on: {newmonthdate} (render_monthly_html aborted; no or invalid data for month)")
    #            continue
    #        script(type='text/javascript', src='scroll2.js')

    #        # Tables for dex entry counts, only included for the most recent month
    #        if n == 0:
    #            # Flatten the dex_entries dict to a list of sublists containing:
    #            # a) the individual dex counts (None -> 0 for sort purposes)
    #            # b) Sum of all dex counts
    #            # c) player name at the end
    #            dex_lists = [ [val or 0 for val in values] + [sum([val or 0 for val in values])] + [player] for player, values in dex_entries.items()]
    #            for idx, dexname in enumerate(DEX_NAMES):
    #                dex_lists.sort(key=lambda x: x[idx], reverse=True)
    #                table_data = [(user_dex[-1], user_dex[idx]) for user_dex in dex_lists[:20] if user_dex[idx] > 0]

    #                div_table2 = div(cls="todo")
    #                with div_table2:
    #                    table2_div = table()
    #                    with table2_div:
    #                        th(f"Pokédex: {dexname}", colspan=3, cls=dexname.replace("3", "Three").replace(" ", ""))
    #                        tr(td(b("Rank")), td(b("Player")), td(b(dexname)))
    #                        [tr(td(cnt+1), td(item[0]), td(item[1])) for cnt, item in enumerate(table_data)]

    #    date_string = str(newmonthdate).rsplit("-", maxsplit=1)[0]
    #    print("Generated page for", date_string)
    #    with open(f"html/{date_string}.html", 'w') as fr:
    #        fr.write(str(doc))

    #    if n == 0:  # copy first generated page to be our 'html/index.html'
    #        try:
    #            shutil.copy(f"html/{date_string}.html", "html/index.html")
    #            print("Copied most recent month to 'html/index.html'")
    #        except shutil.SameFileError:
    #            pass
    #        except PermissionError:
    #            print("Weird. A permission error when copying to 'html/index.html'...")
    #        except Exception as e:
    #            print("an unexpected Exception occurred that I was too lazy to predict...")
    #            raise


if __name__ == "__main__":
    parser = ArgumentParser(description="Grab a google sheet (or use a specified local CSV) "
                                        "and generate HTML stat pages")
    parser.add_argument("file", default="pogo_sj_stats_oct2021.csv",
                        help="CSV file from google sheets, containing entire history of form responses")
    args = parser.parse_args()

    db_specifier = LOCAL_DB_SPECIFIER 
    engine = create_engine(db_specifier)
    session = Session(engine, autoflush=True)

    main(args, session)
