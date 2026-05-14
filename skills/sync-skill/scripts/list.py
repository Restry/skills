#!/usr/bin/env python3
"""List skills available on the backend."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import Config, http_json


def main() -> None:
    cfg = Config.load()
    data = http_json("GET", f"{cfg.server_url}/skills")
    skills = data.get("skills", [])
    if not skills:
        print("(no skills published)")
        return
    width = max(len(s["name"]) for s in skills)
    for s in skills:
        print(f"{s['name']:<{width}}  {s.get('description', '')}")


if __name__ == "__main__":
    main()
