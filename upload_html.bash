#!/usr/bin/env bash

# Select and upload HTML files

# Read config.toml; just need the login line
login=$(grep login config.toml | cut -d' ' -f3 | tr -d '"')

# Upload based on user input
./upload_prompter.py
files=$(cat upload_list.txt)
scp $files $login:/home/public/static/
echo "All done!"
