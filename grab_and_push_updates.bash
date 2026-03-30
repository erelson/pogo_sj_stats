# Read config.toml; just need the login line
login=$(grep login config.toml | cut -d' ' -f3 | tr -d '"')

local_db_location="pogo_sj.db"  # TODO get this from config.toml
temp_db_location="pogo_sj.db.tmp"
remote_db_location="/home/public/db/pogo_sj.db"

# Grab database from server to temporary location
echo "Grabbing current DB from server..."
scp $login:$remote_db_location $temp_db_location

if [ "$EXIT_AFTER_GRAB" = 'true' ]; then
    # Move temp to final location and exit
    mv $temp_db_location $local_db_location
    echo "Database downloaded to $local_db_location"
    exit 0
fi

# Validate database schema compatibility
echo ""
echo "Validating database schema..."
schema_valid=false
migration_attempted=false

while [[ "$schema_valid" = false ]]; do
    if python3 validate_db_schema.py $temp_db_location; then
        schema_valid=true
        break
    fi

    echo ""
    echo "WARNING: Downloaded database schema is incompatible with current code!"

    # Offer schema migration only once
    if [[ "$migration_attempted" = false ]]; then
        echo ""
        echo "The downloaded database appears to be an older schema version."
        echo "Would you like to attempt automatic schema migration? (y/n)"
        echo "(This will run tables.py and fill_static_tables.py on the downloaded DB)"
        read -r answer

        if [[ "$answer" = "y" ]]; then
            migration_attempted=true
            echo ""
            echo "Running schema migration on temporary database..."
            echo ""

            # Run tables.py to add missing tables/columns
            echo "Step 1: Updating schema with tables.py..."
            if DB_LOCATION=$temp_db_location python3 tables.py; then
                echo "✓ Schema update completed"
            else
                echo "✗ Schema update had errors, but continuing..."
            fi
            echo ""

            # Run fill_static_tables.py to populate static data and metrics
            echo "Step 2: Populating static data with fill_static_tables.py..."
            if DB_LOCATION=$temp_db_location python3 fill_static_tables.py; then
                echo "✓ Static data populated"
            else
                echo "✗ Static data population had errors, but continuing..."
            fi
            echo ""

            echo "Migration complete. Re-validating schema..."
            echo ""
            # Loop will re-validate automatically
            continue
        fi
    fi

    # Migration not attempted or failed - ask if want to continue anyway
    echo ""
    echo "Do you want to use the incompatible database anyway? (y/n)"
    read -r answer
    if [[ "$answer" != "y" ]]; then
        echo "Aborting. Keeping existing database, removing incompatible download."
        rm -f $temp_db_location
        exit 1
    fi
    echo "Continuing despite schema incompatibility..."
    schema_valid=true  # Exit loop
done

echo ""
if [[ "$migration_attempted" = true ]]; then
    echo "✓ Schema migration successful. Using migrated database."
else
    echo "✓ Schema validation passed. Using downloaded database."
fi
mv $temp_db_location $local_db_location

# Ask if need to edit the database
echo "Do you need to correct/edit records in the DB? (y/n)"
read -r answer
if [[ "$answer" = "y" ]]; then
    while true; do
        echo "Which method do you want to use?"
        echo "1: fuzzy lookup of responses with db_editor.py"
        echo "2: manual hand-edit with sqlitebrowser"
        echo "3: rename or merge a trainer with rename_trainer.py"
        read -r -p "Answer: " user_input
        case "$user_input" in
            1)
                python3 db_editor.py $local_db_location
                break
                ;;
            2)
                sqlitebrowser $local_db_location
                break
                ;;
            3)
                python3 rename_trainer.py $local_db_location
                break
                ;;
            *)
                echo "Invalid input. Please try again."
                ;;
        esac
    done
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
