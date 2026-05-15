# vault 主解密身份轮换 + 跨平台 key 设置

## 触发

- "换 vault 解密 key" / "rotate vault identity"
- "在新机器（mac / Linux / Windows）上接入 vault"
- "我换了一台机，怎么解 vault？"
- 旧 key 怀疑泄露

## 0. 当前架构（2026-05-15 后）

| 项 | 值 |
|---|---|
| Key 类型 | ssh-ed25519，**无 passphrase** |
| 默认路径 | `~/.ssh/vault_id_ed25519` |
| Recipients 文件 | `~/.vault/store/.age-recipients` |
| 加密工具 | `age` |
| Agent 兼容性 | ✅ 完全自动（无需 ssh-agent / 无需 tty） |

**为什么无 passphrase**：
1. `age` 不会查询 ssh-agent——SSH key 有 passphrase 就强制 tty，agent 进程跑不了
2. macOS Keychain 方案对所有用户态进程开放，安全等价于无 passphrase
3. 跨平台一致（mac / Linux / Windows-WSL 都同一套）
4. 笔电 FileVault / Linux LUKS / Windows BitLocker 已是叠 buff

**真正的纵深防御**走 per-machine recipients（每台一对 key，全部 pubkey 都加进 recipients），不是 passphrase。

## 1. 跨平台新机器接入（最常见场景）

### macOS / Linux

```bash
# 1. 装 age
brew install age          # mac
sudo apt install age      # debian/ubuntu

# 2. 装 vault CLI（从主机器拷或者拉打包文件，参考 cross-machine-bootstrap.md）

# 3. 生成本机 key
ssh-keygen -t ed25519 -f ~/.ssh/vault_id_ed25519 -N '' -C "vault-$(hostname)-$(date +%Y%m%d)"
chmod 600 ~/.ssh/vault_id_ed25519

# 4. 把本机 pubkey 发给主机器持有人
cat ~/.ssh/vault_id_ed25519.pub
```

