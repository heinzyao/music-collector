#!/usr/bin/env bash
# Music Collector — Finder/Terminal launcher for full Apple Music recovery flow

set -u

cd "$(dirname "$0")"

./recover-apple-music-sync.sh
status=$?

if [ "$status" -eq 0 ]; then
  printf "\nApple Music recovery flow finished successfully."
else
  printf "\nApple Music recovery flow finished with exit code %s." "$status"
fi

printf "\nPress Enter to close..."
read -r _
exit "$status"
