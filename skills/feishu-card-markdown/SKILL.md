---
name: feishu-card-markdown
description: 飞书结构化消息渲染——Hermes feishu gateway 自动把含表格 / 末尾问号的 LLM 回复转成 schema 2.0 交互卡片。Agent 直接用 markdown 写表格 / 用 `？` 结尾即可，gateway 自动处理。手动场景用 lark-cli 发 interactive 卡片。
version: 3.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [Feishu, Lark, Markdown, Card, IM]
    related_skills: [lark-im, lark-markdown]
---

# feishu-card-markdown

## 🪄 自动转换（Hermes feishu gateway 内置）

`gateway/platforms/feishu.py` `_build_outbound_payload` 自动把 agent 回复转成卡片，**agent 不用调任何 API**：

| 触发条件 | 行为 |
|---|---|
| 含 markdown 表格 (`\| --- \|`) | 转 schema 2.0 卡片（蓝 header），表格在卡片里完美渲染 |
| 末尾 10 字符含 `?` / `？` | 转卡片 + 附 3 个 quick-reply 按钮（橙 header） |
| 两个都中 | 蓝/橙 header + 表格 + 末尾按钮 |
| 都不中 | 走默认 text/post 发送 |

**卡片标题**自动从回复第一行提取（剥 markdown 标记，截 28 字），保证爸爸一眼看出卡片是讲什么的。

### Quick-reply 按钮

3 个万能按钮，点了直接当用户的下一条消息：

- 👍 是/好 → "好的"
- 👎 不/算了 → "不用了"
- 💬 我自己打 → "（用户选择手动输入）"

点完按钮卡片立刻变成绿色 ✓ 状态（保留原标题），按钮消失，agent 收到 synthetic TEXT event 继续处理。

## ✍️ Agent 怎么用

**写 markdown 就行**，gateway 帮你转：

```
当前进度：

| 任务 | 状态 |
|---|---|
| A | ✓ |
| B | ⏳ |

要继续推进吗？
```

→ gateway 自动渲染成卡片 + 末尾加 3 个按钮，标题取 "当前进度："。

什么时候**不要**靠自动转换：
- 需要自定义 header 颜色 / 多元素布局 / 图表 / 自定义按钮 → 用 lark-cli 手动发（见下面）
- 单行闲聊 / 短确认 / 含图片附件 → 让默认 text 路径走，别加表格/问号

## 🛠️ 手动发卡片（lark-cli）

需要图表、复杂按钮、自定义颜色、多元素布局时，用 lark-cli 直接发 schema 2.0 interactive 卡片。

### ⚠️ 铁律：raw card JSON 绝不走 send_message

Hermes 的 `send_message` 工具 → feishu gateway 只会把 **markdown 表格 / 末尾问号** 自动转卡片；把一坨 `{"msg_type":"interactive","card":{...}}` JSON 塞进 `send_message.message` 字段 = **原样当文本发**，爸爸收到一屏 JSON。

正确路径：当用户说"用卡片消息"或要"指定 header 颜色 / 多段布局 / 表格 + 按钮组合"，直接 `lark-cli im +messages-send --msg-type interactive`，**不要走 send_message**。

### lark-cli 安装 + 绑定（一次性）

```bash
npm install -g @larksuite/cli
lark-cli config bind --identity bot-only   # 不要带 --source，会报 "does not match detected Agent environment"
```

bind 成功后返回 `{"ok":true,"app_id":"cli_xxx","workspace":"hermes"}`，配置落 `~/.lark-cli/hermes/config.json`。

```bash
lark-cli im +messages-send \
  --chat-id <oc_xxx> \
  --msg-type interactive \
  --content "$(cat card.json)"
```

成功返回 `data.message_id` (`om_xxx`)。

### schema 2.0 卡片模板

