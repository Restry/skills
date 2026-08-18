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

## Step 0 · 源材料确认(必读,先做)

用户说"根据 X 文档建群"时,X **必须真实存在且可读**才进 Step 1。飞书通知一发即不可撤;凭空建群 + 后续再填内容 = 二次打扰。找源、判歧义、拿不到就问 —— **绝不脑补**。

### 0.1 三处并搜找源

```bash
# a. 飞书云文档全库搜(user 身份)
lark-cli drive +search --query "<关键词>" --page-size 20 --as user --format json 2>&1 \
  | python3 -c "import json,sys; raw=sys.stdin.read(); d=json.loads(raw[raw.find('{'):])
for r in d.get('data',{}).get('results',[]):
    print(r['result_meta']['doc_types'], r['result_meta']['token'], r['title_highlighted'])"

# b. wiki 空间树扫父节点(用 +node-list,不是 +space-node-list——后者是错命令)
lark-cli wiki +node-list --space-id "$WIKI_SPACE_ID" --page-size 50 --as user

# c. 会话历史 — 用户可能之前粘过 URL/token,session_search(query="<项目名>")
```

⚠️ **flag 陷阱** — `lark-cli drive` 搜索用 `+search --query "..."`,**不是** `+files-list`(不存在),**不是** `--params '{"search_key":...}'`(unknown_flag)。

### 0.2 命中空文档 = 等同没材料

`drive +search` 找到一个同名 wiki 但 fetch 出来 body 只有 `# 标题` → 用户刚占了个坑位准备后续填。**等同于没材料**,不能拿它当\"源\"。

### 0.3 名字碰撞歧义(portfolio 里必查)

新项目名跟已有项目**同音/近似** → 建错群/挂错文档不可撤。判定:

```bash
# 已知项目清单里查
grep -i "<近似关键词>" ~/.hermes/feishu-groups.json
# 过往会话查
# session_search(query="<项目名>", limit=5)
```

任一命中 → clarify 一次问用户是哪个。例:"Park Horizon"(新)vs "PackHorizon"(旧 SaaS `ph`)—— SLD 差 1 字母,web 搜出来完全不同域也可能撞车。

### 0.4 找不到就问一次,不再追

3 处都空 + 名字无歧义 + 用户在场 → **单次 clarify**,给三选一:

1. 把文档 PDF/截图/URL 发到当前 DM
2. 告诉我 wiki token / 别的可访问路径
3. 口述关键信息我起草你审

**10 分钟没回响不追第二次** —— 输出简短待机说明("已就位,缺 X 材料,回来告诉我 3 选 1"),停手等。

用户不在场(cron/派工场景)→ 直接退出报"缺源材料",禁建群。

**铁律 — 绝不用 web 公开信息 / 旧 session 讨论碎片脑补源材料**(股权条款、项目定位、合作方名单等)来建群 = 编造。

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

**两种姿势,按内容准备程度选**:

#### 3A · 一步建空 wiki docx,后续用 `docs +update append` 填内容(**推荐**)

内容还在整理 / 想分段追加 / 想让文档 native 挂在 wiki 树里 → 用这个:

```bash
lark-cli wiki nodes create \
  --params "{\"space_id\":\"$WIKI_SPACE_ID\"}" \
  --data "{\"parent_node_token\":\"$WIKI_PARENT_NODE_TOKEN\",\"node_type\":\"origin\",\"obj_type\":\"docx\",\"title\":\"<emoji> <标题>\"}" \
  --as user --format json 2>&1 > /tmp/.wiki-create.json

# 一次拿齐 3 个 token
python3 <<'PY' > /tmp/.<slug>-tokens.env
import json
d = json.load(open('/tmp/.wiki-create.json'))
node = d['data']['node']
print(f"WIKI_TOKEN={node['node_token']}")     # wiki URL 用它
print(f"OBJ_TOKEN={node['obj_token']}")       # docs +update 用它
print(f"WIKI_URL=https://<TENANT>.feishu.cn/wiki/{node['node_token']}")
PY
source /tmp/.<slug>-tokens.env

# 然后 append markdown(注意:必须相对路径,见 Pitfall #3)
cd /tmp && lark-cli docs +update \
  --doc "$OBJ_TOKEN" --command append --doc-format markdown \
  --content @./<slug>-wiki.md \
  --as user --format json
```

优点:一次 API 调用建成 wiki 节点,不用后续 `+move`,`node_token` 和 `obj_token` 同一响应拿齐。追加式写文档也天然支持 rev 增量。

#### 3B · 已有完整 markdown → Drive `+create` + `wiki +move`(两步)

