#!/usr/bin/env bash
# Downloads the nflverse files the New Value weekly build reads (study/new_value_weekly.py), in the layout it expects.
# Usage: scripts/fetch-new-value-data.sh DIR SEASON
# Past seasons never change, so a cache can keep them; this script skips any file already present except SEASON's.
set -euo pipefail
D="$1"; S="$2"
R="https://github.com/nflverse/nflverse-data/releases/download"
mkdir -p "$D"/{nflv,rosters,weekly,wrost,inj,snaps,sched}

get() {  # get URL FILE [always]
  if [[ -s "$2" && "${3:-}" != always ]]; then return 0; fi
  curl -sSfL --retry 4 --retry-delay 5 -o "$2.part" "$1" && mv "$2.part" "$2"
}

get "$R/players/players.csv"                         "$D/nflv/players.csv" always
get "$R/draft_picks/draft_picks.csv"                 "$D/nflv/draft_picks.csv" always
get "$R/player_stats/player_stats_season.csv"        "$D/nflv/player_stats_season.csv"
get "$R/stats_player/stats_player_reg_2025.csv"      "$D/nflv/stats_player_reg_2025.csv"
get "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv" "$D/sched/games.csv" always

for y in $(seq 1999 "$S"); do
  a=""; [[ "$y" == "$S" ]] && a=always
  get "$R/stats_player/stats_player_week_${y}.csv"   "$D/weekly/stats_player_week_${y}.csv" $a
  if (( y >= 2001 )); then get "$R/rosters/roster_${y}.csv"               "$D/rosters/roster_${y}.csv" $a; fi
  if (( y >= 2002 )); then get "$R/weekly_rosters/roster_weekly_${y}.csv" "$D/wrost/roster_weekly_${y}.csv" $a; fi
  if (( y >= 2009 )); then get "$R/injuries/injuries_${y}.csv"            "$D/inj/injuries_${y}.csv" $a; fi
  if (( y >= 2012 )); then get "$R/snap_counts/snap_counts_${y}.csv"      "$D/snaps/snap_counts_${y}.csv" $a; fi
done
echo "nflverse files ready in $D"
