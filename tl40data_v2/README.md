# A site f
Database


# Tech stack:

- Python3
- Flask
- WTForms
- Sqlalchemy

# Maintenance

There are several task that will periodically need doing to keep this site useful


# Notes on hosting setup
The hosting site provides an apache2 server.

The flask app is run as a daemon process.

The flask app is what you see on the website, via a reverse proxy to port 80. (HTTPS/port 443 forthcoming some day)
