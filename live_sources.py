from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from models import Match

TZ = ZoneInfo("Asia/Jerusalem")
USER_AGENT = "Mozilla/5.0 FootballCalendarAgent/2.0"


@dataclass
class RawEvent:
    uid: str
    summary: str
    start: datetime
    fields: Dict[str, str]


def _unescape_ics(value: str) -> str:
    return (value or "").replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _unfold_ics(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: List[str] = []
    for line in text.split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _parse_dt(key: str, value: str) -> datetime:
    value = value.strip()
    tzid = None
    m = re.search(r"TZID=([^;:]+)", key)
    if m:
        tzid = m.group(1)

    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    if "T" in value:
        dt = datetime.strptime(value, "%Y%m%dT%H%M%S") if len(value) >= 15 else datetime.strptime(value, "%Y%m%dT%H%M")
        if tzid:
            try:
                return dt.replace(tzinfo=ZoneInfo(tzid))
            except Exception:
                pass
        return dt.replace(tzinfo=TZ)
    return datetime.strptime(value, "%Y%m%d").replace(hour=12, tzinfo=TZ)


def parse_ics(text: str) -> List[RawEvent]:
    events: List[RawEvent] = []
    current: Optional[Dict[str, str]] = None
    dt_key = "DTSTART"
    for line in _unfold_ics(text):
        if line == "BEGIN:VEVENT":
            current = {}
            dt_key = "DTSTART"
            continue
        if line == "END:VEVENT" and current is not None:
            if current.get("DTSTART") and current.get("SUMMARY"):
                try:
                    events.append(RawEvent(
                        uid=current.get("UID", current["SUMMARY"] + "|" + current["DTSTART"]),
                        summary=_unescape_ics(current["SUMMARY"]),
                        start=_parse_dt(dt_key, current["DTSTART"]),
                        fields=current.copy(),
                    ))
                except ValueError:
                    pass
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        base = key.split(";", 1)[0].upper()
        if base == "DTSTART":
            dt_key = key
        current[base] = value
    return events


def fetch_text(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/calendar,text/plain,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _split_fixture(summary: str) -> Optional[tuple[str, str]]:
    clean = re.sub(r"\s+", " ", summary).strip()
    for sep in (" - ", " – ", " — ", " vs ", " v "):
        if sep in clean:
            left, right = clean.split(sep, 1)
            right = re.sub(r"\s+\d+\s*[-–:]\s*\d+\s*$", "", right).strip()
            return left.strip(), right.strip()
    return None


def _norm_team(name: str) -> str:
    s = name.lower().strip()
    s = s.replace("fc ", "").replace(" fc", "")
    s = s.replace("hapoel ", "h. ").replace("maccabi ", "m. ")
    s = re.sub(r"[^a-z0-9]+", "", s)
    aliases = {
        "hbeersheva": "beersheva",
        "beersheva": "beersheva",
        "htelaviv": "htelaviv",
        "mhaifa": "mhaifa",
        "fcbarcelona": "barcelona",
        "barcelona": "barcelona",
    }
    return aliases.get(s, s)


def _event_key(ev: RawEvent) -> Optional[tuple[str, str, str]]:
    fixture = _split_fixture(ev.summary)
    if not fixture:
        return None
    home, away = fixture
    # Date is deliberately used instead of exact minute because feeds can express the same
    # fixture in different timezone encodings. Team names + date is enough for this use case.
    local_date = ev.start.astimezone(TZ).strftime("%Y-%m-%d")
    return (_norm_team(home), _norm_team(away), local_date)


def build_competition_index(config: dict) -> tuple[Dict[tuple, str], List[str]]:
    index: Dict[tuple, str] = {}
    failures: List[str] = []
    for item in config.get("competition_feeds", []):
        try:
            text = fetch_text(item["url"])
            events = parse_ics(text)
            if not events:
                raise RuntimeError("empty feed")
            for ev in events:
                key = _event_key(ev)
                if key:
                    index[key] = item["name"]
            print(f"OK competition feed {item['name']}: {len(events)} events")
        except Exception as exc:
            failures.append(f"{item['name']}: {exc}")
            print(f"WARN competition feed {item['name']}: {exc}")
    return index, failures


def detect_competition(event: RawEvent, default_competition: str, comp_index: Dict[tuple, str]) -> str:
    key = _event_key(event)
    if key and key in comp_index:
        return comp_index[key]

    haystack = "\n".join(_unescape_ics(v) for v in event.fields.values()).lower()
    rules = [
        ("uefa champions league", "UEFA Champions League"),
        ("champions league", "UEFA Champions League"),
        ("europa league", "UEFA Europa League"),
        ("conference league", "UEFA Conference League"),
        ("uefa super cup", "UEFA Super Cup"),
        ("club friend", "Club Friendlies"),
        ("friendly", "Club Friendlies"),
        ("israel state cup", "Israel State Cup"),
        ("state cup", "Israel State Cup"),
        ("fa cup", "FA Cup"),
        ("league cup", "League Cup"),
        ("efl cup", "League Cup"),
        ("carabao", "League Cup"),
        ("community shield", "FA Community Shield"),
        ("copa del rey", "Copa del Rey"),
        ("supercopa", "Supercopa de Espana"),
        ("la liga", "La Liga"),
        ("efl championship", "EFL Championship"),
        ("championship", "EFL Championship"),
        ("premier league", "Premier League"),
        ("ligat ha", "Israeli Premier League"),
    ]
    for needle, name in rules:
        if needle in haystack:
            return name
    return default_competition


def _allowed(competition: str, rule: dict) -> bool:
    excludes = {x.lower() for x in rule.get("exclude", [])}
    if competition.lower() in excludes:
        return False
    if rule.get("mode") == "uefa_only":
        return competition in {
            "UEFA Champions League",
            "UEFA Europa League",
            "UEFA Conference League",
            "UEFA Super Cup",
        }
    if rule.get("mode") == "include_competitions":
        return competition.lower() in {x.lower() for x in rule.get("competitions", [])}
    return True


def fetch_team_matches(rule: dict, comp_index: Dict[tuple, str], now: Optional[datetime] = None) -> List[Match]:
    now = now or datetime.now(TZ)
    source = rule.get("source", {})
    if source.get("type") != "fixtures_ics":
        raise ValueError(f"Unsupported source type for {rule['team']}: {source.get('type')}")
    url = source["url"]
    text = fetch_text(url)
    raw_events = parse_ics(text)
    if not raw_events:
        raise RuntimeError(f"No events received for {rule['team']} from {url}")

    default_comp = rule.get("default_competition", "Football")
    horizon_days = int(rule.get("horizon_days", 370))
    cutoff = now - timedelta(days=1)
    horizon = now + timedelta(days=horizon_days)
    out: List[Match] = []
    for ev in raw_events:
        kickoff = ev.start.astimezone(TZ)
        if kickoff < cutoff or kickoff > horizon:
            continue
        fixture = _split_fixture(ev.summary)
        if not fixture:
            continue
        home, away = fixture
        competition = detect_competition(ev, default_comp, comp_index)
        if not _allowed(competition, rule):
            continue
        out.append(Match(
            team=rule["team"], home=home, away=away, competition=competition,
            kickoff=kickoff, source_id=ev.uid, channel=None, source_url=url,
        ))
    return out


def fetch_all(config: dict) -> List[Match]:
    comp_index, comp_failures = build_competition_index(config)

    # UEFA-only teams require the UEFA competition feeds to classify their team-feed matches.
    required_uefa = {"UEFA Champions League", "UEFA Europa League", "UEFA Conference League"}
    failed_names = {x.split(":", 1)[0] for x in comp_failures}
    if required_uefa & failed_names:
        raise RuntimeError(
            "A required UEFA competition feed failed; calendar was NOT overwritten:\n- "
            + "\n- ".join(comp_failures)
        )

    all_matches: List[Match] = []
    failures: List[str] = []
    for rule in config["tracking"]:
        try:
            team_matches = fetch_team_matches(rule, comp_index)
            all_matches.extend(team_matches)
            print(f"OK {rule['team']}: {len(team_matches)} matching future fixtures")
        except Exception as exc:
            failures.append(f"{rule['team']}: {exc}")

    if failures:
        raise RuntimeError("Live source refresh failed; calendar was NOT overwritten:\n- " + "\n- ".join(failures))

    dedup: Dict[tuple, Match] = {}
    for m in all_matches:
        key = (m.home.lower(), m.away.lower(), m.kickoff.astimezone(timezone.utc).strftime("%Y%m%dT%H%M"))
        if key not in dedup:
            dedup[key] = m
        else:
            existing = dedup[key]
            teams = []
            for t in (existing.team, m.team):
                if t not in teams:
                    teams.append(t)
            existing.team = " / ".join(teams)
    return sorted(dedup.values(), key=lambda x: x.kickoff)
