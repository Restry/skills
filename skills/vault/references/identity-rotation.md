# vault — 换主解密身份 (rotate identity)

**踩过的坑** (2026-05-15)：旧 ssh-rsa 无 passphrase → 新 ed25519 带 passphrase。

## 死结：age + SSH key passphrase + 非交互

- `age -d -i ~/.ssh/key_with_passphrase` 必须从 **/dev/tty** 读 passphrase
- env / stdin / SSH_ASKPASS 全部不行
- ssh-agent 在 hermes execute_code sandbox 里没法 ssh-add（"Could not open a connection"）

## 解法：用 macOS 自带 `expect` 包装

```tcl
# /tmp/age_decrypt.exp
set timeout 30
set passphrase [lindex $argv 0]
set keyfile [lindex $argv 1]
set infile [lindex $argv 2]
set outfile [lindex $argv 3]
spawn age -d -i $keyfile -o $outfile $infile
expect {
    "Enter passphrase" { send "$passphrase\r"; exp_continue }
    eof
}
catch wait result
exit [lindex $result 3]
```

## 完整流程

```bash
# 1. 备份
tar -czf ~/vault-backup-$(date +%s).tar.gz -C ~ .vault/store

# 2. 生成新 key (ed25519 比 rsa 强且短)
ssh-keygen -t ed25519 -f ~/.ssh/vault_id_ed25519 -N "PASSPHRASE" -C "vault-YYYY-MM-DD"

# 3. 替换 .age-recipients (只留新公钥，旧的删除)
cat ~/.ssh/vault_id_ed25519.pub > ~/.vault/store/.age-recipients

# 4. 批量重加密 (旧 key 解 → 新 recipients 加密)
#    旧 key 无 passphrase 直接 age -d；否则也要 expect 包装
for f in ~/.vault/store/**/*.age:
    plaintext = age -d -i ~/.ssh/id_rsa
    new = age -R ~/.vault/store/.age-recipients -o $f.new
    mv $f.new $f

# 5. 验证：新 key 能解，旧 key "no identity matched"
expect /tmp/age_decrypt.exp PASSPHRASE ~/.ssh/vault_id_ed25519 some.age /tmp/v.bin
age -d -i ~/.ssh/id_rsa some.age  # 应失败

# 6. 改 vault CLI 默认 identity (~/.vault/bin/vault 第 9 行)
sed -i '' 's|id_rsa|vault_id_ed25519|' ~/.vault/bin/vault

# 7. commit + push
cd ~/.vault/store && git add -A && git commit -m "rotate identity" && git push
```

## 用户必须手动做一次（agent 做不了）

```bash
# 在正常 Terminal (有 TTY) 跑：
ssh-add --apple-use-keychain ~/.ssh/vault_id_ed25519
# 输入 passphrase
# 之后 vault 命令自动通过，passphrase 永久存 macOS Keychain
```

## 多机同步

- 235/其他 Linux 机：复制新私钥 `vault_id_ed25519` 过去 + `ssh-add` 加 passphrase
- 旧 `~/.ssh/id_rsa` **保留文件**（用户要求），但已从 recipients 移除

## 速度

- 413 文件重加密 ~27 秒（subprocess 串行）
- 无需关 hook（git 操作在 store/，hook 在 store/.git/hooks 或 ~/.vault/hooks）

## 反模式

- ❌ 试图 ssh-add 在 sandbox 里 → "Could not open a connection to your authentication agent"
- ❌ SSH_ASKPASS + DISPLAY → ssh-add 不调用，age 也不识别
- ❌ pip install pexpect → macOS PEP 668 拦截
- ✅ macOS 自带 `expect`，免装直接用
