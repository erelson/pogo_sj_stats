# A survey and leaderboard site for local Pokémon Go communities

This is a replacement for the old tl40 surveys that stopped at the end of 2022 or so.

It also improves the UX in various ways (particularly, per-trainer ordering of medals by platinum/gold/silver/bronze/none level).


# Tech stack:

- Python3
- Flask
- WTForms
- Sqlalchemy + Sqlite3

# Notes on hosting setup
The hosting site provides an apache2 server.

The flask app (`app.py`) is run as a daemon process.

The flask app is what you see on the website, via a reverse proxy to port 80. (HTTPS/port 443 forthcoming some day)

The sqlite3 database file lives in a directory on the hosting site (controlled by `settings.py`).

I download the DB from the server, generate stats locally, and push the generated HTML back to the server.

Icons used in the survey and leaderboards are uploaded to the server in appropriate directories. They are not part of the git repo, however.

## Local testing

Given a local db file (and optionally generated HTML files), you can do `python3 app.py fakekeytexthere` and visit http://localhost:5000/survey to test things. Note that icons are not included in this repo.

# Maintenance playbooks

There are several task that will periodically need doing to keep this site useful

## Updating limits (monthly)

1. Review links in stat_max_notes.md, figure out changes
1. Update stats.json
1. Run upload_stat_limits.bash

## Adding a new field to the survey:

1. Add to stats.json
    1. For medals, need to try and figure out the order of the new medal relative to other medals in stats.json
1. Add to report_fields_1.json if desired. (these are really "leaderboard fields")
1. Update platinum_counts.json if applicable
1. Git commit the changes to the files above
1. Find an icon image and put it in static/ (I don't version control these presently)
    1. e.g. from https://pokemongo.fandom.com/wiki/Medals
1. Pull down the latest DB
1. Run fill_static_tables.py
1. Inspect the db e.g. with sqlitebrowser
1. Upload the updated DB
1. Run upload_stat_limits.bash
1. Copy the new icon to static/ folder on server
1. Check the survey loads correctly (better yet, submit a survey and check things)

## Renaming a stat on the survey
1. Update title-case name in stats.json
1. Edit title-case name in db with sqlitebrowser
1. Upload stats.json and db to server
