# Football Calendar Agent — Live V6

Live football calendar generator for the configured tracked clubs and competitions.

## Run locally

```bat
py main.py
```

Outputs:
- `public/football.ics` — subscribable calendar file
- `public/preview.txt` — human-readable fixture list with Israeli TV channel when confidently identified

## Automatic GitHub refresh

`.github/workflows/update-calendar.yml` runs automatically about every two days and can also be started manually from the GitHub Actions tab.
It regenerates the calendar and commits changed `football.ics`, `preview.txt`, and the snapshot back to the repository.

## Broadcast behavior

The agent checks configured Israeli football TV schedules and only writes a channel when the match is matched conservatively to one channel. If uncertain, it writes `טרם פורסם`.

Israeli TV channels are only published for fixtures up to 14 days ahead. Matches farther away remain `טרם פורסם` and are checked again on every run.

Configured season window: 2026-07-01 through 2027-06-30 (Asia/Jerusalem).
