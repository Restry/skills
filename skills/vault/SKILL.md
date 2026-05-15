---
name: vault
description: 爸爸自托管的密钥仓库 — `vault` CLI（age + git + GitHub 私有 repo `Restry/vault-data`）。**别名：门神**（爸爸口语都说"门神"，听到"门神"立即加载本 skill）。零订阅、跨平台、本地/云端体验一致、解锁靠 SSH key、~10ms 取值。**已替代 1Password**。任何 agent 取/存密钥用 `vault get` / `vault inject`。
version: 3.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [Credentials, Secrets, age, git, Self-Hosted, CLI]
    related_skills: [mvp-deployer, claude-code]
---

# vault — 自托管加密密钥仓库

## 📚 References — 5 秒决策表

| 场景 | 读哪个 reference |
|---|---|
| 跨机器 / 新机器初始化 vault | [cross-machine-bootstrap.md](references/cross-machine-bootstrap.md) |
| 批量 ≥10 条凭据入库 | [bulk-import.md](references/bulk-import.md) |
| 项目首次接入门神 (.env → vault 双轨) | [project-onboard.md](references/project-onboard.md) |
| vault export 特殊字符 / 转义污染 / DB 名乱码 | [export-shell-escape.md](references/export-shell-escape.md) |
| 应用运行时读 vault / 部署含 vault 数据的 UI | [snapshot-deploy.md](references/snapshot-deploy.md) |
| 健康检查 v3（9 类问题 + 一键脚本） | [health-check.md](references/health-check.md) |
| 批量改 index.toml.age（避免循环 vault meta） | [bulk-retag.md](references/bulk-retag.md) |
| 换主解密身份 / 新机器装 vault / 加新机器到 recipients（含跨平台 mac/Linux/Windows） | [identity-rotation.md](references/identity-rotation.md) |
| 当前状态 / 已巡检项目 / Roadmap | [changelog.md](references/changelog.md) |

## ⛔ Agent 铁律：永远不读 secret 真值

**Hermes terminal 输出层会单向 mask 所有长字符串（≥32 字符的 hex/base64、`tvly-/sk-/ghp_/AKIA-` 前缀 token 等）成 `prefix-X...XXXX` 形式。Agent 自己也看不到中间字节。**

→ 所以：**永远不要把"打印 secret + 比对"作为验证方式**。所有 secret 操作走以下决策表：

| 任务 | ❌ 错路（被 mask 困） | ✅ 根方案 |
|---|---|---|
| 验证刚写入 | `vault get` 看长度/前缀 | **API 实测调一次**（200 = 写对，401 = 写错） |
| 给程序用 | `KEY=$(vault get X) && curl -H "Auth: $KEY"` | `vault inject template > .env` 或程序自读 vault |
| 部署到 server | scp 明文 .env | snapshot 模式 / mvp-deployer manifest.env |
| 调试连不通 | 打印 key 对比 | 看服务端 401/403/IP allowlist/quota 响应，不看 key |
| 必须拿到真值（极少） | `terminal('vault get X')` | `execute_code` 内 `subprocess.run(['vault','get',K], capture_output=True).stdout` 绕开 mask；值只在 sandbox 内用，禁 print |

**踩过的坑** (2026-05-15)：替换 Tavily key 后反复"看长度 13 字符以为又写错"，实际是 mask 显示，写入早就对了。**判断写对没 = API 调一次，不是看长度**。

详见 `hermes-mask-secrets-pipe-pattern` skill。

## 为什么不用 1Password

爸爸 2026-05-01 第一性原理拆解后认定：1P 解锁 10 分钟 cache 太烦；云端 Linux 要付 $20/月 Service Account；op CLI 在无 GUI 子进程里弹不出 Touch ID；99% 功能（团队/SSO/审计/Watchtower）一人用不到。

**自做 = age + git + 100 行 bash CLI**。本机/Win/云端 Linux 体验一致，零订阅，~10ms 取值。

## 架构

```
GitHub 私有 repo  Restry/vault-data
      │ git push/pull (透明，每次命令自动)
      ▼
~/.vault/store/   = git working tree
├── .age-recipients          # 公钥列表（明文，可 commit）
├── index.toml.age           # 全局元数据索引（tags/notes/category）
├── echo/
│   ├── DATABASE_URL.age     # 每个 secret 一个 .age 文件
│   └── ...
├── cspy/...
└── 20+ 项目，225+ 条 secret

~/.vault/cache/              # 解密 cache（chmod 700，运行时清）
~/.vault/bin/vault           # CLI 主体（500 行 bash）
/usr/local/bin/vault         # 软链
```

