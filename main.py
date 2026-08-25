import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from change_detector import compare, load_snapshot, save_snapshot
from ics_writer import write_ics
from live_sources import fetch_all
from broadcast_sources import enrich_broadcasts

TZ = ZoneInfo('Asia/Jerusalem')


def in_season(match, season_start: datetime, season_end: datetime) -> bool:
    k = match.kickoff.astimezone(TZ)
    return season_start <= k <= season_end


def write_preview(matches, path: Path):
    grouped = defaultdict(list)
    for m in matches:
        for team in m.team.split(' / '):
            grouped[team].append(m)

    lines = []
    for team in sorted(grouped):
        lines.append(f'=== {team} ===')
        for m in sorted(grouped[team], key=lambda x: x.kickoff):
            local = m.kickoff.astimezone(TZ)
            channel = m.channel or "טרם פורסם"
            lines.append(
                f"{local:%d/%m/%Y %H:%M} | {m.home} - {m.away} | {m.competition} | 📺 {channel}"
            )
        lines.append(f'Total: {len(grouped[team])}')
        lines.append('')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text(encoding='utf-8'))

    output_file = root / config['output_file']
    snapshot_file = root / config.get('snapshot_file', 'data/snapshot.json')
    preview_file = root / config.get('preview_file', 'public/preview.txt')

    season = config.get('season', {})
    start_s = season.get('start', '2026-07-01')
    end_s = season.get('end', '2027-06-30')
    season_start = datetime.fromisoformat(start_s + 'T00:00:00').replace(tzinfo=TZ)
    season_end = datetime.fromisoformat(end_s + 'T23:59:59').replace(tzinfo=TZ)

    matches = fetch_all(config)
    matches = [m for m in matches if in_season(m, season_start, season_end)]
    broadcast_warnings = enrich_broadcasts(matches, config)
    if not matches:
        raise RuntimeError('No matching fixtures in configured season. Existing calendar was left untouched.')

    write_preview(matches, preview_file)

    snapshot = {m.stable_uid: m.to_dict() for m in matches}
    old = load_snapshot(snapshot_file)
    changes = compare(old, snapshot)

    write_ics(matches, output_file, config['calendar_name'])
    save_snapshot(snapshot_file, snapshot)

    print(f'Season window: {start_s} .. {end_s}')
    print(f'Generated {output_file} with {len(matches)} events')
    print(f'Preview: {preview_file}')
    print(f'Changes: {len(changes)}')
    if broadcast_warnings:
        print(f'Broadcast source warnings: {len(broadcast_warnings)} (calendar still generated)')
    for kind, uid, _, _ in changes:
        print(kind, uid)


if __name__ == '__main__':
    main()
