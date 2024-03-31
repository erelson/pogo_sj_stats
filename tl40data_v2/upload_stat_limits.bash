# Read config.toml; parsing is simple because we only need the login line
login=$(grep login config.toml | cut -d' ' -f3 | tr -d '"')

echo "From config, will log into server as: $login"

# Only check for differences in stats.json, but commit changes to stat_max_notes.md too.
if [[ -n "$(git diff stats.json)" ]]; then
  echo "Now reviewing changes:"
  git diff stats.json stat_max_notes.md
  
  echo "Do you want to commit those changes? (y/n)"
  read -r answer
  if [[ "$answer" = "y" ]]; then
      git add stats.json stat_max_notes.md
      git commit
  else
      echo "Do you want to abort? (y/n)"
      read -r answer
      if [[ "$answer" = "y" ]]; then
          echo Not uploading. Exiting.
          exit 0
      fi
  fi
#else
#    # No changes for git but we still do upload
fi

# Ask if upload updated stats.json
echo "Do you want to upload the latest stats.json? (y/n)"
read -r answer
if [[ "$answer" != "y" ]]; then
    echo Not uploading. Exiting.
    exit 0
fi

# Upload
scp stats.json $login:/home/public/stats.json
echo "All done!"
