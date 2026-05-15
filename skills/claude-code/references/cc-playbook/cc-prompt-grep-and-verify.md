---
name: cc-prompt-grep-and-verify
description: 派 CC（Claude Code）改代码时，用「grep pattern + 机器可验收」替代「列文件 + 读 commit message」。防止 hotfix prompt 写窄漏同类、多 phase 任务被 CC 偷偷缩水。从 wx-gateway admin 重构（72a8e75..a2867cf）实战提炼。
---

# CC Prompt：用 grep 和机器验收，不要列文件清单

## 触发场景

派 CC 干以下任一类活时，**必须**按本 skill 写 prompt：

- hotfix（已知 bug pattern 散落多文件）
- 多 phase / 多子任务（5 tab、6 模块这种）
- 大范围重命名 / 重构（路径迁移、API 改名）
- 任何"改完不能漏同类"的活

否则**默认踩坑**：CC 严格按字面办事，prompt 漏一个文件 = 漏一个 bug。

## 反模式 1：hotfix 列"只改 X 和 Y"

### 症状
bug 在 prompt 列的文件里修了，同类 pattern 在其他文件里没动，部署上线复现。

### 实战（2026-04-29 wx-gateway slug bug）
- 第一发 prompt：「只改 `app/panel/page.tsx` 和 `lib/admin/api-base.ts`，slug 解析改成取前 2 段」
- CC 严格遵守，那两个文件确实修了
- 但 `app/panel/_components/PanelShell.tsx` sidebar 里 5 个 `<Link href="/_a/apps">` 同类硬编码完全没碰
- 上线后用户点 sidebar tab 全 404
- 第二发 prompt 才补 grep 整仓库清完

### 修法

**禁**：列文件清单。  
**用**：列 grep pattern，让 CC 自己找全。

```markdown
## 任务

1. **grep 整仓库**找出所有同类 pattern：
   ```bash
   rg -n '"/_a' --type ts --type tsx
   rg -n "'/_a" --type ts --type tsx
   rg -n 'pathname\.split.*\[0\]' --type ts --type tsx
   ```
2. 全部改成 `getSlug()` 拼接，不要硬编码
3. 特别检查：sidebar / nav / breadcrumb / logout / 任何 `<Link>` / `router.push()`
```

辅助清单（"特别检查"）只是引导，不是穷尽——主力靠 grep。

## 反模式 2：多 phase 任务读 commit message 验收

### 症状
CC 偷偷缩水范围，commit message 自圆其说，文字汇报"完工"，实际只做了一部分。

### 实战（2026-04-29 wx-gateway phase 5）
- prompt：「polish overview / invites / scans / payments / admins 5 个 tab」
- CC 只做了 overview
- commit message 自动缩水成 `feat(admin): phase 5 — polish overview tab`
- 文字汇报"phase 5 完工"
- 用户截图 review 才发现其他 4 tab 还是 phase 2 裸表格

### 修法

**禁**：依赖人工读 commit message 或 CC 自报"完工"。  
**用**：prompt 里写明**机器可跑的 grep / 计数 / 文件存在性**验收，让 CC 自己跑给你看。

```markdown
## 验收（CC 必须把每条命令实际输出贴到最终报告）

1. `npm run build` 0 error 0 warning
2. **必须有 N 个 commit**（每子任务一个，不许合并）：
   - `feat(panel/invites): badge + actions + create dialog + empty state`
   - `feat(panel/scans): timeline view + stats + promote action`
   - `feat(panel/payments): toolbar + filters + drawer reuse + stats`
   - `feat(panel/admins): card list + add/remove dialog`
3. grep 自查（必须 0 命中）：
   ```bash
   rg -n '"/_a' app/ lib/ components/         # 无硬编码 admin path
   rg -n 'fetch\("/' app/panel/                # 全走 apiFetch 不裸 fetch
   rg -n 'admin\.css' app/panel/               # 不引用老 CSS
   ```
4. 输出 `git log --oneline -8`
5. 输出每条 grep 命令的实际 stdout
```

每子任务列举式 commit + grep 0 命中 = CC 没法缩水到 1 commit 不被发现。

## 反问规则（推翻"严禁反问"）

之前 force prompt 写「严禁中途反问，再反问按失败处理」——逼得 CC 遇到真该问的（凭据缺失、必需 API 不存在、build 30min 修不掉）也硬猜，回归代价更大。

### 校准后的 force prompt 模板

```markdown
> ⚠️ **默认硬推**。任何"是否要…/要不要先…/请 PM 定 A/B"的犹豫，
> 按更激进/更快推进的方向自决，结果记入最终报告。
> **仅当**满足：
>   ① 真阻塞（build 30min 修不掉 / 凭据缺失 / 必需 API 不存在）
>   ② 自己穷举 3+ 方案都行不通
> 才能停下来问。
> 决策权在 PM 不在你。CC = 工人按图施工，不是 architect。
```

差别：从「绝对禁止」→「高门槛 + 列举式触发条件」。CC 默认硬推，遇到真阻塞还能停。

## 一句话总结

| ❌ 反模式 | ✅ 正确 |
|---|---|
| prompt 列**改哪些文件** | 列**grep pattern**，CC 自己找全 |
| 验收**读 commit message** | 验收**跑 grep / build / 计数**，CC 把 stdout 贴回 |
| **严禁反问** | **3+ 方案穷尽 + 真阻塞**才能停问 |
| 多任务**1 commit 合并** | **每子任务 1 commit**，prompt 列举出来 |

## 实战 commit 链

`72a8e75..a2867cf` (wx-gateway) — phase 1-5 + 2 hotfix + 4 polish，全套套路验证过。
