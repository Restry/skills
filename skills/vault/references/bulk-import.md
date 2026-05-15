# vault-bulk-import

## 何时用
- 要入库的凭据 **≥ 10 条**（< 10 条直接 `vault add` 没必要）
- 数据来自一份文档/Notion/.env，需要解析 + 分类 + 批量写
- 含 secret 模式串（`sk-xxx` / `ghp_xxx` / PAT）

## 为什么不能用 `vault add` CLI 循环
单条 `vault add` 内部串：
1. `git pull origin main`（无网络也试）
2. `git add + commit`
3. `git push origin main`（**4 秒 SSH 握手**，每次都重）
4. 触发 `~/.vault/hooks/post-write.sh` → 重生 snapshot + 重部署 menshen-ui（**2-3 秒**）

→ **单条 ≈ 9 秒 × 100 条 = 15 分钟**，bash 终端 60s 超时砍，你永远跑不完。

## 正确套路（5 步，总耗时 < 30 秒 / 100 条）

### 1. 关 hook
```bash
mv ~/.vault/hooks/post-write.sh ~/.vault/hooks/post-write.sh.disabled
```

### 2. 把数据写成 JSON 分批文件
**严禁 inline 在 LLM streaming 里写 100 条** — Copilot/Claude provider 会 ReadTimeout，看上去像"卡死"，其实是大 streaming 含 secret 触发延迟/过滤。

**分批 ≤ 35 条 / 文件**，每个文件 < 4KB：
```bash
# /tmp/v_b1.json
[
  {"k":"_global/GEMINI_API_KEY","v":"AIza..."},
  {"k":"_global/HUGGINGFACE_TOKEN","v":"hf_..."},
  ...
]
```

key 路径策略（爸爸偏好）：
- 资源类（Gemini / HF / Twilio / FileVault / Discord token）→ `_global/`
- 真有项目归属（image-studio 微信支付）→ 现有项目目录
- **不为分类创伪项目**（mattermost / email-smtp 这种全是凭据壳的项目壳，删掉）
- 靠 `vault meta --tags` 分类

### 3. age 加密 + 落盘（绕过 vault CLI）
```bash
R=~/.vault/store/.age-recipients
S=~/.vault/store
for f in /tmp/v_b*.json; do
  python3 -c "
import json,subprocess,os
data=json.load(open('$f'))
for e in data:
    p=os.path.expanduser('$S/'+e['k']+'.age')
    os.makedirs(os.path.dirname(p),exist_ok=True)
    subprocess.run(['age','-R',os.path.expanduser('$R'),'-o',p],input=e['v'].encode(),check=True)
    print('✓',e['k'])
"
done
```
实测 **127 条 / 5 秒**。

### 4. 一次 git commit + push
```bash
cd ~/.vault/store
git add -A
git commit -m "bulk add N secrets" -q
git push -q origin main   # 一次握手 ≈ 4-5 秒
```

### 5. 一次 snapshot 重生 + 一次部署
```bash
python3 ~/.vault/hooks/regen-snapshot.py    # ~15s, 全量解密重建 menshen-ui/.vault-snapshot.json
mv ~/.vault/hooks/post-write.sh.disabled ~/.vault/hooks/post-write.sh
~/.vault/hooks/post-write.sh                # 后台异步部署 menshen-ui
```

## 验证
```bash
# 总数对得上？
~/.vault/bin/vault list 2>/dev/null | wc -l

# 抽查取值
~/.vault/bin/vault get _global/GEMINI_API_KEY

# snapshot 已更新？
ls -la ~/Projects/menshen-ui/.vault-snapshot.json   # mtime 应是刚刚

# 远程也同步了？
gh api repos/Restry/vault-data/commits --jq '.[0].commit.message'
```

## 关键陷阱（踩过的）

### ⚠️ vault CLI 的 `git push` 用 `|| true` 静默吞错
`vault add` 里的 push 行：`git push -q origin main 2>&1 | grep -v 'Everything up' || true` —— **push 失败也假装成功**。本地 commit 进了但远程没，门神 UI 看不到新值，还以为入库失败。

→ 真要确认远程同步，用 `gh api` 或 `git ls-remote` 查。

### ⚠️ Hermes LLM streaming 大输出 = provider 超时
我（Hermes Agent）每个 tool call 都是 LLM 输出。**一次性 inline 写 100 条 secret** 的 write_file = LLM streaming 几 KB → Copilot provider ReadTimeout → 用户看到"Reconnecting / failed"以为我卡死，其实命令根本没敲。

→ 解法：**分批 ≤ 35 条 / write_file**，单次输出 < 4KB。

### ⚠️ 空壳项目要清
`vault project rm` 也走 git_sync，慢且会触发 hook。批量删用：
```bash
cd ~/.vault/store && rm -rf project1 project2 ...
# 最后统一 git add/commit/push
```

### ⚠️ 60 秒 bash 超时
任何串行循环超过 60 秒会被砍。要么后台跑（`background=true notify_on_complete=true`），要么用 Python 一把梭（execute_code）避免 shell 循环开销。

## ⚠️ Step 5.5 — 必补 metadata（**容易被忘**）

光入值是**不可用状态**：门神 UI 搜不到分类、看不到 vendor/severity/desc。每条入库后必须补：

```python
# 直接改 ~/.vault/store/index.toml.age（age 加密的 toml）
# 解密 → 追加 [project/KEY] block → 加密回写
import subprocess, os
INDEX = os.path.expanduser('~/.vault/store/index.toml.age')
RECIPIENT = os.path.expanduser('~/.vault/store/.age-recipients')
IDENTITY = os.path.expanduser('~/.ssh/id_rsa')
existing = subprocess.check_output(['age','-d','-i',IDENTITY,INDEX]).decode()
# 追加：
# [_global/GEMINI_API_KEY]
# desc = "..."
# vendor = "..."
# severity = "critical|high|medium|low"
# category = "credential|payment|database|recovery-key|config"
# tags = "vendor/X,type/Y,project/Z,env/prod"
# created_at = "2026-05-09"
# 加密回写：
subprocess.run(['age','-R',RECIPIENT,'-o',INDEX,'/tmp/new.toml'], check=True)
```

**分类规则模板**（按 key 名前缀自动判定）见 `/tmp/vault_meta_patch.py`（已存档参考）。

### ⚠️ 不要用 `vault meta KEY` 不带任何字段的命令
**会清空该条所有 metadata**！要么提供完整字段，要么走 toml 直改路线。

## 经验铁律
- **任何"批量"动作先量化时间**：单条 × 数量，> 30 秒立刻换方案
- **绕过封装层直达瓶颈下游**：CLI 慢就直接动文件
- **关 hook → 批量 → 一次同步 → 一次部署**：循环里永远不触发部署
- **大数据走文件不走 LLM streaming**：write_file 落 JSON，命令读文件
- **临界点立刻 stop**：第 1 条卡了别幻想第 2 条会快
