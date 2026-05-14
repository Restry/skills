#!/usr/bin/env python3
"""Initialize sync-skill on this machine."""
import argparse
import platform
import sys
import uuid
from pathlib import Path

from _common import (
    CONFIG_PATH, Config, DEFAULT_CACHE, DEFAULT_TARGET,
    ensure_clone, send_heartbeat,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--server", required=True, help="Backend URL, e.g. http://host:8000/api")
    p.add_argument("--repo", required=True, help="git URL of skill repo")
    p.add_argument("--target", default=None, help=f"Install dir (default {DEFAULT_TARGET})")
    p.add_argument("--runtime", default="claude")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    if CONFIG_PATH.exists() and not args.force:
        sys.exit(f"config already exists at {CONFIG_PATH} (use --force to overwrite)")

    cfg = Config(
        server_url=args.server.rstrip("/"),
        repo_url=args.repo,
        target_dir=str(Path(args.target).expanduser()) if args.target else str(DEFAULT_TARGET),
        machine_id=str(uuid.uuid4()),
        hostname=platform.node(),
        runtime=args.runtime,
        cache_repo_dir=str(DEFAULT_CACHE),
    )
    cfg.save()
    ensure_clone(cfg.repo_url, Path(cfg.cache_repo_dir))
    send_heartbeat(cfg)
    print(f"Initialized. machine_id={cfg.machine_id}")
    print(f"Config: {CONFIG_PATH}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
