#!/usr/bin/env python3
"""Build N Feishu topic rooms from a TOPICS table — idempotent batch.

Drop-in template. Edit the TOPICS table + the two constants (DADDY_OPEN_ID,
FRIES_GROUP_ID) for your case, drop avatar PNGs into AVATAR_SRC_DIR named
`{slug}-avatar.png`, run.

For each room: upload avatar → create chat (bot identity, set_bot_manager,
invite Daddy) → send intro interactive card with doc link → pin → add to feed
group. Per-room progress saved to STATE_FILE so re-runs resume cleanly.

Run with `python3 build_topic_rooms.py`; do NOT use execute_code (blocked on
secure profiles). Background recommended (terminal background=True,
notify_on_complete=True, timeout=1200).
"""
import json
import subprocess
import time
from pathlib import Path

# ===== EDIT THESE =====
DADDY_OPEN_ID = "ou_XXX_open_id_of_human_to_invite_XXX"
FRIES_GROUP_ID = "ofg_XXX_feed_group_id_for_tagging_XXX"  # create once with lark-cli im feed.groups create
AVATAR_SRC_DIR = Path.home() / ".hermes/img_out/topic-rooms"  # where {slug}-avatar.png lives
STATE_FILE = Path("/tmp/topic-rooms-state.json")
WORKDIR = Path("/tmp")  # lark-cli requires relative paths for --file / --data @file

# (slug, emoji, name, oneline_desc, status_bullets, wiki_node_token)
TOPICS = [
    ("wingman", "🛩️", "wingman 僚机",
     "监控飞书话题消息、推送主会话的元工程项目",
     ["✅ daemon 在 Fries launchd 上跑（KeepAlive）",
      "🟢 cockpit 已并入 wingman，统一一处",
      "📂 ~/projects/wingman/"],
     "HPHZwXyQbi5qEBkFk0lcgp6vnph"),
    # ... add more rows
]
# ===== END EDIT =====


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKDIR), **kw)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


EMOJI_SCRIPT = Path.home() / ".hermes/skills/integration/feishu-group-builder/scripts/emoji_to_avatar.py"


def ensure_avatar(slug, emoji):
    """If avatar PNG missing, render from emoji. Idempotent — returns target path."""
    target = AVATAR_SRC_DIR / f"{slug}-avatar.png"
    if target.exists() and target.stat().st_size > 1000:
        return target
    AVATAR_SRC_DIR.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["python3", str(EMOJI_SCRIPT), emoji, str(target)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"emoji_to_avatar failed for {slug}/{emoji}: {r.stderr[:300]}")
    return target


def upload_avatar(slug):
    src = AVATAR_SRC_DIR / f"{slug}-avatar.png"
    if not src.exists():
        raise RuntimeError(f"missing avatar {src} (run ensure_avatar first)")
    tmp = WORKDIR / f"{slug}-avatar.png"
    if not tmp.exists():
        tmp.write_bytes(src.read_bytes())
    r = run(["lark-cli", "im", "images", "create", "--as", "bot",
             "--data", '{"image_type":"avatar"}',
             "--file", f"image={tmp.name}"])
    d = json.loads(r.stdout)
    if d.get("code") != 0:
        raise RuntimeError(f"upload failed: {r.stdout[:300]}")
    return d["data"]["image_key"]


def create_chat(slug, emoji, name, desc, image_key, wiki_node_token):
    body = {
        "name": f"{emoji} {name}",
        "description": f"{desc} · 话题记忆 wiki/{wiki_node_token}",
        "avatar": image_key,
        "chat_type": "private",
        "user_id_list": [DADDY_OPEN_ID],
        "edit_permission": "all_members",
        "hide_member_count_setting": "all_members",
    }
    body_file = WORKDIR / f"{slug}-chat.json"
    body_file.write_text(json.dumps(body, ensure_ascii=False))
    r = run(["lark-cli", "im", "chats", "create", "--as", "bot",
             "--params", '{"set_bot_manager":true}',
             "--data", f"@{body_file.name}"])
    d = json.loads(r.stdout)
    if d.get("code") != 0:
        raise RuntimeError(f"create chat failed: {r.stdout[:300]}")
    return d["data"]["chat_id"]


