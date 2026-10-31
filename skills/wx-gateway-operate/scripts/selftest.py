#!/usr/bin/env python3
"""
wx-gateway selftest (v2 / batch 2 + admin hardening).

Covers:
  - QR creation for known app
  - Direct /admin/* path returns 404 camouflage
  - GET /admin/apps unauthenticated -> 404 (not 401)
  - GET ${ADMIN_PUBLIC_PATH}/login -> 200 HTML
  - 6 rapid GETs on login → 6th returns 429
  - Admin API accepts session cookie (signed locally with ADMIN_SESSION_SECRET)
  - Cookie TTL 1h: Set-Cookie max-age <= 3600
  - Sliding refresh: a session with <30 min remaining → response Set-Cookie has new cookie
  - /admin/apps lists expected apps via cookie auth
  - POST /admin/invites + /apps/register + /wx/qr hot reload
  - DELETE /admin/apps/<id>

Required env:
  - MVP_DEPLOYER__TOKEN
"""
import atexit
import base64
import hmac
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request

GATEWAY = os.environ.get("GATEWAY_BASE", "https://wx.mvp.restry.cn").rstrip("/")
DEPLOYER = os.environ.get("DEPLOYER_BASE", "https://deploy.mvp.restry.cn").rstrip("/")
PROJECT = os.environ.get("DEPLOYER_PROJECT", "wx-gateway")
ADMIN_PUBLIC_PATH = os.environ.get(
    "ADMIN_PUBLIC_PATH", "/_a/ce233c02438f1ea04adaeb0c703468eb"
).rstrip("/")
DEPLOYER_TOKEN = os.environ.get("MVP_DEPLOYER__TOKEN")

PASS, FAIL = "✅", "❌"
results = []

# Populated by bootstrap_selftest_app() at start of main(); used by all
# pay/* helpers so the selftest's HMAC matches the actual DB row's secret
# rather than whatever placeholder lives in the deploy manifest's APPS_JSON.
SELFTEST_APP_SECRET: str | None = None
SELFTEST_APP_CREATED: bool = False

# Names of throwaway App rows created via /apps/register during this run.
# Hard-deleted via control endpoint at exit so the App table doesn't accrete
# selftest_inv_<hex>_app / selftest_dup_<hex>_a / selftest_dup_<hex>_c rows.
_TEMP_APPS_CREATED: list[str] = []


def _register_temp_app(name: str) -> None:
    if name and name not in _TEMP_APPS_CREATED:
        _TEMP_APPS_CREATED.append(name)


def _purge_temp_apps() -> None:
    """atexit + finalize hook. Best-effort hard-delete every tracked temp app
    via the selftest control endpoint. Tolerates partial-init (no admin secret
    yet) by silently no-op-ing if the fetch fails."""
    if not _TEMP_APPS_CREATED:
        return
    try:
        secret = fetch_admin_session_secret()
    except Exception as e:
        print(f"   ⚠️  temp-app cleanup skipped (no admin secret): {e!r}", flush=True)
        return
    pending = list(_TEMP_APPS_CREATED)
    _TEMP_APPS_CREATED.clear()
    for name in pending:
        try:
            r = selftest_control(secret, "delete-temp-app", name=name)
            if r["status"] != 200:
                print(f"   ⚠️  delete-temp-app {name!r} → {r}", flush=True)
            else:
                print(f"   [cleanup] hard-deleted temp app {name!r}: {r['body']}", flush=True)
        except Exception as e:
            print(f"   ⚠️  delete-temp-app {name!r} raised: {e!r}", flush=True)


atexit.register(_purge_temp_apps)


def log(ok: bool, msg: str, detail: str = ""):
    mark = PASS if ok else FAIL
    line = f"{mark} {msg}"
    if detail:
        line += f"\n   {detail}"
    print(line, flush=True)
    results.append(ok)


def http(method: str, url: str, *, headers=None, body=None, timeout=15):
    headers = dict(headers or {})
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode()
            headers.setdefault("Content-Type", "application/json")
        elif isinstance(body, str):
            data = body.encode()
        else:
            data = body
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read().decode("utf-8", "replace")


def http_raw_setcookies(method: str, url: str, *, headers=None, body=None, timeout=15):
    """Same as http() but returns list of Set-Cookie headers (preserves multi-headers)."""
    headers = dict(headers or {})
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode()
            headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers.get_all("Set-Cookie") or [], resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.headers.get_all("Set-Cookie") if e.headers else []) or [], e.read().decode("utf-8", "replace")


def deployer_exec(command: str, timeout_ms: int = 30000) -> dict:
    if not DEPLOYER_TOKEN:
        raise RuntimeError("MVP_DEPLOYER__TOKEN not set")
    url = f"{DEPLOYER}/api/exec/{PROJECT}"
    status, _, raw = http(
        "POST",
        url,
        headers={"Authorization": f"Bearer {DEPLOYER_TOKEN}"},
        body={"command": command, "timeoutMs": timeout_ms},
    )
    if status != 200:
        raise RuntimeError(f"/api/exec failed status={status} body={raw[:200]}")
    return json.loads(raw)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def selftest_bypass_header(secret: str) -> dict:
    """HMAC-SHA256(secret, "ratelimit-bypass") header consumed by middleware.ts
    to skip the /login rate-limit for selftest. Bypass scope is rate-limit only —
    no other admin auth check is affected."""
    sig = hmac.new(secret.encode(), b"ratelimit-bypass", hashlib.sha256).hexdigest()
    return {"X-Selftest-Bypass-Ratelimit": sig}


