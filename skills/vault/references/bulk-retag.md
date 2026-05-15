# vault — 批量改 index.toml.age

避免循环 `vault meta` 的网络抖动（10 条要 120s）。**直接编辑 index 一次 commit**（10 条 7 秒）。

## 通用脚本骨架

```python
import subprocess, os, re
STORE = os.path.expanduser("~/.vault/store")
IDX = f"{STORE}/index.toml.age"
PLAIN = "/tmp/_idx.toml"

# 解
content = subprocess.run(["age","-d","-i",os.path.expanduser("~/.ssh/id_rsa"),IDX],
                         capture_output=True, text=True).stdout

FIXES = [(key, tags, notes), ...]
for key, tags, notes in FIXES:
    content = re.sub(rf'\n?\[{re.escape(key)}\][^\[]*', '', content, flags=re.S)
    content += f'\n\n[{key}]\ntags = "{tags}"\nnotes = """\n{notes}\n"""\n'

open(PLAIN,"w").write(content)
subprocess.run(["age","-R",f"{STORE}/.age-recipients","-o",IDX,PLAIN])
os.unlink(PLAIN)
subprocess.run(["git","-C",STORE,"add","-A"])
subprocess.run(["git","-C",STORE,"commit","-m","retag: project/X refine"])
subprocess.run(["git","-C",STORE,"push","origin","main"])
```

## 批量加 status/non-secret tag（实测 64 条 0.3 秒）

```python
import re, subprocess, os
STORE = os.path.expanduser("~/.vault/store")
IDENTITY = os.path.expanduser("~/.ssh/id_rsa")
INDEX = f"{STORE}/index.toml.age"
idx = subprocess.run(["age","-d","-i",IDENTITY,INDEX], capture_output=True, text=True, check=True).stdout
for k in todo_keys:  # ["proj/KEY", ...]
    pat = re.compile(rf'(\[{re.escape(k)}\][^\[]*)', re.S)
    m = pat.search(idx)
    if not m: continue
    block = m.group(1)
    if "status/non-secret" in block: continue
    if re.search(r'^tags\s*=\s*"[^"]*"', block, re.M):
        new = re.sub(r'^(tags\s*=\s*")([^"]*)(")',
                     lambda mm: mm.group(1) + (mm.group(2)+"," if mm.group(2) else "") + "status/non-secret" + mm.group(3),
                     block, flags=re.M)
    else:
        new = block.rstrip() + '\ntags = "status/non-secret"\n'
    idx = idx.replace(block, new, 1)
pub = subprocess.run(["ssh-keygen","-y","-f",IDENTITY], capture_output=True, text=True).stdout.strip()
subprocess.run(["age","-e","-r",pub,"-o",INDEX], input=idx, text=True)
# 然后 cd ~/.vault/store && git add -A && git commit && git push && ~/.vault/hooks/post-write.sh
```

## 实测对比

| 方式 | 10 条耗时 | 100 条耗时 |
|---|---|---|
| 循环 `vault meta` | 120s（卡到超时） | 永远不完 |
| 直接编辑 index | 7s | 30s |

## 关键提醒

整改完一定 `~/.vault/hooks/post-write.sh` 触发重生 snapshot + 部署 menshen-ui，否则 UI 看到的还是旧数据。
