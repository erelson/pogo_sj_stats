# Read config.toml; just need the login line
login=$(grep login config.toml | cut -d' ' -f3 | tr -d '"')

local_db_location="pogo_sj.db"  # TODO get this from config.toml
remote_db_location="/home/public/db/pogo_sj.db"

echo "Are you sure you want to upload the local DB to the server? (y/n)"
read -r answer
if [[ "$answer" = "y" ]]; then
    scp $local_db_location $login:$remote_db_location
fi