一次性把完整 markdown 塞进新 Drive doc 再挂 wiki:

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
      {"tag": "markdown", "content": "**📚 文档**\\n[<标题>](https://${TENANT_SUBDOMAIN}.feishu.cn/wiki/${WIKI_TOKEN})"},
      {"tag": "hr"},
      {
        "tag": "button",
        "text": {"tag": "plain_text", "content": "📄 打开完整档案"},
        "type": "primary_filled",
        "width": "default",
        "size": "medium",
        "behaviors": [
          {"type": "open_url", "default_url": "https://${TENANT_SUBDOMAIN}.feishu.cn/wiki/${WIKI_TOKEN}"}
        ]
      }
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
[ -n "$MSG_ID" ] || { echo "❌ message_id 没拿到，禁止继续 Pin"; exit 1; }
```

⚠️ **铁律** — `--content "$(cat file.json)"` 内联,**绝不用 `--content @file`**(会被当字面字符串发)。多步脚本必须启用 `set -e`，或把发送与 Pin 放进同一段 Python 控制流；发送脚本出现 SyntaxError/API error 后不得继续用空 `MSG_ID` 调 Pin。

### Step 6 · Pin 卡片

```bash
lark-cli im pins create --as bot \
  --data "{\"message_id\":\"$MSG_ID\"}"
```

⚠️ **子命令名易记错** — pin 是 **`im pins create`**（`pins` 是资源，`create` 是动作）。**不是**：
- ❌ `im +messages-pin` — 报 `unknown subcommand`（`+messages-pin` 根本不存在）
- ❌ `im messages pin` — 也不存在

规律：lark-cli 里 "对某消息做资源类操作"（pin / react / flag）都走 **`im <resource>s create`** 而不是消息子命令。

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

### 2. lark-cli 列表 API 的 key **不统一**，凭印象写 `data.items` 会**静默返回空**；写请求 body 也一样

**返回 key 表**：

| 命令 | 列表 key |
|---|---|
| `im +chat-list` | `data.chats` |
| `im +chat-search` | `data.items` |
| `wiki +node-list` | `data.nodes`(且 stdout 第一行是 `Found N node(s)` banner,要 `raw[raw.find('{'):]` 去掉) |
| `im +messages-search` | `data.messages` |
| `drive +search` | `data.results`(**参数用 `--query "X"`,不是 `--params '{...}'`**;子命令是 `+search`,**不是 `+files-list`**——后者不存在) |

**防御**:先 `print(list(d.get('data',{}).keys()))` 看 key 名再取。

**同款陷阱在请求 body**：不同命令的 items 数组字段名也不统一，凭印象拼会拿到 `error_code + error_message` 但 **HTTP code=0 假成功**：

| 命令 | items 元素 key |
|---|---|
| `im feed.groups batch_add_item` | **`feed_id` / `feed_type`**（❌ 不是 `item_id`/`item_type`——前者会返 `230006 only feed_type=chat is supported, got feed_type=''`） |
| `im chat.members create` | **`id_list`**（`open_id` 数组，不是 `members`/`users`） |
| `im pins create` | **`message_id`** 单值（不是 items 数组） |

**防御**：写 body 前先 `lark-cli schema <resource>.<method>` 查真实 schema，或者提交后**必看 `data.failed_items` / `data.invalid_*`**（HTTP code=0 但 failed_items 非空 = 部分失败，别信 `success` 二字）。

### 3. lark-cli `--file` / `--data @file` / `--content @file` 都不支持绝对路径

任何 `@file` / `--file` 形态的入参 CLI 都强制要求相对路径 + 在 cwd 内:

```
❌ --file image=/Users/x/pics/avatar.png
❌ --content @/tmp/wiki.md         # docs +update 同样中招
✅ cd /tmp && cp ~/pics/avatar.png . && --file image=avatar.png
✅ cd /tmp && --content @./wiki.md
```

报错原文(踩到就是这句):
```
--content: invalid file path "/tmp/wiki.md":
--file must be a relative path within the current directory,
got "/tmp/wiki.md" (hint: cd to the target directory first, or use a relative path like ./filename)
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

### 12. Schema 2.0 卡片里 `{"tag":"action","actions":[...]}` 已废弃 → 用**裸 button 元素**

想在首条卡片放个"查看 wiki"按钮时最容易踩。schema **2.0** 拒收 v1 的 action 包装,报:

```
code 230099 / ext ErrCode: 200861
ErrMsg: cards of schema V2 no longer support this capability;
ErrorValue: unsupported tag action
```

**修法** — button 作为 body element 直接摆,`behaviors` 数组承载点击动作:

```json
{
  "tag": "button",
  "text": {"tag": "plain_text", "content": "📄 查看完整档案 wiki"},
  "type": "primary_filled",
  "width": "default",
  "size": "medium",
  "behaviors": [
    {"type": "open_url", "default_url": "https://<tenant>.feishu.cn/wiki/<token>"}
  ]
}
```

