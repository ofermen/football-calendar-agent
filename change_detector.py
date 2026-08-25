import json
from pathlib import Path

def load_snapshot(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def compare(old, new):
    changes = []
    old_keys, new_keys = set(old), set(new)
    for uid in sorted(new_keys - old_keys):
        changes.append(("added", uid, None, new[uid]))
    for uid in sorted(old_keys - new_keys):
        changes.append(("removed", uid, old[uid], None))
    for uid in sorted(old_keys & new_keys):
        if old[uid] != new[uid]:
            changes.append(("changed", uid, old[uid], new[uid]))
    return changes

def save_snapshot(path, snapshot):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
