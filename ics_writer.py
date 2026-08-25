from pathlib import Path
from datetime import timedelta, timezone

def esc(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

def fmt_utc(dt):
    if dt.tzinfo is None:
        raise ValueError("kickoff must be timezone-aware")
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def build_ics(matches, calendar_name="Selected Football Matches"):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Football Calendar Agent//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(calendar_name)}",
        "X-WR-TIMEZONE:Asia/Jerusalem",
    ]
    for m in sorted(matches, key=lambda x: x.kickoff):
        start = m.kickoff
        end = start + timedelta(hours=2)
        channel = m.channel or "טרם פורסם"
        summary = f"⚽ {m.home} – {m.away}"
        desc = f"{m.competition}\\n📺 {channel}"
        if m.source_url:
            desc += f"\\nSource: {m.source_url}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{esc(m.stable_uid)}",
            f"DTSTAMP:{fmt_utc(start)}",
            f"DTSTART:{fmt_utc(start)}",
            f"DTEND:{fmt_utc(end)}",
            f"SUMMARY:{esc(summary)}",
            f"DESCRIPTION:{esc(desc)}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

def write_ics(matches, path, calendar_name):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_ics(matches, calendar_name), encoding="utf-8")
