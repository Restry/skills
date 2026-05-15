# CC Playbook — 派 Claude Code 时的 prompt 心法

本目录是 `claude-code` skill 的延伸 references。原本散落在 `software-development/` 的 7 条独立 skill 已合并到这里——它们不是独立任务流，而是「派 CC 时该用什么 prompt 套路 / 防什么坑」的经验集合。

加载 `claude-code` skill 时，遇到对应场景再 grep 本目录。

## 索引

| 文件 | 用途 |
|---|---|
| cc-anti-procrastination-prompt.md | 防 CC 摆烂/反问/越权/外包的 prompt 反制套路 |
| cc-frontend-e2e-pitfalls.md | 派 CC 跑 browser-agent (4821/4822) 测前端的常见坑 |
| cc-prompt-explicit-export-commands.md | 凭据/路径必须给现成可抄的 shell 行，禁描述性指令 |
| cc-prompt-grep-and-verify.md | 用「grep pattern + 机器可验收」替代「列文件 + 读 commit msg」 |
| cc-review-verify-fix-loop.md | review → verify → fix 三段式（防静态分析脑补） |
| claude-code-stepwise-refactor.md | 大型多文件 refactor 的分步派单模式 |

## 加载方式

需要时:
```python
skill_view('claude-code', file_path='references/cc-playbook/cc-anti-procrastination-prompt.md')
```
