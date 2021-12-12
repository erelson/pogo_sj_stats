#! /usr/bin/env python3

# Some assumptions:
# - All dates listed on tl40 are MM/DD/YYYY regardless of locale, etc.

from argparse import ArgumentParser, Namespace
import calendar
import csv
import datetime
import json
import os
import shutil

# Third party
import dominate
from dominate.tags import a, b, img, link, option, select, table, tr, td, th, div, script
from dateutil.relativedelta import relativedelta


# Keep a list of current and past column headers tracked in the survey.
# This lets us support old submissions when a column is added and present in newer submissions.
# Could maybe refer to these as schemas?
# ASSUMPTION: first column_names file should be the most complete one
column_names_files = ["columns_11-7.json", "columns_11-7_no-types.json"]
column_names = []

report_fields_path = "report_fields_1.json"

DAY_TO_INT = dict(zip(calendar.day_name, range(7)))
SURVEY_LINK = "https://docs.google.com/forms/d/e/1FAIpQLScOSB49nQMQDIKamSqdLwCL65AddprQJF7Htm5R9J03OjOESw/viewform?usp=sf_link"


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
    """
    Arguments:
        datestr - string: String starting with e.g. "Today", "Last Sunday", "Yesterday"
        ref_date_str - ...: "MM/DD/YYYY HH:mm:ss" string, though only the date part is used

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

def parse_csv_to_clean_submissions(fileobj, column_names=None):
    """
    Returns:
        entries: dict by user (lowercase), to subdict by "Response Date" list values

    """
    # Load columns, if needed.
    # This feature lets us support old entries on the google form, in case tl40 adds additional columns later.
    if column_names is None:
        column_names = get_column_names(column_names_files)
    print("Have column sets to match to, with lengths:")
    for colset in column_names:
        print("-", len(colset))

    raw = csv.reader(fileobj)
    raw_entries = [row for row in raw]
    # TODO(enhancement) change from list to transformed list that matches latest survey columns...
    entries = {}  # dict by user (lowercase), to subdict by "Response Date" list values

    for lineno, raw_entry in enumerate(raw_entries[1:]):  # One copy-paste by a participant; possibly including multiple submissions to TL40.
        input_lines = raw_entry[2].splitlines()
        print("Num input lines in submission:", len(input_lines))
        form_sub_time = raw_entry[0]
        user = raw_entry[1]
        if user.lower() not in entries:
            entries[user.lower()] = {}
        input_lines = [line.split("\t") for line in input_lines]
        # Filter out first-column things, as well as "Survey History" and leading empty strings
        for idx in range(len(input_lines)):
            if len(input_lines[idx]) == 0:
                continue
            #print(len(input_lines), idx)
            #print(len(input_lines[idx]))
            while input_lines[idx] and input_lines[idx][0].strip() in ["edit", "done", "warning", "verified_user", "Survey History", '']:
                #print("prePOP!", input_lines[idx])
                input_lines[idx] = input_lines[idx][1:]
                #print("POP!")#, input_lines[idx])
        # Filter out empty lines...
        input_lines = [inp for inp in input_lines if inp]
        #print([len(l) for l in input_lines])

        # Toss truncated start/end lines from copy-paste variation
        if len(input_lines) > 2:
            # Remove truncated last line
            if len(input_lines[1]) > len(input_lines[-1]):
                input_lines = input_lines[:-1]
            # Remove truncated first line
            #if len(input_lines[1]) > len(input_lines[-1]):  # Buggy version probably
            if len(input_lines[0]) < len(input_lines[-1]):
                input_lines = input_lines[1:]
            first_len = len(input_lines[0])
            # Check consistent length of remaining "full" lines
            if len(input_lines) > 1 and not all(first_len == len(line) for line in input_lines[1:]):
                print(f"Warning: for entry {raw_entry[:2]} got varying number of line parts... should investigate...")
                print(f"   had {len(input_lines)} after cleanup when checking this...")
        for line in input_lines:  # Iterate over each TL40 submission
            # Discard lines that are too short
            # TODO... "for ncolumns in known_column_groups: try to match line to group"
            # Keep lines of right length
            found_colset = False
            for colset in column_names:  # Iterate over known line lengths (i.e. number of columns)
                # Match based on length... lines will have one extra entry
                # Note: above we already remove "done" (the check mark's alt text) and similar from start of lines
                #if len(line.split()) - 1 == len(colset):
                #print("COMPARE", len(line), len(colset))
                if len(line) == len(colset):
                    #if colset[0] == line[0]: # lazy but maybe we need to fix this
                    #    # Skipping header line
                    #    print("skip:", line[:3])
                    #    continue

                    #print("Matched to a header set!")
                    found_colset = True
                    break
                # TODO validate line further

            #print(colset[0] == line[0], f"'{colset[0]}' '{line[0]}'")
            if colset[0] == line[0].strip(): # lazy but maybe we need to fix this
                # Skipping header line
                #print("match then skip:", line[:3])
                continue
            if not found_colset:
                print(f"!!!!!!!!!!!Was unable to find colset for line {lineno+2} ({raw_entry[1]})...", len(line))  # TODO more debug output
                print(line)
                continue
            # ???
            #lineparts = line.split('\t')
            submission_time = line[0]

            #print('\t\t\t\t', submission_time)
            try:
                sub_mon, sub_day, sub_year = [int(part) for part in submission_time.split()[0].split("/")]
                submission_date = datetime.date(sub_year, sub_mon, sub_day)
            except:  # TODO exception types
                submission_date = relative_date_string_to_date(submission_time, form_sub_time)
            #entries[user.lower()] = {str(submission_date):
            #entries[user.lower()][str(submission_date)] = \
            entries[user.lower()][submission_date] = \
                    { field: get_val(val)  for field, val in zip(colset, line)} #column_names[0]}
            # Fill in extra columns
            #entries[user.lower()] = {str(submission_date):
            #        { field: val for field, val  in zip(colset, line)} }#column_names[0]}

    return entries


def get_val(valstring):
    # A bunch of lazy parsing logic
    # TODO decide what empty/missing values ought to be and explicitly define meaning of None or empty string, etc.
    valstring = valstring.strip()
    if valstring == "---" or not valstring:
        return (None, None)
    #print(valstring)
    if len(valstring) == 10 and valstring[2] == "/": # dates
        return (valstring, '')
    try:
        int(valstring[0])
    except:
        # non-numeric values
        return (valstring.strip(), '')
    val = valstring.split()[0]  # For now we ignore the diffs
    val = int(val.replace(",", ""))
    if len(valstring.split()) == 2:
        incrstring = valstring.split()[1]
        incrstring = int(incrstring.strip("()+").replace(",", ""))
    else: incrstring = 0
    return (val, incrstring)


def find_near_date(all_data, target_date, day_delta=1):
    """Find form submissions near specific date (typically look for last day of month +/- 1 day)

    Arguments
        all_data : entries : dict by user, containing subdict by date
        target_date : datetime.date
        day_delta : integer : half-window size around target_date, e.g. 1 -> +/- 1 day.

    Returns
        dict by user, containing survey values/increments data dictionary.
            Users without data near a date won't be in this returned dict
    """
    min_date = target_date - datetime.timedelta(days=day_delta)
    max_date = target_date + datetime.timedelta(days=day_delta)
    def in_date_range(_date):
        return min_date <= _date <= max_date

    nearest_entries = {}
    for user, entries in all_data.items():
        entry_date = None
        # Pick the latest date within the range
        for date in entries.keys():
            if in_date_range(date):
                if entry_date is None or (entry_date is not None and date > entry_date):
                    entry_date = date
        if entry_date:
            nearest_entries[user] = entries[entry_date]

    return nearest_entries


#def render_monthly(entries):
#
#    with open(report_fields_path, 'r') as fr:
#        report_fields_dict = json.load(fr)  # expect a list of strings matching field keys
#    report_fields = list(report_fields_dict.keys())
#
#    # TODO for range ... months
#    today_date = datetime.date.today()
#    starting_date = datetime.date(day=1, year=today_date.year, month=today_date.month)
#    for n in range(12):
#        newdate = starting_date + relativedelta(months=-1 * n, days=-1)
#    oct_data = find_near_date(entries, datetime.date(2021, 10, 31))
#    #sept_data = find_near_date(entries, datetime.date(2021, 9, 30))
#    #print(len(oct_data.keys()))
#    #print(len(sept_data.keys()))
#
#    results_tables = []
#    #for key in ["Hero", "Gold Gym Badges"]:
#    for key in report_fields:
#        data = [(oct_data[player][key][0], oct_data[player][key][1], player) for player in oct_data.keys()
#                if oct_data[player][key] != (None, None)]
#
#        data.sort(reverse=True)
#        results_tables.append(["Total all time",])
#        results_tables.append(["Rank", "Player", key])
#        results_tables.extend([[cnt+1, item[2], item[0]] for cnt, item in enumerate(data)])
#        results_tables.append([""])
#
#        data.sort(key=lambda x: -x[1])
#        results_tables.append(["October increase",])
#        results_tables.append(["Rank", "Player", key])
#        results_tables.extend([[cnt+1, item[2], item[1]] for cnt, item in enumerate(data)])
#        results_tables.append([""])
#
#    #for x in results_tables:
#    #    print(x)
#    with open ("results.csv", 'w') as fw:
#        co = csv.writer(fw)
#        co.writerows(results_tables)

def to_increment_str(val):
    """Return passed value with a preceding '+' if it is a positive number"""
    try:
        float(val)
    except:
        return val
    if float(val) > 0:
        return "+" + str(val)
    else:
        return val

def render_monthly_html(entries, month=None, running_totals=None):
    """Return a list of HTML divs, one per calendar month, and data derived from entries

    These are meant to be (one at a time) added to a parent HTML document.

    Args:
        entries:
        month:
        running_totals: TBD
    """
    with open(report_fields_path, 'r') as fr:
        report_fields_dict = json.load(fr)  # expect a list of strings matching field keys
    report_fields = list(report_fields_dict.keys())

    # Get 12 months of data
    if month is None:
        today_date = datetime.date.today()
        starting_date = datetime.date(day=1, year=today_date.year, month=today_date.month)
        month = starting_date

    #oct_data = find_near_date(entries, datetime.date(2021, 10, 31))
    #sept_data = find_near_date(entries, datetime.date(2021, 9, 30))
    #months_data = find_near_date(entries, datetime.date(2021, 9, 30))
    months_data = find_near_date(entries, month)
    #monthname = calendar.month_name[months_data.month]
    monthname = calendar.month_name[month.month]


    if not running_totals:
        running_totals = {}  # dict of dicts by stat: [ {user: all-time-total,  ... } ]

    content_div = div(cls="content")
    with content_div:
        for key in report_fields:
            # Update the all-time data (Absolutely a weird spot to do this, but feels nice to overoptimize sometimes)
            # Build data: For a report field: [ [month-reported-total, diff, player], ...]
            data = [(months_data[player][key][0], months_data[player][key][1], player) for player in months_data.keys()
                    if months_data[player][key] != (None, None)]

            if key not in running_totals:
                running_totals[key] = {}

            for tup in data:  # and tup[1] is not None?
                month_reported_tot = tup[0]
                player = tup[2]
                if player not in running_totals[key]:
                    running_totals[key][player] = month_reported_tot
                elif month_reported_tot > running_totals[key][player]:
                    running_totals[key][player] = month_reported_tot

            # Generate the HTML
            metric_row = div(cls="row")
            with metric_row:
                keyname = report_fields_dict[key]
                a(cls="anchor", id=keyname)  # link anchor, with negative y offset in stylesheet typically
                div_icon = div(cls="iconcolumn")
                with div_icon:
                    a(img(width=50, title=keyname, alt=keyname, src=f"{keyname}.png"), href=f"#{keyname}")

                # Total all-time
                totals_data = list(running_totals[key].items())  # list of [user, total] pairs
                totals_data.sort(key=lambda x: -x[1])
                div_table1 = div(cls="column")
                with div_table1:
                    table1 = table()
                    with table1:
                        th("Total all time", colspan=3)
                        tr(td(b("Rank")), td(b("Player")), td(b(key)))
                        [tr(td(cnt+1), td(item[0]), td(item[1])) for cnt, item in enumerate(totals_data[:20])]

                # Monthly gains rankings
                data.sort(key=lambda x: -x[1])
                div_table2 = div(cls="column")
                with div_table2:
                    table2_div = table()
                    with table2_div:
                        th(f"{monthname} Increases", colspan=3)
                        tr(td(b("Rank")), td(b("Player")), td(b(key)))
                        [tr(td(cnt+1), td(item[2]), td(to_increment_str(item[1]))) for cnt, item in enumerate(data[:20])]

        #print(metric_row)
    return content_div, running_totals


def main(args):
    #args = Namespace
    #args.file = "pogo_sj_stats_oct2021.csv"
    with open(args.file, 'r') as fr:
        entries = parse_csv_to_clean_submissions(fr)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("file", default="pogo_sj_stats_oct2021.csv",
                        help="CSV file from google sheets, containing form responses")
    args = parser.parse_args()
    #main(args)

    # TEST
    #args = Namespace
    #args.file = "pogo_sj_stats_oct2021.csv"
    with open(args.file, 'r') as fr:
        entries = parse_csv_to_clean_submissions(fr)

    #render_monthly(entries)

    # Generate HTML for each month
    today_date = datetime.date.today()
    starting_date = datetime.date(day=1, year=today_date.year, month=today_date.month)
    running_totals = None  # will become a dict
    for n in range(-11, 1):  # last 12 months, starting from 12 months ago
        newmonthdate = starting_date + relativedelta(months=n, days=-1)  # e.g. 10-31-2021

        # Start of an HTML document
        doc = dominate.document(title='PoGo Stats - San Jose')
        with doc.head:
            link(rel='stylesheet', href='style.css')
        with doc:
            # TODO move to func?
            with open(report_fields_path, 'r') as fr:
                report_fields_dict = json.load(fr)  # expect a list of strings matching field keys
            report_fields = list(report_fields_dict.keys())
            # Top bar with linked icons, survey link, and dropdown
            header_box = div(cls="headerbox", id="myHeader")
            with header_box:
                with div(cls="iconsbox"):
                    for key in report_fields:
                        keyname = report_fields_dict[key]
                        a(img(width=50, title=keyname, alt=keyname, src=f"{keyname}.png"), href=f"#{keyname}")
                    month_selector = select(name="months", id="months_select", onchange="monthSelect()")
                    with month_selector:
                        option(calendar.month_name[newmonthdate.month] + " " + str(newmonthdate.year), selected="selected")
                        for m in range(12):
                            monthdate = starting_date + relativedelta(months=-1 * m, days=-1)  # e.g. 10-31-2021
                            month_year_str = calendar.month_name[monthdate.month] + " " + str(monthdate.year)
                            opt = option(month_year_str, value=str(monthdate).rsplit("-", maxsplit=1)[0] + ".html")
                    a("Submit survey data", href=SURVEY_LINK, cls="headerlinks")

            # Tables for each stat
            content, running_totals = render_monthly_html(entries, newmonthdate, running_totals)
            script(type='text/javascript', src='scroll2.js')

        date_string = str(newmonthdate).rsplit("-", maxsplit=1)[0]
        print("Generated page for", date_string)
        with open(f"html/{date_string}.html", 'w') as fr:
            fr.write(str(doc))

        if n == 0:  # copy first generated page to be our 'html/index.html'
            try:
                shutil.copy(f"html/{date_string}.html", "html/index.html")
                print("Copied most recent month to 'html/index.html'")
            except shutil.SameFileError:
                pass
            except PermissionError:
                print("Weird. A permission error when copying to 'html/index.html'...")
            except Exception as e:
                print("an unexpected Exception occurred that I was too lazy to predict...")
                raise
