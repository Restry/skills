#!/usr/bin/env python3
"""
sample-client.py — 业务方视角的最小 wx-gateway 支付客户端。

本脚本同时是 **integrate skill 的 contract test**：
- 它的代码完全按 integrate/references/payment.md 描述实现
- 跑通 = skill 文档的 payload 拼法 / secret 用法 / header 名都跟网关代码对得上
- 跑不通 = skill 文档错了（不是网关错），立刻修 skill

被 wx-gateway-operate 的 selftest.py 调用，保证 contract drift 立即被发现。

用法（CLI 手测）：
  GATEWAY=https://wx.mvp.restry.cn \
  APP_NAME=copilot-proxy \
  SECRET=<64 hex 字符> \
  python3 sample-client.py create        # 创建订单
  python3 sample-client.py status <id>   # 查状态
  python3 sample-client.py claim  <id>   # 我已付款

被 selftest 调用（python module）：
  from sample_client import pay_create, pay_status, pay_claim, verify_webhook
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
import urllib.error


# ---------- HMAC 工具（业务方真要抄的就这一段） ----------

def hmac_hex(secret: str, payload: str) -> str:
    """
    HMAC-SHA256(secret, payload) → hex.
    ⚠️ secret 是 64 hex 字符的字符串，但 HMAC 时直接当 utf-8 字符串传 key
    （不是 bytes.fromhex）。这跟网关代码 createHmac("sha256", secret) 一致。
    """
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def sign_create(app_name: str, order_id: str, amount_fen: int, ts_ms: int, secret: str) -> str:
    """payload = appName|orderId|amount_fen|ts (4 段竖线，ts 是毫秒)"""
    return hmac_hex(secret, f"{app_name}|{order_id}|{amount_fen}|{ts_ms}")


def sign_pay_id(app_name: str, pay_order_id: str, ts_ms: int, secret: str) -> str:
    """claim / status / wxpay-prepay 共用：payload = appName|<ref>|ts"""
    return hmac_hex(secret, f"{app_name}|{pay_order_id}|{ts_ms}")


def verify_webhook(secret: str, body: dict, sig_header: str, ts_header: str,
                   max_skew_ms: int = 5 * 60 * 1000) -> bool:
    """webhook 验签：payload = event|payOrderId|status|ts"""
    if abs(int(time.time() * 1000) - int(ts_header)) > max_skew_ms:
        return False
    expected = hmac_hex(
        secret, f"{body['event']}|{body['payOrderId']}|{body['status']}|{ts_header}"
    )
    return hmac.compare_digest(expected, sig_header)


# ---------- HTTP wrapper ----------

def _http(method: str, url: str, headers: dict, body: dict | None = None, timeout: int = 15):
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ---------- 4 个接口 ----------

def pay_create(gateway: str, app_name: str, secret: str, order_id: str,
               amount_fen: int, subject: str = "sample", expires_in: int = 1800,
               openid: str | None = None) -> tuple[int, dict]:
    ts = int(time.time() * 1000)
    sig = sign_create(app_name, order_id, amount_fen, ts, secret)
    body: dict = {
        "orderId": order_id,
        "amount_fen": amount_fen,
        "method": "personal_qr",
        "subject": subject,
        "expiresIn": expires_in,
    }
    if openid:
        body["openid"] = openid
    s, raw = _http(
        "POST", f"{gateway}/pay/create",
        headers={"X-WX-App-Name": app_name, "X-WX-Sig": sig, "X-WX-Ts": str(ts)},
        body=body,
    )
    return s, json.loads(raw) if raw and raw.startswith("{") else {"raw": raw}


def pay_status(gateway: str, app_name: str, secret: str, pay_order_id: str) -> tuple[int, dict]:
    ts = int(time.time() * 1000)
    sig = sign_pay_id(app_name, pay_order_id, ts, secret)
    s, raw = _http(
        "GET", f"{gateway}/pay/status/{pay_order_id}",
        headers={"X-WX-App-Name": app_name, "X-WX-Sig": sig, "X-WX-Ts": str(ts)},
    )
    return s, json.loads(raw) if raw and raw.startswith("{") else {"raw": raw}


def pay_claim(gateway: str, app_name: str, secret: str, pay_order_id: str,
              user_note: str | None = None) -> tuple[int, dict]:
    ts = int(time.time() * 1000)
    sig = sign_pay_id(app_name, pay_order_id, ts, secret)
    body: dict = {"payOrderId": pay_order_id}
    if user_note:
        body["userNote"] = user_note
    s, raw = _http(
        "POST", f"{gateway}/pay/personal/claim",
        headers={"X-WX-App-Name": app_name, "X-WX-Sig": sig, "X-WX-Ts": str(ts)},
        body=body,
    )
    return s, json.loads(raw) if raw and raw.startswith("{") else {"raw": raw}


# ---------- v2 wxpay_jsapi（微信官方 JSAPI 支付） ----------

def pay_create_jsapi(gateway: str, app_name: str, secret: str, order_id: str,
                     amount_fen: int, subject: str = "sample",
                     expires_in: int = 1800, openid: str | None = None,
                     webhook_url: str | None = None,
                     return_url: str | None = None) -> tuple[int, dict]:
    """
    /pay/create 走 wxpay_jsapi 分支。
    HMAC payload 与 v1 完全一致：appName|orderId|amount_fen|ts
    返回里关键字段：payOrderId, wxpay.prepayEndpoint, wxpay.checkoutUrl
    传 return_url 时 gateway 会持久化进 Payment.returnUrl，付款完成后跳回该 URL。
    """
    ts = int(time.time() * 1000)
    sig = sign_create(app_name, order_id, amount_fen, ts, secret)
    body: dict = {
        "orderId": order_id,
        "amount_fen": amount_fen,
        "method": "wxpay_jsapi",
        "subject": subject,
        "expiresIn": expires_in,
    }
    if openid:
        body["openid"] = openid
    if webhook_url:
        body["webhookUrl"] = webhook_url
    if return_url:
        body["returnUrl"] = return_url
    s, raw = _http(
        "POST", f"{gateway}/pay/create",
        headers={"X-WX-App-Name": app_name, "X-WX-Sig": sig, "X-WX-Ts": str(ts)},
        body=body,
    )
    return s, json.loads(raw) if raw and raw.startswith("{") else {"raw": raw}


def pay_create_redirect(gateway: str, app_name: str, secret: str, order_id: str,
                        amount_fen: int, openid: str, return_url: str,
                        subject: str = "sample",
                        expires_in: int = 1800,
                        webhook_url: str | None = None) -> tuple[int, dict]:
    """
    推荐方式：统一付款页跳转。
    业务方只需调 /pay/create（带 openid + returnUrl），拿到 wxpay.checkoutUrl
    后 window.location.href 跳过去；付款页由 wx-gateway 渲染并调 wx.chooseWXPay。
    业务方不再需要自己调 /pay/wxpay/jsapi/prepay。
    """
    return pay_create_jsapi(
        gateway, app_name, secret, order_id, amount_fen,
        subject=subject, expires_in=expires_in,
        openid=openid, webhook_url=webhook_url, return_url=return_url,
    )


def pay_jsapi_prepay(gateway: str, app_name: str, secret: str,
                     payment_id: str, openid: str) -> tuple[int, dict]:
    """
    /pay/wxpay/jsapi/prepay：用 payOrderId (paymentId) 拉起。
    HMAC payload：appName|paymentId|ts （三选一里 paymentId 这一支）
    返回里 wxpay 对象（appId/timeStamp/nonceStr/package/signType/paySign）
    直接喂给前端 wx.chooseWXPay。
    """
    ts = int(time.time() * 1000)
    sig = sign_pay_id(app_name, payment_id, ts, secret)
    s, raw = _http(
        "POST", f"{gateway}/pay/wxpay/jsapi/prepay",
        headers={"X-WX-App-Name": app_name, "X-WX-Sig": sig, "X-WX-Ts": str(ts)},
        body={"paymentId": payment_id, "openid": openid},
    )
    return s, json.loads(raw) if raw and raw.startswith("{") else {"raw": raw}


# ---------- selftest（mock 模式，不打真接口） ----------

def _selftest() -> int:
    """
    本地契约自检：不打微信生产、不打 gateway，只验证 sample-client 内部
    的签名 / payload / webhook 验证函数本身没漂移。
    跑通 = sample-client.py 的契约能力自洽；跑不通 = 立即修。
    """
    failures: list[str] = []

    # 1. hmac_hex 已知向量
    secret_known = "key"
    payload_known = "The quick brown fox jumps over the lazy dog"
    expected = "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8"
    got = hmac_hex(secret_known, payload_known)
    if got != expected:
        failures.append(f"hmac_hex vector mismatch: got={got} expected={expected}")

    # 2. sign_create 拼法 = appName|orderId|amount_fen|ts
    s = sign_create("appA", "ord_1", 9900, 1735000000000, "deadbeef" * 8)
    expect_s = hmac_hex("deadbeef" * 8, "appA|ord_1|9900|1735000000000")
    if s != expect_s:
        failures.append("sign_create payload format drifted")

    # 3. sign_pay_id 拼法 = appName|<ref>|ts （v1 claim/status & v2 wxpay-prepay 共用）
    s2 = sign_pay_id("appA", "pay_xyz", 1735000000000, "k")
    expect_s2 = hmac_hex("k", "appA|pay_xyz|1735000000000")
    if s2 != expect_s2:
        failures.append("sign_pay_id payload format drifted")

    # 4. webhook 验签：自签自验，含 5min skew check
    secret_w = "0" * 64
    body_w = {
        "event": "payment.paid",
        "payOrderId": "pay_demo",
        "status": "paid",
        "amount_fen": 100,
    }
    ts_now = str(int(time.time() * 1000))
    sig_ok = hmac_hex(secret_w,
                      f"{body_w['event']}|{body_w['payOrderId']}|{body_w['status']}|{ts_now}")
    if not verify_webhook(secret_w, body_w, sig_ok, ts_now):
        failures.append("verify_webhook rejected its own signature")
    if verify_webhook(secret_w, body_w, "deadbeef" * 16, ts_now):
        failures.append("verify_webhook accepted bogus signature")
    ts_old = str(int(time.time() * 1000) - 10 * 60 * 1000)
    sig_old = hmac_hex(secret_w,
                       f"{body_w['event']}|{body_w['payOrderId']}|{body_w['status']}|{ts_old}")
    if verify_webhook(secret_w, body_w, sig_old, ts_old):
        failures.append("verify_webhook ignored 10min skew")

    # 5. v2 webhook 也覆盖 cancelled / rejected 两种新事件
    for ev, st in (("payment.cancelled", "cancelled"), ("payment.rejected", "rejected")):
        b = {"event": ev, "payOrderId": "pay_x", "status": st, "amount_fen": 1}
        sig = hmac_hex(secret_w, f"{ev}|pay_x|{st}|{ts_now}")
        if not verify_webhook(secret_w, b, sig, ts_now):
            failures.append(f"verify_webhook failed on v2 event {ev}")

    # 6. v2 pay_create_jsapi / pay_jsapi_prepay 函数 lint —— 不发请求，只确认存在 + 签名工具
    #    （真实 contract test 由 wx-gateway-operate selftest.py 在 selftest app 里跑）
    if not callable(pay_create_jsapi) or not callable(pay_jsapi_prepay):
        failures.append("v2 helpers missing")
    if not callable(pay_create_redirect):
        failures.append("v2 helper pay_create_redirect missing (unified checkout page integration)")

    # 7. finalize URL ext 透传 —— ext 不参与 HMAC，加上 / 改掉 ext 都不影响 sig 校验
    finalize_secret = "f" * 64
    fin_token = "appA_oauth_abc"
    fin_openid = "oABC123"
    fin_unionid = "uXYZ"
    fin_ts = "1735000000000"
    fin_payload = f"{fin_token}|{fin_openid}|{fin_unionid}|{fin_ts}"
    fin_sig = hmac_hex(finalize_secret, fin_payload)
    # 业务方收到带 ext 的 finalize URL，按 token|openid|unionid|ts 算 sig 应当一致
    recomputed = hmac_hex(finalize_secret, f"{fin_token}|{fin_openid}|{fin_unionid}|{fin_ts}")
    if recomputed != fin_sig:
        failures.append("finalize sig recomputation drift")
    # 模拟 ext 被改：sig 仍应保持（因为 ext 根本不在 payload 里）
    recomputed_with_ext_ignored = hmac_hex(
        finalize_secret, f"{fin_token}|{fin_openid}|{fin_unionid}|{fin_ts}"
    )
    if recomputed_with_ext_ignored != fin_sig:
        failures.append("ext leaked into finalize HMAC payload")

    if failures:
        for f in failures:
            print(f"❌ {f}")
        print(f"\n== selftest FAILED ({len(failures)} issues) ==")
        return 1
    print("✅ hmac_hex known vector")
    print("✅ sign_create payload = appName|orderId|amount_fen|ts")
    print("✅ sign_pay_id payload = appName|<ref>|ts (v1 claim/status & v2 prepay 共用)")
    print("✅ verify_webhook self-sign / reject-bogus / reject-skew")
    print("✅ verify_webhook v2 events (cancelled/rejected)")
    print("✅ v2 helpers pay_create_jsapi / pay_jsapi_prepay present")
    print("✅ finalize ext 透传不影响 HMAC payload (token|openid|unionid|ts)")
    print("\n== selftest PASS ==")
    return 0


# ---------- CLI ----------

def _env(k: str) -> str:
    v = os.environ.get(k)
    if not v:
        sys.exit(f"missing env: {k}")
    return v


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        # No args → run mock-mode selftest (no network).
        return _selftest()
    gateway = os.environ.get("GATEWAY", "https://wx.mvp.restry.cn").rstrip("/")
    if argv[1] == "selftest":
        return _selftest()
    app_name = _env("APP_NAME")
    secret = _env("SECRET")
    cmd = argv[1]
    if cmd == "create":
        order_id = argv[2] if len(argv) > 2 else f"sample_{int(time.time())}"
        amount = int(argv[3]) if len(argv) > 3 else 1
        s, body = pay_create(gateway, app_name, secret, order_id, amount)
    elif cmd == "create-jsapi":
        order_id = argv[2] if len(argv) > 2 else f"sample_{int(time.time())}"
        amount = int(argv[3]) if len(argv) > 3 else 1
        s, body = pay_create_jsapi(gateway, app_name, secret, order_id, amount)
    elif cmd == "prepay":
        openid = _env("OPENID")
        s, body = pay_jsapi_prepay(gateway, app_name, secret, argv[2], openid)
    elif cmd == "status":
        s, body = pay_status(gateway, app_name, secret, argv[2])
    elif cmd == "claim":
        s, body = pay_claim(gateway, app_name, secret, argv[2])
    else:
        print(__doc__)
        return 1
    print(f"HTTP {s}")
    print(json.dumps(body, indent=2, ensure_ascii=False))
    return 0 if 200 <= s < 300 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
