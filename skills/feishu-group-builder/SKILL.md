---
name: feishu-group-builder
description: 用 lark-cli 一键建飞书群 — 生成 emoji 头像、bot 建群、发首条 interactive 卡片、pin、可选打入 feed-group 标签。用于给项目/话题/文档配一个专属群作为长期入口。触发词 — "建一个 X 群"、"给这个文档配个群"、"建群并把机器人加进去"、"改群名/描述"。
---

# feishu-group-builder

用 `lark-cli` 端到端建一个飞书群 + 挂文档 + pin 卡片 + 打标签。7 步走完 ≈ 30 秒,全程 bot 建群 bot 当群主便于后续自动化。

## 前置

- 装了 [`lark-cli`](https://github.com/larksuite/lark-cli) 并跑过 `lark-cli auth login`(bot + user 两个身份都要)
- Python 3.10+ + Pillow(`pip install Pillow`),用于 emoji 头像渲染
- 想打 feed-group 标签的话,bot 需要 `im:feed_group_v1:read im:feed_group_v1:write` scope

## 用法

先在**顶部**配好这几个变量(每个用户不一样,只改一次):

```bash
# 你的飞书 open_id(建群时被邀进去的用户),lark-cli contact +search-user --query "<你的名字>" --as user
OWNER_OPEN_ID=ou_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 目标 wiki 空间 + 父节点(想把文档挂在哪个 wiki 节点下)
WIKI_SPACE_ID=xxxxxxxxxxxxxxxxxxx
WIKI_PARENT_NODE_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx

# 可选:feed-group 标签 id(不想打标签就留空,跳过 Step 6)
FEED_GROUP_ID=ofg_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 你的飞书租户前缀(生成文档链接用)
TENANT_SUBDOMAIN=<yourtenant>   # 例:公司叫 acme,填 acme,链接是 acme.feishu.cn/wiki/<token>
```

---

## 完整 7 步

### Step 1 · 生 emoji 头像(0.5 秒)

```bash
SCRIPT=~/.hermes/skills/integration/feishu-group-builder/scripts/emoji_to_avatar.py
mkdir -p /tmp/avatars
python3 $SCRIPT 🚗 /tmp/avatars/<slug>-avatar.png
# 可选参数: --bg "#F5F1E8" (背景色) / --emoji-pct 0.75 (emoji 占比)
```

- **1 个群 1 个 emoji**,禁双 emoji 拼接(64px 渲染会糊)
- Twemoji CDN 首次拉取后缓存到 `~/.hermes/emoji-cache/`,之后离线可用
- 内网没网时:手动放 PNG 到 `/tmp/avatars/<slug>-avatar.png` 跳过本步

### Step 2 · 上传头像换 `image_key`

```bash
cd /tmp/avatars && lark-cli im images create --as bot \
  --data '{"image_type":"avatar"}' \
  --file image=<slug>-avatar.png
# → {"image_key": "v3_xxx..."}
```

⚠️ **必须相对路径** — lark-cli 的 `--file` 参数不支持绝对路径,`cd` 到目录后用文件名。

### Step 3 · 建 wiki 文档并挂到 wiki 树下(可选)

如果这个群要挂一份 wiki 文档,先建文档(2 步:先 Drive 建 docx,再 move 到 wiki):

```bash
# a. 建 Drive doc
cd /tmp && lark-cli docs +create --api-version v2 \
  --doc-format markdown --content "$(cat /tmp/<slug>-doc.md)" \
  --as user --format json 2>&1 > /tmp/.doc.json
OBJ_TOKEN=$(python3 -c "
import json; d=json.load(open('/tmp/.doc.json'))
print(d['data']['document']['document_id'])
")

# b. move 到 wiki 树
lark-cli wiki +move \
  --obj-token "$OBJ_TOKEN" --obj-type docx \
  --target-space-id "$WIKI_SPACE_ID" \
  --target-parent-token "$WIKI_PARENT_NODE_TOKEN" \
  --as user --format json 2>&1 > /tmp/.move.json
WIKI_TOKEN=$(python3 -c "
import json; d=json.load(open('/tmp/.move.json'))
print(d['data']['wiki_token'])
")
```

⚠️ `+move` 返回的 **`wiki_token` ≠ `obj_token`** — 后续卡片链接、群描述里都用**新的** `wiki_token`(URL 格式 `<TENANT>.feishu.cn/wiki/<wiki_token>`)。

### Step 4 · 建群(bot 身份 + set_bot_manager + 邀你)

```bash
IMAGE_KEY="<from Step 2>"
cat > /tmp/<slug>-chat.json <<EOF
{
  "name": "<emoji> <群名>",
  "description": "<一句话说明> · 文档: wiki/${WIKI_TOKEN}",
  "avatar": "$IMAGE_KEY",
  "chat_type": "private",
  "user_id_list": ["$OWNER_OPEN_ID"],
  "edit_permission": "all_members",
  "hide_member_count_setting": "all_members"
}
EOF

cd /tmp && lark-cli im chats create --as bot \
  --params '{"set_bot_manager":true}' \
  --data @<slug>-chat.json --format json 2>&1 > /tmp/.chat.json

CHAT_ID=$(python3 -c "
import json; d=json.load(open('/tmp/.chat.json'))
print(d['data']['chat_id'])
")
[ -n "$CHAT_ID" ] || { echo "❌ chat_id 没拿到,不许继续"; exit 1; }
```

要点:
- `--as bot` — headless 建群只能 bot(user 身份没 `im:chat:create_by_user` scope)
- `set_bot_manager:true` — bot 当 manager,后续能自动 pin/发卡片/改群
- **不传 `owner_id`** — bot 默认当群主,你是被邀成员
- **必须 `--format json` + 立刻解析 + 落文件保存 CHAT_ID**(见 Pitfall #1)
- 群 description 上限 **100 字符**(中文按字符计)

### Step 5 · 发首条 interactive 卡片

```bash
cat > /tmp/<slug>-card.json <<EOF
{
  "schema": "2.0",
  "header": {
    "title": {"tag": "plain_text", "content": "<emoji> <群名>"},
    "subtitle": {"tag": "plain_text", "content": "<一句话状态>"},
    "template": "wathet"
  },
  "body": {
    "elements": [
      {"tag": "markdown", "content": "**一句话**\n<内容>"},
      {"tag": "hr"},
      {"tag": "markdown", "content": "**当前状态**\n- ✅ ...\n- 🟢 ..."},
      {"tag": "hr"},
      {"tag": "markdown", "content": "**📚 文档**\n[<标题>](https://${TENANT_SUBDOMAIN}.feishu.cn/wiki/${WIKI_TOKEN})"}
    ]
  }
}
EOF

cd /tmp && lark-cli im +messages-send \
  --chat-id "$CHAT_ID" --as bot --msg-type interactive \
  --content "$(cat <slug>-card.json)" --format json 2>&1 > /tmp/.msg.json

MSG_ID=$(python3 -c "
import json; d=json.load(open('/tmp/.msg.json'))
print(d['data']['message_id'])
")
```

⚠️ **铁律** — `--content "$(cat file.json)"` 内联,**绝不用 `--content @file`**(会被当字面字符串发)。

### Step 6 · Pin 卡片

```bash
lark-cli im pins create --as bot \
  --data "{\"message_id\":\"$MSG_ID\"}"
```

### Step 7 · 打 feed-group 标签(可选)

```bash
[ -n "$FEED_GROUP_ID" ] && \
  lark-cli im feed.groups batch_add_item --as user \
    --params "{\"feed_group_id\":\"$FEED_GROUP_ID\"}" \
    --data "{\"items\":[{\"feed_id\":\"$CHAT_ID\",\"feed_type\":\"chat\"}]}"
```

⚠️ `feed.groups` 必须 **`--as user`**(bot scope 没有 `im:feed_group_v1:*`)。

### 验证

```bash
lark-cli im chats get --as bot --params "{\"chat_id\":\"$CHAT_ID\"}"
lark-cli im pins list --as bot --params "{\"chat_id\":\"$CHAT_ID\"}"
```

---

## 已知踩坑(必读)

### 1. `chats create` 必须同一次调用就存 `chat_id`,不能"建完再查"

`lark-cli im chats create` **没有幂等**,同名同 desc 同 avatar 重复调 = 建 N 个群。之后想找刚建的:
- `im +chat-list --as bot` 看不到 bot 自己建的群(scope 不在视野)
- `im +chat-search --as user` 不一定立刻索引

**姿势**:`--format json` + 立刻 python 解析 CHAT_ID + 落文件(参见 Step 4 模板)。

### 2. lark-cli 列表 API 的 key **不统一**,凭印象写 `data.items` 会**静默返回空**

| 命令 | 列表 key |
|---|---|
| `im +chat-list` | `data.chats` |
| `im +chat-search` | `data.items` |
| `wiki +node-list` | `data.nodes`(且 stdout 第一行是 `Found N node(s)` banner,要 `raw[raw.find('{'):]` 去掉) |
| `im +messages-search` | `data.messages` |

**防御**:先 `print(list(d.get('data',{}).keys()))` 看 key 名再取。

### 3. lark-cli `--file` / `--data @file` 不支持绝对路径

```
❌ --file image=/Users/x/pics/avatar.png
✅ cd /tmp && cp ~/pics/avatar.png . && --file image=avatar.png
```

### 4. images create 的 `image_type` 必须 `avatar` 而非 `message`

`message` 类型 image_key **不能拿来当群头像**。头像分辨率不能超 4096×4096(1024×1024 稳)。

### 5. `set_bot_manager:true` 只在 bot 当群主时生效

传了 `owner_id` 指定别人当群主 → bot 只是普通成员,`set_bot_manager` 失效,要单独设 manager。

### 6. bot 建群时不能邀"app 视野外"用户(外租户 / 外部联系人)—— code 232043

```json
{"code": 232043, "msg": "bot is invisible to user ids: [...]"}
```

**修法**:两步走。Step 4 建群时 `user_id_list` 只放内部用户(通常就是你自己),之后用 **user 身份**补加外部:

```bash
lark-cli im chat.members create \
  --params "{\"chat_id\":\"$CHAT_ID\",\"member_id_type\":\"open_id\"}" \
  --data '{"id_list":["ou_<外部用户>"]}' --as user
```

**判定** — `lark-cli contact +search-user --query "<name>" --as user` 拿得到 ou_id 但 bot 拿不到 = 外部用户。

### 7. 群 description 最大 100 字符(含中文按字符计)

超了报 `--description exceeds the maximum of 100 characters`。文档链接缩写成 `wiki/<token>` 省空间。

### 8. feed group 名称短纯英文会被拒(code 230001)

```
❌ "Fries"            → param is invalid
✅ "🍟 Fries" / "薯条" / "fries-group"
```

短英文名加 emoji 前缀绕过。

### 9. `wiki +node-delete` 用 raw token 常报 not found,改用 URL 形式

```bash
# ❌ 常报 [131005] not found
lark-cli wiki +node-delete --node-token EmlC... --obj-type docx --as user --yes

# ✅ URL 形式让 CLI 自动 infer
lark-cli wiki +node-delete --node-token "https://<tenant>.feishu.cn/wiki/EmlC..." --as user --yes
```

### 10. 飞书不支持解散群 — 用"改名前缀 + 从标签移除"废弃

lark-cli 没有 chat disband API,bot 也 leave 不了(它是群主)。废弃姿势:

```bash
# 1. 改群名前缀标废弃
lark-cli im +chat-update --as bot --chat-id "$OLD_CHAT" \
  --name "[废弃] <原名>" --description "已合并到 X 群"

# 2. 从 feed group 标签移除
lark-cli im feed.groups batch_remove_item --as user \
  --params "{\"feed_group_id\":\"$FEED_GROUP_ID\"}" \
  --data "{\"items\":[{\"feed_id\":\"$OLD_CHAT\",\"feed_type\":\"chat\"}]}"

# 3. wiki 节点删掉(URL 形式)
lark-cli wiki +node-delete --node-token "<wiki URL>" --as user --yes
```

### 11. 改群名/描述前必读源头材料(禁只看群当前名字推测)

已存在的群名/描述 ≠ ground truth,可能是上次建群时的错联想或过期快照。**改之前先读**项目的 README / 最近 git commit / UI 上真实显示的字符串(placeholder / `<title>` / metadata),三处对齐再动手。groups description 里**优先放"是什么" + 仓库源 + 本地路径**,不放"进度状态"(状态会过时)。

### 12. 建群前先 dedup 查重(避免二次创建)

```bash
# 查 feed-group 里有没有同名群
lark-cli im +feed-group-list-item --feed-group-id "$FEED_GROUP_ID" \
  --as user --format json > /tmp/.fries.json 2>&1
python3 -c "
import json; raw=open('/tmp/.fries.json').read()
d=json.loads(raw[raw.find('{'):])
for it in d.get('data',{}).get('items',[]):
    n=it.get('chat_name','')
    if '<你要建的关键词>' in n.lower():
        print('HIT:', n, it.get('feed_id'))
"

# 查 wiki 父节点下有没有同名文档
lark-cli wiki +node-list --space-id "$WIKI_SPACE_ID" \
  --parent-node-token "$WIKI_PARENT_NODE_TOKEN" \
  --as user --format json > /tmp/.wiki.json 2>&1
```

两处都空命中 → 安全建。任一命中 → 复用已有 chat_id / node_token,不要重复建。

---

## 批量建群

如果一次建 N 个群(每个 1 张文档配 1 个群),用 `scripts/build_topic_rooms.py`:

```bash
python3 ~/.hermes/skills/integration/feishu-group-builder/scripts/build_topic_rooms.py
```

它把 Step 1-7 打成 idempotent 流水线,状态写 `/tmp/topic-rooms-state.json`,断点续跑 — Step 4 失败时重跑不会建重复群(每步先看 state 里是否已完成)。改 `TOPICS` 表 + 顶部几个常量即可。

后台跑,别 foreground:
```
terminal(background=True, notify_on_complete=True, timeout=1200)
```

---

## 附:占位符速查

改用本 skill 时你要填的:

| 占位符 | 从哪拿 |
|---|---|
| `<slug>` | 你的项目/话题 slug,例 `myproject`(小写连字符) |
| `<emoji>` | 一个能表达项目主题的 emoji |
| `$OWNER_OPEN_ID` | `lark-cli contact +search-user --query "<你的名字>" --as user` |
| `$WIKI_SPACE_ID` + `$WIKI_PARENT_NODE_TOKEN` | 飞书 wiki 界面 URL 复制 + `lark-cli wiki +node-list --space-id X` 找 |
| `$FEED_GROUP_ID` | `lark-cli im +feed-group-list --as user` |
| `$TENANT_SUBDOMAIN` | 你飞书租户 URL 前缀,例 `acme.feishu.cn` 就填 `acme` |

## 支持文件

- `scripts/emoji_to_avatar.py` — emoji → 1024×1024 PNG(Pillow + Twemoji),零 LLM 依赖
- `scripts/build_topic_rooms.py` — 批量建群 idempotent orchestrator 模板