主机器执行 [节 3](#3-加新机器到-recipients并重加密) 把这个 pubkey 加进 recipients 并重加密。

```bash
# 5. clone vault-data repo
mkdir -p ~/.vault && cd ~/.vault
git clone git@github.com:<owner>/vault-data.git store

# 6. 验证
vault get _global/TAVILY_API_KEY   # 应该秒回真值
```

### Windows（推荐 WSL2）

WSL 里走上面 Linux 流程。原生 Windows 走 git-bash + scoop 装 age，但 hermes/CC 在 Windows 上一般通过 WSL 跑，没必要做原生方案。

### 服务器 / 容器（无人值守）

1. 在服务器上 `ssh-keygen` 生成 key（永远本机生成，禁止从笔电拷）
2. pubkey 发给主机器加 recipients
3. clone repo → `vault get` 验证
4. 如果 image 化部署，key 通过 secret manager（k8s secret / docker secret）注入到 `~/.ssh/vault_id_ed25519`，**不入镜像**

## 2. macOS 特殊：ssh-agent + Keychain（已废弃）

**不再使用**。如果你看到老文档说"`ssh-add --apple-use-keychain`"，那是带 passphrase 的旧方案。新方案 key 无 passphrase，agent 直接读文件。

如果 `~/.ssh/vault_id_ed25519` 还有老 passphrase 残留：

```bash
# 去除 passphrase（交互输入旧 passphrase，新设为空）
ssh-keygen -p -f ~/.ssh/vault_id_ed25519 -N ''
```

## 3. 加新机器到 recipients 并重加密

主机器执行：

```bash
NEW_PUB="ssh-ed25519 AAAA... vault-newmachine"
echo "$NEW_PUB" >> ~/.vault/store/.age-recipients

# 解密所有文件 + 用新 recipients 重加密
cd ~/.vault/store
mkdir -p /tmp/vault-redo
find . -name "*.age" -not -path "./.git/*" | while read f; do
  rel="${f#./}"
  out="/tmp/vault-redo/$rel"
  mkdir -p "$(dirname "$out")"
  age -d -i ~/.ssh/vault_id_ed25519 "$f" > "$out"
done

find . -name "*.age" -not -path "./.git/*" | while read f; do
  rel="${f#./}"
  age -R .age-recipients -o "$f" < "/tmp/vault-redo/$rel"
done

shred -uz /tmp/vault-redo/*/*.age 2>/dev/null; rm -rf /tmp/vault-redo

git add -A && git commit -m "add recipient: <newmachine>" && git push
```

新机器 `cd ~/.vault/store && git pull` 即可解开所有 secret。

## 4. 完整轮换主 key（怀疑泄露 / 周期性安全更新）

如果**主 key 本身**要换（不是加新机器），步骤同节 3，但额外做：

```bash
# 0. 备份
tar -czf ~/vault-backup-$(date +%s).tar.gz ~/.vault/store

# 1. 备份旧 key（解密老备份用）
mv ~/.ssh/vault_id_ed25519 ~/.ssh/vault_id_ed25519.old.bak
mv ~/.ssh/vault_id_ed25519.pub ~/.ssh/vault_id_ed25519.old.bak.pub

# 2. 生成新 key
ssh-keygen -t ed25519 -f ~/.ssh/vault_id_ed25519 -N '' -C "vault-$(date +%Y%m%d)"

# 3. 替换 .age-recipients（新 pubkey 单条，或加上其他机器的 pubkey）
cat ~/.ssh/vault_id_ed25519.pub > ~/.vault/store/.age-recipients

# 4. 解 + 重加密（用 .old.bak 做 -i 解，新 recipients 重加密）
cd ~/.vault/store
mkdir -p /tmp/vault-redo
find . -name "*.age" -not -path "./.git/*" | while read f; do
  rel="${f#./}"
  out="/tmp/vault-redo/$rel"
  mkdir -p "$(dirname "$out")"
  age -d -i ~/.ssh/vault_id_ed25519.old.bak "$f" > "$out"
done
find . -name "*.age" -not -path "./.git/*" | while read f; do
  rel="${f#./}"
  age -R .age-recipients -o "$f" < "/tmp/vault-redo/$rel"
done
shred -uz /tmp/vault-redo/*/*.age 2>/dev/null; rm -rf /tmp/vault-redo

# 5. 验证
vault get _global/TAVILY_API_KEY    # 应秒回

# 6. push
git add -A && git commit -m "rotate: new identity $(date +%Y%m%d)" && git push

# 7. 通知所有持有 vault 副本的机器：本机重做节 3 流程发新 pubkey
```

## 5. 历史：为什么不用 passphrase / Keychain / expect

之前尝试过的方案 + 失败原因：

| 方案 | 失败原因 |
|---|---|
| ssh key + passphrase + ssh-agent | age 不查 ssh-agent，强制 tty |
| ssh key + passphrase + expect 包装 | 每次 fork pty 慢、hermes agent shell 无 tty |
| native age key 文件 + macOS Keychain 存 key | 跨平台炸（Linux/Windows 各自 keystore），安全等价于明文 |
| ssh key + passphrase + macOS Keychain | 同上，且 vault wrapper 要写 OS 分支 |

**结论**：纵深防御走 per-machine recipients，不要在单机 key 上加密码学防护。

## 6. Pitfalls

1. **禁止跨机拷 key**：每台机一对，破解面隔离
2. **新 key 必须本机 keygen**：不要从主机器 `scp` 私钥
3. **重加密前必备份**：`tar -czf ~/vault-backup-$(date +%s).tar.gz ~/.vault/store`
4. **重加密后必验证**：`vault get` 一个已知 key 看真值
5. **`.age-recipients` 是 secret 等级 0**：进 git，公开（pubkey 而已）
6. **私钥永不入 git**：`~/.ssh/vault_id_ed25519` 在 `~/.ssh/` 下，跟 vault repo 无关
7. **rotate 后通知所有持有者**：否则其他机器下次 `git pull + vault get` 全炸
