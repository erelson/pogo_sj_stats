# Read config.toml; just need the login line
login=$(grep login config.toml | cut -d' ' -f3 | tr -d '"')

echo $login

# Ask if upload new html (and which)
echo "Do you want to upload the latest stats.json? (y/n)"
read -r answer
if [[ "$answer" != "y" ]]; then
    echo Not uploading. Exiting.
    exit 0
fi

# Upload
scp stats.json $login:/home/public/stats.json
echo "All done!"