```json
{
  "schema": "2.0",
  "header": {
    "title": {"tag": "plain_text", "content": "📋 标题"},
    "subtitle": {"tag": "plain_text", "content": "副标题（可选）"},
    "template": "blue"
  },
  "body": {
    "elements": [
      {"tag": "markdown", "content": "GFM 表格 / 富文本 / 彩字 `<font color='green'>X</font>` 都能渲染"},
      {"tag": "hr"},
      {
        "tag": "chart",
        "chart_spec": {
          "type": "bar",
          "data": {"values": [{"x": "A", "y": 1}, {"x": "B", "y": 2}]},
          "xField": "x", "yField": "y"
        }
      },
      {
        "tag": "column_set",
        "columns": [
          {"tag": "column", "elements": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "✓ 继续"},
            "type": "primary",
            "behaviors": [{"type": "callback", "value": {"action": "go"}}]
          }]},
          {"tag": "column", "elements": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🌐 看文档"},
            "type": "default",
            "behaviors": [{"type": "open_url", "default_url": "https://example.com"}]
          }]}
        ]
      },
      {"tag": "markdown", "content": "<font color='grey'>🤖 模拟页脚（schema 2.0 没有 footer）</font>"}
    ]
  }
}
```

### Header template 色板

| template | 用途 |
|---|---|
| `blue` | 信息/汇报（默认） |
| `green` | 成功/完成 |
| `orange` | 警告/确认（gateway 的 quick-reply 卡用这个） |
| `red` | 错误/危险 |
| `purple` | 重要决策 |
| `grey` | 次要信息 |
| `turquoise` | 进度/中间态 |

### Button

- `type`: `primary` 蓝 / `default` 灰 / `danger` 红
- `behaviors`:
  - `{"type": "callback", "value": {...}}` — 回调（需要 Hermes feishu.py 接住 value）
  - `{"type": "open_url", "default_url": "..."}` — 跳链接

### schema 2.0 vs 老 schema

| 想要 | schema 2.0 怎么办 |
|---|---|
| 代码块 | markdown fenced ` ```bash ... ``` ` |
| 页脚 | 灰色 markdown 模拟 `<font color='grey'>...</font>` |
| 操作按钮 | `column_set` + `button` element + `behaviors` |
| 分隔线 | `{"tag": "hr"}` |

❌ **别用老格式** `{"config": {"wide_screen_mode": true}, "elements": [...]}` — markdown 表格不渲染。

## Python 组装（推荐）

```python
import json, subprocess
card = {
  "schema": "2.0",
  "header": {"title": {"tag": "plain_text", "content": "..."}, "template": "blue"},
  "body": {"elements": [
    {"tag": "markdown", "content": "| a | b |\n|---|---|\n| 1 | 2 |"},
  ]}
}
subprocess.run([
    "lark-cli", "im", "+messages-send",
    "--chat-id", chat_id,
    "--msg-type", "interactive",
    "--content", json.dumps(card, ensure_ascii=False)
], check=True)
```

## 常用 chat_id

- 爸爸 DM：`oc_ffa37ba1bef2fb4e834aac29900e0eca`
- 爸爸 open_id：`ou_c01660d7c077b57b85b8d14b1a374a26`

## 📚 知识库 / 云文档 / drive 操作踩坑

完整集见 `references/lark-cli-wiki-docs-pitfalls.md`。要点：
- `lark-cli wiki spaces create` 没 `--name` flag，只接 `--data` JSON
- `lark-cli docs +update --content @file` 必须**相对路径**（cp 到 cwd）
- **bot owner 的文档 API 删不掉 / 转不出去**（双向死锁），唯一可行：给 user 加 full_access → 用户去飞书 App 手动删；从一开始就用 user token 建文档
- 飞书开权限：爸爸偏好「批量开通 JSON」`{"scopes":{"tenant":[],"user":[...]}}` 贴后台，**第一次就多开**避免反复要权限
- device flow 拿 user token：`lark-cli auth login --domain all --no-wait --json` → 把 URL 给用户 → 用户授权后 `--device-code <code>` 续上

## 📄 lark-cli docs +create 文档创建踩坑

爸爸要"在飞书里整理文档"时走这条，不要纯发消息。

```bash
# ✅ 工作的姿势（v1 默认，v2 当前要 --content 字段未跑通）
cp /tmp/out.md ./out.md   # 必须 cwd 下的相对路径
lark-cli docs +create \
  --title "标题" \
  --markdown "@./out.md"
```

**坑 1：`--markdown @file` 只接受当前目录的相对路径**
- ❌ `--markdown "@/tmp/foo.md"` → `--file must be a relative path within the current directory`
- ✅ `cp /tmp/foo.md ./` 然后 `--markdown "@./foo.md"`

