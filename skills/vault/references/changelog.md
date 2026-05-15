# vault — Changelog & Roadmap

## 当前状态（2026-05-02 v2 升级后）

- ✅ **225 条 secret / 20 项目**（v2 新增 71 条 + 7 新项目）
- ✅ **元数据 v2**: 每条 secret 含 `desc/vendor/severity/where_to_get/category/tags`
- ✅ **项目元数据**: `[_project.<name>]` 段含 `desc/aliases/stack/domain/repo/local_path/deploy/app_slug/wechat_app/status`
- ✅ **冲突拆分**: prod 默认无后缀，多环境用 `__dev`/`__test`/`__remote`/`__local` 后缀
- ✅ 153 条原有 secret 保留
- ✅ GitHub `Restry/vault-data` private repo 同步中
- ✅ CLI 在 `/usr/local/bin/vault`，源 `~/.vault/bin/vault`
- ✅ Smoke test 全通（add/get/list/meta/show/list -t）
- ✅ **1Password 已弃用**；vault 是唯一真实来源
- ⏳ 各项目仓库的 `.env` / `~/.credentials/.env` / `~/.zshrc` 中的明文 key 退役

## 已巡检项目

- ✅ **bnef** (2026-05-01) — 30 条
- ✅ **全 vault 5 维 tag 批量补全** (2026-05-02) — 108 条补 type/vendor/scope
- ✅ **schema 重构** (2026-05-02) — image-studio-test 合并到 image-studio 用 __test 后缀
- ⏳ cspy / packhorizon / packsmith / image-studio / wx-gateway / nexora_wx_gw / echo

## Roadmap

### 短期
- [ ] **vault reencrypt** 命令（recipient 改了批量重加密）
- [ ] **vault rotate <key>** 命令：自动生成新值 + 调外部服务 update API
- [ ] **vault history <key>**：基于 git log 看变更历史
- [ ] **vault audit**：列长期未轮换 / 未引用的 key
- [ ] **vault edit**：在 $EDITOR 里改

### 中期
- [ ] **CLI v2 用 Go 重写**：单二进制、`--strict` 模式、TUI 选 item（fzf）、shell completion
- [ ] **mvp-deployer 集成**：每个项目一份 `manifest.tpl.json` 模板，部署脚本自动 `vault inject`
- [ ] **退役 `~/.credentials/.env`**：备份 + 删除
- [ ] **CLI 推到 vault-data repo bin/**，新机器一行 curl 装

### 安全增强
- [ ] **Passphrase 二次加密私钥**（防 GitHub 仓库被脱）
  - `age -p` 加密 `~/.vault/key.txt` → `key.txt.age`，提交进 vault-data repo
  - 删本地明文 key.txt（先备份）
  - `vault unlock` 子命令解出来留本机，本机被偷靠 FileVault 兜底
  - 工作量 15 分钟，密码 16+ 位高熵存 1Password
