# Hermes 内部状态数据探测(画系统类报告专用)

画 Hermes 内部机制类报告(skill 数量、token 占用、system prompt 长度、内存使用等)时,**这些是实时探测命令**,**不要用缓存**。

## 🚨 0. 枚举源完整性自检(画前必读)

**最常见 bug**: 你跑了一个探测命令,但它只覆盖了你脑子里**已经知道的子集**,漏掉了系统里其他的项。Dad 一眼看出来,说"我怎么感觉太少了"。

具体 case(2026-06-05): 我画 skill 折叠报告时,只列了已经标了 `collapsed: true` 的 16 个分类,忘了系统里还有 11 个其他分类(包括 7 个未折叠的真分类 + 4 个顶层裸 skill)。Dad 直觉立刻发现。

**画前必做**: 找出**最大覆盖的枚举源**,从那里反向筛选,而不是从你的"假设清单"出发:

```bash
# ✅ 完整枚举: filesystem 真实状态
find ~/.hermes/skills -maxdepth 2 -name "DESCRIPTION.md" -o -maxdepth 1 -name "SKILL.md"
# 或者用 hermes 内建 API
python3 -c "import hermes_agent; print(hermes_agent.skills_list())"

# ❌ 不完整: 你的标记子集
grep -l "collapsed: true" ~/.hermes/skills/*/DESCRIPTION.md
```

报告里所有"系统里有 N 个 X"声明,都要能跑出**精确 N**的 1-line 命令,把那个命令注释或写在 reference 里。

## 1. Skills 真实数量与分类分布

```bash
# 真实 SKILL.md 文件数(不含软链)
find ~/.hermes/skills -name "SKILL.md" -type f | wc -l

# 含软链(显示数量,LLM 看到的)
find -L ~/.hermes/skills -name "SKILL.md" -type f | wc -l

# 所有顶级分类目录
find ~/.hermes/skills -maxdepth 1 -mindepth 1 -type d | sort
```

注意:有的"分类目录"其实顶层就是单 skill(直接 SKILL.md 没子目录),要区分:

```bash
# 顶层单 skill 分类(分类位置错放)
for d in ~/.hermes/skills/*/; do
  name=$(basename "$d")
  if [ -f "$d/SKILL.md" ]; then
    echo "$name : TOP-LEVEL SKILL(没子目录)"
  fi
done
```

## 2. System prompt skills 段实际长度(折叠前后对比)

需要 venv,在 `~/.hermes/hermes-agent` 跑:

```bash
cd ~/.hermes/hermes-agent && source venv/bin/activate && python3 << 'PY'
import sys; sys.path.insert(0, '.')
from agent.prompt_builder import build_skills_system_prompt
out = build_skills_system_prompt()
print(f'LINES: {len(out.splitlines())}')
print(f'CHARS: {len(out)}')
en = sum(1 for c in out if ord(c) < 128); zh = len(out) - en
print(f'TOK_EST: {int(en/4 + zh*1.5)}  (en {en}, zh {zh})')
PY
```

## 3. 测量折叠收益(before/after)

```python
# Save/restore DESCRIPTION.md 试折叠/展开两态
import sys, os, glob, importlib
sys.path.insert(0, '.')
from agent.prompt_builder import build_skills_system_prompt

out_a = build_skills_system_prompt()  # 当前态

# 把所有 collapsed: 注掉,模拟全展开
modified = []
for p in glob.glob(os.path.expanduser('~/.hermes/skills/**/DESCRIPTION.md'), recursive=True):
    c = open(p).read()
    if 'collapsed:' in c:
        modified.append((p, c))
        open(p, 'w').write('\n'.join(l for l in c.splitlines() if 'collapsed:' not in l))

import agent.prompt_builder as pb; importlib.reload(pb)
out_b = pb.build_skills_system_prompt()

for p, c in modified:  # 还原
    open(p, 'w').write(c)

print(f'COLLAPSED: {len(out_a.splitlines())}L / {len(out_a)}c')
print(f'EXPANDED:  {len(out_b.splitlines())}L / {len(out_b)}c')
```

## 4. 折叠收益预测公式(决定是否要折某分类)

