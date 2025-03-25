#! /usr/bin/env python3

# Some assumptions:
# - All dates listed on tl40 are MM/DD/YYYY regardless of locale, etc.

# Standard library
from argparse import ArgumentParser
import calendar
import datetime
import json
import os
import random
import shutil

# Third party
import dominate
from dominate.tags import a, b, img, link, option, select, table, tr, td, th, div, script, meta, sup
from dateutil.relativedelta import relativedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Local
from tables import Stat, Response, Trainer
from settings import LOCAL_DB_SPECIFIER


# TODO these should be pulled from DB
report_fields_path = "../report_fields_1.json"
platinum_counts_path = "../platinum_counts.json"

DAY_TO_INT = dict(zip(calendar.day_name, range(7)))
SURVEY_LINK = "http://pogo.gertlex.com/survey"

# Note that the survey ignores the regular dex count. Our "Sum of All" doesn't include this, which is rather arbitrary.
DEX_NAMES = ["Pokédex: Total",
             "Pokédex: Purified",
             "Pokédex: Shadow",
             "Pokédex: Perfect",
             #"Special Dex: 3 Stars",
             #"Special Dex: Shiny 3 Stars",
             "Pokédex: Shiny",
             "Pokédex: Lucky",
             "Pokédex: XXL",
             "Pokédex: XXS",
             #"Special Dex: Event/Costume",
             "Pokédex: G-Max",
             "Mega/Primal Evolution Guru"#, "Special Dex: Sum of All Dex Counts"]
N_TYPE_MEDALS = 18
STATNAME_DEX_SUM = "Sum of All Dex Counts"

# April fools quips on the leaderboards
APRIL_FOOLS = False
quips = [
        '"I\'m so proud!"',
        '"You tried."',
        '"The best there ever was!"',
        '"... did you steal my cabbages? :\'("',
        '"Very a-Mew-sing"',
        r'"¯\_(ツ)_/¯"',
        '"Those other trainers ain\'t got a Chansey against you"',
        '"Blasting off again!"',
        '"You ain\'t no casual!"',
        '"But did you find Kecleon yet?"',
        '"You reached previously Unown levels!"',
        '"Big oof, err, I mean, Bidoof."',
        '"Ho-oh, you can do better."',
        '"Da real Machamp!"',
        '"What an incredible journey!"',
        '"Did you get a bit Drowzee this month?"',
        '"You\'re a Staryu!"',
        '"Did you run out of Pokéballs?"',
        '"Good work Trainer!"',
        '"Wait till I tell Professor Oak!"',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
#        '""',
        ]

def random_quip():
    idx = random.randrange(0, len(quips))
    return quips[idx]


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


def add_monthly_changes(entries, quantity_names):
    """Add derived fields to all survey entries for monthly deltas

    Args:
        entries: dictionary by user of ... ?
        quantity_names: List of fields we care about for dashboards?
    """
    for user in entries:
        try:
            dates = sorted(entries[user])  # list of dates (datetime.date)
        except TypeError:
            print(user)
            print(entries[user])
            continue
        # Submissions debug
        #print(user)
        #print(dates)
        #print(len(dates))

        # Case 1: first submission for user
        # Case 2: only have one tl40 submission for user... set all changes to None
        # Case 3: preceding submission exists... normalize changes to length of month
        for idx, d in enumerate(dates):
            if idx == 0:  # Case 1
                for stat in quantity_names:
                    if stat == "Platinum Badges":  # TODO not implemented
                        continue
                    try:
                        entries[user][d][stat]["calculated_monthly_change"] = None
                        entries[user][d][stat]["calculated_with_tdelta"] = None
                    except KeyError:
                        # entries in report_fields_1.json that are not used yet?
                        continue
                continue
            else:
                prev_month_idx = idx - 1
                # Crudely Check that the previous date is long enough ago that it's probably the previous month.
                # This avoids small diffs when two submissions are made for the same month for whatever reason.
                d_current = dates[idx]
                d_prev = dates[prev_month_idx]
                while prev_month_idx > 0 and d_current - d_prev < datetime.timedelta(days=20):
                    prev_month_idx -= 1
                    d_prev = dates[prev_month_idx]

                # TODO validate elapsed time between d and dates[prev_month_idx] is... long enough
                #for stat in entries[user][d]:
                    #if stat in quantity_names:
                for stat in quantity_names:
                    if stat == "Platinum Badges":  #TODO not implemented
                        continue
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
                    scale_factor = current_month_length / tdelta

                    try:
                        current = entries[user][d][stat]["value"]
                    except KeyError:
                        # entries in report_fields_1.json that are not used yet?
                        continue
                    except ValueError:
                        # blank entries
                        continue
                    previous = entries[user][d_prev][stat]["value"]
                    if current is None or previous is None or current == '' or previous == '':
                        entries[user][d][stat]["calculated_monthly_change"] = None
                        entries[user][d][stat]["calculated_with_tdelta"] = None
                        continue  # Assumption: None means this value didn't exist in current/previous surveys
                    try:
                        current = int(current)
                        previous = int(previous)
                        change = current - previous
                    except (TypeError, ValueError):
                        print("Something unexpected when trying to calculate a numeric change...")
                        print(stat, idx, prev_month_idx)
                        print(current, previous)
                        raise
                    entries[user][d][stat]["calculated_monthly_change"] = scale_factor * change
                    entries[user][d][stat]["calculated_with_tdelta"] = tdelta


def find_near_date(all_data, target_date, day_delta=3):  # TODO be smarter/more reasonable about the day_delta. Used to be '1'.
    """Find form submissions near specific date (typically look for last day of month +/- 1 day)

    Returns one submission per user.

    Arguments
        ALTERNATELY: all_data: lookup table of responses by date for each user.
        all_data : entries : dict by user, containing subdict by date
        target_date : datetime.date
        day_delta : integer : half-window size around target_date, e.g. 1 -> +/- 1 day.

    Returns
        dict by user, containing survey values/increments data dictionary.
            Users without data near a date won't be in this returned dict.
            For a user with multiple entries in `target_date +/- day_delta`,
            will select the "bets" date. See test cases for all variations.
    """
    min_date = target_date - datetime.timedelta(days=day_delta)
    max_date = target_date + datetime.timedelta(days=day_delta)

    def in_date_range(_date):
        return min_date <= _date <= max_date

    nearest_entries = {}
    for user, entries in all_data.items():
    #for response in all_data:
        entry_date = None
        #print(response.timestamp)
        #entry_date = datetime.datetime.fromtimestamp(response["timestamp"], tz=timezone('US/Pacific'))
        #entry_date = datetime.datetime.fromtimestamp(response.timestamp, tz=timezone('US/Pacific'))
        # Pick the latest date within the range
        for date in entries.keys():
            if in_date_range(date):
                if entry_date is None or (entry_date is not None and date > entry_date):
                    entry_date = date
        if entry_date:
            nearest_entries[user] = entries[entry_date]
    #for user, entries in all_data.items():
    #    entry_date = None
    #    # Pick the latest date within the range
    #    for date in entries.keys():
    #        if in_date_range(date):
    #            if entry_date is None or (entry_date is not None and date > entry_date):
    #                entry_date = date
    #    if entry_date:
    #        nearest_entries[user] = entries[entry_date]

    return nearest_entries



def to_increment_str(val):
    """Return passed value with a preceding '+' if it is a positive number"""
    try:
        float(val)
    except:
        return val
    #if (10*val) % 10 == 0:
    #    val = int(val)
    #else:
    #    val = ((100*val) // 10) / 10
    #if float(val) > 0:
    #    return f"+{val:,}"
    #else:
    #    return f"{val:,}"
    if float(val) > 0:
        return f"+{int(float(val)):,}"
    else:
        return f"{int(float(val)):,}"

def render_monthly_html(entries, month_date=None, running_totals=None, player_platinum_tracker=None):
    """Return a list of HTML divs, one per calendar month, and data derived from entries

    These are meant to be (one at a time) added to a parent HTML document.

    Args:
        entries: List of responses from Responses table in DB
        month_date: Can specify month, but defaults to current month based on datetime.date.today().
            This is a date object of the first day of a month.
        running_totals: None or a dictionary. Stores latest data from previous months, so diffs
            can be calculated
        player_platinum_tracker: None or a dictionary

    Returns:
        content_div: HTML
        running_totals: Updated dictionary
        player_platinum_tracker: Updated dictionary
        player_count: Number of players with diffs in the current month.
        aborted (bool): If True, did not have (valid) data to render for the month. Other
            return values may simply be None, and should not be used
    """
    with open(report_fields_path, 'r') as fr:
        report_fields_dict = json.load(fr)  # expect a list of strings matching field keys
    # Note: we want platinum badges as the last 'field' in this list, which we do below
    report_fields = list(report_fields_dict.keys())

    # Dictionary by badge type of the number needed to earn the platinum badge
    plat_badge_thresholds = json.loads(open(platinum_counts_path, 'r').read())
    # Drop the platinum badge count from end of the list, then re-add it after appending other fields (like special dexes)
    all_fields = report_fields[:-1] + [x for x in plat_badge_thresholds.keys() if x not in list(report_fields)]
    # Put Platinum Badge count last in our processing order
    all_fields.append("Platinum Badges")

    # Get 12 months of data
    if month_date is None:
        today_date = datetime.date.today()
        starting_date = datetime.date(day=1, year=today_date.year, month=today_date.month)
        month_date = starting_date

    months_data = find_near_date(entries, month_date)
    monthname = calendar.month_name[month_date.month]
    month_year = f" ({monthname} {month_date.year})"

    if len(months_data.keys()) == 0:
        print("Debug: Seems to be no data for this month. Skipping...")
        return None, None, None, True

    if not running_totals:
        running_totals = {}  # dict of dicts by stat; subdicts are: [ {player: all-time-total,  ... } ]
    if not player_platinum_tracker:
        player_platinum_tracker = {}
    # Dict of {player: dex sum} used for "Sum of All Dex Counts"
    dex_sums = {}
    # Add trainers that are new this month to the platinum badge status tracker
    for player in months_data.keys():
        if player not in player_platinum_tracker.keys():
            player_platinum_tracker[player] = {platname: False for platname in plat_badge_thresholds.keys()}
    # Monthly increase counts by user
    player_dex_sum_increment = {player: 0
                                for player in months_data.keys()}
    player_platinum_increment = {player: 0
                                 for player in months_data.keys()}
    player_count = "(unset)"  # Number of players that responded to the survey for the being-generated month

    content_div = div(cls="content")
    with content_div:
        for stat in all_fields:
            # Skip stats that are defined but not yet recorded by survey
            if stat not in months_data["gertlex"] and stat != "Platinum Badges" and stat != STATNAME_DEX_SUM:
                print("Skipping", stat)
                continue

            plat_badge_threshold = plat_badge_thresholds.get(stat, 0)

            if stat not in running_totals:
                running_totals[stat] = {}

            # Note: Expect this stat to be the last one in the for loop
            if stat == "Platinum Badges":
                data = []
                for player in player_platinum_tracker:
                    count = sum([1 for platname in plat_badge_thresholds.keys()
                                 if player_platinum_tracker[player][platname]])
                    running_totals["Platinum Badges"][player] = [count, month_year]
                    data.append([count,
                                 0,
                                 player,
                                 0,
                                 0])
                # Changedata for Platinum badges
                # TODO in next comment line, last two may be swapped.
                # list of tuples of: new val, ???, player, raw change, time averaged change
                changedata = []
                for player in player_platinum_increment.keys():
                    # Also filter out new players, or first time adding type medals
                    total_platinum_badges = sum(list(player_platinum_tracker[player].values()))
                    # Only set changedata for players that had non-zero change
                    if player_platinum_increment[player] != total_platinum_badges:
                        # Crude: detect first time reporting type medals
                        if player_platinum_increment[player] >= N_TYPE_MEDALS:
                            player_platinum_increment[player] -= N_TYPE_MEDALS
                        changedata.append((player_platinum_tracker[player],
                                           player_platinum_increment[player],
                                           player,
                                           player_platinum_increment[player],  # TODO month-averaged not implemented
                                           player_platinum_increment[player]
                                           ))

            elif stat == STATNAME_DEX_SUM:
                #for player, dex_sum in dex_sums.items():
                #    running_totals[STATNAME_DEX_SUM][player] = [dex_sum, month_year]
                # TODO in next comment line, last two may be swapped.
                # list of tuples of: new val, ???, player, raw change, time averaged change
                changedata = []
                # fill in running_totals and changedata
                for player, dex_sum in dex_sums.items():
                    # Skip for new players who have no running total
                    if player not in running_totals[STATNAME_DEX_SUM]:
                        running_totals[STATNAME_DEX_SUM][player] = [dex_sum, month_year]
                        continue
                    change = dex_sum - running_totals[STATNAME_DEX_SUM][player][0]
                    running_totals[STATNAME_DEX_SUM][player] = [dex_sum, month_year]
                    # Also filter out new players, or first time adding type medals
                    #total_platinum_badges = sum(list(player_platinum_tracker[player].values()))
                    # Only set changedata for players that had non-zero change
                    if change:
                    #if player_dex_sum_increment[player] != dex_sum:
                        #if player_dex_sum_increment[player] >= N_TYPE_MEDALS:
                        #    player_dex_sum_increment[player] -= N_TYPE_MEDALS
                        changedata.append((dex_sum,
                                           player_dex_sum_increment[player],
                                           player,
                                           change,  # TODO month-averaged not implemented
                                           change
                                           ))

            elif stat not in report_fields:
                # Typically this block is type medals and regional dex values;
                # which we just want to see if the platinum threshold is crossed
                if plat_badge_threshold > 0:
                    for player in months_data.keys():
                        # Some players didn't submit a row with type medal entries, so skip them here
                        if stat not in months_data[player]:
                            continue

                        # The value here can be None, e.g. for many folks' Wayfarer badge
                        if months_data[player][stat]["value"] \
                                and months_data[player][stat]["value"] >= plat_badge_threshold:
                            # TODO check if False -> True, and increment a platinum badge count change dict
                            if not player_platinum_tracker[player][stat]:
                                player_platinum_increment[player] += 1
                            player_platinum_tracker[player][stat] = True
            else:
                # TODO(cleanup) Don't need these two list comprehensions to duplicate so much of each other.
                # Update the ALL-TIME data (Absolutely a weird spot to do this, but feels nice to overoptimize sometimes)
                # Build month's data: For a report field: [ [month-reported-total, diff, player], ...]
                data = [(months_data[player][stat]["value"],
                         'null',
                         player,
                         months_data[player][stat]["calculated_monthly_change"],
                         months_data[player][stat]["calculated_with_tdelta"]
                         ) for player in months_data.keys()
                        if months_data[player][stat]["value"] != None]
                # list of tuples of: new val, ???, player, raw change, time averaged change
                changedata = [(months_data[player][stat]["value"],
                               'null',  #months_data[player][stat]["change"],
                               player,
                               months_data[player][stat]["calculated_monthly_change"],
                               months_data[player][stat]["calculated_with_tdelta"]
                              )
                              for player in months_data.keys()
                              if months_data[player][stat]["calculated_monthly_change"] != None]

                # Update each player's platinum badge dictionary
                if plat_badge_threshold > 0:
                    for player in months_data.keys():
                        # The months_data value here can be None, e.g. for many folks' Wayfarer badge
                        # (TODO the above comment may mostly apply to tl40data surveys?)
                        if months_data[player][stat]["value"] \
                                and months_data[player][stat]["value"] >= plat_badge_threshold:
                            # TODO check if False -> True, and increment a platinum badge count change dict
                            if not player_platinum_tracker[player][stat]:
                                player_platinum_increment[player] += 1
                            player_platinum_tracker[player][stat] = True

            # We don't generate HTML for all stats (e.g. type medals)
            if stat not in report_fields:
                continue

            # Update running totals (Note: for now, only for stats we report)
            for tup in data:
                month_reported_total = tup[0]
                player = tup[2]
                if player not in running_totals[stat]:  # Add for first time for player
                    running_totals[stat][player] = [month_reported_total, month_year]
                elif month_reported_total > running_totals[stat][player][0]:  # or update if higher
                    running_totals[stat][player] = [month_reported_total, month_year]

                if stat in DEX_NAMES:
                    dex_sums[player] = dex_sums.get(player, 0) + month_reported_total

            # Generate the HTML for this stat
            metric_row = div(cls="row")
            with metric_row:
                keyname = report_fields_dict[stat]
                a(cls="anchor", id=keyname)  # link anchor, with negative y offset in stylesheet typically
                div_icon = div(cls="iconcolumn")
                with div_icon:
                    a(img(width=50, title=keyname, alt=keyname, src=f"{keyname}.png"), href=f"#{keyname}")

                # Total all-time
                totals_data = list(running_totals[stat].items())  # list of [player, total, datestr]
                try:
                    # TODO shouldn't need this int here, but we forgot to cast somewhere
                    totals_data.sort(key=lambda x: -int(x[1][0]))
                except TypeError:
                    print(totals_data)
                    raise
                div_table1 = div(cls="column")
                with div_table1:
                    ranklength = 50 if keyname == "total_xp" else 20  # Treat total XP specially: show everyone!
                    table1 = table()
                    with table1:
                        th(f"{stat} — Total all time", colspan=3)
                        tr(td(b("Rank")), td(b("Player")), td(b(stat)))
                        [tr(td(cnt+1),
                            td(item[0] + f"{item[1][1] if item[1][1] != month_year else ''}"),
                            td(f"{item[1][0]:,}")
                           ) for cnt, item in enumerate(totals_data[:ranklength])]

                # Monthly gains rankings
                changedata.sort(key=lambda x: -x[3]) # normalized values
                div_table2 = div(cls="column")
                with div_table2:
                    table2_div = table()
                    with table2_div:
                        th(f"{monthname} Increases", colspan=3)
                        tr(td(b("Rank")), td(b("Player")), td(b(stat)))

                        # Regular
                        if not APRIL_FOOLS:
                            [tr(td(cnt+1), td(item[2]), td(to_increment_str(item[3])))
                                    for cnt, item in enumerate(changedata[:20])] # normalized value

                        # April fools
                        else:
                            [tr(td(cnt+1), td(item[2]), td(to_increment_str(item[3]), img(width=25, src="prof_willow_round.webp"), sup(random_quip())))
                                    for cnt, item in enumerate(changedata[0:1])] # normalized value # 1
                            [tr(td(cnt+2), td(item[2]), td(to_increment_str(item[3])))
                                    for cnt, item in enumerate(changedata[1:20])] # normalized value #s 2-20
                        # End April fools

                # Populate player response count from the first field we track
                # This doesn't count players that took survey for first time;
                # they have no month-to-month comparison to count here.
                # NOTE: If I were to ever revisit how I handle surveys from the
                # middle of a month, maybe this would be found to have edge cases.
                if keyname == "total_xp":
                    player_count = len(changedata)

    return content_div, running_totals, player_platinum_tracker, player_count, False


def load_entries_from_db():
    """Read all entries from db into a giant dictionary

    Returns:
        entries: dict by user (lowercase), to subdict by "Response Date" (datetime.date) list values, containing
            dictionary of stat values.
    """
    entries = {}

    # Open DB
    db_specifier = LOCAL_DB_SPECIFIER
    engine = create_engine(db_specifier)
    session = Session(engine)

    # Get our user ID lookup from the DB
    users = session.query(Trainer).all()
    users_lookup = {user.id: user.name for user in users}

    # Read all responses
    responses = session.query(Response).all()
    for response in responses:
        user = users_lookup[response.trainer_id]
        if user == "test" or user == "*_-#test":
            continue
        if user not in entries:
            entries[user] = {}

        # Convert from timestamp (db) to datetime (used by our code)
        #entry_date = datetime.datetime.fromtimestamp(float(response.timestamp), tz=timezone('US/Pacific'))
        # Convert from timestamp (db) to datetime.date (used by our code)
        entry_date = datetime.date.fromtimestamp(float(response.timestamp))#, tz=timezone('US/Pacific'))

        entries[user][entry_date] = Stat.unpack_strdata(response.strdata, session, pad_data=True)

    return entries


def main(args):
    # ...
    with open(report_fields_path, 'r') as fr:
        report_fields_dict = json.load(fr)  # expect a list of strings matching field keys
    report_fields = list(report_fields_dict.keys())

    entries = load_entries_from_db()

    # Calculate monthly diffs
    add_monthly_changes(entries, list(report_fields_dict.keys()))

    # Generate HTML for each month
    today_date = datetime.date.today()
    starting_date = datetime.date(day=1, year=today_date.year, month=today_date.month)
    #starting_date = datetime.date(day=1, year=2022, month=2)  # Manual override for testing
    running_totals = None  # will become a dict
    player_platinum_tracker = None  # will become a dict
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
                    # Build drop-down selection for prior months
                    month_selector = select(name="months", id="months_select", onchange="monthSelect()")
                    with month_selector:
                        option(calendar.month_name[newmonthdate.month] + " " + str(newmonthdate.year),
                               value="index.html",  # to redirect to latest
                               selected="selected")  # this one is the current value (selected) on page-load
                        option("Latest",
                               value="index.html")  # to redirect to latest
                        for m in range(12):
                            monthdate = starting_date + relativedelta(months=-1 * m, days=-1)  # e.g. 10-31-2021
                            month_year_str = calendar.month_name[monthdate.month] + " " + str(monthdate.year)
                            option(month_year_str, value=str(monthdate).rsplit("-", maxsplit=1)[0] + ".html")
                    # Link to survey form
                    a("Submit survey data", href=SURVEY_LINK, cls="headerlinks")

            # Tables for each stat
            content, running_totals, player_platinum_tracker, player_count, aborted = \
                    render_monthly_html(entries,
                                        newmonthdate,
                                        running_totals,
                                        player_platinum_tracker)
            if aborted:
                print(f"Skipped month ending on: {newmonthdate} (render_monthly_html aborted; "
                      "no or invalid data for month)")
                continue
            script(type='text/javascript', src='static/scroll2.js')

        date_string = str(newmonthdate).rsplit("-", maxsplit=1)[0]
        print("Generated page for", date_string, f"({player_count} returning trainers)")
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
    parser = ArgumentParser(description="Load/process the sqlite3 database, "
                                        "and generate HTML stat pages for past several months.")
    #parser.add_argument("file", default="pogo_sj_stats_oct2021.csv",
    #                    help="CSV file from google sheets, containing entire history of form responses")
    args = parser.parse_args()

    main(args)
