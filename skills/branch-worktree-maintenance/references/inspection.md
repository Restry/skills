# 只读命令与核对方法

本文只提供盘点方法，不执行清理。授权、安全门和阈值以 `../SKILL.md` 为准；该相对路径以本文件所在目录解析。

## 仓库定位

1. 从技能所在目录向上找到前端 Git 工作区，使用 `git rev-parse --path-format=absolute --git-common-dir` 定位共享元数据。
2. 对 GemFlow 的非 bare 标准布局，Git common dir 是前端主目录的 `.git`，其父目录才是前端主目录。不要把当前 linked worktree 当作主目录。
3. 后端默认是这个主目录同级的 `GemFlow-Services`。验证它是独立 Git 仓库，有本地 `dev`；布局不符则使用用户指定位置，不猜其他仓库。
4. 将 `R` 设置为正在检查的主仓库绝对路径，`WT` 设置为从 Git 注册记录取得并核实的 worktree 绝对路径，`P` 为仓库内相对路径。下列变量必须先赋值，不复制历史会话中的机器路径。

## 分支与注册目录

```bash
git -C "$R" for-each-ref --format='%(HEAD) %(refname:short) | %(objectname:short) | %(worktreepath)' refs/heads/
git -C "$R" worktree list --porcelain -z
git -C "$R" rev-parse --verify refs/heads/dev
```

逐个本地分支使用完整引用，避免把远程分支或特殊参数混进检查：

```bash
git -C "$R" merge-base --is-ancestor "refs/heads/$BRANCH" refs/heads/dev
git -C "$R" rev-list --count "refs/heads/dev..refs/heads/$BRANCH"
```

`merge-base` 返回 0 是已包含，1 是未包含，其他退出码是错误。`rev-list` 的 0 仅说明没有独有提交。未提交内容、忽略文件和是否仍有人使用，都不由这两个结果决定。

## 创建时间

分支创建时间取分支 reflog 最早一条（通常是 `branch: Created from …`）；worktree 创建时间取目录 birth time，并与 `.git/worktrees/<名>` 管理目录 birth time 互证：

```bash
git -C "$R" reflog show "refs/heads/$BRANCH" --format='%ct|%gs' | tail -1
stat -f '%SB' -t '%Y-%m-%d %H:%M' "$WT"
NAME=$(sed -n 's|^gitdir: .*/worktrees/||p' "$WT/.git")
stat -f '%SB' -t '%Y-%m-%d %H:%M' "$R/.git/worktrees/$NAME"
```

判读规则：

- reflog 有保留期；首条缺失时报告“无 reflog”，用分支名日期后缀与首个独有提交时间作估计并标注。
- worktree 内 HEAD reflog 的时间戳可能早于目录 birth time，git 状态会从更早的位置或会话延续过来；两层证据一致时，目录 birth time 才是当前路径上 worktree 的真实创建时间，不一致时分别如实报告。
- `.git/worktrees/` 下 `backend1`、`frontend2` 这类编号是 basename 冲突的自动编号，反映创建先后，不是重建。
- 目录 mtime 不是创建时间，也不作为最后使用时间（见下节）。

## 工作区差异

```bash
git -C "$WT" status --porcelain=v1 -z --untracked-files=all
git -C "$WT" diff --cached --name-status -z
git -C "$WT" diff --name-status -z
git -C "$WT" ls-files --others --exclude-standard -z
git -C "$WT" ls-files --others --ignored --exclude-standard --directory -z
```

程序解析必须使用 NUL 分隔，正确处理重命名的两个路径；不要按空格拆分文件名。命令失败不能当作干净。忽略目录先只列路径，不递归输出 `.env`、密钥或业务文件内容。

对 Git 可见的每个变化路径检查：

```bash
git -C "$R" ls-tree refs/heads/dev -- "$P"
git -C "$WT" diff refs/heads/dev -- "$P"
git -C "$R" log -5 --format='%h %ad %s' --date=iso-strict refs/heads/dev -- "$P"
```

