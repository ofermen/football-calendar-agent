from datetime import datetime
from zoneinfo import ZoneInfo
from live_sources import parse_ics, _event_key, detect_competition

TZ=ZoneInfo('Asia/Jerusalem')

def event(summary, dt='20260827T200000'):
    text=f'''BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x\nDTSTART;TZID=Europe/Amsterdam:{dt}\nSUMMARY:{summary}\nEND:VEVENT\nEND:VCALENDAR\n'''
    return parse_ics(text)[0]

# Cross-feed classification: team feed itself has no competition metadata.
ev=event('H. Tel Aviv - Atalanta')
idx={_event_key(ev): 'UEFA Conference League'}
assert detect_competition(ev,'Israeli Premier League',idx)=='UEFA Conference League'

# West Ham's 2026/27 domestic default is Championship, not Premier League.
ev2=event('West Ham United - Wrexham AFC')
assert detect_competition(ev2,'EFL Championship',{})=='EFL Championship'

print('tests OK')
