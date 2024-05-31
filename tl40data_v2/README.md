# A site f
Database


# Tech stack:

- Python3
- Flask
- WTForms
- Sqlalchemy

# Maintenance playbooks

There are several task that will periodically need doing to keep this site useful

## Updating limits (monthly)

1. Review links in stat_max_notes.md, figure out changes
1. Update stats.json
1. Run upload_stat_limits.bash

## Adding a new field to the survey:

1. Find an icon image and put it in static/
1. Add to stats.json
   1. For medals, need to try and figure out the order of the new medal relative to other medals in stats.json
1. Add to report_fields_1.json
1. Update platinum_counts.json if applicable
1. Git commit the changes to the files above
1. Pull down the latest DB
1. Run fill_static_tables.py
1. Inspect the db e.g. with sqlitebrowser
1. Upload the updated DB
1. Run upload_stat_limits.bash
1. Check the survey loads correctly (better yet, submit a survey and check things)

# Notes on hosting setup
The hosting site provides an apache2 server.

The flask app is run as a daemon process.

The flask app is what you see on the website, via a reverse proxy to port 80. (HTTPS/port 443 forthcoming some day)
