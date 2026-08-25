from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

@dataclass
class Match:
    team: str
    home: str
    away: str
    competition: str
    kickoff: datetime
    source_id: str
    channel: Optional[str] = None
    source_url: Optional[str] = None

    @property
    def stable_uid(self) -> str:
        # Do NOT include kickoff time: time/date may change.
        safe = f"{self.competition}|{self.home}|{self.away}|{self.source_id}"
        return safe.lower().replace(" ", "-").replace("/", "-") + "@football-calendar-agent"

    def to_dict(self):
        d = asdict(self)
        d["kickoff"] = self.kickoff.isoformat()
        return d
