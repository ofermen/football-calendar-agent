from __future__ import annotations

import html
import re
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, Iterable, List
from zoneinfo import ZoneInfo

from models import Match

USER_AGENT = "Mozilla/5.0 FootballCalendarAgent/6.0"
TZ = ZoneInfo("Asia/Jerusalem")


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def visible_text(raw_html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw_html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def norm(value: str) -> str:
    value = html.unescape(value or "").lower()
    value = value.replace("’", "'").replace("–", "-").replace("—", "-")
    value = re.sub(r"\[[^\]]+\]", "", value)
    value = re.sub(r"\bfc\b", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"[^a-z0-9]+", "", value)


def aliases(name: str, alias_map: Dict[str, List[str]]) -> List[str]:
    vals = [name] + alias_map.get(name, [])
    seen = set()
    out = []
    for v in vals:
        n = norm(v)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def fixture_on_page(page_text: str, match: Match, alias_map: Dict[str, List[str]]) -> bool:
    # Matching intentionally ignores kickoff time. Channel schedule sites may render times
    # in a visitor-specific timezone, while home/away pairing is stable.
    compact = norm(page_text)
    homes = aliases(match.home, alias_map)
    aways = aliases(match.away, alias_map)
    for h in homes:
        for a in aways:
            if h + "vs" + a in compact or h + "v" + a in compact or h + a in compact:
                return True
    return False


def enrich_broadcasts(matches: Iterable[Match], config: dict) -> List[str]:
    broadcast = config.get("broadcast", {})
    sources = broadcast.get("sources", [])
    alias_map = broadcast.get("team_aliases", {})
    horizon_days = int(broadcast.get("max_days_ahead", 14))
    now = datetime.now(TZ)
    horizon = now + timedelta(days=horizon_days)
    warnings: List[str] = []

    pages = []
    for source in sources:
        try:
            text = visible_text(fetch_text(source["url"]))
            pages.append((source["channel"], text, source["url"]))
            print(f"OK broadcast source {source['channel']}")
        except Exception as exc:
            warnings.append(f"{source.get('channel', 'unknown')}: {exc}")
            print(f"WARN broadcast source {source.get('channel', 'unknown')}: {exc}")

    for match in matches:
        kickoff_local = match.kickoff.astimezone(TZ)
        # TV schedules are intentionally trusted only close to kickoff.
        # Far-future channel pages can contain placeholders, repeated widgets,
        # or stale associations that look authoritative but are not final.
        if kickoff_local < now or kickoff_local > horizon:
            match.channel = None
            continue

        found = []
        for channel, page_text, _ in pages:
            if fixture_on_page(page_text, match, alias_map):
                found.append(channel)

        found = list(dict.fromkeys(found))
        if len(found) == 1:
            # Conservative rule: only publish a channel when the match resolves
            # uniquely to one configured Israeli channel page. Channel pages can
            # contain cross-channel/global fixture widgets, so multi-page matches
            # are treated as ambiguous rather than guessed.
            match.channel = found[0]
        elif len(found) > 1:
            match.channel = None
            warnings.append(
                f"ambiguous broadcast: {match.home} - {match.away} matched "
                + ", ".join(found)
            )
            print(
                f"AMBIG broadcast {match.home} - {match.away}: "
                + " / ".join(found)
                + " -> left unpublished"
            )

    return warnings
