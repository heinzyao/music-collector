#!/usr/bin/env bash
# Music Collector — Finder/Terminal launcher for Apple Music sync

set -u

cd "$(dirname "$0")"

./sync-apple-music.sh
status=$?

if [ "$status" -eq 0 ]; then
  printf "\nApple Music sync finished successfully."
else
  printf "\nApple Music sync finished with exit code %s." "$status"
fi

printf "\nPress Enter to close..."
read -r _
exit "$status"
