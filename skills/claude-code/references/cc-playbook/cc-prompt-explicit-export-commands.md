---
name: cc-prompt-explicit-export-commands
description: 派 CC 时凭据/路径/上下文必须给现成可抄的 shell 行（`export X="$(vault get ...)"`），而不是描述性指令（"用门神取 token"）。CC 看描述性指令会视而不见，跑到一半问"找不到 token，要从哪取？"——这是 prompt 没明示 export 命令的信号。Triggers — 派 CC 任务 / CC 反问凭据 / CC 找 1Password 而非门神 / 任何"用 vault/env/config 取 X"的模糊措辞.
---

# 派 CC 凭据必须明示 export 命令

## 真实事故

派 CC 干 wx-gateway Phase A，prompt 里写：

> 凭据 = 门神 vault，禁找 1Password 禁问爸爸要 token

CC 写完代码 push commit 后停下来汇报：
> 需要 `MVP_DEPLOYER__TOKEN` 才能触发 deploy + 跑 selftest + 浏览器 E2E。Shell env / 1Password 都没找到。爸爸是导出 token 让我继续，还是自己 deploy 后让我接着跑 selftest + E2E？

CC **完全没去 vault get**——尽管 prompt 说了。原因：CC 看到「门神/vault」是名词概念不是动作指令，不会主动展开成 `vault get xxx`。

## 根因

CC 是 single-shot 看 prompt，**找具体可抄的 shell 行**，不会把"用门神"翻译成 vault get 命令。任何模糊指令 = 视而不见。

## 正确写法（直接抄进 CC prompt）

```markdown
## 凭据
**禁找 1Password / 禁问爸爸要 token**，先跑这一行：
\`\`\`bash
export MVP_DEPLOYER__TOKEN="$(vault get mvp-deployer/TOKEN)"
export ADMIN_PUBLIC_PATH="$(vault get wx-gateway/ADMIN_PUBLIC_PATH)"
export DATABASE_URL="$(vault get wx-gateway/DATABASE_URL)"
\`\`\`

后续所有命令直接用 `$MVP_DEPLOYER__TOKEN` 引用。
```

## 错误写法（CC 会忽略）

❌ 「凭据走门神 vault」
❌ 「用 vault get 取 token」
❌ 「token 在门神里」
❌ 「需要的 secret 见 `vault project show wx-gateway`」（让 CC 自己探索 = 它不会探索）
❌ 「凭据 = 门神（vault）」（名词概念，不是命令）

## 派 CC 任务前的自检清单

写 prompt 时跑一遍：

1. **任务里需要的所有外部资源**（token / DB URL / API key / admin path / endpoint URL / 邀请码）
   都列出来 ✅
2. 每个资源都给了**具体的 shell 行**而不是描述 ✅
3. shell 行可以**直接复制粘贴**到 zsh 不需要修改 ✅
4. 如果用到第三方服务（mvp-deployer / GitHub / 微信 API），明示 endpoint URL 和 auth header
   格式 ✅

## 关联 skills

- `claude-code` — CC 调用基础（含门神段，但不够明示）
- `cc-anti-procrastination-prompt` — CC 退出/反问的其他模式
- `cc-prompt-grep-and-verify` — CC prompt 的另一类强约束写法
- `vault` — 门神 CLI 用法