```
折叠收益 = expanded_chars − folded_chars

expanded_chars ≈ Σ(skill.name_len + min(60, skill.desc_len) + 10) + cat_desc_len + 30
folded_chars   ≈ len(f"  {cat}: {cat_desc} (N={n} skills hidden — use skills_list(category={cat}) to list them)")
```

**决策表**:

| 情形 | 折叠? |
|---|---|
| n_skills ≥ 2 且 cat_desc 中等长(<150 字) | ✅ 折 |
| n_skills ≥ 3 不论 cat_desc 长度 | ✅ 折 |
| n_skills = 1 且 cat_desc > 80 字 | ❌ 不折(折叠后反而更长) |
| n_skills = 1 且 cat_desc < 80 字 | 🤔 折叠收益边际,可不折 |
| 顶层 SKILL.md(没子目录) | ❌ 折叠无意义 |

`mlops` 是个反例 — 顶层只有 1 个 skill(huggingface-hub),其余进了 4 个子分类。但 mlops 顶层 cat_desc 写得长(讲整个 mlops 体系),所以"折叠 1 个 skill"其实不省;真正省的是 4 个子分类各自折叠。

## 5. Token 估算口径

Anthropic / OpenAI tokenizer 大致:
- 英文 ASCII: 1 token ≈ 4 chars
- 中文: 1 char ≈ 1.5 tokens(BPE 经常一个字拆 2 个 token,有时合并)

简化估算:`tok ≈ en_chars/4 + zh_chars * 1.5`(对系统 prompt 段够用)

精确算用 `tiktoken` 库,但 Claude 用的是不同 tokenizer,只能近似。

## 6. 成本估算口径

Claude Opus 4.x 定价(2026):
- Input: $15 / MTok
- Output: $75 / MTok

System prompt 算 input。每回合都重传(不打缓存就重计费)。

Dad 日常使用 ~80 turns/day 这个估算 stable,不要乱改。

## 7. Context window 占用

Claude Opus 4.x: 200K tokens context window。

报告里说"context window 占用 X%" 时用 `tokens / 200_000 * 100`。

## 8. 历史数据(2026-06-05 这次报告)

| 指标 | 全展开 | 全折叠 | Delta |
|---|---|---|---|
| Lines | 163 | 49-50 | −113 (−69.3%) |
| Chars | 12,136 | 7,538-7,635 | −4,501~−4,598 (−37%~−38%) |
| Tokens | 4,559 | 2,958-3,043 | −1,516~−1,601 (−33%~−35%) |
| Cost/year @ 80 turns/day | — | — | $664~$701 |

数字浮动是因为画报告过程中调整了折叠策略:
- v1: 16 折叠 / 7 不折单 skill / 4 顶层 = 27 分类(原始)
- v2: 15 折叠(撤掉 mlops/research,因为它折叠反负收益) / 8 不折 / 4 顶层 = 27 分类
- v3: 把 4 顶层裸 skill 挪入对应分类 → 23 真分类 / 15 折叠 / 8 不折(更干净)

**经验**: 折叠前**一定要测 delta**,有的分类折叠会负收益(cat_desc 太长 + skill 太少)。

## 9. 顶层裸 skill 的处理决策

历史上有 4 个 skill 没分类直接放顶层(`dogfood`, `sync-skill`, `vault`, `wx-gateway-integrate`)—— 这是建 skill 时没传 `category` 参数的遗留状态。

**hermes-agent 怎么处理**: `prompt_builder.py` line ~974 把它们塞进虚拟分类 `"general"`。LLM 看到 `general:` + skills 列表。

**决策**: 现状用户偏好挪入真实分类(让顶层从 27 降到 23),但**不强制** — `skill_manage(action='create')` 的 `category` 仍是 optional。**自动生成的 skill 如果不会分类,允许顶层裸放**,会以 `general:` 出现在 system prompt。

**软链注意**: `sync-skill` / `vault` / `wx-gateway-integrate` 是 `~/.claude/skills/` 的软链(claude-code 系统也用)。挪不能 `mv`,要 `rm + ln -s` 到新位置,源不动。`dogfood` 是真目录可以 `mv`。
