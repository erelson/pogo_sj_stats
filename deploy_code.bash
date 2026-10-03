#!/bin/bash
# Deploy code/template files to the server
# Uses a deploy manifest file to determine which files to sync

set -e

# Read config.toml; just need the login line
login=$(grep login config.toml | cut -d' ' -f3 | tr -d '"')

# Server-specific paths live in deploy/servers/<name>/; pick one with SERVER=<name>
server="${SERVER:-prod}"
server_dir="deploy/servers/$server"
if [[ ! -f "$server_dir/server.env" ]]; then
    echo "ERROR: no such server '$server' (expected $server_dir/server.env)"
    echo "Available: $(ls -1 deploy/servers 2>/dev/null | tr '\n' ' ')"
    exit 1
fi
source "$server_dir/server.env"

echo "Will deploy to: $login:$remote_path (server: $server)"
echo ""

# Prompt user to select a manifest file
echo "Select deployment manifest:"
echo "  1) deploy_manifest_main_survey.txt (default)"
echo "  2) deploy_manifest_age_survey.txt"
echo "  3) deploy_manifest_full.txt"
echo ""
read -r -p "Enter choice [1]: " choice

case "$choice" in
    2) manifest="deploy/deploy_manifest_age_survey.txt" ;;
    3) manifest="deploy/deploy_manifest_full.txt" ;;
    *) manifest="deploy/deploy_manifest_main_survey.txt" ;;
esac

echo ""
echo "Using manifest: $manifest"
echo ""

# Show which files have local changes (if in a git repo)
if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    changed_files=$(git diff --name-only HEAD 2>/dev/null || true)
    if [[ -n "$changed_files" ]]; then
        echo "Uncommitted changes detected in:"
        echo "$changed_files" | sed 's/^/  /'
        echo ""
    fi
fi

# Dry run first to show what would be transferred
echo "Files that would be updated:"
rsync -avz --dry-run --files-from=$manifest ./ "$login:$remote_path/" 2>/dev/null | grep -E "^[^.]" | grep -v "^sending\|^sent\|^total\|^$" || echo "  (no changes detected)"
echo ""

# settings.py is in the manifests, so it overwrites whatever is on the server.
# Re-assert the server's path overrides in the same breath, or the app falls
# back to the repo defaults and reads the wrong database.
echo "Server config that would be pushed:"
echo "  $server_dir/settings.json -> $remote_path/settings.json"
sed 's/^/    /' "$server_dir/settings.json"
echo ""

# Ask for confirmation
echo "Do you want to deploy these files? (y/n)"
read -r answer
if [[ "$answer" != "y" ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Perform the actual sync
echo ""
echo "Deploying..."
rsync -avz --files-from=$manifest ./ "$login:$remote_path/"

echo ""
echo "Pushing server config..."
rsync -avz "$server_dir/settings.json" "$login:$remote_path/settings.json"

echo ""
echo "Deployment complete!"
echo ""
echo "Remember: You may need to restart the Flask daemon for changes to take effect."
