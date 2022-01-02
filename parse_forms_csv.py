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
from dominate.tags import a, b, img, link, option, select, table, tr, td, th, div, script, meta
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

N_DEX_ENTRIES = 9
DEX_NAMES = ["Purified", "Shadow", "Perfect", "3 Stars", "Shiny 3 Stars", "Shiny", "Lucky", "Event", "Mega"]


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


def parse_csv_to_clean_submissions(fileobj, column_names=None):
    """
    Returns:
        entries: dict by user (lowercase), to subdict by "Response Date" list values.
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
    # When tl40 adds new survey fields, we'll have additional columns, but still want to handle old pasted data.
    entries = {}  # dict by user (lowercase), to subdicts by "Response Date" list values
    dex_entries = {}  # dict by user (lowercase), to subdicts by "Response Date" list values  TODO

    for lineno, raw_entry in enumerate(raw_entries[1:]):  # One copy-paste by a participant; possibly including multiple submissions to TL40.
        input_lines = raw_entry[2].splitlines()
        print("Num input lines in submission:", len(input_lines))
        form_sub_time = raw_entry[0]
        user = raw_entry[1]

        if user.lower() not in entries:
            entries[user.lower()] = {}
        # NOTE: dex entry counts are different from survey responses of tl40 data because there's
        # only one "row" per submission (while we might have multiple tl40 rows in one response)
        if user.lower() not in dex_entries:
            #dex_entries[user.lower()] = {}#[None] * N_DEX_ENTRIES
            dex_entries[user.lower()] = [None] * N_DEX_ENTRIES
        dex_data = [int(val) if val else None for val in raw_entry[3:12]]  # 9 dex entries we started recording
        for cnt, (dex_cnt, dex_cnt2) in enumerate(zip(dex_entries[user.lower()], dex_data)):
            if dex_cnt2:
                if dex_cnt is None or dex_cnt2 > dex_cnt:
                    dex_entries[user.lower()][cnt] = dex_cnt2

        input_lines = [line.split("\t") for line in input_lines]
        for cnt, line in enumerate(input_lines):
            if len(line) == 1:  # 8x spaces instead of tabs?
                input_lines[cnt] = line[0].split("        ")
        # Filter out first-column things, as well as "Survey History" and leading empty strings
        for idx in range(len(input_lines)):
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
        for line in input_lines:  # Iterate over each TL40 submission
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
            # ???
            submission_time = line[0]

            try:
                sub_mon, sub_day, sub_year = [int(part) for part in submission_time.split()[0].split("/")]
                submission_date = datetime.date(sub_year, sub_mon, sub_day)
            except:  # TODO exception types
                submission_date = relative_date_string_to_date(submission_time, form_sub_time)
            entries[user.lower()][submission_date] = \
                    {field: get_val(val)  for field, val in zip(colset, line)} #column_names[0]}
            # Fill in extra columns
            #entries[user.lower()] = {str(submission_date):
            #        { field: val for field, val  in zip(colset, line)} }#column_names[0]}

    return entries, dex_entries


def get_val(valstring):
    """A bunch of lazy parsing logic for contents of each "table cell" copied from tl40data.com.

    Categories:
    1. Date of submission
    2. String, like a username
    3. Numeric value, with or without an increment
    4. No data, represented as "---"

    Returns dictionary of the two parsed values, "value" and "change" that may be present.
    If there's no "change", that value will be None.
    """
    # TODO decide what empty/missing values ought to be and explicitly define meaning of None or empty string, etc.
    valstring = valstring.strip()
    if valstring == "---" or not valstring:
        return {"value": None, "change": None}
    if len(valstring) == 10 and valstring[2] == "/": # column is a date; just return value
        return {"value": valstring, "change":''}
    try:
        int(valstring[0])
    except:
        # non-numeric values; just return the value
        return {"value": valstring.strip(), "change": ''}
    # We've got a numeric value like '12345 (+123)' or just '12345'.
    val = valstring.split()[0] # column total value, e.g. '12345'
    val = int(val.replace(",", ""))
    if len(valstring.split()) == 2:
        incrstring = valstring.split()[1] # column monthly increase, e.g. '(+123)'
        incrstring = int(incrstring.strip("()+").replace(",", ""))
    else: incrstring = 0
    return {"value": val, "change": incrstring}


def add_monthly_changes(entries, quantity_names):
    """Add derived fields to all survey entries for monthly deltas"""
    for user in entries:
        dates = sorted(entries[user])
        # Case: first submission for user
        # Case: only have one tl40 submission for user... set all changes to None
        # Case: preceding submission exists... normalize changes to length of month
        for idx, d in enumerate(dates):
            if idx == 0:
                for stat in quantity_names:
                    entries[user][d][stat]["calculated_monthly_change"] = None
                    entries[user][d][stat]["calculated_with_tdelta"] = None
                continue
            else:
                prev_month_idx = idx - 1
                # TODO... what was my plan for this while loop? Go back further than 'nearby' dates? Which I would determine... how?
                #while prev_month_idx > 0 and dates[idx] - dates[prev_month_idx]:
                #    prev_month_idx -= 1

                # TODO validate elapsed time between d and dates[prev_month_idx] is... long enough
                #for stat in entries[user][d]:
                    #if stat in quantity_names:
                for stat in quantity_names:
                    d_prev = dates[prev_month_idx]
                    tdelta = d - d_prev
                    tdelta = tdelta.days  # days, since we don't factor in seconds or microseconds
                    # Targeting our monthly comparisons, use the 'day' to determine if we want the
                    # length of the month in 'd', or for the month prior.
                    if d.day < 3:  # Simple criteria: For both 11-2 and 10-31, use 'the length of month 10'
                        prev_month = d.month - 1
                        year = d.year
                        if prev_month == 0:
                           prev_month = 12
                           year = d.year - 1
                        current_month_length = calendar.monthrange(year, prev_month)[1]
                    else:
                        current_month_length = calendar.monthrange(d.year, d.month)[1]
                    scale_factor = tdelta / current_month_length

                    current = entries[user][d][stat]["value"]
                    previous = entries[user][d_prev][stat]["value"]
                    if current is None or previous is None:
                        entries[user][d][stat]["calculated_monthly_change"] = None
                        entries[user][d][stat]["calculated_with_tdelta"] = None
                        continue  # Assumption: None means this value didn't exist in current/previous surveys
                    try:
                        current = int(current)
                        previous = int(previous)
                        change = current - previous
                    except TypeError:
                        print("Something unexpected when trying to calculate a numeric change...")
                        print(stat, idx, prev_month_idx)
                        print(previous)
                        raise
                    entries[user][d][stat]["calculated_monthly_change"] = scale_factor * change
                    entries[user][d][stat]["calculated_with_tdelta"] = tdelta


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
        return f"+{val:,}"
    else:
        return f"{val:,}"

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
    months_data = find_near_date(entries, month)
    monthname = calendar.month_name[month.month]

    if not running_totals:
        running_totals = {}  # dict of dicts by stat: [ {user: all-time-total,  ... } ]

    content_div = div(cls="content")
    with content_div:
        for key in report_fields:
            # TODO(cleanup) Don't need these two list comprehensions to duplicate so much of each other.
            # Update the ALL-TIME data (Absolutely a weird spot to do this, but feels nice to overoptimize sometimes)
            # Build data: For a report field: [ [month-reported-total, diff, player], ...]
            data = [(months_data[player][key]["value"], months_data[player][key]["change"], player, months_data[player][key]["calculated_monthly_change"], months_data[player][key]["calculated_with_tdelta"]) for player in months_data.keys()
                    if months_data[player][key]["value"] != None]
            changedata = [(months_data[player][key]["value"], months_data[player][key]["change"], player, months_data[player][key]["calculated_monthly_change"], months_data[player][key]["calculated_with_tdelta"]) for player in months_data.keys()
                    if months_data[player][key]["calculated_monthly_change"] != None]

            if key not in running_totals:
                running_totals[key] = {}

            for tup in data:
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
                        th(f"{key} — Total all time", colspan=3)
                        tr(td(b("Rank")), td(b("Player")), td(b(key)))
                        [tr(td(cnt+1), td(item[0]), td(f"{item[1]:,}")) for cnt, item in enumerate(totals_data[:20])]

                # Monthly gains rankings
                #data.sort(key=lambda x: -x[1]) # raw +XXX values
                changedata.sort(key=lambda x: -x[3]) # normalized values
                div_table2 = div(cls="column")
                with div_table2:
                    table2_div = table()
                    with table2_div:
                        th(f"{monthname} Increases", colspan=3)
                        tr(td(b("Rank")), td(b("Player")), td(b(key)))
                        #[tr(td(cnt+1), td(item[2]), td(to_increment_str(item[1]))) for cnt, item in enumerate(data[:20])]
                        [tr(td(cnt+1), td(item[2]), td(to_increment_str(item[1]))) for cnt, item in enumerate(changedata[:20])]

    return content_div, running_totals


def main(args):
    # ...
    with open(report_fields_path, 'r') as fr:
        report_fields_dict = json.load(fr)  # expect a list of strings matching field keys
    report_fields = list(report_fields_dict.keys())

    # Read CSV file
    with open(args.file, 'r') as fr:
        entries, dex_entries = parse_csv_to_clean_submissions(fr)

    # Calculate monthly diffs
    add_monthly_changes(entries, list(report_fields_dict.keys()))

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
            meta(charset='utf-8')
        with doc:
            # TODO move to func?
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

            # Tables for dex entry counts, only included for the most recent month
            if n == 0:
                # Flatten the dict to a list, with player at the end; None -> 0 for sort purposes
                dex_lists = [[val or 0 for val in values] + [player] for player, values in dex_entries.items()]
                for idx, dexname in enumerate(DEX_NAMES):
                    dex_lists.sort(key=lambda x: x[idx], reverse=True)
                    table_data = [(user_dex[-1], user_dex[idx]) for user_dex in dex_lists[:20] if user_dex[idx] > 0]

                    div_table2 = div(cls="todo")
                    with div_table2:
                        table2_div = table()
                        with table2_div:
                            th(f"Pokédex: {dexname}", colspan=3, cls=dexname.replace("3", "Three").replace(" ", ""))
                            tr(td(b("Rank")), td(b("Player")), td(b(dexname)))
                            [tr(td(cnt+1), td(item[0]), td(item[1])) for cnt, item in enumerate(table_data)]

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


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("file", default="pogo_sj_stats_oct2021.csv",
                        help="CSV file from google sheets, containing entire history of form responses")
    args = parser.parse_args()

    main(args)
