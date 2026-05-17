#!/usr/bin/env python3
"""
mvp-deployer async pipeline client.

POST /api/deploy is always async: upload zip + manifest, get taskId, then
poll /api/deploy/tasks/<taskId> until success/failure.

Token loading order:
  1. ~/.credentials/mvp-deployer.env  -> DEPLOYER_TOKEN=...
  2. ~/.credentials/.env              -> MVP_DEPLOYER__TOKEN=...
Never hardcode or print the token.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DEPLOYER_URL = "https://deploy.mvp.restry.cn"
LEGACY_CREDS = Path.home() / ".credentials" / "mvp-deployer.env"
PREFIXED_CREDS = Path.home() / ".credentials" / ".env"


def _read_kv(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    try:
        for line in path.read_text().splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith(f"{key}="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def load_token() -> str:
    tok = _read_kv(LEGACY_CREDS, "DEPLOYER_TOKEN")
    if tok:
        return tok
    tok = _read_kv(PREFIXED_CREDS, "MVP_DEPLOYER__TOKEN")
    if tok:
        return tok
    sys.exit(
        f"DEPLOYER_TOKEN not found. Tried:\n"
        f"  - {LEGACY_CREDS} (DEPLOYER_TOKEN=...)\n"
        f"  - {PREFIXED_CREDS} (MVP_DEPLOYER__TOKEN=...)\n"
        f"chmod 600 the credential file and add the token."
    )


def deploy(token: str, manifest: dict, zip_path: str) -> str:
    cmd = [
        "curl", "-sS", "-X", "POST", f"{DEPLOYER_URL}/api/deploy",
        "-H", f"Authorization: Bearer {token}",
        "-F", f"file=@{zip_path}",
        "-F", "manifest=" + json.dumps(manifest),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        sys.exit(f"curl failed: {r.stderr}")
    try:
        resp = json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.exit(f"non-JSON response: {r.stdout[:500]}")
    if "taskId" not in resp:
        sys.exit(f"no taskId in response: {resp}")
    return resp["taskId"]


def poll(token: str, task_id: str, max_wait: int = 600) -> dict:
    url = f"{DEPLOYER_URL}/api/deploy/tasks/{task_id}"
    start = time.time()
    last_phase = None
    while time.time() - start < max_wait:
        r = subprocess.run(
            ["curl", "-sS", "-H", f"Authorization: Bearer {token}", url],
            capture_output=True, text=True, timeout=30,
        )
        try:
            task = json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(3)
            continue
        phase = task.get("phase")
        status = task.get("status")
        if phase != last_phase:
            elapsed = int(time.time() - start)
            print(f"[{elapsed:3d}s] {status} :: {phase}", file=sys.stderr)
            last_phase = phase
        if status in ("succeeded", "success", "done"):
            return task
        if status in ("failed", "error"):
            print(f"FAILED at phase {phase}", file=sys.stderr)
            print("---logs---", file=sys.stderr)
            for line in task.get("logs", [])[-20:]:
                print(line.rstrip(), file=sys.stderr)
            print(f"---error---\n{task.get('error', '(none)')}", file=sys.stderr)
            if task.get("rolledBack"):
                print("Server rolled back to previous version.", file=sys.stderr)
            sys.exit(1)
        time.sleep(4)
    sys.exit(f"poll timeout after {max_wait}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--zip", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--build", default=None,
                    help="Build command (bash -lc). If omitted, server falls back to package.json scripts.build when present.")
    ap.add_argument("--host", required=True,
                    help="Public hostname Caddy will serve (required, no default).")
    ap.add_argument("--type", default="node", choices=["node", "python", "static"])
    ap.add_argument("--env", action="append", default=[],
                    help="KEY=VALUE; repeatable. Goes into manifest.env (highest precedence over vault and credentials).")
    ap.add_argument("--preserve-data", action="append", default=None,
                    help="Relative dir to preserve across deploys (repeatable). Default ['data']. Pass --no-preserve to opt out.")
    ap.add_argument("--no-preserve", action="store_true",
                    help="Disable preserveData entirely (preserveData=false).")
    ap.add_argument("--smoke-path", action="append", default=[],
                    help="Extra path to probe after deploy (in addition to '/').")
    ap.add_argument("--smoke-disabled", action="store_true",
                    help="Skip the HTTPS smoke test (emergency only).")
    args = ap.parse_args()

    if not Path(args.zip).exists():
        sys.exit(f"zip not found: {args.zip}")

    token = load_token()
    env = {}
    for pair in args.env:
        if "=" not in pair:
            sys.exit(f"--env must be KEY=VALUE, got: {pair}")
        key, value = pair.split("=", 1)
        env[key] = value
    if env.get("NODE_ENV") == "production":
        print("Stripping NODE_ENV=production (breaks pnpm devDeps)", file=sys.stderr)
        del env["NODE_ENV"]

    manifest = {
        "project": args.project,
        "type": args.type,
        "port": args.port,
        "run": args.run,
        "host": args.host,
        "env": env,
    }
    if args.no_preserve:
        manifest["preserveData"] = False
    elif args.preserve_data is not None:
        manifest["preserveData"] = args.preserve_data
    # else: omit -> server defaults to ['data']
    if args.build:
        manifest["build"] = args.build
    if args.smoke_path:
        manifest["smokePaths"] = args.smoke_path
    if args.smoke_disabled:
        manifest["smokeDisabled"] = True

    print(
        f"-> Deploying {args.project} -> {args.host} (port {args.port}, {len(env)} manifest env vars)...",
        file=sys.stderr,
    )
    task_id = deploy(token, manifest, args.zip)
    print(f"-> taskId: {task_id}", file=sys.stderr)
    poll(token, task_id)
    print(f"OK {args.project} deployed -> https://{args.host}/", file=sys.stderr)


if __name__ == "__main__":
    main()
