# A survey and leaderboard site for local Pokémon Go communities

This is a replacement for the old tl40 surveys and leaderboards that stopped at the end of 2022 or so.

It also improves the survey UX in various ways:

- per-trainer ordering of medals by platinum/gold/silver/bronze/none level
- limits on stats that match the game
- typo-protection via warnings for large stat increases
- several minor details improved on to reduce user errors


# Tech stack:

- Python3
- Flask
- WTForms
- Sqlalchemy + Sqlite3

## Local setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and [sqlitebrowser](https://sqlitebrowser.org/):

```bash
sudo apt install sqlitebrowser
```

Then install Python dependencies and initialize the local database:

```bash
uv sync
uv run ./fill_static_tables.py
```

To run the Flask app locally for testing:

```bash
uv run python3 app.py fakekeytexthere
```

Then visit http://localhost:5000/survey.

To work with a copy of the production database, download it first:

```bash
./grab_latest_db.bash
```


# Notes on hosting setup
The hosting site provides an apache2 server.

The flask app (`app.py`) is run as a daemon process.

The flask app is what you see on the website, via a reverse proxy to port 80. HTTPS was added by the hosting provider in 2024.

The sqlite3 database file lives in a directory on the hosting site (controlled by `settings.py`).

I download the DB from the server, generate stats locally, and push the generated HTML back to the server. Later, I added an admin interface to do this remotely.

Icons used in the survey and leaderboards are uploaded to the server in appropriate directories. They are not part of the git repo, however.

## Local testing

Given a local db file (and optionally generated HTML files), you can do
`python3 app.py fakekeytexthere` and visit http://localhost:5000/survey to test
things. Note that icons are not included in this repo.

# Maintenance playbooks

There are several task that will periodically need doing to keep this site useful

## Updating limits (monthly)

1. Log in to https://godex.site
1. ./parse_and_update_from_godex.site.py
1. Run upload_stat_limits.bash
1. Git commit the changes

Old manual way:

1. Review links in stat_max_notes.md, figure out changes
1. Update stats.json
1. Run upload_stat_limits.bash
1. Git commit the changes

## Adding a new field to the survey:

1. Add to stats.json
    1. For medals, need to try and figure out the order of the new medal relative to other medals in stats.json
1. Add to report_fields_1.json if desired. (these are really "leaderboard fields")
1. Update platinum_counts.json if applicable
1. Dex counts only: Update `dashboard_html_from_db.py`'s list of `DEX_NAMES` to aggregate
1. Git commit the changes to the files above
1. Find an icon image and put it in static/ (I don't version control these presently)
    1. e.g. from https://pokemongo.fandom.com/wiki/Medals
1. Pull down the latest DB: ./grab_latest_db.bash
1. Run ./fill_static_tables.py
1. Inspect the db e.g. with sqlitebrowser
1. Upload the updated DB: ./push_db.bash
1. Run upload_stat_limits.bash
1. Copy the new icon to static/ folder on server
1. Check the survey loads correctly (better yet, submit a survey and check things)

## Renaming a stat on the survey
1. Update title-case name in stats.json
1. Edit title-case name in db with sqlitebrowser
1. Upload stats.json and db to server
1. Update report_fields_1.json (tentative)
1. Pokédex counts: Update dashboard_html_from_db.py

## Modifying order of stats on the survey
1. Get report of incorrect order, usually.
1. Compare with notes, and/or git log. (TODO where are my notes on this)
1. Edit stats.json and re-arrange corresponding lines.

## Removing a stat from the survey
As an example: with the new pokédex UI in early 2025, the 3* dexes were removed.

1. Edit stats.json, and change each stat to be removed to have the `required` field set to -1.
   This will prevent it being displayed. Under the hood, the DB will still
   record the last non-zero reported value (or 0) for removed stats.
1. To remove it from the leaderboards, remove it from `report_fields_1.json`
1. To remove dex counts from the "Sum of All Dex Counts", modify `DEX_NAMES` in
   `dashboard_html_from_db.py`.

## Updating code on the server

When making changes locally, the below files need to be copied to the server:

### Python Application Files
- `app.py` - Main Flask application
- `tables.py` - SQLAlchemy database models
- `settings.py` - Configuration (paths, database location)
- `age_survey.py` - Age survey routes and plotting

### Configuration Files
- `stats.json` - Survey field definitions, medal thresholds, limits
- `stat_help.json` - Help text for survey fields

### Templates (`templates/` directory)
- `survey_template.html` - Main survey form
- `trainer_visualization.html` - Trainer stats visualization page
- `debug_thresholds.html` - Debug view for warning thresholds
- `age_survey.html` - Age survey form
- `_formhelpers.html` - WTForms rendering macros
- `graph.html` - Graph display template

### Static Files (`static/` directory)
- `style.css` - Main stylesheet
- `scroll2.js` - Sticky header and month selector JavaScript
- `index.html` - Root static page

**Note:** Icons (PNG files in `static/`) are managed separately and are not version controlled.

### Automation
- The deploy folder contains manifests for the above categories
- The deploy_code.bash script prompts which upload manifest to use

## Past notes

Originally, there was the Trainer Level 40 club, for tracking stats for those who had maxed out
the original Level 40 limit in Pokemon go.  This group ran a survey form, and mailed regional spreadsheet leaderboards.

They briefly tried to join with another website to make fancier per-user stat listings, but shut this down due to misuse.

I implemented a google form to collect the various medals' information, and parsed the submissions to
this form to make the leaderboards.

Later, I added my own survey page and sqlite database. It's been well received as easier to use.