- `git diff dev` 同时包含“旧 worktree 缺少 dev 新内容”的差异，不代表所有差异都是待合并工作。
- 普通文件：读取 dev 的 blob（`git show "refs/heads/dev:$P"`）与工作区实际字节比较，另核对 `ls-tree` 的文件类型和可执行位。不要仅与该 worktree 的旧 HEAD 比。
- 符号链接：比较链接目标字符串，不沿链接读取主目录依赖。缺失路径要区分真实删除与断链。
- 未跟踪文件：`git diff` 不包含它，必须单独检查。如果 dev 有同路径 blob，按内容和类型比较；否则检查主工作区是否另有同内容副本，并明确其仍未提交。
- 要判断“只是旧版”，结合工作区 HEAD → 工作区内容、该 HEAD → dev 的变化及对应提交。证据不足就保留，不能仅凭文件看起来相似作结论。

## 空间统计

```bash
du -sk "$WT"
```

从 Git 注册清单选择所有额外 worktree，排除两个核实的主目录；分别执行以上命令，将结果的 KiB 整数相加。只接受退出码 0 且路径存在的测量，报错时合计为不完整。

- `MiB = KiB / 1024`，`GiB = KiB / 1048576`。
- `totalKiB > 1048576` 才超过阈值。
- 不加 `-L`，不追随 `node_modules` 等链接；不另加链接目标的大小。
- 解释构成时先判断依赖／构建路径是否符号链接。实体目录可再 `du -sk`，但这些是总量的组成，不重复累加。
- 同一 worktree 不因被两个输入别名引用而重复计数。规范化路径并按 Git common dir 对仓库去重。

## 年龄、活动与清理前证据

```bash
git -C "$WT" reflog show -1 --format='%ct %gs' HEAD
git -C "$WT" log -1 --format='%ct %h %s' HEAD
```

有真实使用／任务结束记录时优先用它；以上时间只能作为排序代理，不能宣称是最后使用时间。不要把本次扫描时间写回所有 worktree 的使用时间。

活动核对需要同时考虑当前会话、其他开发者／Agent 的任务归属和进程。可在本机检查相关进程的 cwd 与命令；输出只保留 PID、路径和结论，遮蔽命令行中的凭据。仅凭没有打开文件或进程 cwd 不在目录内，不能证明没有 Agent 正通过绝对路径写文件。

清理前记录至少包含：主仓库、规范化 worktree 路径、分支与 HEAD、本地 dev HEAD、完整 Git 状态、忽略路径检查结果、大小、年龄依据、任务已结束证据以及备份位置（如有）。再次检查状态是否变化后，才进入 `SKILL.md` 的移除步骤。

## 全量清理：占用核查与未提交内容备份

用户明确授权全量清理（`SKILL.md` 第 6 节）时使用。

占用核查（每个目录移除前重跑）：

```bash
lsof +D "$WT"                         # 任何打开文件都算占用
ps -p $PID -o pid,ppid,lstart,command # 查明占用者身份与启动时间
```

shell 的 cwd 停在目录内（其他 Agent 会话）也视为占用；归属不明按占用处理，跳过并报告。

脏 worktree 备份（先于任何 `--force`，备份放在所有待删 worktree 之外，权限 700）：

```bash
git -C "$WT" diff --binary --cached > "$BK/$NAME/staged.patch"
git -C "$WT" diff --binary > "$BK/$NAME/unstaged.patch"
git -C "$WT" ls-files --others --exclude-standard -z | while IFS= read -r -d '' f; do
  case "$f" in
    *node_modules*) ;; # 依赖不备份，写入 info 记录
    *) mkdir -p "$BK/$NAME/untracked/$(dirname "$f")"; cp -p "$WT/$f" "$BK/$NAME/untracked/$f" ;;
  esac
done
# 忽略文件中的非依赖内容：与主工作区逐字节一致可不备（记录写明），有差异必须备份
diff -rq "$MAIN/public/manual" "$WT/public/manual" >/dev/null 2>&1 || cp -Rp "$WT/public/manual" "$BK/$NAME/public-manual
```

每个备份目录写 info（worktree、分支、HEAD、时间、状态条目数、跳过的依赖）与 `shasum -a 256` 校验清单。单份 diff 不保存未跟踪文件，diff 与实际内容两者都要。备份完成不等于跳过逐目录复查；`--force` 前仍按 `SKILL.md` 复查合入状态与占用。
