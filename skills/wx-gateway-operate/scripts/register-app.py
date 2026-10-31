#!/usr/bin/env python3
"""
向 wx-gateway 注册新业务 app（v2 自助注册流程）。

不同于 v1：v2 把 app 注册改成 DB-backed + 邀请码自助，**不再改 APPS_JSON / 不再 redeploy**。
admin Dashboard 颁发邀请码 → 业务方持邀请码调 /apps/register → 网关返 secret。
本脚本是**业务方侧**的便捷封装，不是 gateway 维护脚本。

用法：
  python3 register-app.py <name> <appBaseUrl> <displayName> [--invite-code CODE] [--finalize-path /api/...]

示例：
  python3 register-app.py copilot-proxy https://api.eagle.openclaws.co.uk "Copilot Proxy" --invite-code 32f...

如果省略 --invite-code，脚本读 ~/.hermes/local/wx-gateway-invite.txt 第一行作为邀请码。

输出：
  1) 校验参数 + appBaseUrl 唯一性预检（GET /apps/preview-baseurl —— 若未实现则跳过）
  2) POST /apps/register（X-Invite-Code header）
  3) 拿到 secret 后追加到 ~/.hermes/local/wx-gateway-secrets.txt（mode 600，不进 git）
  4) 打印业务方该写进自家 .env 的字段

不做的事（v2 vs v1 反差）：
  - 不读生产 APPS_JSON（v2 已不用 env，APPS_JSON 仅 fallback）
  - 不 redeploy 网关（DB 注册即时生效，cache TTL 60s 自动失效）
  - 不跑 selftest（业务方改完自家 .env 后自己测）
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

GATEWAY_DEFAULT = "https://wx.mvp.restry.cn"
SECRETS_FILE = pathlib.Path.home() / ".hermes/local/wx-gateway-secrets.txt"
INVITE_FILE = pathlib.Path.home() / ".hermes/local/wx-gateway-invite.txt"


def http_post(url: str, headers: dict, body: dict, timeout: int = 15):
    data = json.dumps(body).encode()
    headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    p = argparse.ArgumentParser(description="Register a new business app with wx-gateway (v2)")
    p.add_argument("name", help="app name [a-z0-9_-]+")
    p.add_argument("app_base_url", help="business app base URL (no trailing slash)")
    p.add_argument("display_name", help="human-readable name")
    p.add_argument("--invite-code", help="32-hex invite code from admin Dashboard")
    p.add_argument("--finalize-path", help="custom finalize callback (default /api/wx/finalize)")
    p.add_argument("--gateway", default=GATEWAY_DEFAULT, help=f"gateway base (default {GATEWAY_DEFAULT})")
    args = p.parse_args()

    # 邀请码：参数优先，否则读本地文件
    invite = args.invite_code
    if not invite:
        if not INVITE_FILE.exists():
            print(f"❌ 未提供 --invite-code 且 {INVITE_FILE} 不存在", file=sys.stderr)
            sys.exit(1)
        invite = INVITE_FILE.read_text().strip().splitlines()[0].strip()
    if not (len(invite) == 32 and all(c in "0123456789abcdef" for c in invite.lower())):
        print(f"❌ invite-code 必须是 32 位 hex（当前 {len(invite)} 字符）", file=sys.stderr)
        sys.exit(1)

    body = {
        "name": args.name,
        "appBaseUrl": args.app_base_url.rstrip("/"),
        "displayName": args.display_name,
    }
    if args.finalize_path:
        body["finalizePath"] = args.finalize_path

    url = f"{args.gateway.rstrip('/')}/apps/register"
    status, text = http_post(url, {"X-Invite-Code": invite}, body)

    if status == 409:
        # 自 Hotfix 1（commit 1d0b5a9）起：同 appBaseUrl 已有 active app 时返 409
        print(f"❌ 409: {text}", file=sys.stderr)
        print("  → 同一 appBaseUrl 已有 active app，先去 admin Dashboard 把旧的 revoke 掉", file=sys.stderr)
        sys.exit(2)
    if status != 200:
        print(f"❌ {status}: {text}", file=sys.stderr)
        sys.exit(2)

    res = json.loads(text)
    secret = res["secret"]

    # 落到本机
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SECRETS_FILE.open("a") as f:
        f.write(f"\n# {args.name} ({args.app_base_url})\n{args.name}_secret={secret}\n")
    SECRETS_FILE.chmod(0o600)

    print(f"✅ app '{args.name}' 注册成功")
    print(f"   secret 已存 {SECRETS_FILE}")
    print()
    print("业务方 .env 加：")
    print(f"   WX_GATEWAY_BASE={args.gateway}")
    print(f"   WX_GATEWAY_APP_NAME={args.name}")
    print("   WX_GATEWAY_SECRET：从上述受保护文件读取，禁止复制到日志")
    print()
    print("⚠️  网关 apps cache TTL 60s — 业务方扫码若秒级失败可等 1 分钟再试")


if __name__ == "__main__":
    main()
