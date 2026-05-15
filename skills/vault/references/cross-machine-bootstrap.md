# vault 跨机器初始化（打包式同步）

## 0. 触发

- 「把门神/vault 技能传到 X 机」
- 「另一台 hermes 也装个门神」
- 「给 235/新服务器 部署 vault」

不适用：同一台机的 vault 日常使用（用主 `vault` skill）。

## 1. 核心原则：身份 ≠ 工具

vault 体系包含 **3 类东西**，跨机器同步只能传第 ① 类：

| 类型 | 内容 | 是否跨机传 |
|---|---|---|
| ① 工具 + 文档 | CLI 二进制(515 行 bash)、scripts/、hooks/、SKILL.md | ✅ 直接拷 |
| ② 身份 | `~/.vault/key.txt` (age 私钥)、GitHub repo owner/name | ❌ **必须目标机自建** |
| ③ 数据 | secret 内容（`~/.vault/store/` 里加密的 .age 文件） | ❌ **目标机有自己的 store** |

**铁律**：**不能** `scp ~/.vault/key.txt` 到另一台机。age key 一台一对，跨机复用 = 一台被脱全部沦陷。

## 2. 打包脚本（打包机）

```bash
PKG=/tmp/vault-skill-pkg
rm -rf $PKG && mkdir -p $PKG/skill-files $PKG/install-files

# ① SKILL.md 脱敏（owner/repo 名替换成占位符）
cp ~/.hermes/skills/devops/vault/SKILL.md $PKG/skill-files/SKILL.md
sed -i '' \
  -e 's|<YOUR_GH_OWNER>/<YOUR_REPO>|<YOUR_USER>/<YOUR_VAULT_REPO>|g' \
  -e 's|git@github.com:<YOUR_GH_OWNER>/<YOUR_REPO>|git@github.com:<YOUR_USER>/<YOUR_VAULT_REPO>|g' \
  $PKG/skill-files/SKILL.md
# 注意：泛指词（"vault-data repo"作普通名词）不必替换

# ② 写 SETUP.md（新机器从零步骤，本 skill 的 templates/setup-md-template.md 有现成模板）

# ③ 工具 + scripts + hooks
cp ~/.vault/bin/vault            $PKG/install-files/vault
cp ~/.vault/scripts/health-check.py $PKG/install-files/
cp ~/.vault/hooks/post-write.sh  $PKG/install-files/
cp ~/.vault/hooks/regen-snapshot.py $PKG/install-files/

# ④ 验证脱敏
grep -E "实际 owner名|实际 repo名" $PKG/skill-files/SKILL.md && echo "❌ 还有真名" || echo "✅ 脱敏"

# ⑤ 打包
cd $PKG && zip -r ~/vault-skill-package.zip skill-files install-files
```

## 3. SETUP.md 必含 6 步（给目标机的指南）

1. **装依赖** — `age + git`（Linux: `apt install`，macOS: `brew`）
2. **装 CLI** — 拷 vault/scripts/hooks 到 `~/.vault/`，软链 `/usr/local/bin/vault`
3. **生 age key** — `age-keygen -o ~/.vault/key.txt && chmod 600`，**禁复用任何其他机的 key**
4. **建 GitHub 私有 repo** — `gh repo create $OWNER/$REPO --private`，**禁复用别的机的 repo**
5. **init store** — clone/init repo + 写 `.vault/recipients.txt` + 装 git hook
6. **自检** — `vault put test/X "y" && vault get test/X && vault rm test/X -y`

## 4. SCP + 给目标机的初始化 prompt 模板

```bash
sshpass -p '<密码>' scp -o StrictHostKeyChecking=no \
  ~/vault-skill-package.zip user@host:~/vault-skill-package.zip
```

prompt 给目标机 hermes/CC（**完整复制可执行**版）见 `templates/target-machine-prompt.md`。
关键点：
- 必含 `gh auth status` 检查（先确认用哪个 GitHub 账号——可能不是爸爸的 Restry）
- 必含「卡住先停问爸爸」铁律（特别是 repo 命名 + 账号归属）
- 必让目标机回贴 5 项：vault --help、本机 age public key、repo URL、自检 round-trip 输出、health-check 末尾

## 5. 多机互通（可选，目标机配好后）

如果想让两台机都能解同一份 secret（比如部署机 + 开发机共享）：

```bash
# 在 vault-data repo 的 .vault/recipients.txt 里加目标机的 public key
echo "$TARGET_PUBKEY" >> .vault/recipients.txt
git commit -am "add recipient: <hostname>"

# 重新加密所有 secret 让新 recipient 也能解
vault reencrypt --all
git push
```

本次任务不涉及（爸爸明确说目标机自建独立 vault），但要让目标机将来能"跟爸爸 Mac 共享密钥"就走这步。

## 6. 已踩的坑

- **不能直接 rsync `~/.vault/`** — 会把 key.txt 一起推过去，等同于把家里钥匙寄给路边
- **不能 clone 现有 vault-data repo 当本机 store** — recipients 不含目标机 pubkey，目标机解不开（看着像 git 同步成功但 vault get 全失败）
- **`gh repo create` 未指定 owner 时默认用当前 `gh auth` 账号** — 可能不是爸爸期望的 owner，必须先 `gh auth status` 确认或 `--owner` 显式指定
- **SKILL.md 脱敏时**：泛指词（"vault-data repo"）不要替换，只替换实际 owner/repo 名（如 `Restry/vault-data` → 占位符）

## 相关 skills

- `vault` — 主 skill，日常使用
- `hermes-skills-cross-machine-sync` — `~/.hermes/skills/` 跨机同步规则（rsync `--delete` 铁律），跟本 skill 互补
- `code-map` 「Linux 远端装 gitnexus」章节 — 同类「跨机器装专门工具」经验
