#!/usr/bin/env python3
"""
mvp-deployer async build pipeline client.

Reads DEPLOYER_TOKEN from ~/.credentials/mvp-deployer.env (chmod 600).
NEVER hardcodes the token. NEVER prints the token.

NOTE: --preserve-env was REMOVED. The server-side SSH-base64 trick
broke silently when the agent had no SSH key (returned {} but only
stderr-warned), wiping production .env. If you need to keep existing
env vars across a redeploy, do it explicitly client-side:

    # Pull current .env via the deployer exec endpoint (no SSH needed):
    BODY=$(curl -sS -H "Authorization: Bearer $DEPLOYER_TOKEN" \\
        -H 'Content-Type: application/json' \\
        -X POST "https://deploy.mvp.restry.cn/api/exec/<project>" \\
        -d '{"command":"cat .env | base64 -w0"}')
    B64=$(echo "$BODY" | jq -r .stdout)
    echo "$B64" | base64 -d > /tmp/<project>.env
    # …merge into your manifest.env and pass with --env KEY=VALUE.

Server then writes ONLY what you sent — no silent fallback to empty.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DEPLOYER_URL = "https://deploy.mvp.restry.cn"
CREDS_PATH = Path.home() / ".credentials" / "mvp-deployer.env"


def load_token() -> str:
    if not CREDS_PATH.exists():
        sys.exit(
            f"❌ {CREDS_PATH} not found.\n"
            f"   Bootstrap: see SKILL.md §1 — copy from server's deployer .credentials,\n"
            f"   then chmod 600 {CREDS_PATH}"
        )
    for line in CREDS_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("DEPLOYER_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit(f"❌ DEPLOYER_TOKEN not in {CREDS_PATH}")


def deploy(token: str, manifest: dict, zip_path: str) -> str:
    cmd = [
        "curl", "-sS", "-X", "POST", f"{DEPLOYER_URL}/api/deploy",
        "-H", f"Authorization: Bearer {token}",
        "-F", f"file=@{zip_path}",
        "-F", "manifest=" + json.dumps(manifest),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        sys.exit(f"❌ curl failed: {r.stderr}")
    try:
        resp = json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.exit(f"❌ non-JSON response: {r.stdout[:500]}")
    if "taskId" not in resp:
        sys.exit(f"❌ no taskId in response: {resp}")
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
            t = json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(3); continue
        phase = t.get("phase")
        status = t.get("status")
        if phase != last_phase:
            elapsed = int(time.time() - start)
            print(f"[{elapsed:3d}s] {status} :: {phase}", file=sys.stderr)
            last_phase = phase
        if status in ("succeeded", "success", "done"):
            return t
        if status in ("failed", "error"):
            print(f"❌ FAILED at phase {phase}", file=sys.stderr)
            print("---logs---", file=sys.stderr)
            for line in t.get("logs", [])[-20:]:
                print(line.rstrip(), file=sys.stderr)
            print(f"---error---\n{t.get('error', '(none)')}", file=sys.stderr)
            if t.get("rolledBack"):
                print("ℹ️  Server rolled back to previous version.", file=sys.stderr)
            sys.exit(1)
        time.sleep(4)
    sys.exit(f"❌ poll timeout after {max_wait}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--zip", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--build", default=None)
    ap.add_argument("--host", required=True,
                    help="Public hostname Caddy will serve (required, no default).")
    ap.add_argument("--type", default="node", choices=["node", "python", "static"])
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--preserve-data", action="append",
                    default=["data", "public/uploads"])
    ap.add_argument("--smoke-path", action="append", default=[],
                    help="Extra path to probe after deploy (in addition to '/').")
    ap.add_argument("--smoke-disabled", action="store_true",
                    help="Skip the HTTPS smoke test (emergency only).")
    args = ap.parse_args()

    if not Path(args.zip).exists():
        sys.exit(f"❌ zip not found: {args.zip}")

    token = load_token()
    env = {}
    for pair in args.env:
        if "=" not in pair:
            sys.exit(f"❌ --env must be KEY=VALUE, got: {pair}")
        k, v = pair.split("=", 1)
        env[k] = v
    if env.get("NODE_ENV") == "production":
        print("⚠️  Stripping NODE_ENV=production (breaks pnpm devDeps)", file=sys.stderr)
        del env["NODE_ENV"]

    manifest = {
        "project": args.project,
        "type": args.type,
        "port": args.port,
        "run": args.run,
        "host": args.host,
        "preserveData": args.preserve_data,
        "env": env,
    }
    if args.build:
        manifest["build"] = args.build
    if args.smoke_path:
        manifest["smokePaths"] = args.smoke_path
    if args.smoke_disabled:
        manifest["smokeDisabled"] = True

    print(f"→ Deploying {args.project} → {args.host} (port {args.port}, {len(env)} env vars)...",
          file=sys.stderr)
    task_id = deploy(token, manifest, args.zip)
    print(f"→ taskId: {task_id}", file=sys.stderr)
    poll(token, task_id)
    print(f"✅ {args.project} deployed → https://{args.host}/", file=sys.stderr)


if __name__ == "__main__":
    main()