**坑 2：v2 API 需要 `--content` 不是 `--markdown`**
- 加 `--api-version v2` 后传 `--markdown` 报 `--content is required`
- 不知道 v2 content 格式前，直接用默认 v1（有 deprecation warning 但能用）

**坑 3：bot 建的文档爸爸打不开**
- 返回 `permission_grant.status: skipped` + `Resource was created with bot identity, but no current CLI user open_id is configured`
- 试 `lark-cli drive permission.members create` 授权给爸爸 open_id → `App scope not enabled: docs:permission.member:create [99991672]`
- 试 `permission.public patch` 设公开 → `docs:permission.setting:write_only [99991672]`
- **根因**：bot app `cli_aa8da93e9078dbc6` 没开协作/分享相关 scope
- **绕开**：① 把 markdown 内容直接当消息发回飞书 ② 或者去 [scope-apply](https://open.feishu.cn/page/scope-apply?clientID=cli_aa8da93e9078dbc6&scopes=docs%3Apermission.member%3Acreate,docs%3Apermission.setting%3Awrite_only) 给 bot 申请这两个 scope（一次性）

## 实操要点

1. **GFM 表格语法**：`| --- |` 紧贴或带空格 `| --- |` 都行。
2. **JSON 含中文**：`json.dumps(..., ensure_ascii=False)`，shell 用 `--content "$(cat card.json)"` 最稳。
3. **手机端预览**：schema 2.0 自动响应式，无需 `wide_screen_mode`。
4. **agent 不复述卡片内容**：CARD-ONLY 策略，卡片发完对话里别再 markdown 重复一遍。

## 🧭 Parser 设计原则（北极星，改 parser 前必读）

当前 `_parse_actionable_card` / `_ends_with_question` 是 v1 实现，主要靠**末段问号**这一条粗粒度信号 → 误报多（任何反问/修辞/疑问代词句都中招），漏报也有（"这个方案好吗？"等动作意图弱的句子被吃掉）。

未来重构遵循这条**架构原则**：

> **L1 prompt 兜语义；parser 只做字面解析 + 长度/对称/否定的字面检查；UI 永远给「手动输入」逃生口。**

### 三个常见坑 + 解法

**坑 1：动作关键词白名单永远追不上自然语言变体**
- ❌ 加白名单（`是否|确认|授权|执行|...`）——治标，模型一变体就漏
- ✅ **信 prompt**：prompt 已经强约束「非动作场景禁问号」，parser 就该信。末句 `?` = 一律按动作确认渲染按钮；用户不点照样能打字。**少即是多**，parser 代码 -30%，假阴性归零

**坑 2：「X 还是 Y？」嵌套否定 / 非平行选项**
- 例：「用 A 方案还是不动？」、「先 deploy 还是 保持现状先观察 24h 再说？」
- ✅ **字面检查 + 降级**：
  - 单选项 `≤ 20 字`
  - 长度差 `≤ 15 字`
  - 含否定词（不/别/取消）的选项 → 强制变 yes_no 的 no 按钮
  - 不达标 → 降级为 yes_no 卡，**用户永远能点**

**坑 3：模型不听 prompt 的剩余 5% 漏网**
- ✅ **每个卡片永远附「💬 手动输入」按钮**（不论 yes_no / multi_choice）
- 代价：多一个按钮
- 收益：100% 兜底，parser 解错 / 模型说怪话 / 用户想自由答全靠它逃生

### Parser 实现参考（爸爸提供的 JS 原型）

`references/parse-actionable-card.js` —— 解析多选 (`A:` / `B:`)、行内 `还是`、动作 yes/no 三类，已内置 markdown 噪音剥离 (`*_~``)、Map 去重、最后问句兜底取（即使后面有「期待回复」之类废话）。Python 翻译版尚未上 gateway，留作 v4 升级蓝本。

### Prompt 端规范（agent/prompt_builder.py 飞书 hint 已落地）

| # | 规范 | 反例 |
|---|---|---|
| 1 | 动作确认问句 = 回复**最后一句**，含动作词（执行/授权/确认/部署/删除），以 `？` 收尾 | `是否执行？请点击按钮` |
| 2 | 多选用 `A：…` / `B：…` 大写字母+冒号，**不要 markdown 加粗前缀** | `**A:** 选项一` |
| 3 | 非动作 / 非选择场景 → **纯文本结尾**，禁制造问号触发卡片 | 末尾来一句「你觉得呢？」 |