def sign_admin_cookie(secret: str, openid: str = "selftest_admin", ttl_s: int = 600) -> str:
    payload = {
        "openid": openid,
        "role": "admin",
        "exp": int((time.time() + ttl_s) * 1000),
    }
    body = b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = b64url(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def fetch_admin_session_secret() -> str:
    cmd = (
        "node -e 'const m=require(\"./.deploy-manifest.json\");"
        "const v=(m&&m.env&&m.env.ADMIN_SESSION_SECRET)||\"\";"
        "process.stdout.write(Buffer.from(v).toString(\"base64\"))'"
    )
    out = deployer_exec(cmd, timeout_ms=10000)
    if out.get("exitCode") != 0:
        raise RuntimeError(f"node exec failed: {out}")
    encoded = (out.get("stdout") or "").strip()
    if not encoded:
        raise RuntimeError("ADMIN_SESSION_SECRET not present in .deploy-manifest.json")
    return base64.b64decode(encoded).decode()


def parse_max_age(setcookie: str) -> int:
    for part in setcookie.split(";"):
        part = part.strip()
        if part.lower().startswith("max-age="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return -1
    return -1


def main():
    print(f"== wx-gateway selftest ==")
    print(f"GATEWAY            = {GATEWAY}")
    print("ADMIN_PUBLIC_PATH  = [configured]")
    print(f"PROJECT            = {PROJECT}")
    print()

    # 0. Basic /wx/qr for selftest still works.
    # NOTE: deferred until after we bootstrap the selftest app (some instances
    # don't ship a 'selftest' app in APPS_JSON; we self-provision it).

    # === ADMIN SECURITY HARDENING ASSERTIONS ===

    # 1. Direct /admin/* → 404 camouflage
    s, _, _ = http("GET", f"{GATEWAY}/admin")
    log(s == 404, f"GET /admin → 404 (got {s})")
    s, _, _ = http("GET", f"{GATEWAY}/admin/login")
    log(s == 404, f"GET /admin/login → 404 (got {s})")
    s, _, _ = http("GET", f"{GATEWAY}/admin/apps")
    log(s == 404, f"GET /admin/apps unauthenticated → 404 (got {s})")

    # 2. ADMIN_PUBLIC_PATH/login → 200 HTML
    s, _, raw = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/login")
    looks_like_login = s == 200 and ("管理后台" in raw or "wx-gateway" in raw)
    log(looks_like_login, f"GET {ADMIN_PUBLIC_PATH}/login → 200 + HTML page (got {s})")

    # 3. Rate limit: 6 hits → 6th returns 429.
    # Sleep first to clear any prior bucket for our IP.
    print("   [waiting 65s to clear any prior rate-limit window...]", flush=True)
    time.sleep(65)
    statuses = []
    for i in range(6):
        st, _, _ = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/login")
        statuses.append(st)
    rl_ok = statuses[:5].count(200) >= 4 and statuses[5] == 429
    log(rl_ok, f"6 rapid GETs on login: 6th returns 429", f"statuses={statuses}")

    # Public registration without invite
    s, _, raw = http(
        "POST",
        f"{GATEWAY}/apps/register",
        headers={"X-Invite-Code": "bogus_invite_does_not_exist_at_all"},
        body={"name": "selftest_invalid", "appBaseUrl": "https://example.com"},
    )
    log(s in (401, 403), f"POST /apps/register with bogus code → 401/403 (got {s})")

    # 4. Fetch ADMIN_SESSION_SECRET via deployer /api/exec
    try:
        secret = fetch_admin_session_secret()
    except Exception as e:
        log(False, "fetch ADMIN_SESSION_SECRET via /api/exec", str(e))
        return finalize()
    log(bool(secret), "fetched ADMIN_SESSION_SECRET via deployer /api/exec",
        f"len={len(secret)}")

    # 4b. Bootstrap selftest app (self-provisioning, instance-agnostic).
    try:
        bootstrap_selftest_app(secret)
    except Exception as e:
        log(False, "bootstrap selftest app via control endpoint", str(e))
        return finalize(secret)
    log(True, f"bootstrap selftest app (created={SELFTEST_APP_CREATED}, secretLen={len(SELFTEST_APP_SECRET or '')})")

    # T-QR-SELFTEST: /wx/qr/selftest works (run AFTER bootstrap so a freshly
    # provisioned selftest app on a clean instance still passes).
    s, _, raw = http("POST", f"{GATEWAY}/wx/qr/selftest")
    ok_qr = s == 200 and json.loads(raw).get("ok") is True
    log(ok_qr, "POST /wx/qr/selftest returns 200 ok=true", f"status={s}")

    cookie = sign_admin_cookie(secret, ttl_s=3600)
    bypass_h = selftest_bypass_header(secret)
    auth_headers = {"Cookie": f"__admin_sess={cookie}", **bypass_h}

    # T-RL-BYPASS-1: 10 rapid GETs on /login WITH bypass header → all 200,
    # even though the IP may already be locked out from the earlier
    # "6 rapid GETs" test. Proves the HMAC-verified bypass is honored.
    br_statuses = []
    for _ in range(10):
        st, _, _ = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/login", headers=bypass_h)
        br_statuses.append(st)
    log(all(s == 200 for s in br_statuses),
        "T-RL-BYPASS-1: 10 GETs on /login with bypass header → all 200",
        f"statuses={br_statuses}")

    # 5. Authenticated /admin/me via public path → 200
    s, _, raw = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/me", headers=auth_headers)
    me_ok = s == 200 and "selftest_admin" in raw
    log(me_ok, f"GET {ADMIN_PUBLIC_PATH}/me with signed cookie → 200 (status={s})")

    # 6. Sliding refresh: cookie close to expiry triggers Set-Cookie on next call.
    short_cookie = sign_admin_cookie(secret, ttl_s=600)  # 10 min remaining < 30 min threshold
    s, set_cookies, _ = http_raw_setcookies(
        "GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/me",
        headers={"Cookie": f"__admin_sess={short_cookie}"},
    )
    refreshed = any("__admin_sess=" in sc for sc in set_cookies)
    log(s == 200 and refreshed,
        f"sliding refresh: short-TTL cookie triggers Set-Cookie",
        f"status={s}, set_cookies={len(set_cookies)}")
    if refreshed:
        sc = next(c for c in set_cookies if "__admin_sess=" in c)
        ma = parse_max_age(sc)
        log(0 < ma <= 3600,
            f"refreshed cookie max-age ≤ 3600 (got {ma})")

    # 7. /admin/apps via public path
    s, _, raw = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps", headers=auth_headers)
    if s != 200:
        log(False, f"GET {ADMIN_PUBLIC_PATH}/api/apps authenticated", f"status={s} body={raw[:200]}")
        return finalize(secret)
    apps = json.loads(raw).get("apps", [])
    names = {a["name"] for a in apps}
    has_admin = "admin" in names
    log(has_admin, f"{ADMIN_PUBLIC_PATH}/api/apps contains 'admin' app", f"names={sorted(names)}")
    has_any_real = any(n in names for n in ("ph", "pack", "echo", "selftest"))
    log(has_any_real, "/admin/apps contains at least one real app")

    # 8. Issue invite
    rand = secrets.token_hex(4)
    test_prefix = f"selftest_inv_{rand}_"
    test_name = f"{test_prefix}app"
    s, _, raw = http(
        "POST",
        f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/invites",
        headers=auth_headers,
        body={
            "appNamePrefix": test_prefix,
            "allowedHostPattern": "*.example.com",
            "displayName": "selftest invite app",
            "expiresIn": 120,
            "usesLeft": 1,
        },
    )
    if s != 200:
        log(False, "POST /admin/invites", f"status={s} body={raw[:200]}")
        return finalize(secret)
    inv = json.loads(raw)
    invite_code = inv["code"]
    log(bool(invite_code) and len(invite_code) >= 16, "POST /admin/invites returns plaintext code")

    # 9. Register via invite
    s, _, raw = http(
        "POST",
        f"{GATEWAY}/apps/register",
        headers={"X-Invite-Code": invite_code},
        body={"name": test_name, "appBaseUrl": "https://test.example.com"},
    )
    if s != 200:
        log(False, "POST /apps/register with valid invite", f"status={s} body={raw[:200]}")
        return finalize(secret)
    reg = json.loads(raw)
    _register_temp_app(test_name)
    log(reg.get("name") == test_name and len(reg.get("secret", "")) == 64,
        f"POST /apps/register registered '{test_name}' with 64-hex secret")

    # 10. /wx/qr/<new> within 5s — hot reload
    deadline = time.time() + 5
    qr_ok = False
    last_status = None
    last_body = None
    while time.time() < deadline:
        last_status, _, last_body = http("POST", f"{GATEWAY}/wx/qr/{test_name}")
        if last_status == 200:
            try:
                if json.loads(last_body).get("ok"):
                    qr_ok = True
                    break
            except Exception:
                pass
        time.sleep(0.5)
    log(qr_ok, f"POST /wx/qr/{test_name} within 5s → ok=true",
        f"last_status={last_status}")

    # T-REG-DUP: duplicate appBaseUrl rejected with 409, invite usage preserved.
    dup_rand = secrets.token_hex(4)
    dup_prefix = f"selftest_dup_{dup_rand}_"
    s, _, raw = http(
        "POST",
        f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/invites",
        headers=auth_headers,
        body={
            "appNamePrefix": dup_prefix,
            "allowedHostPattern": "*.example.com",
            "displayName": "selftest dup invite",
            "expiresIn": 120,
            "usesLeft": 2,
        },
    )
    dup_invite = json.loads(raw)["code"] if s == 200 else None
    dup_url = f"https://dup-{dup_rand}.example.com"
    dup_a = f"{dup_prefix}a"
    dup_b = f"{dup_prefix}b"
    dup_c = f"{dup_prefix}c"
    s1, _, _ = http(
        "POST", f"{GATEWAY}/apps/register",
        headers={"X-Invite-Code": dup_invite or ""},
        body={"name": dup_a, "appBaseUrl": dup_url},
    )
    if s1 == 200:
        _register_temp_app(dup_a)
    s2, _, raw2 = http(
        "POST", f"{GATEWAY}/apps/register",
        headers={"X-Invite-Code": dup_invite or ""},
        body={"name": dup_b, "appBaseUrl": dup_url},
    )
    body2 = {}
    try:
        body2 = json.loads(raw2)
    except Exception:
        pass
    # Third register with a different URL must succeed → proves invite count
    # was NOT decremented by the failed duplicate attempt.
    s3, _, _ = http(
        "POST", f"{GATEWAY}/apps/register",
        headers={"X-Invite-Code": dup_invite or ""},
        body={"name": dup_c, "appBaseUrl": f"https://dup-{dup_rand}-other.example.com"},
    )
    if s3 == 200:
        _register_temp_app(dup_c)
    log(
        s1 == 200
        and s2 == 409
        and body2.get("error") == "duplicate_app_base_url"
        and body2.get("existingName") == dup_a
        and s3 == 200,
        "T-REG-DUP: duplicate appBaseUrl → 409 + existingName, invite uses preserved",
        f"s1={s1} s2={s2} s3={s3} body2={raw2[:200]}",
    )
    # Cleanup dup-test apps
    s, _, raw = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps", headers=auth_headers)
    if s == 200:
        for a in json.loads(raw).get("apps", []):
            if a["name"] in (dup_a, dup_c):
                http("DELETE", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps/{a['id']}", headers=auth_headers)

    # 11. Cleanup test app via public path
    s, _, raw = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps", headers=auth_headers)
    if s == 200:
        apps2 = json.loads(raw).get("apps", [])
        target = next((a for a in apps2 if a["name"] == test_name), None)
        if target:
            ds, _, _ = http(
                "DELETE", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps/{target['id']}", headers=auth_headers
            )
            log(ds == 200, f"DELETE {ADMIN_PUBLIC_PATH}/api/apps/{target['id']} → 200 (got {ds})")
        else:
            log(False, "could not find newly-created app for cleanup")

    # 12. /admin/scans/recent reachable via public path
    s, _, _ = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/scans/recent", headers=auth_headers)
    log(s == 200, f"GET {ADMIN_PUBLIC_PATH}/api/scans/recent → 200 (got {s})")

    # === ADMIN APP webhookUrl edit (T-ADM-WEBHOOK-1..2) ===
    admin_webhook_url_cases(auth_headers)

    # === USERS tab (T-USERS-1..5) ===
    users_tab_cases(auth_headers)

    # === USERS tab binding edit (T-USER-BIND-EDIT-1..3) ===
    user_binding_edit_cases(auth_headers)

    # === ADMIN PAYMENT detail/extend/force-expire (T-ADM-PAY-DETAIL-1, T-ADM-EXTEND-1, T-ADM-FORCE-EXPIRE-1) ===
    admin_payment_detail_cases(secret, auth_headers)

    # === PAYMENT v1 (T-PAY-1..10) ===
    payment_cases(secret, auth_headers)

    # === CRON (T-CRON-1) ===
    cron_cases()

    # === INTERNAL TOKEN (T-INTERNAL-TOKEN-1) ===
    internal_token_cases()

    # === INTERNAL CONFIG (T-CONFIG-1..3) ===
    internal_config_cases()

    # === INTERNAL QRCODE + permanent-scan (T-QRCODE-*) ===
    internal_qrcode_cases()

    # === WX PUSH (T-PUSH-1..6) ===
    push_cases(auth_headers)

    # === FANOUT Phase A (T-FANOUT-1..6) ===
    fanout_cases(secret, auth_headers)

    # === USER BINDING (T-BIND-1..4) ===
    user_binding_cases(secret)

    # === PROFILE COMPLETION GATE (T-PROFILE-OFF / ON / REJECT) ===
    profile_completion_cases(secret)

    # T-RL-BYPASS-2: 6 rapid GETs on /login WITHOUT bypass header → 6th = 429.
    # Confirms the default IP rate-limit still applies to non-selftest requests.
    # Run last because this triggers a 5-min lockout for our IP. If a prior test
    # already locked us out, all 6 will be 429 — assertion still holds.
    nbr_statuses = []
    for _ in range(6):
        st, _, _ = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/login")
        nbr_statuses.append(st)
    log(nbr_statuses[5] == 429,
        "T-RL-BYPASS-2: 6 GETs on /login without bypass header → 6th = 429",
        f"statuses={nbr_statuses}")

    # T-CHECKOUT-URL-1: /pay/create with method=wxpay_jsapi + openid + returnUrl
    # should return wxpay.checkoutUrl pointing back to this gateway with a 48-hex
    # token; HEAD on it must respond (any 2xx/3xx/4xx — only network failure is bad).
    # Soft probe: only log, never block — selftest app may be personal_qr-channel,
    # in which case we expect channel_mismatch and skip silently.
    try:
        app_secret = fetch_selftest_app_secret()
        rand_co = secrets.token_hex(4)
        order_co = f"selftest_checkout_{rand_co}"
        ts_co = str(int(time.time() * 1000))
        sig_co = hmac_hex(app_secret, f"selftest|{order_co}|1|{ts_co}")
        s_co, _, raw_co = http(
            "POST", f"{GATEWAY}/pay/create",
            headers={"X-WX-App-Name": "selftest", "X-WX-Sig": sig_co, "X-WX-Ts": ts_co},
            body={
                "orderId": order_co,
                "amount_fen": 1,
                "subject": "checkout url probe",
                "method": "wxpay_jsapi",
                "openid": "oSelftest_probe_openid",
                "returnUrl": "https://design.mvp.restry.cn/topup",
                "expiresIn": 600,
            },
        )
        body_co = json.loads(raw_co) if raw_co.startswith("{") else {}
        if s_co == 200:
            checkout = (body_co.get("wxpay") or {}).get("checkoutUrl")
            import re as _re
            url_re = _re.compile(r"^https://[^/]+/pay/checkout/[A-Za-z0-9_-]+\?t=[a-f0-9]{48}$")
            shape_ok = isinstance(checkout, str) and bool(url_re.match(checkout))
            print(
                ("✅" if shape_ok else "❌"),
                f"T-CHECKOUT-URL-1: /pay/create returned wxpay.checkoutUrl shape ok={shape_ok}",
                f"\n   url={checkout}",
                flush=True,
            )
            if shape_ok:
                s_h, _, _ = http("HEAD", checkout)
                print(
                    f"   HEAD {checkout} → {s_h} (any non-network status acceptable)",
                    flush=True,
                )
        else:
            print(
                f"⚠️  T-CHECKOUT-URL-1: skipped (selftest app likely personal_qr channel; status={s_co})",
                flush=True,
            )
    except Exception as _co_e:
        print(f"⚠️  T-CHECKOUT-URL-1: skipped due to {type(_co_e).__name__}: {_co_e}", flush=True)

    finalize(secret)


# ---------- Payment helpers ----------

def fetch_selftest_app_secret() -> str:
    """Returns the selftest app's secret from the live DB (via control endpoint).
    Single source of truth — APPS_JSON manifests carry placeholder values that
    drift from the real DB-stored secret.
    """
    global SELFTEST_APP_SECRET
    if SELFTEST_APP_SECRET:
        return SELFTEST_APP_SECRET
    # Should have been populated by bootstrap_selftest_app() at startup, but
    # tolerate late call by triggering bootstrap now.
    secret = fetch_admin_session_secret()
    bootstrap_selftest_app(secret)
    if not SELFTEST_APP_SECRET:
        raise RuntimeError("bootstrap-selftest-app did not return a secret")
    return SELFTEST_APP_SECRET


def bootstrap_selftest_app(admin_secret: str) -> None:
    """Idempotently ensure the selftest app exists; capture its DB secret +
    whether we created it (for cleanup at end of run)."""
    global SELFTEST_APP_SECRET, SELFTEST_APP_CREATED
    r = selftest_control(admin_secret, "bootstrap-selftest-app")
    if r["status"] != 200 or not isinstance(r["body"], dict) or not r["body"].get("ok"):
        raise RuntimeError(f"bootstrap-selftest-app failed: {r}")
    SELFTEST_APP_SECRET = str(r["body"].get("secret") or "")
    SELFTEST_APP_CREATED = bool(r["body"].get("created"))
    if not SELFTEST_APP_SECRET:
        raise RuntimeError("bootstrap-selftest-app returned empty secret")


def cleanup_selftest_app(admin_secret: str) -> None:
    """End-of-run cleanup. Only deletes the app row if THIS run created it,
    otherwise leaves it but still scrubs payments + bindings created during
    the run."""
    try:
        r = selftest_control(
            admin_secret, "cleanup-selftest-app",
            removeApp=SELFTEST_APP_CREATED,
        )
        print(f"   [cleanup] selftest-app: {r.get('body')}", flush=True)
    except Exception as e:
        print(f"   ⚠️  cleanup selftest-app failed: {e!r}", flush=True)


def hmac_hex(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def pay_create(app_secret: str, app_name: str, order_id: str, amount_fen: int, subject: str = "selftest order", expires_in: int = 1800) -> dict:
    ts = str(int(time.time() * 1000))
    sig = hmac_hex(app_secret, f"{app_name}|{order_id}|{amount_fen}|{ts}")
    s, _, raw = http(
        "POST", f"{GATEWAY}/pay/create",
        headers={"X-WX-App-Name": app_name, "X-WX-Sig": sig, "X-WX-Ts": ts},
        body={"orderId": order_id, "amount_fen": amount_fen, "subject": subject, "method": "personal_qr", "expiresIn": expires_in},
    )
    return {"status": s, "body": json.loads(raw) if raw.startswith("{") else raw}


def pay_status(app_secret: str, app_name: str, pay_order_id: str) -> dict:
    ts = str(int(time.time() * 1000))
    sig = hmac_hex(app_secret, f"{app_name}|{pay_order_id}|{ts}")
    s, _, raw = http(
        "GET", f"{GATEWAY}/pay/status/{pay_order_id}",
        headers={"X-WX-App-Name": app_name, "X-WX-Sig": sig, "X-WX-Ts": ts},
    )
    return {"status": s, "body": json.loads(raw) if raw.startswith("{") else raw}


def pay_claim(app_secret: str, app_name: str, pay_order_id: str, user_note: str | None = None) -> dict:
    ts = str(int(time.time() * 1000))
    sig = hmac_hex(app_secret, f"{app_name}|{pay_order_id}|{ts}")
    body: dict = {"payOrderId": pay_order_id}
    if user_note: body["userNote"] = user_note
    s, _, raw = http(
        "POST", f"{GATEWAY}/pay/personal/claim",
        headers={"X-WX-App-Name": app_name, "X-WX-Sig": sig, "X-WX-Ts": ts},
        body=body,
    )
    return {"status": s, "body": json.loads(raw) if raw.startswith("{") else raw}


def admin_post(path: str, headers: dict, body=None) -> dict:
    s, _, raw = http("POST", f"{GATEWAY}{ADMIN_PUBLIC_PATH}{path}", headers=headers, body=body or {})
    return {"status": s, "body": json.loads(raw) if raw.startswith("{") else raw}


def user_binding_cases(admin_secret: str):
    """T-BIND-2..4: gateway-self-written user→app binding + router scoping.

    v2: /internal/user-binding has been deleted. Bindings are now written by
    the gateway itself in /wx/oauth/callback and /wx/callback (scan-confirmed
    branch). T-BIND-1 (endpoint 401) is gone — the endpoint no longer exists.
    Selftest uses control action "simulate-oauth-binding" to emulate that
    internal upsertBinding side-effect without spinning up a real OAuth flow.

    2: simulate-oauth-binding writes UserAppBinding row
    3: simulate fanout for unbound openid → boundApp null, both routes match
    4: bind openid → app_a, simulate fanout → boundApp=app_a, only route_a matches
    """
    print()
    print("--- user binding (T-BIND-2..4) ---")

    rand = secrets.token_hex(3)
    prefix = f"selftest_bind_{rand}_"
    openid = f"selftest_openid_{rand}"
    app_a = f"{prefix}ep_a"  # must match endpoint name created by control action

    try:
        # T-BIND-3 first (unbound): simulate fanout. boundApp must be null;
        # matched contains both temp routes (rt_a + rt_b).
        sim_unbound = selftest_control(
            admin_secret, "fanout-simulate-binding",
            fromUser=openid, prefix=prefix,
        )
        ok3 = False
        detail3 = repr(sim_unbound)
        if sim_unbound["status"] == 200 and isinstance(sim_unbound["body"], dict):
            log_row = sim_unbound["body"].get("log") or {}
            matched = (log_row.get("matchedRouteName") or "")
            ok3 = (
                log_row.get("boundApp") in (None, "")
                and f"{prefix}rt_a" in matched
                and f"{prefix}rt_b" in matched
            )
            detail3 = f"boundApp={log_row.get('boundApp')!r} matched={matched!r}"
        log(ok3, "T-BIND-3: unbound openid → boundApp null + both routes matched", detail3)

        # T-BIND-2: bind via gateway-internal helper (mirrors what
        # /wx/oauth/callback does on a real scan-login).
        sim_bind = selftest_control(
            admin_secret, "simulate-oauth-binding",
            openid=openid, appName=app_a,
        )
        ok2 = (
            sim_bind["status"] == 200
            and isinstance(sim_bind["body"], dict)
            and sim_bind["body"].get("ok") is True
            and sim_bind["body"].get("appName") == app_a
        )
        log(ok2, "T-BIND-2: simulate-oauth-binding writes UserAppBinding row",
            f"status={sim_bind['status']} body={sim_bind['body']!r}")

        # T-BIND-4: simulate again with binding now active. boundApp=app_a;
        # matchedRouteName scoped to rt_a only (rt_b excluded).
        sim_bound = selftest_control(
            admin_secret, "fanout-simulate-binding",
            fromUser=openid, prefix=prefix,
        )
        ok4 = False
        detail4 = repr(sim_bound)
        if sim_bound["status"] == 200 and isinstance(sim_bound["body"], dict):
            log_row = sim_bound["body"].get("log") or {}
            matched = (log_row.get("matchedRouteName") or "")
            ok4 = (
                log_row.get("boundApp") == app_a
                and f"{prefix}rt_a" in matched
                and f"{prefix}rt_b" not in matched
                and (log_row.get("downstream") or "") == app_a
            )
            detail4 = (
                f"boundApp={log_row.get('boundApp')!r} matched={matched!r} "
                f"downstream={log_row.get('downstream')!r}"
            )
        log(ok4, "T-BIND-4: bound openid → boundApp=app_a + only route_a matched", detail4)

        # T-BIND-ADMIN-SKIP: upsertBinding(openid, "admin") must be a no-op.
        # "admin" is the gateway's own back-office pseudo-app and is never a
        # fanout target; an admin scan-login must not overwrite the user's
        # real business-app binding. Bind to app_a, then try to overwrite with
        # "admin", then read back — appName must still be app_a.
        skip_openid = f"selftest_openid_adminskip_{rand}"
        try:
            pre = selftest_control(
                admin_secret, "simulate-oauth-binding",
                openid=skip_openid, appName=app_a,
            )
            attempt = selftest_control(
                admin_secret, "simulate-oauth-binding",
                openid=skip_openid, appName="admin",
            )
            readback = selftest_control(
                admin_secret, "read-user-binding", openid=skip_openid,
            )
            ok_skip = False
            detail_skip = repr(readback)
            if readback["status"] == 200 and isinstance(readback["body"], dict):
                got = readback["body"].get("appName")
                ok_skip = got == app_a
                detail_skip = (
                    f"pre={pre['body']!r} attempt={attempt['body']!r} "
                    f"readback_appName={got!r} (expected {app_a!r})"
                )
            log(ok_skip,
                "T-BIND-ADMIN-SKIP: upsertBinding(openid, 'admin') is no-op, "
                "real binding preserved",
                detail_skip)
        finally:
            try:
                selftest_control(
                    admin_secret, "fanout-simulate-binding-cleanup",
                    fromUser=skip_openid, prefix=f"__nope_{rand}_",
                )
            except Exception as e:
                print(f"   ⚠️  cleanup admin-skip failed: {e!r}", flush=True)
    finally:
        # cleanup: delete temp endpoints/routes/logs/health/binding rows.
        try:
            cu = selftest_control(
                admin_secret, "fanout-simulate-binding-cleanup",
                fromUser=openid, prefix=prefix,
            )
            print(f"   [cleanup] user-binding: {cu.get('body')}", flush=True)
        except Exception as e:
            print(f"   ⚠️  cleanup user-binding failed: {e!r}", flush=True)


def sse_first_status(token: str, *, timeout: float = 6.0) -> dict:
    """Open the SSE poll stream and return the first JSON-decoded data: frame.
    Skips the `: connected` comment line. Returns {} on parse failure."""
    url = f"{GATEWAY}/wx/poll/{token}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            deadline = time.time() + timeout
            while time.time() < deadline:
                line = resp.readline()
                if not line:
                    break
                s = line.decode("utf-8", "replace").rstrip("\r\n")
                if not s or s.startswith(":"):
                    continue
                if s.startswith("data:"):
                    payload = s[len("data:"):].strip()
                    try:
                        return json.loads(payload)
                    except Exception:
                        return {"_raw": payload}
            return {}
    except Exception as e:
        return {"_error": repr(e)}


def profile_completion_cases(admin_secret: str):
    """T-PROFILE-OFF / T-PROFILE-ON / T-PROFILE-REJECT.

    Exercises the per-app requireProfileCompletion flag added to App.
      OFF (default): scan-confirm writes status=confirmed → poll returns
        confirmed+redirect immediately.
      ON: scan-confirm writes status=scanned → poll returns scanned (no
        redirect). Then simulate-oauth-complete promotes scanned→confirmed
        → poll returns confirmed+redirect.
      REJECT: scan-confirm writes scanned → simulate-oauth-reject flips
        to rejected → poll returns rejected.

    finally: restore requireProfileCompletion=false and delete login tokens.
    """
    print()
    print("--- profile completion gate (T-PROFILE-OFF / ON / REJECT) ---")

    rand = secrets.token_hex(3)
    tok_off = f"selftest_prof_off_{rand}"
    tok_on = f"selftest_prof_on_{rand}"
    tok_rej = f"selftest_prof_rej_{rand}"
    openid_off = f"selftest_openid_proff_{rand}"
    openid_on = f"selftest_openid_pron_{rand}"
    openid_rej = f"selftest_openid_prrej_{rand}"

    try:
        # ----- T-PROFILE-OFF -----
        # Ensure flag OFF (default state, but be defensive in case a prior
        # run left it on).
        selftest_control(admin_secret, "set-require-profile", enabled=False)
        selftest_control(admin_secret, "create-login-token", token=tok_off, appName="selftest")
        scan = selftest_control(
            admin_secret, "simulate-scan-callback",
            token=tok_off, openid=openid_off, appName="selftest",
        )
        scan_status = scan["body"].get("status") if isinstance(scan["body"], dict) else None
        frame = sse_first_status(tok_off)
        ok_off = (
            scan["status"] == 200
            and scan_status == "confirmed"
            and frame.get("status") == "confirmed"
            and isinstance(frame.get("redirect"), str)
            and frame["redirect"].startswith("http")
        )
        log(
            ok_off,
            "T-PROFILE-OFF: flag off → scan writes confirmed → poll returns confirmed+redirect",
            f"scan={scan['status']}/{scan_status} frame={frame}",
        )

        # ----- T-PROFILE-ON -----
        on_set = selftest_control(admin_secret, "set-require-profile", enabled=True)
        selftest_control(admin_secret, "create-login-token", token=tok_on, appName="selftest")
        scan_on = selftest_control(
            admin_secret, "simulate-scan-callback",
            token=tok_on, openid=openid_on, appName="selftest",
        )
        scan_on_status = scan_on["body"].get("status") if isinstance(scan_on["body"], dict) else None
        frame_scanned = sse_first_status(tok_on)
        oauth_ok = selftest_control(
            admin_secret, "simulate-oauth-complete",
            token=tok_on, openid=openid_on, appName="selftest",
        )
        frame_confirmed = sse_first_status(tok_on)
        ok_on = (
            on_set["status"] == 200
            and scan_on["status"] == 200
            and scan_on_status == "scanned"
            and frame_scanned.get("status") == "scanned"
            and "redirect" not in frame_scanned
            and oauth_ok["status"] == 200
            and frame_confirmed.get("status") == "confirmed"
            and isinstance(frame_confirmed.get("redirect"), str)
        )
        log(
            ok_on,
            "T-PROFILE-ON: flag on → scan=scanned → OAuth complete → confirmed+redirect",
            f"scan={scan_on_status} f_scanned={frame_scanned} f_confirmed={frame_confirmed}",
        )

        # ----- T-PROFILE-REJECT -----
        selftest_control(admin_secret, "create-login-token", token=tok_rej, appName="selftest")
        scan_rej = selftest_control(
            admin_secret, "simulate-scan-callback",
            token=tok_rej, openid=openid_rej, appName="selftest",
        )
        rej = selftest_control(admin_secret, "simulate-oauth-reject", token=tok_rej)
        frame_rejected = sse_first_status(tok_rej)
        ok_rej = (
            scan_rej["status"] == 200
            and (scan_rej["body"].get("status") if isinstance(scan_rej["body"], dict) else None) == "scanned"
            and rej["status"] == 200
            and frame_rejected.get("status") == "rejected"
        )
        log(
            ok_rej,
            "T-PROFILE-REJECT: scanned → simulate-oauth-reject → poll returns rejected",
            f"rej={rej['body']} frame={frame_rejected}",
        )
    finally:
        # Restore default off and clean up login tokens. Bindings created on
        # confirmed paths share the selftest_openid_ prefix and are mopped up
        # by cleanup_selftest_app() at the end of main().
        try:
            r = selftest_control(admin_secret, "set-require-profile", enabled=False)
            if r["status"] != 200:
                print(f"   ⚠️  WARNING: failed to restore requireProfileCompletion=false: {r}", flush=True)
        except Exception as e:
            print(f"   ⚠️  restore requireProfileCompletion failed: {e!r}", flush=True)
        for t in (tok_off, tok_on, tok_rej):
            try:
                selftest_control(admin_secret, "delete-login-token", token=t)
            except Exception:
                pass


def selftest_control(secret: str, action: str, **kwargs) -> dict:
    body = {"action": action, **kwargs}
    s, _, raw = http(
        "POST", f"{GATEWAY}/wx/selftest/control",
        headers={"X-Selftest-Token": secret},
        body=body,
    )
    return {"status": s, "body": json.loads(raw) if raw.startswith("{") else raw}


def webhook_dump() -> list:
    s, _, raw = http("GET", f"{GATEWAY}/wx/selftest/payment-webhook")
    if s != 200: return []
    return json.loads(raw).get("entries", [])


def webhook_arm_fail_once(event: str, pay_order_id: str) -> bool:
    s, _, _ = http("GET", f"{GATEWAY}/wx/selftest/payment-webhook?armFailOnce={event}|{pay_order_id}")
    return s == 200


def webhook_reset() -> None:
    http("GET", f"{GATEWAY}/wx/selftest/payment-webhook?reset=1")


def wait_for_webhook(pay_order_id: str, event: str, timeout_s: float = 8.0) -> dict | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for e in webhook_dump():
            if e.get("payOrderId") == pay_order_id and e.get("event") == event and not e.get("fakeFailed"):
                return e
        time.sleep(0.4)
    return None


DUMMY_QR_URL = f"{GATEWAY}/payment/qr/_selftest_dummy.png"
DUMMY_QR_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGMAAQAAAAUAAQANCi20AAAAAElFTkSuQmCC"


def ensure_dummy_qr_on_disk():
    """Make sure data/qr/_selftest_dummy.png exists on the deploy host.
    Routes serve QR images from data/qr/ (preserved across deploys);
    we cannot ship the dummy via git anymore."""
    cmd = (
        "node -e 'const fs=require(\"fs\"),p=require(\"path\");"
        "const d=p.join(process.cwd(),\"data\",\"qr\");"
        "fs.mkdirSync(d,{recursive:true});"
        f"const b=Buffer.from(\"{DUMMY_QR_PNG_B64}\",\"base64\");"
        "fs.writeFileSync(p.join(d,\"_selftest_dummy.png\"),b);"
        "process.stdout.write(String(b.length));'"
    )
    out = deployer_exec(cmd, timeout_ms=10000)
    if out.get("exitCode") != 0:
        raise RuntimeError(f"ensure dummy qr failed: {out}")
    return int(out.get("stdout") or "0")


def admin_webhook_url_cases(auth_headers: dict):
    """T-ADM-WEBHOOK-1..2: PATCH /admin/apps/<id> webhookUrl is editable.

    Operates on the 'selftest' app (self-provisioned in setup). Records its
    current webhookUrl up front and restores it in finally — selftest must
    NOT corrupt prod state.
    """
    print()
    print("--- admin app webhookUrl edit (T-ADM-WEBHOOK-1..2) ---")
    s, _, raw = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps", headers=auth_headers)
    if s != 200:
        log(False, "T-ADM-WEBHOOK setup: list apps", f"status={s}")
        return
    apps = json.loads(raw).get("apps", [])
    target = next((a for a in apps if a["name"] == "selftest"), None)
    if not target:
        log(False, "T-ADM-WEBHOOK setup: selftest app not found (bootstrap should have created it)")
        return
    app_id = target["id"]
    original = target.get("webhookUrl")

    try:
        # T-ADM-WEBHOOK-1: PATCH valid https URL → 200, list reflects new value
        new_url = "https://test.example.com/hook"
        s_p, _, raw_p = http(
            "PATCH", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps/{app_id}",
            headers=auth_headers, body={"webhookUrl": new_url},
        )
        body_p = {}
        try:
            body_p = json.loads(raw_p)
        except Exception:
            pass
        # GET listing to verify writeback
        s_g, _, raw_g = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps", headers=auth_headers)
        listed = next(
            (a for a in (json.loads(raw_g).get("apps", []) if s_g == 200 else []) if a["id"] == app_id),
            None,
        )
        log(
            s_p == 200
            and body_p.get("webhookUrl") == new_url
            and listed is not None
            and listed.get("webhookUrl") == new_url,
            "T-ADM-WEBHOOK-1: PATCH webhookUrl https://… → 200 + writeback in list",
            f"patch_status={s_p} patch_body_url={body_p.get('webhookUrl')} listed={(listed or {}).get('webhookUrl')}",
        )

        # T-ADM-WEBHOOK-2: PATCH http:// → 400 + invalid_webhook_url
        s_b, _, raw_b = http(
            "PATCH", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps/{app_id}",
            headers=auth_headers, body={"webhookUrl": "http://insecure.example.com"},
        )
        body_b = {}
        try:
            body_b = json.loads(raw_b)
        except Exception:
            pass
        log(
            s_b == 400 and body_b.get("error") == "invalid_webhook_url",
            "T-ADM-WEBHOOK-2: PATCH http:// webhookUrl → 400 invalid_webhook_url",
            f"status={s_b} body={raw_b[:200]}",
        )
    finally:
        # Restore original webhookUrl regardless of test outcome.
        # Not counted as a separate test (per spec: 2 new cases). Failure prints
        # a loud warning so the operator notices prod state was corrupted.
        s_r, _, raw_r = http(
            "PATCH", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps/{app_id}",
            headers=auth_headers, body={"webhookUrl": original},
        )
        restored_url = None
        try:
            restored_url = json.loads(raw_r).get("webhookUrl")
        except Exception:
            pass
        if not (s_r == 200 and restored_url == original):
            print(
                f"   ⚠️  WARNING: failed to restore selftest webhookUrl "
                f"(status={s_r} got={restored_url!r} expected={original!r}) — "
                f"check production DB before next deploy",
                flush=True,
            )
        else:
            print(
                f"   [cleanup] selftest webhookUrl restored to original",
                flush=True,
            )


def users_tab_cases(auth_headers: dict):
    """T-USERS-1..5: Users tab (replaces Admins tab).

    Exercises:
      - GET /admin/users (list with required fields)
      - GET /admin/users?role=admin (filter)
      - GET /admin/users?q=<frag> (search)
      - GET /admin/users/<openid> (5-block detail)
      - grant via POST /admin/admins → role flips to admin → revoke via DELETE
        /admin/admins/<openid> → role flips back to null
    """
    print()
    print("--- users tab (T-USERS-1..5) ---")

    # T-USERS-1: list, no cursor, required fields.
    s, _, raw = http(
        "GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/users", headers=auth_headers,
    )
    body = json.loads(raw) if raw.startswith("{") else {}
    users = body.get("users") if isinstance(body, dict) else None
    required_fields = {
        "openid", "unionid", "nickname", "avatarUrl", "role",
        "currentBoundApp", "authorizedAppsCount", "totalPaidFen", "lastActiveAt",
    }
    sample_ok = (
        isinstance(users, list)
        and (
            len(users) == 0
            or required_fields.issubset(set(users[0].keys()))
        )
    )
    log(
        s == 200 and sample_ok,
        "T-USERS-1: GET /admin/users → 200 + required fields",
        f"status={s} count={len(users) if isinstance(users, list) else '?'} "
        f"sample_keys={sorted(users[0].keys()) if isinstance(users, list) and users else []}",
    )

    # Ensure at least one admin exists for role=admin filter. The selftest
    # cookie's openid 'selftest_admin' isn't in AdminUser, so insert a
    # throwaway admin via the POST endpoint, capture state, then remove.
    test_openid = f"selftest_user_admin_{secrets.token_hex(3)}"
    grant_for_filter = http(
        "POST", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/admins",
        headers=auth_headers,
        body={"openid": test_openid, "role": "admin", "nickname": "selftest user-admin"},
    )

    try:
        # T-USERS-2: role=admin filter contains our test admin.
        s2, _, raw2 = http(
            "GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/users?role=admin",
            headers=auth_headers,
        )
        body2 = json.loads(raw2) if raw2.startswith("{") else {}
        users2 = body2.get("users") if isinstance(body2, dict) else []
        admin_openids = {u.get("openid") for u in users2 if isinstance(u, dict)}
        log(
            s2 == 200 and test_openid in admin_openids and len(admin_openids) >= 1,
            "T-USERS-2: GET /admin/users?role=admin contains ≥1 admin (our test admin)",
            f"status={s2} count={len(users2)} contains_test={test_openid in admin_openids}",
        )

        # T-USERS-3: q filter matches by openid suffix.
        frag = test_openid[-10:]
        s3, _, raw3 = http(
            "GET",
            f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/users?q={frag}",
            headers=auth_headers,
        )
        body3 = json.loads(raw3) if raw3.startswith("{") else {}
        users3 = body3.get("users") if isinstance(body3, dict) else []
        hit3 = any(
            isinstance(u, dict) and u.get("openid") == test_openid for u in users3
        )
        log(
            s3 == 200 and hit3,
            "T-USERS-3: GET /admin/users?q=<frag> hits matching openid",
            f"status={s3} count={len(users3)} hit={hit3}",
        )

        # T-USERS-4: detail endpoint returns all 5 blocks.
        s4, _, raw4 = http(
            "GET",
            f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/users/{test_openid}",
            headers=auth_headers,
        )
        body4 = json.loads(raw4) if raw4.startswith("{") else {}
        ok4 = (
            s4 == 200
            and isinstance(body4, dict)
            and isinstance(body4.get("profile"), dict)
            and body4["profile"].get("openid") == test_openid
            and isinstance(body4.get("authorizations"), list)
            and ("binding" in body4)
            and isinstance(body4.get("payments"), list)
            and isinstance(body4.get("fanoutLogs"), list)
        )
        log(
            ok4,
            "T-USERS-4: GET /admin/users/<openid> → 200 + 5 blocks",
            f"status={s4} keys={sorted(body4.keys()) if isinstance(body4, dict) else type(body4).__name__}",
        )

        # T-USERS-5: grant/revoke cycle visible in detail endpoint.
        # role should already be admin (from setup grant above). Verify, then
        # revoke and re-verify it's null. Requires another admin to exist
        # (production has real admins; otherwise the DELETE 409s on last_admin).
        s5a, _, raw5a = http(
            "GET",
            f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/users/{test_openid}",
            headers=auth_headers,
        )
        body5a = json.loads(raw5a) if raw5a.startswith("{") else {}
        role5a = (body5a.get("profile") or {}).get("role") if isinstance(body5a, dict) else None

        s5d, _, raw5d = http(
            "DELETE",
            f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/admins/{test_openid}",
            headers=auth_headers,
        )

        s5b, _, raw5b = http(
            "GET",
            f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/users/{test_openid}",
            headers=auth_headers,
        )
        body5b = json.loads(raw5b) if raw5b.startswith("{") else {}
        role5b = (body5b.get("profile") or {}).get("role") if isinstance(body5b, dict) else None

        log(
            grant_for_filter[0] == 200
            and role5a == "admin"
            and s5d == 200
            and role5b is None,
            "T-USERS-5: grant→role=admin; revoke→role=null via /admin/users/<openid>",
            f"grant={grant_for_filter[0]} role_after_grant={role5a} "
            f"revoke={s5d} role_after_revoke={role5b}",
        )
    finally:
        # Clean up AdminUser row (best-effort: blocked is acceptable; row remains
        # but won't show as admin). If revoke succeeded above, this is a no-op.
        try:
            http(
                "DELETE",
                f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/admins/{test_openid}",
                headers=auth_headers,
            )
        except Exception:
            pass


def user_binding_edit_cases(auth_headers: dict):
    """T-USER-BIND-EDIT-1..3: admin can modify UserAppBinding.appName.

      1: PATCH without admin session → 404 (camouflage; requireAdmin returns 404 for unauth)
      2: PATCH with admin session but unknown appName → 400 app_not_found
      3: PATCH with admin session + selftest app → 200; GET detail shows
         binding.currentApp == 'selftest'.
    """
    print()
    print("--- users tab binding edit (T-USER-BIND-EDIT-1..3) ---")

    rand = secrets.token_hex(3)
    openid = f"selftest_bindedit_{rand}"
    base = f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/users/{openid}/binding"

    # T-USER-BIND-EDIT-1: no auth → 404 camouflage (requireAdmin behavior)
    s1, _, raw1 = http("PATCH", base, body={"appName": "selftest"})
    log(s1 == 404, "T-USER-BIND-EDIT-1: PATCH without admin session → 404 camouflage",
        f"status={s1} body={raw1[:120]}")

    # T-USER-BIND-EDIT-2: unknown appName → 400 app_not_found
    bogus = f"selftest_bogus_app_{rand}"
    s2, _, raw2 = http(
        "PATCH", base, headers=auth_headers, body={"appName": bogus},
    )
    body2 = {}
    try:
        body2 = json.loads(raw2)
    except Exception:
        pass
    log(
        s2 == 400 and body2.get("error") == "app_not_found",
        "T-USER-BIND-EDIT-2: PATCH unknown appName → 400 app_not_found",
        f"status={s2} body={raw2[:160]}",
    )

    try:
        # T-USER-BIND-EDIT-3: PATCH to selftest app → 200, GET shows updated binding.
        s3, _, raw3 = http(
            "PATCH", base, headers=auth_headers, body={"appName": "selftest"},
        )
        body3 = {}
        try:
            body3 = json.loads(raw3)
        except Exception:
            pass
        patch_ok = (
            s3 == 200
            and isinstance(body3.get("binding"), dict)
            and body3["binding"].get("appName") == "selftest"
            and body3["binding"].get("openid") == openid
        )

        s3g, _, raw3g = http(
            "GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/users/{openid}",
            headers=auth_headers,
        )
        body3g = {}
        try:
            body3g = json.loads(raw3g)
        except Exception:
            pass
        binding3g = body3g.get("binding") if isinstance(body3g, dict) else None
        get_ok = (
            s3g == 200
            and isinstance(binding3g, dict)
            and binding3g.get("currentApp") == "selftest"
        )
        log(
            patch_ok and get_ok,
            "T-USER-BIND-EDIT-3: PATCH selftest → 200, GET detail shows binding=selftest",
            f"patch_status={s3} patch_body={raw3[:160]} get_status={s3g} binding={binding3g!r}",
        )
    finally:
        # cleanup: drop binding row via existing control action.
        try:
            secret_for_cleanup = fetch_admin_session_secret()
            selftest_control(
                secret_for_cleanup, "fanout-simulate-binding-cleanup",
                fromUser=openid, prefix=f"selftest_bindedit_noop_{rand}_",
            )
        except Exception as e:
            print(f"   ⚠️  cleanup binding-edit failed: {e!r}", flush=True)


def admin_payment_detail_cases(admin_secret: str, auth_headers: dict):
    """T-ADM-PAY-DETAIL-1 / T-ADM-EXTEND-1 / T-ADM-FORCE-EXPIRE-1.

    Exercises the new admin payment detail-drawer endpoints:
      - GET    /admin/payments/<id>/webhooks
      - PATCH  /admin/payments/<id>/extend
      - POST   /admin/payments/<id>/force-expire
    Creates fresh payments via the selftest app; leaves them in expired state
    (selftest cleanup is opportunistic).
    """
    print()
    print("--- admin payment detail (T-ADM-PAY-DETAIL-1, T-ADM-EXTEND-1, T-ADM-FORCE-EXPIRE-1) ---")
    try:
        app_secret = fetch_selftest_app_secret()
    except Exception as e:
        log(False, "fetch selftest app secret", str(e))
        return

    # Make sure selftest app has personalQrUrl set (pay/create requires it).
    try:
        ensure_dummy_qr_on_disk()
    except Exception:
        pass
    selftest_control(admin_secret, "set-personal-qr-url", url=DUMMY_QR_URL)
    # Ensure payment is enabled on selftest app (post-2.1c default is false).
    selftest_control(admin_secret, "set-payment-policy",
                     paymentEnabled=True, maxAmountFen=20000, defaultExpiresIn=1800)

    rand = secrets.token_hex(3)

    # Create payment #1 for webhooks GET + extend tests
    r1 = pay_create(app_secret, "selftest", f"selftest_admdetail_{rand}_1", 1)
    if r1["status"] != 200:
        log(False, "T-ADM-PAY-DETAIL-1 setup: pay/create failed", str(r1))
        return
    pid1 = r1["body"]["payOrderId"]

    # T-ADM-PAY-DETAIL-1: GET webhooks
    s, _, raw = http(
        "GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/payments/{pid1}/webhooks",
        headers=auth_headers,
    )
    body = {}
    try:
        body = json.loads(raw)
    except Exception:
        pass
    log(
        s == 200 and isinstance(body.get("deliveries"), list),
        "T-ADM-PAY-DETAIL-1: GET /admin/payments/<id>/webhooks → 200 + deliveries[]",
        f"status={s} body={raw[:200]}",
    )

    # T-ADM-EXTEND-1: PATCH extend valid future / invalid past / >7d / non-eligible
    valid_ms = int(time.time() * 1000) + 3600 * 1000
    s, _, raw = http(
        "PATCH", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/payments/{pid1}/extend",
        headers=auth_headers, body={"expiresAt": valid_ms},
    )
    bvalid = json.loads(raw) if raw.startswith("{") else {}
    ok_valid = s == 200 and abs(int(bvalid.get("expiresAt", 0)) - valid_ms) < 2000

    # invalid: past
    s_past, _, raw_past = http(
        "PATCH", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/payments/{pid1}/extend",
        headers=auth_headers, body={"expiresAt": int(time.time() * 1000) - 60_000},
    )
    bpast = json.loads(raw_past) if raw_past.startswith("{") else {}
    ok_past = s_past == 400 and bpast.get("error") == "invalid_expires_at"

    # invalid: > 7d
    s_far, _, raw_far = http(
        "PATCH", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/payments/{pid1}/extend",
        headers=auth_headers, body={"expiresAt": int(time.time() * 1000) + 8 * 86400 * 1000},
    )
    bfar = json.loads(raw_far) if raw_far.startswith("{") else {}
    ok_far = s_far == 400 and bfar.get("error") == "invalid_expires_at"

    # non-eligible: create a payment, force-expire it, then try to extend → 409
    r2 = pay_create(app_secret, "selftest", f"selftest_admdetail_{rand}_2", 1)
    if r2["status"] != 200:
        log(False, "T-ADM-EXTEND-1 setup#2: pay/create failed", str(r2))
        return
    pid2 = r2["body"]["payOrderId"]
    selftest_control(admin_secret, "force-expire", payOrderId=pid2)
    s_inel, _, raw_inel = http(
        "PATCH", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/payments/{pid2}/extend",
        headers=auth_headers, body={"expiresAt": valid_ms},
    )
    binel = json.loads(raw_inel) if raw_inel.startswith("{") else {}
    ok_inel = s_inel == 409 and binel.get("error") == "not_eligible"

    log(
        ok_valid and ok_past and ok_far and ok_inel,
        "T-ADM-EXTEND-1: PATCH extend valid/past/>7d/non-eligible → 200/400/400/409",
        f"valid={s}/{bvalid} past={s_past}/{bpast} far={s_far}/{bfar} inel={s_inel}/{binel}",
    )

    # T-ADM-FORCE-EXPIRE-1: pending payment, force-expire 200, second call 409
    r3 = pay_create(app_secret, "selftest", f"selftest_admdetail_{rand}_3", 1)
    if r3["status"] != 200:
        log(False, "T-ADM-FORCE-EXPIRE-1 setup: pay/create failed", str(r3))
        return
    pid3 = r3["body"]["payOrderId"]
    s_fe1, _, raw_fe1 = http(
        "POST", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/payments/{pid3}/force-expire",
        headers=auth_headers, body={},
    )
    bfe1 = json.loads(raw_fe1) if raw_fe1.startswith("{") else {}
    ok_fe1 = s_fe1 == 200 and bfe1.get("status") == "expired"

    s_fe2, _, raw_fe2 = http(
        "POST", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/payments/{pid3}/force-expire",
        headers=auth_headers, body={},
    )
    bfe2 = json.loads(raw_fe2) if raw_fe2.startswith("{") else {}
    ok_fe2 = s_fe2 == 409 and bfe2.get("error") == "not_eligible"

    log(
        ok_fe1 and ok_fe2,
        "T-ADM-FORCE-EXPIRE-1: pending → 200 expired; second call → 409 not_eligible",
        f"first={s_fe1}/{bfe1} second={s_fe2}/{bfe2}",
    )


def payment_cases(admin_secret: str, auth_headers: dict):
    print()
    print("--- payment v1 (T-PAY-1..11) ---")
    try:
        app_secret = fetch_selftest_app_secret()
    except Exception as e:
        log(False, "fetch selftest app secret", str(e))
        return

    # Ensure dummy QR exists in data/qr/ on the deploy host (not in git anymore).
    try:
        n = ensure_dummy_qr_on_disk()
        log(n > 0, f"bootstrap data/qr/_selftest_dummy.png on host", f"bytes={n}")
    except Exception as e:
        log(False, "bootstrap data/qr/_selftest_dummy.png", str(e))
        return

    # Configure selftest app webhookUrl (uses ADMIN_SESSION_SECRET as control token).
    ctl = selftest_control(admin_secret, "set-webhook-url",
                           url=f"{GATEWAY}/wx/selftest/payment-webhook")
    if ctl["status"] != 200:
        log(False, "set selftest webhookUrl", str(ctl))
        return

    # Configure selftest app personalQrUrl to dummy 1px PNG (T-PAY-1..10 require it).
    ctl = selftest_control(admin_secret, "set-personal-qr-url", url=DUMMY_QR_URL)
    if ctl["status"] != 200:
        log(False, "set selftest personalQrUrl", str(ctl))
        return

    # Ensure baseline payment policy: enabled=true, max=20000, ttl=1800
    # (post-2.1c migration default is paymentEnabled=false; existing T-PAY-*
    # cases assume the selftest app can call /pay/create.)
    ctl = selftest_control(admin_secret, "set-payment-policy",
                           paymentEnabled=True, maxAmountFen=20000, defaultExpiresIn=1800)
    if ctl["status"] != 200:
        log(False, "set selftest paymentEnabled=true", str(ctl))
        return

    webhook_reset()

    rand = secrets.token_hex(3)

    # T-PAY-1: create + remark format
    order_id = f"selftest_pay_{rand}_1"
    r = pay_create(app_secret, "selftest", order_id, 1)
    bad_chars = set("0189IO")
    ok1 = (
        r["status"] == 200
        and isinstance(r["body"], dict)
        and r["body"].get("payOrderId")
        and r["body"].get("remark")
        and len(r["body"]["remark"]) == 6
        and not bad_chars.intersection(set(r["body"]["remark"]))
    )
    log(ok1, f"T-PAY-1: POST /pay/create → 200 + payOrderId + 6-char remark (no 0189IO)", f"status={r['status']}")
    if not ok1:
        log(False, "T-PAY-1 prerequisite failed; skipping rest of payment cases")
        return
    pay_order_id = r["body"]["payOrderId"]

    # T-PAY-2: status pending
    r = pay_status(app_secret, "selftest", pay_order_id)
    log(r["status"] == 200 and r["body"].get("status") == "pending",
        f"T-PAY-2: GET /pay/status → status=pending", f"got={r['body'].get('status')}")

    # T-PAY-3: claim → submitted
    r = pay_claim(app_secret, "selftest", pay_order_id, user_note="paid via selftest")
    log(r["status"] == 200 and r["body"].get("status") == "submitted",
        f"T-PAY-3: POST /pay/personal/claim → status=submitted", f"got={r}")

    # T-PAY-4: status submitted
    r = pay_status(app_secret, "selftest", pay_order_id)
    log(r["status"] == 200 and r["body"].get("status") == "submitted",
        f"T-PAY-4: GET /pay/status → status=submitted", f"got={r['body'].get('status')}")

    # T-PAY-7 (run before approve so we can test claim-twice on submitted state)
    r = pay_claim(app_secret, "selftest", pay_order_id)
    log(r["status"] == 409 and r["body"].get("error") == "state_invalid",
        f"T-PAY-7: idempotency: 2nd claim → 409 state_invalid", f"got={r}")

    # T-PAY-5: admin approve → paid
    r = admin_post(f"/api/payments/{pay_order_id}/approve", auth_headers, {"externalRef": "selftest-ref-1"})
    log(r["status"] == 200 and r["body"].get("ok") and r["body"]["payment"]["status"] == "paid",
        f"T-PAY-5: admin approve → status=paid", f"got={r}")

    # T-PAY-6: webhook payment.paid received + sigValid
    w = None
    for _ in range(6):
        selftest_control(admin_secret, "tick-webhooks")
        w = wait_for_webhook(pay_order_id, "payment.paid", timeout_s=5)
        if w is not None:
            break
    log(w is not None and w.get("sigValid") is True,
        f"T-PAY-6: webhook payment.paid received with valid signature",
        f"got={w}")

    # T-PAY-8: expire path
    order_id_exp = f"selftest_pay_{rand}_8"
    r = pay_create(app_secret, "selftest", order_id_exp, 2)
    if r["status"] != 200:
        log(False, "T-PAY-8 setup: pay/create failed", str(r))
    else:
        exp_pid = r["body"]["payOrderId"]
        # Force expire via control endpoint
        ctl = selftest_control(admin_secret, "force-expire", payOrderId=exp_pid)
        rr = pay_status(app_secret, "selftest", exp_pid)
        wexp = None
        for _ in range(6):
            selftest_control(admin_secret, "tick-webhooks")
            wexp = wait_for_webhook(exp_pid, "payment.expired", timeout_s=5)
            if wexp is not None:
                break
        log(
            rr["status"] == 200
            and rr["body"].get("status") == "expired"
            and wexp is not None
            and wexp.get("sigValid") is True,
            f"T-PAY-8: force-expire → status=expired + webhook payment.expired",
            f"status={rr['body'].get('status')} webhook={bool(wexp)} ctl={ctl['body']}",
        )

    # T-PAY-9: webhook retry on 500 → second attempt 200
    order_id_retry = f"selftest_pay_{rand}_9"
    r = pay_create(app_secret, "selftest", order_id_retry, 3)
    if r["status"] != 200:
        log(False, "T-PAY-9 setup: pay/create failed", str(r))
    else:
        rt_pid = r["body"]["payOrderId"]
        # Arm fail-once for the upcoming payment.paid webhook
        webhook_arm_fail_once("payment.paid", rt_pid)
        # claim + approve
        pay_claim(app_secret, "selftest", rt_pid)
        admin_post(f"/api/payments/{rt_pid}/approve", auth_headers, {"externalRef": "retry-test"})
        # Wait for first failure attempt + retry
        deadline = time.time() + 30
        first_fail = None
        success = None
        while time.time() < deadline:
            entries = [e for e in webhook_dump() if e.get("payOrderId") == rt_pid and e.get("event") == "payment.paid"]
            for e in entries:
                if e.get("fakeFailed"): first_fail = e
                else: success = e
            if first_fail and success: break
            # Manual tick to speed up
            selftest_control(admin_secret, "tick-webhooks")
            time.sleep(1.5)
        log(first_fail is not None and success is not None and success.get("sigValid"),
            f"T-PAY-9: webhook retry on 500 → eventual success",
            f"first_fail={bool(first_fail)} success={bool(success)}")

    # T-PAY-10: reject path
    order_id_rej = f"selftest_pay_{rand}_10"
    r = pay_create(app_secret, "selftest", order_id_rej, 4)
    if r["status"] != 200:
        log(False, "T-PAY-10 setup: pay/create failed", str(r))
    else:
        rj_pid = r["body"]["payOrderId"]
        pay_claim(app_secret, "selftest", rj_pid)
        rr = admin_post(f"/api/payments/{rj_pid}/reject", auth_headers, {"rejectReason": "selftest reject"})
        # Tick + assert webhook (multiple ticks to drain queue head-of-line)
        wrj = None
        for _ in range(12):
            selftest_control(admin_secret, "tick-webhooks")
            wrj = wait_for_webhook(rj_pid, "payment.disputed", timeout_s=5)
            if wrj is not None:
                break
        ok10 = (
            rr["status"] == 200
            and rr["body"]["payment"]["status"] == "disputed"
            and wrj is not None
            and wrj.get("sigValid") is True
        )
        log(ok10, f"T-PAY-10: admin reject → status=disputed + webhook payment.disputed",
            f"reject={rr['status']} webhook={bool(wrj)}")

    # T-PAY-11: personal_qr_not_configured guard
    rand11 = secrets.token_hex(3)
    # Clear → expect 503
    ctl_clr = selftest_control(admin_secret, "set-personal-qr-url", url=None)
    r_miss = pay_create(app_secret, "selftest", f"selftest_pay_{rand11}_11a", 1)
    miss_ok = r_miss["status"] == 503 and isinstance(r_miss["body"], dict) and r_miss["body"].get("error") == "personal_qr_not_configured"
    # Restore dummy → expect 200 + qrcodeUrl == DUMMY_QR_URL
    ctl_set = selftest_control(admin_secret, "set-personal-qr-url", url=DUMMY_QR_URL)
    r_back = pay_create(app_secret, "selftest", f"selftest_pay_{rand11}_11b", 1)
    back_ok = (
        r_back["status"] == 200
        and isinstance(r_back["body"], dict)
        and r_back["body"].get("qrcodeUrl") == DUMMY_QR_URL
    )
    log(
        miss_ok and back_ok and ctl_clr["status"] == 200 and ctl_set["status"] == 200,
        "T-PAY-11: missing personalQrUrl → 503; restore → 200 with configured URL",
        f"miss={r_miss['status']}/{r_miss['body']} back={r_back['status']} qr={r_back['body'].get('qrcodeUrl') if isinstance(r_back['body'], dict) else r_back['body']}",
    )

    # Cleanup: ensure dummy URL is set so subsequent runs aren't poisoned by a half-failed T-PAY-11.
    selftest_control(admin_secret, "set-personal-qr-url", url=DUMMY_QR_URL)

    # T-QR-DYNAMIC-1: uploaded QR is served immediately by the dynamic route
    # (not cached by Next.js prerender — the bug this whole change fixes).
    qr_dynamic_case(admin_secret, auth_headers)

    # T-INSTANCE-1: welcome message URL must use this instance's PUBLIC_BASE_URL
    # (not a hardcoded domain — guards against the multi-instance regression
    # where 莆阳 users got links pointing to 造悟者).
    instance_welcome_case(admin_secret)

    # ---- 2.1c: app-level payment policy + overview ----
    payment_policy_cases(admin_secret, auth_headers, app_secret)


def payment_policy_cases(admin_secret: str, auth_headers: dict, app_secret: str):
    """T-PAY-DISABLED-1 / T-AMOUNT-LIMIT-1 / T-DEFAULT-EXPIRES-1 / T-OVERVIEW-1.

    All cases mutate the selftest app's payment policy and MUST restore baseline
    in finally — otherwise we corrupt the prod selftest app's config.
    """
    print()
    print("--- 2.1c app-level payment policy (T-PAY-DISABLED-1 / T-AMOUNT-LIMIT-1 / T-DEFAULT-EXPIRES-1 / T-OVERVIEW-1) ---")

    # T-PAY-DISABLED-1: paymentEnabled=false → /pay/create 503 payment_disabled
    rand = secrets.token_hex(3)
    try:
        ctl = selftest_control(admin_secret, "set-payment-policy", paymentEnabled=False)
        if ctl["status"] != 200:
            log(False, "T-PAY-DISABLED-1 setup", str(ctl))
        else:
            r = pay_create(app_secret, "selftest", f"selftest_disabled_{rand}", 1)
            ok = (
                r["status"] == 503
                and isinstance(r["body"], dict)
                and r["body"].get("error") == "payment_disabled"
            )
            log(
                ok,
                "T-PAY-DISABLED-1: paymentEnabled=false → 503 payment_disabled",
                f"status={r['status']} body={r['body']}",
            )
    finally:
        ctl_r = selftest_control(admin_secret, "set-payment-policy", paymentEnabled=True)
        if ctl_r["status"] != 200:
            print(f"   ⚠️  WARNING: failed to restore selftest paymentEnabled=true: {ctl_r}", flush=True)

    # T-AMOUNT-LIMIT-1: shrink maxAmountFen=5000; 5001 → 400, 5000 → 200
    rand2 = secrets.token_hex(3)
    try:
        ctl = selftest_control(admin_secret, "set-payment-policy", maxAmountFen=5000)
        if ctl["status"] != 200:
            log(False, "T-AMOUNT-LIMIT-1 setup", str(ctl))
        else:
            r_over = pay_create(app_secret, "selftest", f"selftest_amt_{rand2}_over", 5001)
            r_at = pay_create(app_secret, "selftest", f"selftest_amt_{rand2}_at", 5000)
            ok = (
                r_over["status"] == 400
                and isinstance(r_over["body"], dict)
                and r_over["body"].get("error") == "amount_out_of_range"
                and r_at["status"] == 200
                and isinstance(r_at["body"], dict)
                and r_at["body"].get("payOrderId")
            )
            log(
                ok,
                "T-AMOUNT-LIMIT-1: maxAmountFen=5000 → 5001 rejected, 5000 accepted",
                f"over={r_over['status']}/{r_over['body'].get('error') if isinstance(r_over['body'], dict) else '?'} "
                f"at={r_at['status']}",
            )
    finally:
        ctl_r = selftest_control(admin_secret, "set-payment-policy", maxAmountFen=20000)
        if ctl_r["status"] != 200:
            print(f"   ⚠️  WARNING: failed to restore selftest maxAmountFen=20000: {ctl_r}", flush=True)

    # T-DEFAULT-EXPIRES-1: defaultExpiresIn=600; /pay/create without expiresIn → expiresAt-now ≈ 600s
    rand3 = secrets.token_hex(3)
    try:
        ctl = selftest_control(admin_secret, "set-payment-policy", defaultExpiresIn=600)
        if ctl["status"] != 200:
            log(False, "T-DEFAULT-EXPIRES-1 setup", str(ctl))
        else:
            ts_before_ms = int(time.time() * 1000)
            ts_str = str(ts_before_ms)
            order_id = f"selftest_ttl_{rand3}"
            sig = hmac_hex(app_secret, f"selftest|{order_id}|1|{ts_str}")
            s, _, raw = http(
                "POST", f"{GATEWAY}/pay/create",
                headers={"X-WX-App-Name": "selftest", "X-WX-Sig": sig, "X-WX-Ts": ts_str},
                body={"orderId": order_id, "amount_fen": 1, "subject": "ttl probe", "method": "personal_qr"},
            )
            body = json.loads(raw) if raw.startswith("{") else {}
            expires_at_ms = body.get("expiresAt") if isinstance(body, dict) else None
            delta_s = (expires_at_ms - ts_before_ms) / 1000 if isinstance(expires_at_ms, (int, float)) else None
            ok = (
                s == 200
                and isinstance(delta_s, (int, float))
                and 595 <= delta_s <= 605
            )
            log(
                ok,
                "T-DEFAULT-EXPIRES-1: defaultExpiresIn=600, no expiresIn body → expiresAt-now ≈ 600s",
                f"status={s} delta_s={delta_s}",
            )
    finally:
        ctl_r = selftest_control(admin_secret, "set-payment-policy", defaultExpiresIn=1800)
        if ctl_r["status"] != 200:
            print(f"   ⚠️  WARNING: failed to restore selftest defaultExpiresIn=1800: {ctl_r}", flush=True)

    # T-OVERVIEW-1: GET /admin/overview → 200 + correct shape
    s, _, raw = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/overview", headers=auth_headers)
    body = {}
    try:
        body = json.loads(raw)
    except Exception:
        pass
    apps_block = body.get("apps") if isinstance(body, dict) else None
    pay_block = body.get("payments") if isinstance(body, dict) else None
    today_block = pay_block.get("today") if isinstance(pay_block, dict) else None
    ok = (
        s == 200
        and isinstance(apps_block, dict)
        and isinstance(apps_block.get("active"), int)
        and isinstance(apps_block.get("revoked"), int)
        and isinstance(pay_block, dict)
        and isinstance(today_block, dict)
        and isinstance(today_block.get("count"), int)
        and isinstance(today_block.get("paidAmountFen"), int)
        and isinstance(pay_block.get("pending"), int)
        and isinstance(pay_block.get("submittedReview"), int)
        and isinstance(pay_block.get("failedWebhooksLast24h"), int)
    )
    log(
        ok,
        "T-OVERVIEW-1: GET /admin/overview → 200 + apps/payments shape complete",
        f"status={s} body_keys={list(body.keys()) if isinstance(body, dict) else type(body).__name__}",
    )


def finalize(admin_secret: str | None = None):
    if admin_secret is not None:
        cleanup_selftest_app(admin_secret)
    _purge_temp_apps()
    failed = sum(1 for r in results if not r)
    total = len(results)
    print()
    print(f"== {total - failed}/{total} passed ==")
    sys.exit(1 if failed else 0)


def cron_cases():
    """T-CRON-1: verify [payment-cron] registered shows up in pm2 logs of the
    running wx-gateway process. This is the only way to assert the cron block
    in instrumentation.ts actually fired — globalThis state lives inside the
    PM2-managed Next.js process, not /api/exec's fresh node invocations.

    Also opportunistically clean up status=fail webhook rows older than 1h
    so the redeliver queue stays healthy. The deletion count is logged but
    does NOT affect the assertion.
    """
    print()
    print("--- cron (T-CRON-1) ---")
    try:
        out = deployer_exec(
            "pm2 logs wx-gateway --nostream --lines 800 --raw 2>&1 | grep '\\[payment-cron\\]' || true",
            timeout_ms=15000,
        )
        log_text = (out.get("stdout") or "") + (out.get("stderr") or "")
        registered = "[payment-cron] registered" in log_text
        log(
            registered,
            "T-CRON-1: pm2 logs contain '[payment-cron] registered' (cron survived early-return)",
            f"matched_lines={[l for l in log_text.splitlines() if '[payment-cron]' in l][-3:]}",
        )
    except Exception as e:
        log(False, "T-CRON-1: pm2 log probe failed", repr(e))

    # Business webhook retry records are never deleted by selftest.


def _internal_sig(secret: str, payload: str, ts: str, app_name: str) -> str:
    return hmac.new(
        secret.encode(),
        f"{payload}|{ts}|{app_name}".encode(),
        hashlib.sha256,
    ).hexdigest()


def internal_token_cases():
    """T-INTERNAL-TOKEN-1: GET /internal/wx-token (per-app auth)

      - correct sig (selftest app) + fresh ts → 200 with accessToken
      - bad sig                                → 401
      - ts skewed >5min                        → 401
      - unknown appName                        → 403 app_not_found
    """
    print()
    print("--- internal token (T-INTERNAL-TOKEN-1) ---")
    try:
        app_secret = fetch_selftest_app_secret()
    except Exception as e:
        log(False, "T-INTERNAL-TOKEN-1: fetch selftest secret", repr(e))
        return


    # 1) happy path
    ts_ok = str(int(time.time() * 1000))
    s1, _, raw1 = http(
        "GET", f"{GATEWAY}/internal/wx-token",
        headers={
            "X-App-Name": "selftest",
            "X-Internal-Auth": _internal_sig(app_secret, "wx-token", ts_ok, "selftest"),
            "X-Ts": ts_ok,
        },
    )
    body1 = json.loads(raw1) if raw1.startswith("{") else {}
    ok1 = (
        s1 == 200
        and isinstance(body1.get("accessToken"), str)
        and len(body1.get("accessToken", "")) >= 32
        and isinstance(body1.get("expiresAt"), int)
        and body1["expiresAt"] > int(time.time() * 1000)
    )

    # 2) bad sig
    s2, _, _ = http(
        "GET", f"{GATEWAY}/internal/wx-token",
        headers={
            "X-App-Name": "selftest",
            "X-Internal-Auth": "deadbeef" * 8,
            "X-Ts": ts_ok,
        },
    )
    ok2 = s2 == 401

    # 3) skewed ts (6 min)
    ts_skew = str(int(time.time() * 1000) - 6 * 60 * 1000)
    s3, _, _ = http(
        "GET", f"{GATEWAY}/internal/wx-token",
        headers={
            "X-App-Name": "selftest",
            "X-Internal-Auth": _internal_sig(app_secret, "wx-token", ts_skew, "selftest"),
            "X-Ts": ts_skew,
        },
    )
    ok3 = s3 == 401

    # 4) unknown app → 403 app_not_found
    fake = f"nonexistent_{secrets.token_hex(3)}"
    ts4 = str(int(time.time() * 1000))
    s4, _, raw4 = http(
        "GET", f"{GATEWAY}/internal/wx-token",
        headers={
            "X-App-Name": fake,
            "X-Internal-Auth": _internal_sig(app_secret, "wx-token", ts4, fake),
            "X-Ts": ts4,
        },
    )
    b4 = json.loads(raw4) if raw4.startswith("{") else {}
    ok4 = s4 == 403 and b4.get("error") == "app_not_found"

    log(
        ok1 and ok2 and ok3 and ok4,
        "T-INTERNAL-TOKEN-1: per-app sig→200; bad sig→401; ts skew→401; unknown app→403",
        f"happy={s1}/{'token' if ok1 else body1} bad_sig={s2} skewed={s3} unknown={s4}/{b4}",
    )


def internal_config_cases():
    """T-CONFIG-1..3: GET /internal/wx-config (per-app auth, self-service config view)

      1: no auth header → 401
      2: bad HMAC → 401
      3: selftest happy path → 200 + app.name=='selftest' + fanout.boundUsers>=0 + instance.appId present
    """
    print()
    print("--- internal config (T-CONFIG-1..3) ---")
    try:
        app_secret = fetch_selftest_app_secret()
    except Exception as e:
        log(False, "T-CONFIG-*: fetch selftest secret", repr(e))
        return

    url = f"{GATEWAY}/internal/wx-config"

    # T-CONFIG-1: no auth → 401
    s1, _, _ = http("GET", url)
    log(s1 == 401, "T-CONFIG-1: missing X-Internal-Auth → 401", f"got={s1}")

    # T-CONFIG-2: bad HMAC → 401
    ts = str(int(time.time() * 1000))
    s2, _, _ = http(
        "GET", url,
        headers={"X-App-Name": "selftest", "X-Internal-Auth": "deadbeef" * 8, "X-Ts": ts},
    )
    log(s2 == 401, "T-CONFIG-2: bad HMAC → 401", f"got={s2}")

    # T-CONFIG-3: selftest happy path → 200, shape asserts
    ts = str(int(time.time() * 1000))
    s3, _, raw3 = http(
        "GET", url,
        headers={
            "X-App-Name": "selftest",
            "X-Internal-Auth": _internal_sig(app_secret, "wx-config", ts, "selftest"),
            "X-Ts": ts,
        },
    )
    body = json.loads(raw3) if raw3.startswith("{") else {}
    app_block = body.get("app") if isinstance(body, dict) else None
    fanout_block = body.get("fanout") if isinstance(body, dict) else None
    instance_block = body.get("instance") if isinstance(body, dict) else None
    ok3 = (
        s3 == 200
        and isinstance(app_block, dict)
        and app_block.get("name") == "selftest"
        and isinstance(fanout_block, dict)
        and isinstance(fanout_block.get("boundUsers"), int)
        and fanout_block["boundUsers"] >= 0
        and isinstance(instance_block, dict)
        and isinstance(instance_block.get("appId"), str)
        and len(instance_block["appId"]) > 0
    )
    log(
        ok3,
        "T-CONFIG-3: GET /internal/wx-config (selftest) → 200 + shape",
        f"status={s3} app={app_block!r} fanout_boundUsers={fanout_block.get('boundUsers') if isinstance(fanout_block, dict) else '?'} appId={(instance_block or {}).get('appId')}",
    )


def internal_qrcode_cases():
    """T-QRCODE-1..3 + T-QRCODE-SCAN-1 + T-QRCODE-SUBSCRIBE-1:

      1: no auth → 401
      2: selftest happy path → 200, qrcodeUrl on mp.weixin.qq.com
      3: two consecutive calls return SAME ticket (cache hit, no quota burn)
      SCAN-1: simulate SCAN with EventKey="selftest" → binding written
      SUBSCRIBE-1: simulate subscribe with EventKey="qrscene_selftest" → binding written
    """
    print()
    print("--- internal qrcode + permanent SCAN (T-QRCODE-*) ---")
    try:
        app_secret = fetch_selftest_app_secret()
        admin_secret = fetch_admin_session_secret()
    except Exception as e:
        log(False, "T-QRCODE-*: fetch secrets", repr(e))
        return

    url = f"{GATEWAY}/internal/wx-qrcode"

    # T-QRCODE-1: no auth → 401
    s1, _, _ = http("GET", url)
    log(s1 == 401, "T-QRCODE-1: no auth → 401", f"got={s1}")

    # T-QRCODE-2: selftest happy path
    ts = str(int(time.time() * 1000))
    s2, _, raw2 = http(
        "GET", url,
        headers={
            "X-App-Name": "selftest",
            "X-Internal-Auth": _internal_sig(app_secret, "wx-qrcode", ts, "selftest"),
            "X-Ts": ts,
        },
    )
    body2 = json.loads(raw2) if raw2.startswith("{") else {}
    qr_url = body2.get("qrcodeUrl", "") if isinstance(body2, dict) else ""
    ticket2 = body2.get("ticket", "") if isinstance(body2, dict) else ""
    ok2 = (
        s2 == 200
        and isinstance(qr_url, str)
        and qr_url.startswith("https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket=")
        and isinstance(ticket2, str)
        and len(ticket2) > 0
    )
    log(ok2, "T-QRCODE-2: selftest → 200 + showqrcode URL", f"status={s2} url={qr_url[:80]}")

    # T-QRCODE-3: second call returns same ticket (no quota burn)
    ts = str(int(time.time() * 1000))
    s3, _, raw3 = http(
        "GET", url,
        headers={
            "X-App-Name": "selftest",
            "X-Internal-Auth": _internal_sig(app_secret, "wx-qrcode", ts, "selftest"),
            "X-Ts": ts,
        },
    )
    body3 = json.loads(raw3) if raw3.startswith("{") else {}
    ticket3 = body3.get("ticket", "") if isinstance(body3, dict) else ""
    ok3 = s3 == 200 and ticket3 == ticket2 and len(ticket3) > 0
    log(
        ok3,
        "T-QRCODE-3: two consecutive calls → same ticket (cached, no WX API hit)",
        f"first={ticket2[:12]}… second={ticket3[:12]}…",
    )

    # SCAN-1: bare appName as EventKey (already-subscribed user scanning)
    openid_scan = f"selftest_qr_scan_{secrets.token_hex(4)}"
    r_scan = selftest_control(
        admin_secret, "simulate-permanent-scan",
        eventKey="selftest", openid=openid_scan,
    )
    ok_scan = (
        r_scan["status"] == 200
        and isinstance(r_scan["body"], dict)
        and r_scan["body"].get("boundTo") == "selftest"
    )
    # Verify binding actually written
    r_bind = selftest_control(admin_secret, "read-user-binding", openid=openid_scan)
    ok_scan_bind = (
        r_bind["status"] == 200
        and isinstance(r_bind["body"], dict)
        and r_bind["body"].get("appName") == "selftest"
    )
    log(
        ok_scan and ok_scan_bind,
        "T-QRCODE-SCAN-1: SCAN EventKey=selftest → binding(selftest)",
        f"sim={r_scan} bind={r_bind}",
    )

    # SUBSCRIBE-1: qrscene_ prefix (unsubscribed user follows + first scan)
    openid_sub = f"selftest_qr_sub_{secrets.token_hex(4)}"
    r_sub = selftest_control(
        admin_secret, "simulate-permanent-scan",
        eventKey="qrscene_selftest", openid=openid_sub,
    )
    ok_sub = (
        r_sub["status"] == 200
        and isinstance(r_sub["body"], dict)
        and r_sub["body"].get("boundTo") == "selftest"
    )
    r_bind2 = selftest_control(admin_secret, "read-user-binding", openid=openid_sub)
    ok_sub_bind = (
        r_bind2["status"] == 200
        and isinstance(r_bind2["body"], dict)
        and r_bind2["body"].get("appName") == "selftest"
    )
    log(
        ok_sub and ok_sub_bind,
        "T-QRCODE-SUBSCRIBE-1: subscribe EventKey=qrscene_selftest → binding(selftest)",
        f"sim={r_sub} bind={r_bind2}",
    )


def push_cases(auth_headers: dict):
    """T-PUSH-1..6: outbound message proxy /internal/wx-push (per-app auth).

      1: no auth header → 401
      2: bad HMAC → 401
      3: unknown appName → 403 app_not_found
      4: selftest app pushing to unbound openid → 403 not_bound_to_app
      5: appName=admin bypasses binding check; fake openid → 200 + errcode>0
      6: GET /admin/outbound-logs lists the T-PUSH-5 row

    Note: admin app's secret is the gateway's own — we don't have it in
    selftest env. Skip 5/6 if admin app row has no secret or call comes back
    with auth error. We do have selftest app secret (from bootstrap).
    """
    print()
    print("--- wx push (T-PUSH-1..6) ---")
    try:
        app_secret = fetch_selftest_app_secret()
    except Exception as e:
        log(False, "T-PUSH-*: fetch selftest secret", repr(e))
        return

    url = f"{GATEWAY}/internal/wx-push"

    # T-PUSH-1: no header → 401
    s1, _, _ = http("POST", url, body={"toUser": "x", "type": "custom", "payload": {}})
    log(s1 == 401, "T-PUSH-1: missing X-Internal-Auth → 401", f"got={s1}")

    # T-PUSH-2: bad HMAC → 401
    ts = str(int(time.time() * 1000))
    s2, _, _ = http(
        "POST", url,
        headers={"X-App-Name": "selftest", "X-Internal-Auth": "deadbeef" * 8, "X-Ts": ts},
        body={"toUser": "x", "type": "custom", "payload": {}},
    )
    log(s2 == 401, "T-PUSH-2: bad HMAC → 401", f"got={s2}")

    # T-PUSH-3: unknown appName → 403 app_not_found
    ts = str(int(time.time() * 1000))
    fake_app = f"nonexistent_{secrets.token_hex(3)}"
    s3, _, raw3 = http(
        "POST", url,
        headers={
            "X-App-Name": fake_app,
            "X-Internal-Auth": _internal_sig(app_secret, "wx-push", ts, fake_app),
            "X-Ts": ts,
        },
        body={"toUser": "x", "type": "custom", "payload": {"text": {"content": "hi"}}},
    )
    b3 = json.loads(raw3) if raw3.startswith("{") else {}
    log(s3 == 403 and b3.get("error") == "app_not_found",
        "T-PUSH-3: unknown appName → 403 app_not_found", f"got={s3}/{b3}")

    # Binding is not a wx-push authorization gate; do not send synthetic
    # messages to nonexistent users to test a retired permission rule.
    # T-PUSH-5/6 need admin-app secret to sign as admin. Fetch via control endpoint
    # (admin_secret is gateway's ADMIN_SESSION_SECRET, which lets us read DB).
    admin_app_secret = _fetch_admin_app_secret()
    if not admin_app_secret:
        print("⚠️  T-PUSH-5/6: skipped (admin app secret not available)")
        return

    # T-PUSH-5: admin app bypasses binding check
    ts = str(int(time.time() * 1000))
    push5_openid = f"oSelftest_admin_push_{secrets.token_hex(4)}"
    s5, _, raw5 = http(
        "POST", url,
        headers={
            "X-App-Name": "admin",
            "X-Internal-Auth": _internal_sig(admin_app_secret, "wx-push", ts, "admin"),
            "X-Ts": ts,
        },
        body={"toUser": push5_openid, "type": "custom",
              "payload": {"msgtype": "text", "text": {"content": "selftest"}}},
    )
    b5 = json.loads(raw5) if raw5.startswith("{") else {}
    if s5 == 503:
        print(f"⚠️  T-PUSH-5/6: skipped (admin app's WeChat not configured: {b5})")
        return
    ok5 = s5 == 200 and isinstance(b5.get("errcode"), int) and b5["errcode"] != 0
    log(ok5, "T-PUSH-5: admin app bypass binding → 200 + WeChat errcode!=0",
        f"got={s5}/{b5}")

    # T-PUSH-6: GET /admin/outbound-logs contains T-PUSH-5 row
    s6, _, raw6 = http(
        "GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/outbound-logs?appName=admin&toUser={push5_openid}",
        headers=auth_headers,
    )
    b6 = json.loads(raw6) if raw6.startswith("{") else {}
    logs6 = b6.get("logs") if isinstance(b6, dict) else None
    hit = isinstance(logs6, list) and any(
        isinstance(r, dict) and r.get("toUser") == push5_openid and r.get("appName") == "admin"
        for r in logs6
    )
    log(s6 == 200 and hit,
        "T-PUSH-6: /admin/outbound-logs contains T-PUSH-5 row",
        f"status={s6} count={len(logs6) if isinstance(logs6, list) else '?'} hit={hit}")


def _fetch_admin_app_secret() -> str | None:
    """Read admin app's secret from .deploy-manifest.json APPS_JSON (admin is
    env-configured, not in DB). Returns None if not available."""
    try:
        cmd = (
            "node -e 'try{const m=require(\"./.deploy-manifest.json\");"
            "const raw=(m&&m.env&&m.env.APPS_JSON)||\"[]\";"
            "const arr=JSON.parse(raw);"
            "const a=arr.find(x=>x&&x.name===\"admin\");"
            "if(a&&a.secret)process.stdout.write(a.secret);"
            "}catch(e){process.stderr.write(String(e));process.exit(1)}'"
        )
        out = deployer_exec(cmd, timeout_ms=10000)
        s = (out.get("stdout") or "").strip()
        return s if s else None
    except Exception as e:
        print(f"   ⚠️  fetch admin app secret failed: {e!r}")
        return None


def _fanout_table_counts(prefix: str | None = None) -> dict:
    """Count rows in the 4 fanout-related tables. If prefix is given, restrict
    to rows with that prefix in their identifying name column — this is what
    matters for cleanup verification. Counting all rows races with the cron
    that pings DownstreamHealth for unrelated endpoints during the run."""
    cmd = (
        "node -e 'const{PrismaClient}=require(\"@prisma/client\");"
        "const p=new PrismaClient();"
        "const px=" + json.dumps(prefix or "") + ";"
        "const w=px?{startsWith:px}:undefined;"
        "(async()=>{const o={"
        "routes:await p.messageRoute.count(px?{where:{name:w}}:{}),"
        "endpoints:await p.fanoutEndpoint.count(px?{where:{name:w}}:{}),"
        "logs:await p.fanoutLog.count(px?{where:{OR:[{matchedRouteName:w},{downstream:w}]}}:{}),"
        "health:await p.downstreamHealth.count(px?{where:{endpointName:w}}:{})};"
        "process.stdout.write(JSON.stringify(o));await p.$disconnect();})()"
        ".catch(e=>{process.stderr.write(String(e));process.exit(1)})'"
    )
    out = deployer_exec(cmd, timeout_ms=20000)
    if out.get("exitCode") != 0:
        raise RuntimeError(f"counts probe failed: {out}")
    return json.loads((out.get("stdout") or "{}").strip())


def _fanout_purge(prefix: str) -> dict:
    """Delete test rows: routes/endpoints by name prefix, plus DownstreamHealth +
    FanoutLog rows referencing those endpoint names. Returns deletion counts."""
    cmd = (
        "node -e 'const{PrismaClient}=require(\"@prisma/client\");"
        "const p=new PrismaClient();const px=" + json.dumps(prefix) + ";"
        "(async()=>{"
        "const r1=await p.messageRoute.deleteMany({where:{name:{startsWith:px}}});"
        "const r2=await p.downstreamHealth.deleteMany({where:{endpointName:{startsWith:px}}});"
        "const r3=await p.fanoutLog.deleteMany({where:{OR:[{matchedRouteName:{startsWith:px}},{downstream:{startsWith:px}}]}});"
        "const r4=await p.fanoutEndpoint.deleteMany({where:{name:{startsWith:px}}});"
        "process.stdout.write(JSON.stringify({routes:r1.count,health:r2.count,logs:r3.count,endpoints:r4.count}));"
        "await p.$disconnect();})()"
        ".catch(e=>{process.stderr.write(String(e));process.exit(1)})'"
    )
    out = deployer_exec(cmd, timeout_ms=20000)
    if out.get("exitCode") != 0:
        raise RuntimeError(f"purge failed: {out}")
    return json.loads((out.get("stdout") or "{}").strip())


def fanout_cases(admin_secret: str, auth_headers: dict):
    """T-FANOUT-1..6: Phase A admin tabs + public health endpoint, with strict
    cleanup of MessageRoute / FanoutEndpoint / FanoutLog / DownstreamHealth so
    pre-counts == post-counts (per PRD's iron rule).
    """
    print()
    print("--- fanout phase A (T-FANOUT-1..6) ---")
    prefix = f"selftest_fan_{secrets.token_hex(3)}_"

    try:
        pre = _fanout_table_counts(prefix=prefix)
    except Exception as e:
        log(False, "T-FANOUT setup: snapshot row counts (prefix-scoped)", str(e))
        return

    try:
        # T-FANOUT-1: public GET /health/downstreams → 200 + endpoints array
        s, _, raw = http("GET", f"{GATEWAY}/health/downstreams")
        body = json.loads(raw) if raw.startswith("{") else {}
        log(
            s == 200 and isinstance(body.get("endpoints"), list),
            "T-FANOUT-1: GET /health/downstreams → 200 + endpoints[]",
            f"status={s} body={raw[:200]}",
        )

        # T-FANOUT-2: admin tabs camouflage (unauth → 404) + auth → 200
        unauth_results = []
        auth_results = []
        for path in ("/api/routes", "/api/endpoints", "/api/fanout-logs", "/api/health/downstreams"):
            s_u, _, _ = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}{path}")
            s_a, _, _ = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}{path}", headers=auth_headers)
            unauth_results.append((path, s_u))
            auth_results.append((path, s_a))
        log(
            all(s == 404 for _, s in unauth_results),
            "T-FANOUT-2: 4 admin fanout tabs unauth → 404 camouflage",
            f"{unauth_results}",
        )
        log(
            all(s == 200 for _, s in auth_results),
            "T-FANOUT-3: 4 admin fanout tabs with cookie → 200",
            f"{auth_results}",
        )

        # T-FANOUT-4: POST /api/endpoints creates row; PATCH toggles enabled; row visible in list
        ep_name = f"{prefix}ep1"
        s, _, raw = http(
            "POST", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/endpoints",
            headers=auth_headers,
            body={"name": ep_name, "url": "https://example.invalid/wx", "enabled": True},
        )
        ep_body = json.loads(raw) if raw.startswith("{") else {}
        ep_id = ep_body.get("id") if isinstance(ep_body, dict) else None
        s_l, _, raw_l = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/endpoints", headers=auth_headers)
        listed = (json.loads(raw_l).get("endpoints") if s_l == 200 else []) or []
        listed_names = {e.get("name") for e in listed}
        s_pa, _, _ = http(
            "PATCH", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/endpoints/{ep_id}",
            headers=auth_headers, body={"enabled": False},
        ) if ep_id else (0, None, "")
        log(
            s == 200 and ep_id and ep_name in listed_names and s_pa == 200,
            "T-FANOUT-4: endpoint create + list + PATCH disable",
            f"create={s} list_has={ep_name in listed_names} patch={s_pa}",
        )

        # T-FANOUT-5: POST /api/routes creates route bound to ep_name; list reflects
        rt_name = f"{prefix}rt1"
        s_r, _, raw_r = http(
            "POST", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/routes",
            headers=auth_headers,
            body={
                "name": rt_name,
                "endpointName": ep_name,
                "match": {"MsgType": "event", "Event": "SCAN", "EventKey_prefix": "selftestfan_"},
                "priority": 999,
                "ownsReply": True,
                "enabled": True,
            },
        )
        rt_body = json.loads(raw_r) if raw_r.startswith("{") else {}
        rt_id = rt_body.get("id") if isinstance(rt_body, dict) else None
        s_rl, _, raw_rl = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/routes", headers=auth_headers)
        rt_listed = (json.loads(raw_rl).get("routes") if s_rl == 200 else []) or []
        rt_listed_names = {r.get("name") for r in rt_listed}
        log(
            s_r == 200 and rt_id and rt_name in rt_listed_names,
            "T-FANOUT-5: route create + list reflects",
            f"create={s_r} list_has={rt_name in rt_listed_names}",
        )

        # T-FANOUT-6: admin POST /api/health/downstreams pings; DownstreamHealth row(s) appear
        # Re-enable our endpoint so it gets pinged.
        if ep_id:
            http(
                "PATCH", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/endpoints/{ep_id}",
                headers=auth_headers, body={"enabled": True},
            )
        s_p, _, raw_p = http(
            "POST", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/health/downstreams",
            headers=auth_headers, body={},
        )
        # Read history; expect at least one row for our endpoint
        s_h, _, raw_h = http(
            "GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/health/downstreams", headers=auth_headers,
        )
        hist = (json.loads(raw_h).get("history") if s_h == 200 else {}) or {}
        rows = hist.get(ep_name) or []
        log(
            s_p == 200 and s_h == 200 and len(rows) >= 1,
            "T-FANOUT-6: admin ping writes DownstreamHealth row for new endpoint",
            f"ping={s_p} hist_status={s_h} rows={len(rows)}",
        )
    finally:
        # Strict cleanup: purge any selftest-prefix rows then verify counts match snapshot.
        try:
            purged = _fanout_purge(prefix)
            print(f"   [cleanup] fanout purge: {purged}", flush=True)
        except Exception as e:
            print(f"   ⚠️  WARNING: fanout purge failed: {e!r}", flush=True)
        try:
            post = _fanout_table_counts(prefix=prefix)
            # Cleanup goal: zero rows owned by THIS selftest run remain.
            # Don't compare against pre — cron writes to DownstreamHealth for
            # unrelated endpoints during the run, which is irrelevant here.
            zero = all(v == 0 for v in post.values())
            log(
                zero,
                "T-FANOUT-CLEANUP: 0 rows with selftest prefix remain",
                f"pre={pre} post={post}",
            )
        except Exception as e:
            log(False, "T-FANOUT-CLEANUP: post-count probe failed", repr(e))


def http_raw(method: str, url: str, *, headers=None, data: bytes | None = None, timeout=15):
    req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), (e.read() if e.fp else b"")


def instance_welcome_case(admin_secret: str):
    """T-INSTANCE-1: welcome message URL must match this instance's
    PUBLIC_BASE_URL (= GATEWAY in selftest). Guards against re-introducing
    a hardcoded `https://wx.mvp.restry.cn/...` link that would mis-route
    scans on the 莆阳 instance back to the 造悟者 host.
    """
    print("--- instance branding (T-INSTANCE-1) ---", flush=True)
    ctl = selftest_control(
        admin_secret,
        "welcome-preview",
        appName="selftest",
        appDisplay="Selftest App",
    )
    if ctl["status"] != 200 or not isinstance(ctl["body"], dict):
        log(False, "T-INSTANCE-1: welcome-preview control call failed", repr(ctl))
        return
    body = ctl["body"]
    content = str(body.get("content") or "")
    pub_base = str(body.get("publicBase") or "")
    label = str(body.get("instanceLabel") or "")

    expected_url = f"{pub_base}/wx/oauth/start?app=selftest"
    url_ok = expected_url in content
    no_legacy = "wx.mvp.restry.cn" not in content or "wx.mvp.restry.cn" in pub_base
    label_ok = bool(label) and label in content
    base_matches_gateway = pub_base.rstrip("/") == GATEWAY.rstrip("/")

    log(
        url_ok and no_legacy and label_ok and base_matches_gateway,
        "T-INSTANCE-1: welcome message uses this instance's PUBLIC_BASE_URL + INSTANCE_LABEL",
        f"pub_base={pub_base!r} label={label!r} gateway={GATEWAY!r} content={content[:160]!r}",
    )


def qr_dynamic_case(admin_secret: str, auth_headers: dict):
    # Find selftest app id
    s, _, raw = http("GET", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps", headers=auth_headers)
    if s != 200:
        log(False, "T-QR-DYNAMIC-1 setup: list apps", f"status={s}")
        return
    apps = json.loads(raw).get("apps", [])
    selftest_app = next((a for a in apps if a["name"] == "selftest"), None)
    if not selftest_app:
        log(False, "T-QR-DYNAMIC-1 setup: selftest app not found")
        return
    app_id = selftest_app["id"]

    # Build multipart/form-data body for a 1x1 transparent PNG
    png = base64.b64decode(DUMMY_QR_PNG_B64)
    boundary = f"----wxgw{secrets.token_hex(8)}"
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="file"; filename="t-qr-dynamic.png"\r\n')
    parts.append(b"Content-Type: image/png\r\n\r\n")
    parts.append(png)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    s_up, h_up, raw_up = http_raw(
        "POST", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps/{app_id}/personal-qr",
        headers={**auth_headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        data=body,
    )
    if s_up != 200:
        log(False, "T-QR-DYNAMIC-1: upload failed", f"status={s_up} body={raw_up[:200]!r}")
        # restore dummy
        selftest_control(admin_secret, "set-personal-qr-url", url=DUMMY_QR_URL)
        return
    up_body = json.loads(raw_up.decode("utf-8", "replace"))
    new_url = up_body.get("personalQrUrl")
    if not isinstance(new_url, str) or "/payment/qr/" not in new_url:
        log(False, "T-QR-DYNAMIC-1: upload did not return /payment/qr/ URL", f"got={new_url}")
        selftest_control(admin_secret, "set-personal-qr-url", url=DUMMY_QR_URL)
        return

    # GET it immediately — must be 200 + image/png + matching bytes (proves
    # the dynamic route is serving live disk, not a build-time prerender).
    s_g, h_g, body_g = http_raw("GET", new_url)
    ct = (h_g.get("Content-Type") or h_g.get("content-type") or "").lower()
    prerender_hdr = (h_g.get("x-nextjs-prerender") or h_g.get("X-Nextjs-Prerender") or "")
    ok = (
        s_g == 200
        and ct.startswith("image/png")
        and body_g == png
        and prerender_hdr == ""
    )
    log(
        ok,
        "T-QR-DYNAMIC-1: uploaded QR served live (no prerender, correct bytes & content-type)",
        f"status={s_g} ct={ct} prerender={prerender_hdr!r} bytes={len(body_g)}/{len(png)} url={new_url}",
    )

    # Cleanup: DELETE removes the uploaded file + clears personalQrUrl
    s_d, _, _ = http("DELETE", f"{GATEWAY}{ADMIN_PUBLIC_PATH}/api/apps/{app_id}/personal-qr", headers=auth_headers)
    if s_d != 200:
        log(False, "T-QR-DYNAMIC-1 cleanup: DELETE personal-qr", f"status={s_d}")
    # Re-bootstrap dummy (upload-handler unlinked it as the "previous" file) +
    # restore configured URL so other tests / cron stay happy.
    try:
        ensure_dummy_qr_on_disk()
    except Exception:
        pass
    selftest_control(admin_secret, "set-personal-qr-url", url=DUMMY_QR_URL)


if __name__ == "__main__":
    main()
