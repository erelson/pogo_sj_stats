# Read config.toml; just need the login line
login=$(grep login config.toml | cut -d' ' -f3 | tr -d '"')

local_db_location="pogo_sj.db"  # TODO get this from config.toml
remote_db_location="/home/public/db/pogo_sj.db"
# Grab database from server
echo "Grabbing current DB from server..."
scp $login:/home/public/db/pogo_sj.db .

if [ "$EXIT_AFTER_GRAB" = 'true' ]; then
    exit 0
fi

# Ask if need to edit the database
echo "Do you need to hand-edit the DB in sqlitebrowser? (y/n)"
read -r answer
if [[ "$answer" = "y" ]]; then
    #sqlitebrowser $local_db_location
    python3 db_editor.py # $local_db_location
    # And re-upload
    echo "Did you make changes and want to upload the modified DB to the server? (y/n)"
    read -r answer
    if [[ "$answer" = "y" ]]; then
        scp $local_db_location $login:$remote_db_location
    fi
fi


# Ask if continue to generate stats
echo "Do you want to generate the latest leaderboard HTML? (y/n)"
read -r answer
if [[ "$answer" != "y" ]]; then
    echo Not generating leaderboards. Exiting.
    exit 0
fi

# Generate html
python3 dashboard_html_from_db.py

# Ask if upload new html (and which)
echo "Do you want to upload the latest generated HTML? (y/n)"
read -r answer
if [[ "$answer" != "y" ]]; then
    echo Not uploading. Exiting.
    exit 0
fi

# Upload
python3 upload_prompter.py
files=$(cat upload_list.txt)
#echo scp $files $login:/home/public/static/
scp $files $login:/home/public/static/
echo "All done!"
