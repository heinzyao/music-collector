#!/usr/bin/env bash
# Music Collector — Finder/Terminal launcher for Apple Music login bootstrap

set -u

cd "$(dirname "$0")"

./bootstrap-apple-music-login.sh
status=$?

if [ "$status" -eq 0 ]; then
  printf "\nApple Music login bootstrap window opened successfully."
else
  printf "\nApple Music login bootstrap finished with exit code %s." "$status"
fi

printf "\nPress Enter to close..."
read -r _
exit "$status"