关键字段:
- `type` — `primary_filled` / `default_filled` / `default` / `text`(v2 命名,不是 v1 的 `primary`/`danger`)
- `width` — `default` / `fill`(fill 铺满一行)
- `behaviors[].type` — `open_url` / `callback` / `form_action`

多按钮 → 用 `column_set` 布局把多个 button 元素横排,不再包 action。

### 13. 建群前先 dedup 查重(避免二次创建)

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

### 14. `wiki +node-get` 双坑 + `+space-node-list` 是幻觉子命令

跟 pitfall #9 同源。**wiki node-* 命令对 raw token 都不友好,优先 URL 形式**:

```bash
# ❌ 两个错一起出
lark-cli wiki +node-get --token XXX --as user
# → Flag --token has been deprecated, use --node-token instead
# → --obj-type is required for a raw obj_token "XXX"
#   (one of: doc, docx, sheet, bitable, mindnote, slides, file)

# ✅ URL 形式,CLI 自动 infer obj_type
lark-cli wiki +node-get --node-token "https://<tenant>.feishu.cn/wiki/XXX" --as user

# ✅ raw token + 显式 --obj-type
lark-cli wiki +node-get --node-token XXX --obj-type docx --as user
```

顺带 —— `wiki +space-node-list` **不存在**,报 `unknown subcommand`。列节点用 `+node-list --space-id X`(可选 `--parent-node-token X` 限定子树)。

### 16. Shell `--data "$(python3 -c "...")"` 引号地狱 → 用 python heredoc + subprocess

生成 interactive card 或复杂 body 时高发。外层 `"..."` 会 kill 掉 inner python 的 `"..."`,inner 又需要 `""` 包 JSON string:

```bash
# ❌ 崩(SyntaxError 或 shell 把 ' 当变量分隔)
lark-cli im messages create \
  --data "$(python3 -c "
import json
print(json.dumps({
    'receive_id': '${CHAT}',
    'msg_type': 'interactive',
    'content': json.dumps(card, ensure_ascii=False)
}, ensure_ascii=False))"
```

**修法** — python heredoc `<<'PY'`(**单引号** heredoc 阻止 shell 变量插值 + `\` 转义)+ `subprocess.run(list)`:

```python
python3 <<'PY'
import json, subprocess
CHAT = "oc_xxx"       # 硬编码进 heredoc,别 $VAR
card = { ... }        # 完整 dict

# 落 JSON 文件比 --data 内联稳
with open('/tmp/card.json','w') as f:
    json.dump(card, f, ensure_ascii=False)

# lark-cli +messages-send 内联读文件(不用 --data JSON)
r = subprocess.run(
    ["bash","-c",
     f'lark-cli im +messages-send --chat-id {CHAT} --msg-type interactive '
     f'--content "$(cat /tmp/card.json)" --as bot --format json'],
    capture_output=True, text=True
)
out = r.stdout or r.stderr
d = json.loads(out[out.find('{'):])
print("msg_id=" + d.get('data',{}).get('message_id','ERR'))
PY
```

**关键规避**:
- heredoc 用 `<<'PY'`(单引号)—— shell 不做变量/命令替换
- 变量硬编码进 heredoc,不用 `${VAR}` 传进去
- **`subprocess.run(list形式)`** 而非 `subprocess.run("string", shell=True)` — 前者 argv 数组直传,后者又回到 shell 引号地狱
- JSON body 复杂时**先落文件再用 `$(cat file)`** 比 `--data '{...}'` 内联稳

同款问题也发生在 `chats create --data '{...含中文..}'` 时。凡是 body 含引号/中文/嵌套 JSON 都走 heredoc,别硬 inline。

### 15. 合同/契约类源材料里签名页/主体信息**空白** = 不能自动填人拉群

Step 0 铁律的补充。合同草案里"甲方 A / 乙方 B / 丙方 C · 身份证:____"这种**明摆着还没落名的**字段,即使会话历史里能推测出角色分配,也**禁止**:

- 用推测名字填 wiki 里的"三方结构"表(会变成看似确定的记录)
- 把推测的三方拉进群(飞书通知即不可撤,拉错人 = 事故)
- 用旧 session 讨论碎片当"事实"填合同条款(编造)

**姿势** — 只按合同白纸黑字有的信息建档:

1. **wiki 里角色行保留 A/B/C 占位符**,不换成猜的名字
2. **群成员只邀请 Owner**(你自己),外部三方缺席
3. 单开一节 `## 待补` 列出所有空白字段(签名/身份证/公司名/日期/联系方式),下次用户来 confirm 才动
4. 首卡片 `**⏳ 待补**` 区块显示相同清单,视觉提示"这不是完整合同"

**判定** — 源材料里出现连续 3+ 个 `____` / `<空>` / `TBD` / `___` 且字段位置在\"主体/签名/联系方式\" → 走本条,不走"直接建三方群"路径。

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
