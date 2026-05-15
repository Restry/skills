# vault — 健康检查 v3

每周 / 接手新项目 / 批量改动后跑一遍。9 类问题按"会影响生产部署 vs 仅元数据脏"排序。

## 检查项

| # | 检查项 | 怎么找 | 严重度 |
|---|---|---|---|
| 1 | **snapshot 同步状态** | 比 `~/Projects/menshen-ui/.vault-snapshot.json` 的 `exported_at` vs `git -C ~/.vault/store log -1 --format=%aI`。差 > 5 分钟 = UI 显示过时数据 | 高 |
| 2 | **5 维 tag 完整性** | 每条 secret 必有 `project/X + env/Y`。**真 secret** 推荐 vendor/X 和 type/X | 中 |
| 3 | **项目元数据** | 每个 `[_project.X]` 应有 `desc`/`stack`/`domain`/`deploy`/`status` 5 字段（aliases 推荐）| 中 |
| 3b | **⭐ Secret meta 完整** | 每条 .age 必须在 `[X/KEY]` 有 meta。**完全无 meta = UI 显示 ?**。也查 desc/severity/vendor 缺失 | 高 |
| 4 | **环境分裂** | `<X>-test` `<X>-dev` 项目并入 `<X>` 用 `__test`/`__dev` 后缀 | 中 |
| 5 | **重复值** | 同真值在多 key 中。合理 vs 应共享 | 低 |
| 6 | **占位符/空值** | `your-` `xxx` `changeme` `admin123` | 高 |
| 7 | **shared_with 标注** | 跨项目共用真值的 secret 应在 notes/shared_with 标记 | 低 |
| 8 | **元数据无 .age** | index 有 section 但文件不存在 | 中 |
| 9 | **⭐ 伪 secret 识别** | 找端口/布尔/公开 URL/slug 等不该进门神的污染。建议 `vault rm` 或加 `tags="status/non-secret"` | 中 |

## 一键脚本

```bash
python3 ~/.vault/scripts/health-check.py
```

骨架（按需实现）：

