#! /usr/bin/env python3

"""Paste the browser-visible content of godex.site, with my custom defined
pokedexes to match in-game limits, into this script's prompt to auto-update
stats.json.
"""

import json
import re
import shlex
from argparse import ArgumentParser
from subprocess import run


# Mapping between the particular dex names I defined for myself at godex.site, to the stat names in stats.json
mappings = {
        "Event (non-clone, non-size)": ["Pokédex: Event/Costume"],
        "Go Dex Simple": ["Pokédex: Total", "Unique Species Seen", "Pokédex: ★ 100%", "Pokédex: 3 Stars", "Pokédex: XXL", "Pokédex: XXS"],
        "Lucky Simple": ["Pokédex: Lucky"],
        "Mega": ["Mega/Primal Evolution Guru", "Pokédex: Mega"],
        #"National Dex": "",
        #"Purified": "",
        "Purified simple": ["Pokédex: Purified"],
        #"Shadow": "",
        "Shadow Simple": ["Pokédex: Shadow"],
        #"Shiny Event Dex": "",
        #"Shiny Purified": "",
        "Shiny simple": ["Pokédex: Shiny 3 Stars", "Pokédex: Shiny"],
        "Gigantamax": ["Pokédex: G-Max"],

        "Kanto":   ["Kanto"],
        "Johto":   ["Johto"],
        "Hoenn":   ["Hoenn"],
        "Sinnoh":  ["Sinnoh"],
        "Unova":   ["Unova"],
        "Kalos":   ["Kalos"],
        "Alola":   ["Alola"],
        "Unknown": ["Unknown Generation"],
        "Galar":   ["Galar"],
        "Hisui":   ["Hisui"],
        "Paldea":  ["Paldea"],
        }


"""
Prior to 12-15-2024:
Values that I offset from this site's reported values for:
- Event dex (-4)
  - the 4 clone mons are counted but don't show in game's dex
- Alola dex (-2)
  - Melmetal + meltan are included
- Basculin is counted twice, for its white-striped version
  - which is part of Galar dex (-1)
  - Lucky dex: (-1)
  - Caught/seen/perfect/3star dex (-1)
- Galar (-7)
  - Galar is combined with Hisui (-6)
  - White stripe basculin (-1)
"""
# As of 12-15-2024: godex.site NO LONGER does the things noted above, that mean we
# modify its values to get our preferred limits
""" as of 12-23:
- Event dex (non-variants form) (+1)
  - Lugia from 1st go fest is missing
"""
modifiers = {
        "Event (non-clone, non-size)": -4,
        "Go Dex Simple": 0,
        "Lucky Simple": 0,
        "Mega": 0,
        "Purified simple": 0,
        "Shadow Simple": 0,
        "Shiny simple": 0,
        "Gigantamax": 0,
        "Kanto": 0,
        "Johto": 0,
        "Hoenn": 0,
        "Sinnoh": 0,
        "Unova": 0,
        "Kalos": 0,
        "Alola": 0,
        "Unknown": 0,
        "Galar": 0,
        "Hisui": 0,
        "Paldea": 0,
        }

def parse_global_dexes(text):
    updates = {}
    category = None
    count = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line == "pokeball":
            continue
        if re.match(r"\d+ / \d+ \(\d+\.\d+%\)", line):
            assert category is not None, "Failure: parsing found a numeric value before first category..."
            if category not in mappings:
                continue  # Ignore extra dexes in godex.site
            # E.g. 37 / 385 (9.61%)
            count = int(line.split()[2]) - modifiers[category]
            for survey_category in mappings[category]:
                updates[survey_category] = count
        else:
            category = line
    return updates

def parse_regional_dexes(text, updates=None):
    if updates is None:
        updates = {}
    region = None
    count = None
    lines = text.splitlines()
    if not lines: return updates  # handle empty input, e.g. during testing
    prev_line = lines[0].strip()
    for line in lines[1:]:
        line = line.strip()
        if re.match(r"\d+ / \d+ \(\d+\.\d+%\)", line):
            region = prev_line
            if region not in mappings:  # e.g. the "Go Dex Simple" line
                if region == "Go Dex Simple":
                    continue
                raise RuntimeError(f"Unexpected region found? (or parsing oversight): {region} / {line}")
            # E.g. 37 / 385 (9.61%)
            #count = int(line.split()[2]) - modifiers[region]
            count = int(line.split()[2])
            for survey_category in mappings[region]:
                updates[survey_category] = count
        prev_line = line
    return updates

def get_multiline_input_from_user():
    """
    Prompts the user to paste multiple lines directly into the terminal,
    until they press Ctrl+C (or Ctrl+D/Ctrl+Z).
    """
    print("Paste your text below. Press Ctrl+C or Ctrl+D (Linux/Mac) / Ctrl+Z (Windows) to finish:\n")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:  # Detect end-of-file (Ctrl+D/Ctrl+Z)
            break
        except KeyboardInterrupt:  # might as well catch ctrl+c too.
            break
        #if not line.strip():
        #    # Stop if an empty line is entered
        #    break
        lines.append(line)

    print("\n")
    return "\n".join(lines)

def update_stats_json(updates):
    with open("stats.json", 'r') as fr:
        stats = json.load(fr)

    # Update 5th value of e.g.: ["Integer",1,24,36,46,43,true,true,"pokedex_entries_mega_dex"]
    for key, limit in updates.items():
        stats["data"][key][5] = limit

    write_prettyprint_json(stats)

"""
Intended styling:
{
  "key": [
    "numtype",
    "bronze",
    ...
  ],
  "data":
  {
    "Total XP":
      G["Integer",0,0,0,0,-1,true,true,"total_xp"],
    "Trainer Level":
      ["Integer",0,0,0,0,50,true,true,"trainer_level"],
    ...
  }
}
"""
def write_prettyprint_json(stats):
    assert " ".join(list(stats.keys())) == "key data", "This function is no longer compatible with stats.json"
    with open("stats.json", 'w') as fw:
        # key list
        fw.write('{\n  "key": [\n')
        for val in stats["key"][:-1]:
            fw.write(f'    "{val}",\n')
        last = stats["key"][-1]  # last line w/o comma
        fw.write(f'    "{last}"\n')
        fw.write('  ],\n  "data":\n  {\n')

        # data dictionary
        for val in list(stats["data"].keys())[:-1]:
            fw.write(f'    "{val}":\n')
            sublist = json.dumps(stats["data"][val], separators=(',', ':'))
            fw.write(f'      {sublist},\n')
        # last lines w/o commas
        last = list(stats["data"].keys())[-1]
        last2 = json.dumps(stats["data"][last], separators=(',', ':'))
        fw.write(f'    "{last}":\n')
        fw.write(f'      {last2}\n')
        fw.write('  }\n}\n')

    print("Updated stats.json!")

def print_current_diff():
    run(shlex.split("git diff stats.json"))

def main():
    print("Go to https://godex.site/ and log in (assumes you have dexes set up to match mappings at top of script)")
    text = get_multiline_input_from_user()
    updates = parse_global_dexes(text)
    print("\nNow paste the contents of 'Go Dex Simple'...")
    text = get_multiline_input_from_user()
    updates = parse_regional_dexes(text, updates)
    print(updates)
    update_stats_json(updates)
    print_current_diff()
    print("\n******All done!******")


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    # For now, argparse is just supporting --help output
    args = parser.parse_args()
    main()