**解密身份**：`~/.ssh/id_rsa`（age 1.x 原生支持 ssh-rsa）。RSA key 即"主密钥"。

## CLI 用法 (v2)

### Secret 命令

```bash
vault add <project>/<KEY> [--value V|--from-stdin]
vault get <project>/<KEY>                 # 取值
vault show <project>/<KEY>                # 元数据 + 值前 60 字符
vault list [-t <tag>] [-p <project>]
vault search <kw>                         # 全文搜
vault rm <project>/<KEY>
vault meta <p/KEY> --desc ... --vendor ... --severity critical|high|medium|low \
                   --where-to-get ... --tags ... --category ... --notes ...
vault export -t <tag> | -p <project>      # 导 .env 格式
vault inject template.json                # 渲染 vault://path 引用
vault sync
```

### 项目命令 (v2 新增)

```bash
vault project list                        # 列所有项目 + 状态 + 描述
vault project show <name>                 # 项目详情 + 该项目所有 secret
vault project search <kw>                 # 按描述/别名搜
vault project rm <name> [-y]              # 删整个项目
vault project set <name> --desc ... --stack ... --domain ... --repo ... \
                        --local-path ... --deploy ... --status prod|dev|paused|archived \
                        --aliases "a,b,c" --notes ...
```

每个写命令自动 git pull + commit + push。读命令自动 git pull。

## 命名约定

```
<project>/<ENV_VAR_NAME>
```

例：`echo/DATABASE_URL`、`cspy/WECHAT_APPSECRET`、`mvp-deployer/TOKEN`

## 部署集成

`manifest.tpl.json`（可 git commit，不含真值）：

```json
{
  "env": {
    "DATABASE_URL": "vault://echo/DATABASE_URL",
    "PORT": "3795"
  }
}
```

部署：

```bash
vault inject manifest.tpl.json > /tmp/m.json
curl -F "manifest=$(cat /tmp/m.json)" ...
rm /tmp/m.json
```

## Agent 调用约定

### Hermes

```python
terminal('vault get echo/DATABASE_URL')
terminal('vault inject ~/projects/echo/manifest.tpl.json > /tmp/m.json')
```

### Claude Code / Codex / OpenClaw

派 CC 时 prompt 里写：

```
## 凭据获取
本项目密钥统一存在 vault（爸爸的自托管密钥仓库），用 `vault` CLI 取：
- `vault get <project>/<KEY>` 单值
- `vault list -t project/<name>` 列项目所有 key
- `vault export -t project/<name>` 导出为 .env 格式
- `vault inject <template>` 渲染模板

不要找爸爸要、不要从 ~/.credentials/.env 读、不要直接读 .env 文件。
```

## ⚠️ 反模式：禁止把读 vault 的服务部署到公网 host

踩过 1 次（2026-05-02 menshen-ui）。把 vault 解密身份 + 数据 store 拷到云端 host = 整个 vault 安全级别 = 那台 host 安全级别。一台机器被攻破 = 225 条 secret 全泄。

**正解**：读 vault 的工具/UI 只在本地（Mac/家里 NAS）跑。出门看用 Tailscale 回家。

## 🚪 凭据准入原则（resley 思想）

**门神只存"真凭据"。不是凭据的不准进。**

### 真凭据判定（必须满足全部）

1. **泄露会有真实损失**（扣钱/被入侵/用户数据外泄/业务被冒充）
2. **不能从代码 / 部署 manifest / 公开配置推出**
3. **轮换需要保密通信**（不能直接 git push）

### 不是凭据 — 别进门神

| 类型 | 例子 | 应该放哪 |
|---|---|---|
| 端口 | `PORT=3812` | manifest.tpl.json / 代码常量 |
| 布尔/枚举 | `MOCK_SMS_SEND=true` `NODE_ENV=production` | 同上 |
| 公开 URL | `NEXT_PUBLIC_*_BASE=https://wx.mvp.restry.cn` | 代码 / env.example |
| App slug | `WX_GATEWAY_APP_NAME=echo` | manifest / 代码 |
| 公开 endpoint | `AZURE_OPENAI_ENDPOINT=https://xx.openai.azure.com` | env.example |

⚠️ **陷阱**：长 hex/base64 字符串看着像 slug 但其实是真密钥。
- `ADMIN_SLUG=ad7c3ec948e19de4bd13dc696d63cf85` → **真密钥**（secure-admin-path 模式）
- `WX_GATEWAY_APP_NAME=echo` → 伪 secret

判断规则：**值是不是看起来像随机生成的（hex/base64/ULID）？是 → 真密钥**。

### 添加新凭据流程