```python
#!/usr/bin/env python3
"""vault 健康检查 - 跑完输出 markdown 报告"""
import subprocess, os, re, json, datetime
from collections import Counter, defaultdict
HOME = os.path.expanduser("~")
STORE = f"{HOME}/.vault/store"
IDENTITY = f"{HOME}/.ssh/id_rsa"
SNAP = f"{HOME}/Projects/menshen-ui/.vault-snapshot.json"

# 解 index
idx = subprocess.run(["age","-d","-i",IDENTITY,f"{STORE}/index.toml.age"],
                     capture_output=True, text=True, check=True).stdout

# 列所有 .age + 元数据
all_keys = []
for root, _, files in os.walk(STORE):
    for f in files:
        if f.endswith('.age') and f != 'index.toml.age':
            rel = os.path.relpath(os.path.join(root,f), STORE).replace('.age','')
            all_keys.append(rel)

projects_meta = {m.group(1): m.group(2) for m in re.finditer(r'\[_project\.([\w-]+)\]([^\[]*)', idx, re.S)}
secrets_meta = {m.group(1): m.group(2) for m in re.finditer(r'\n\[([\w-]+/[A-Z0-9_]+(?:__[\w-]+)?)\]([^\[]*)', idx, re.S)}

# 1. snapshot 新鲜度
if os.path.exists(SNAP):
    snap = json.load(open(SNAP))
    snap_t = datetime.datetime.fromisoformat(snap["exported_at"].replace("Z","+00:00"))
    git_t_str = subprocess.run(["git","-C",STORE,"log","-1","--format=%aI"], capture_output=True, text=True).stdout.strip()
    git_t = datetime.datetime.fromisoformat(git_t_str)
    drift = (git_t - snap_t).total_seconds() / 60
    if drift > 5:
        print(f"⚠️ snapshot 落后 vault {drift:.0f} 分钟，跑 ~/.vault/hooks/post-write.sh 重生")

# 2. tag 完整性
weak_tags = []
for k, body in secrets_meta.items():
    proj = k.split("/")[0]
    tag_m = re.search(r'tags\s*=\s*"([^"]*)"', body)
    tags = set(t.strip() for t in (tag_m.group(1).split(",") if tag_m else []))
    sev_m = re.search(r'severity\s*=\s*"([^"]*)"', body); sev = sev_m.group(1) if sev_m else ""
    missing = []
    if not any(t.startswith("project/") for t in tags): missing.append("project/")
    if not any(t.startswith("env/") for t in tags): missing.append("env/")
    if sev in ("critical","high") and not any(t.startswith("vendor/") for t in tags): missing.append("vendor/")
    if missing: weak_tags.append((k, missing))
print(f"## tag 不全: {len(weak_tags)} 条")

# 3. 项目元数据
no_desc = [p for p, b in projects_meta.items() if 'desc =' not in b]
no_aliases = [p for p, b in projects_meta.items() if 'aliases =' not in b]
print(f"## 项目缺 desc: {len(no_desc)}: {no_desc}")
print(f"## 项目缺 aliases: {len(no_aliases)}: {no_aliases}")

# 4. 环境分裂
projs_with_files = set(k.split("/")[0] for k in all_keys)
splits = []
for p in projs_with_files:
    for sfx in ["-test","-dev","-staging","-demo","_test","_dev"]:
        if p.endswith(sfx) and p[:-len(sfx)] in projs_with_files:
            splits.append((p[:-len(sfx)], p))
if splits: print(f"## 环境分裂: {splits}")

# 5. 重复值
values = {}
for k in all_keys:
    v = subprocess.run(["age","-d","-i",IDENTITY,f"{STORE}/{k}.age"], capture_output=True, text=True).stdout
    values[k] = v
val_to_keys = defaultdict(list)
for k, v in values.items():
    if v and len(v.strip()) > 8: val_to_keys[v.strip()].append(k)
dupes = [(v[:8]+"...", ks) for v, ks in val_to_keys.items() if len(ks) > 1]
print(f"## 重复值: {len(dupes)} 组")

# 6. 占位符/空值
PLACEHOLDER = re.compile(r'^(your-|YOUR-|changeme|xxx+|TODO|<.*>|placeholder|admin123|password|test123)', re.I)
bad = [(k,v[:30]) for k,v in values.items() if not v.strip() or PLACEHOLDER.match(v.strip())]
if bad: print(f"## 占位符/空值: {len(bad)}: {bad[:5]}")

# 7. 元数据无文件
ghost = set(secrets_meta) - set(all_keys)
if ghost: print(f"## 脏元数据(无 .age 文件): {len(ghost)}: {list(ghost)[:5]}")

# 8. 项目元数据但无文件
ghost_proj = set(projects_meta) - projs_with_files
if ghost_proj: print(f"## 脏项目(无 secret): {ghost_proj}")
```

## 整改套路

1. **tag 不全** → 跑批量 retag 脚本（见 [bulk-retag.md](bulk-retag.md)）
2. **元数据无文件** → 直接编辑 index.toml.age 删 section
3. **环境分裂** → 用 `__test` 后缀合并范式
4. **占位符** → 立即查项目 .env 拿真值入库
5. **重复值** → 决定合理共用 vs 统一到 vendor/ 项目

整改完一定 `~/.vault/hooks/post-write.sh` 触发重生 snapshot + 部署 menshen-ui。

## 历史已发现并修复

| 日期 | 问题 | 修复 |
|---|---|---|
| 2026-05-01 | bnef VITE_* 没标 status/public | retag |
| 2026-05-02 | 108 条 secret 缺 type/vendor/scope tag | 批量 retag (commit `3bcfd62`) |
| 2026-05-02 | image-studio-test 应该并入 image-studio | __test 后缀合并 (commit `75a5710`) |
| 2026-05-02 | wx-msg-fanout 3 条元数据无 .age 文件 | 删 section (commit `860c0fa`) |
| 2026-05-02 | echo/AZURE_OPENAI_API_KEY 与 azure-openai/ 共用未标注 | 加 shared_with (commit `860c0fa`) |
| 2026-05-02 | snapshot 落后 vault 6 小时（hook 卡死） | 修 hook flock bug，改 timestamp debounce |
