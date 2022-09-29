#! /usr/bin/env python3

# Standard library
import json
import os
import re
import sys

# Local import
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")  # TODO assumes linux-like
from parse_forms_csv import column_names_files, get_column_names


def parse_pasted_input(raw_entry):
    """

    Heavily adapted from parse_forms_csv.parse_csv_to_clean_submissions()
    """
    column_names = get_column_names(column_names_files)

    input_lines = raw_entry.splitlines()

    input_lines = [line.split("\t") for line in input_lines]
    for cnt, line in enumerate(input_lines):
        # Cleanup: sometimes there are 8x spaces instead of tabs, so split that way.
        if len(line) == 1:
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
        if len(input_lines[0]) < len(input_lines[-1]):
            input_lines = input_lines[1:]
    # Skip header lines - no numbers at all in them
    line = input_lines[0]  # list of values
    if not re.search("\d", "".join(line)):
        print(line)
        line = input_lines[1]  # list of values  # NEW

    # Match lines to column sets by length, aka number of columns
    # Note: above we already remove "done" (the check mark's alt text) and similar from start of lines
    found_colset = False
    for colset in column_names:  # Iterate over known line lengths (i.e. number of columns)
        if len(line) == len(colset):
            found_colset = True
            break
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
        print("!!!!!!!!!!!Was unable to find colset for line ... length of line:", len(line))
        if oldline:
            print("Full line parts:")
            print(oldline)
            print(f"Line parts after stripping '---' (resulting in {len(line)} remaining parts)")
        print(line)
        return None  # TODO

    # Skipping header lines, i.e. lines that match the colset's column names
    if colset[0] == line[0].strip(): # lazy but maybe we need to fix this
        return None  # TODO

    return line  # list of values

# List by column, matching order in survey rows' columns
print("Paste one complete row of data from tl40data.com:")
raw = input()
row_data = parse_pasted_input(raw)[2:]

with open("survey_to_pogo_order_mapping.json", 'r') as fr:
    column_lookup = json.load(fr)  # given a div element id, get the column for that element's data in a tl40 row

with open("medal_counts.json", 'r') as fr:
    categories = json.loads(fr.read())

for cnt, key in enumerate(categories):
    x = categories[key]  # We don't actually use the key names in this script...
    if x[4] not in column_lookup:
        #print("SKIPPING:", x[4])
        continue  # Skip some things that aren't in the survey, like Alola and Hisui dexes
    try:
        val = int(row_data[column_lookup[x[4]]].split()[0].replace(",", ""))
    except ValueError:
        #print("Got empty value for", key, column_lookup[x[4]], x[4], row_data[column_lookup[x[4]]], "; Assuming 0.")
        val = 0

    if x[0] == 0:  # Always put these categories at top
        order = -400 + cnt
    else:  # All other categories, lower orders for higher badge numbers, displayed first
        order = cnt
        idx = 0
        while idx < 4 and val > x[idx]:
            order -= 100
            idx += 1

    print(f"    #main-panel .mdl-grid > #{x[4]} " + "{ order: " + f"{order}; " + "}")

print("Paste the above #main-panel... lines into your userContent.css, then restart Firefox")