def build_card(emoji, name, desc, status_bullets, wiki_node_token):
    status_md = "**当前状态**\n" + "\n".join(f"- {b}" for b in status_bullets)
    return {
        "schema": "2.0",
        "header": {
            "title": {"tag": "plain_text", "content": f"{emoji} {name}"},
            "subtitle": {"tag": "plain_text", "content": desc},
            "template": "wathet",
        },
        "body": {
            "elements": [
                {"tag": "markdown", "content": f"**一句话**\n{desc}"},
                {"tag": "hr"},
                {"tag": "markdown", "content": status_md},
                {"tag": "hr"},
                {"tag": "markdown",
                 "content": f"**📚 话题记忆文档**（权威源）\n[{name} — 话题记忆]"
                            f"(https://lewayteam.feishu.cn/wiki/{wiki_node_token})"},
                {"tag": "hr"},
                {"tag": "markdown",
                 "content": "<font color='grey'>本群用法：项目讨论 / 派工 / 复盘集中在此。"
                            "文档已 pin 顶部。</font>"},
            ]
        },
    }


def send_card(slug, chat_id, card):
    card_file = WORKDIR / f"{slug}-card.json"
    card_file.write_text(json.dumps(card, ensure_ascii=False))
    # Use bash -c so $(cat ...) inline interpolation works — lark-cli requires
    # this for interactive cards (--content @file is treated as a literal string).
    r = run(["bash", "-c",
             f'lark-cli im +messages-send --chat-id {chat_id} --as bot '
             f'--msg-type interactive --content "$(cat {card_file.name})"'])
    d = json.loads(r.stdout)
    if not d.get("ok", True) and d.get("code") not in (0, None):
        raise RuntimeError(f"send card failed: {r.stdout[:300]}")
    return d.get("data", {}).get("message_id") or d.get("message_id")


def pin_message(message_id):
    r = run(["lark-cli", "im", "pins", "create", "--as", "bot",
             "--data", json.dumps({"message_id": message_id})])
    d = json.loads(r.stdout)
    if d.get("code") != 0:
        raise RuntimeError(f"pin failed: {r.stdout[:300]}")


def tag_chat(chat_id):
    r = run(["lark-cli", "im", "feed.groups", "batch_add_item", "--as", "user",
             "--params", json.dumps({"feed_group_id": FRIES_GROUP_ID}),
             "--data", json.dumps({"items": [{"feed_id": chat_id, "feed_type": "chat"}]})])
    d = json.loads(r.stdout)
    if d.get("code") != 0:
        raise RuntimeError(f"tag failed: {r.stdout[:300]}")


def main():
    state = load_state()
    for slug, emoji, name, desc, status, wiki in TOPICS:
        if state.get(slug, {}).get("done"):
            print(f"  SKIP {slug:18s} already done")
            continue
        s = state.setdefault(slug, {})
        try:
            print(f"  GO   {slug:18s} starting...", flush=True)
            if "image_key" not in s:
                ensure_avatar(slug, emoji)  # render emoji → PNG if missing
                s["image_key"] = upload_avatar(slug); save_state(state)
            if "chat_id" not in s:
                s["chat_id"] = create_chat(slug, emoji, name, desc, s["image_key"], wiki)
                save_state(state)
            if "message_id" not in s:
                card = build_card(emoji, name, desc, status, wiki)
                s["message_id"] = send_card(slug, s["chat_id"], card); save_state(state)
            if not s.get("pinned"):
                pin_message(s["message_id"]); s["pinned"] = True; save_state(state)
            if not s.get("tagged"):
                tag_chat(s["chat_id"]); s["tagged"] = True; save_state(state)
            s["done"] = True; save_state(state)
            print(f"  OK   {slug:18s} chat={s['chat_id']}", flush=True)
        except Exception as e:
            print(f"  FAIL {slug:18s} {e}", flush=True)
            save_state(state)
        time.sleep(0.5)
    done = sum(1 for v in state.values() if v.get("done"))
    print(f"\n=== {done}/{len(TOPICS)} rooms built ===")


if __name__ == "__main__":
    main()
