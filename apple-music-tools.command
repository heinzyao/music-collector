#!/usr/bin/env bash
# Music Collector — Unified Apple Music tools launcher

set -u

cd "$(dirname "$0")"

printf "\nMusic Collector Apple Music Tools\n"
printf "=================================\n"
printf "1) Login bootstrap (open normal Chrome for Apple login)\n"
printf "2) Recovery flow (login -> validate session -> sync)\n"
printf "3) Sync only (reuse current Apple session)\n"
printf "q) Quit\n\n"
printf "Choose an action: "
read -r choice

status=0
case "$choice" in
  1)
    ./bootstrap-apple-music-login.sh
    status=$?
    ;;
  2)
    ./recover-apple-music-sync.sh
    status=$?
    ;;
  3)
    ./sync-apple-music.sh
    status=$?
    ;;
  q|Q)
    printf "\nNo action selected.\n"
    status=0
    ;;
  *)
    printf "\nInvalid selection. Please run the launcher again and choose 1, 2, 3, or q.\n"
    status=1
    ;;
esac

if [ "$status" -eq 0 ]; then
  printf "\nSelected Apple Music action finished successfully."
else
  printf "\nSelected Apple Music action finished with exit code %s." "$status"
fi

printf "\nPress Enter to close..."
read -r _
exit "$status"
