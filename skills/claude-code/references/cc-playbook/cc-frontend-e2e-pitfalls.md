---
name: cc-frontend-e2e-pitfalls
description: 派 Claude Code 用 browser-agent (4821/4822 hook) 测前端 web 应用时的高频踩坑集合。Pairing/login UI 卡死、route 路径解析陷阱误造假 bug、DB count 读法误判、URL 路径错（/ws vs /client）。爸爸说"派 CC 测前端"或"用 browser-agent E2E"时载入。
---

# CC 派单测前端 E2E 的踩坑

业务上下文：Clawline 这类 React SPA + WebSocket 后端的 web 应用，CC 用 browser-agent /hook 跑 E2E 时反复踩到的几个独立问题。

## 1. 严禁让 CC 操作多步 UI 流（pairing/login/modal/确认对话框）

**症状**：CC 跑 10 分钟超时退出，给一堆"自我介绍"、"reset 抢断"、"无法定位元素"等垃圾汇报。日志显示 read_page → click → read_page → click 反复循环找不到正确按钮。

**踩过的次数**：本 session 至少 2 次（nexora pairing 一次、Levis pairing 一次）。

**正确做法**：

✅ 让爸爸手动 pair 一次，CC 接着进 chat 测  
✅ 直接读 `localStorage.getItem('openclaw.connections')` 找现成 connection  
✅ 直接 navigate 到目标路由（如 `/chat/<id>`）跳过列表页  
✅ 必要时直接 setItem localStorage 注入 connection 数据  

❌ 让 CC 自己粘 URL 到 pairing 输入框  
❌ 让 CC 点"删除旧连接 → 确认 → 添加新 → 提交"系列对话框  

**派 CC prompt 必带**："**禁操作 pairing/login/modal UI**。如果没现成可用 connection，直接报告停止，不要尝试 UI 配置。"

## 2. SPA 路由路径解析陷阱：CC navigate 假 URL 会造出假 bug

**症状**：CC 直接 `navigate http://localhost:4026/chat/<X>`，然后报"sync API 返回 400 invalid agentId"，给一份看似确凿的根因分析。

**真相**：client-web 路由 `/chat/:agentId` 把整个 path 段当 agentId 使用（如 App.tsx:99 `pathname.slice('/chat/'.length)`）。CC 凭印象拼了个 `<connId>/<senderId>/<agentName>` 三段路径，结果 agentId 就被解析成 `conn-xxx/Levis/main`，gateway SAFE_ID_RE 拒绝。

**问题在测试方法不在被测代码**。如果 Hermes 信了 CC 报告，会去修一个不存在的 bug。

**判别**：
- 看真实用户操作产生的 URL（从 ChatList 点击进去后的 URL），对比 CC 直接 navigate 的 URL，**字面差异即假 bug**
- 在 DB 里 `select distinct agent_id` 看真实数据格式，对比 CC 抓到的 agentId 格式，**不一致即 CC 拼错**
- 让 CC 用 `localStorage.getItem('openclaw.connections')` 拿到 connection 信息后，**通过点击 ChatList 进入**，不要直接 navigate

**派 CC prompt 必带**："进入 ChatRoom 用点击 ChatList 的方式，不要直接 navigate 到 /chat/<X>，因为 SPA 路由可能把 path 整段当业务 ID 解析。"

## 3. PostgREST count header 读法陷阱

**症状**：调用 `Prefer: count=exact` 拿到 `Content-Range: 0-0/1318`，以为该 query 命中 1318 条。

**真相**：count 是**整个 from 表的总行数**，不受 select 列表影响，但**受 query filter 影响**。如果你的 filter 漏写了某个条件（如忘加 `agent_id=eq.X`），count 算的是宽口径。

**踩过**：本 session 我做 `?channel_id=eq.fires&chat_id=eq.Levis&agent_id=eq.main&select=id` 拿到 `0-0/1318`，以为 fires/Levis/main 有 1318 条；实际是只看 channel_id+chat_id 的总数（含其他 agent）。真实 fires/Levis/main 只有 30 条。差点让我冤枉 gateway 分页 bug。

**判别**：
- count 数和你 list 出来的实际 row 数对不上 → query filter 哪条漏了
- 用 `select=count` 直接返回 JSON 而不是看 header，更不易出错
- 重要 query 用两种方式验证 count（PostgREST count header + 直接 select limit 大数 len）

## 4. Clawline 特定：WS pairing URL 路径是 /client 不是 /ws

详见 skill `clawline-local-dev`。这次踩了一次（CC 用了 /ws），生成的 connection 在 client-web localStorage 里 serverUrl 也存了 /ws，永远 close 1006 重连失败。

## 5. CC 报告"完成"但实际只是触发兜底文案

**症状**：CC `result: "Task completed"` exit 0，但内容是它的"自我介绍"或泛泛复述任务，没有真实测试数据。

**根因**：CC 内部 conversation compaction / max-iterations 触发，前面真实 work 被截断，最后一帧给个空回退。

**判别**：
- 看 `num_turns` 字段，如果 < 5 多半没真做事
- 看 result 里有没有具体的 URL/status/timestamp 等可验数据
- 检查 `total_cost_usd`，> $1 才说明真跑过 work

**对策**：prompt 里强制要求"汇报必须包含：抓到的真实 URL、status code、response body 前 200 字、当前 DOM 中可见消息条数"等机械可验数据，不接受抽象描述。

## 派 CC 测前端的标准 prompt 骨架

```
TASK: <一句话目标>

## 服务现状（已就绪）
- <列出端口和状态>

## 强约束（违反任一即 fail）
- 禁操作 pairing/login/modal UI（卡死过 N 次）
- 禁直接 navigate 业务 ID 路径（SPA 解析陷阱）
- 禁 puppeteer / playwright / headless chromium
- 禁 kill / restart Chrome
- 禁让爸爸做手动操作

## 步骤
1. 端口侦察 4821/4822
2. browser-agent navigate <入口 URL>
3. 读 localStorage 找现成 connection
4. <主测试>

## 汇报必填字段（机械可验，禁抽象描述）
- 真实抓到的 URL 完整字符串
- HTTP status code
- response body 前 200 字
- 涉及的 DOM 元素 count
- 时间戳

## 不在范围
- <列出禁动的代码区>

不修代码、不操作 UI 配置流。
```

## 反模式

- ❌ 派 CC 跑端到端"包括 pairing"——pairing 卡死 90%
- ❌ 信 CC 报告的根因不去 DB / 真实代码核实——假 bug 引你修真代码
- ❌ 用 PostgREST count header 单独决策——必须配合实际 row 拉取
- ❌ 让 CC 自己造 URL 测——必须从真实 UI 流引导出 URL