```bash
# 1. 先问自己：这是真凭据吗？
# 2. 真的 → vault add，立即 vault meta 补全 4 字段：
vault add myproj/MY_SECRET --value "..."
vault meta myproj/MY_SECRET \
  --desc "用途一句话" \
  --severity critical \
  --vendor azure-openai \
  --where-to-get "https://portal.azure.com/.../keys"
# 3. 不是 → 不要进门神
```

## Tag 词典

- `project/<name>` / `env/<prod|dev|test|demo>` / `vendor/<X>` — 必备
- `scope/backend` / `scope/edge-fn` / `scope/frontend` — 同 key 多副本时区分用在哪层
- `status/critical` — 超权 key（service_role / master / root token），泄露=灾难
- `status/public` — 实际会被打包公开的（VITE_/NEXT_PUBLIC_ 前缀）
- `status/dev-only` — 弱口令 / seed / 测试，绝不可当真密钥
- `status/non-secret` — 是配置不是密钥（开关/URL/PORT/TEMPLATE_ID）

Severity 判定：

- **critical 🚨** = OAuth secret / HMAC / 私钥 / prod DB password / 付费 API key
- **high 🔑** = NextAuth secret / 内部 token / cron secret
- **medium** = 一般 token / API key（dev/staging）
- **low** = 弱凭据（本地 dev password、test fixture）

## Pitfalls（核心 10 条）

1. **`~/.ssh/id_rsa` 就是主密钥** — 丢了 = 所有 secret 解不了。备份到 U盘 / 离线介质。
2. **age 不接受加密的 SSH 私钥** — 设了 passphrase 每次都要输。解法：`ssh-add` 加 ssh-agent；或单独生成无 passphrase age key。
3. **`.age-recipients` 必须 push 到 repo**（明文，公钥可公开）。固定 1 个主 recipient，所有机器同一份 SSH key。
4. **多端写冲突** — A/B 同时 `vault add` 同一 key 会 git push 冲突。`cd ~/.vault/store && git pull --rebase`。
5. **`git push` 失败 vault CLI 不报警** — 当前 `git_sync` 用 `|| true` 吞错。本地 commit 进了远程没收到，调试懵逼。
6. **bash 对特殊字符脆弱** — value 含 `$`/反引号/换行用 `--from-stdin` 而非 `--value 'xxx'`。
7. **macOS 跨大小写文件系统** — 路径区分大小写。键名规范全大写下划线。
8. **大量并行 `vault get`** — 没 cache，每次 fork age 进程。一次 `vault export -t xxx` 替代多次 get。
9. **批量入新 secret 别用循环 `vault add`** — 所有写命令都内置 `git_sync`，单条 6-9 秒，120 条 = 12-18 分钟，bash terminal 60s 超时全砍。
   **正确做法**：关 hook + 直接 `age -R .age-recipients` 写文件 + 一次 commit。详见 [bulk-import.md](references/bulk-import.md)。
10. **🚨 Hermes terminal tool 自动 mask secrets** — `terminal('vault get xxx')` 输出形如 `tvly-l...7A7w` 的 mask，**不是真值**。验证 vault 存对了的标准流程：`execute_code` 里 `subprocess.run` 读真值 + API 调一次。

`vault add` 必须用 `--value`，不接受位置参数。`vault --help` 因 unbound var 报错，用 `vault help`。

## 多端 setup

```bash
# 1. 装依赖
brew install age git           # 或 apt install / winget install

# 2. clone vault data
mkdir -p ~/.vault/cache
git clone git@github.com:Restry/vault-data.git ~/.vault/store
chmod 700 ~/.vault ~/.vault/cache

# 3. 装 CLI
# 当前主机：~/.vault/bin/vault + /usr/local/bin/vault 软链
# 新机器临时：scp 主机的 ~/.vault/bin/vault 过来

# 4. 解密身份
ls -la ~/.ssh/id_rsa  # 必须存在

# 5. 测试
vault list && vault get echo/DATABASE_URL
```

云端 Linux 完全相同。**不需要任何订阅、桌面 app、GUI**。

## Selftest

```bash
vault get echo/DATABASE_URL | head -c 30
vault list -t project/cspy | wc -l
vault search "造悟者"
echo '{"x": "vault://test/HELLO"}' > /tmp/t.json && vault inject /tmp/t.json && rm /tmp/t.json
vault sync
```

## 相关 skills

- `mvp-deployer` — 部署流程，应改用 `vault inject` 渲染 manifest
- `claude-code` — 派 CC 时 prompt 模板需提示用 vault CLI 取密钥
- `hermes-mask-secrets-pipe-pattern` — terminal mask 机制详解
