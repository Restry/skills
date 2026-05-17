# mvp-deployer 管理员维护手册

> ⚠️ **普通 agent 不要看这份文件**。这里全是 SSH `claw@163.228.243.161` 的命令，前提是你本机有那台机的 SSH key。普通 agent 没有，照抄也跑不动；正确做法是用 `/api/exec` + `/api/deploy`（见主 SKILL.md §3）。
>
> 这份只给 deployer 作者本人（Daddy）维护时翻。

---

## 1. 更新 deployer 自身（rsync 上线流程）

```bash
cd ~/projects/mvp-deployer
# 改完 commit 后
rsync -az --delete \
  --exclude='node_modules' --exclude='.git' --exclude='public/uploads' \
  --exclude='data' --exclude='*.log' --exclude='.credentials' \
  ./ claw@163.228.243.161:/opt/mvp-deployer/
ssh claw@163.228.243.161 'pm2 restart mvp-deployer && pm2 status mvp-deployer'
```

改了 `ecosystem.config.js` 或启动 env 逻辑用 `pm2 delete + pm2 start ecosystem.config.js` 代替 restart（restart 不重读 env，token 会退到默认 fallback 导致 API 401）。

⚠️ **加新 ecosystem env 字段时（不只是 rotate 已有 key）**：光 `pm2 delete + pm2 start` 还不够。PM2 会跟 `~/.pm2/dump.pm2` 缓存的旧 env 合并，新加的 key 进程里拿到 `undefined`。必须叠 `--update-env`：

```bash
set -a; source ~/.credentials/.env; set +a
pm2 delete mvp-deployer
pm2 start ecosystem.config.js --update-env   # ← 关键
pm2 save
```

验证：`PID=$(pm2 jlist | jq '.[]|select(.name=="mvp-deployer").pid'); sudo cat /proc/$PID/environ | tr '\0' '\n' | grep <NEW_KEY>=` 必须看到值。2026-05 加 IP_ALLOWLIST / AUDIT_READ_TOKEN / TRUST_PROXY 时踩过：第一次没 `--update-env`，进程 env 全空，白名单形同虚设（任何 IP 都能调通）。

🔥 **铁律**：deployer 自身**只能** ssh+rsync+`pm2 delete && pm2 start`。**禁止把 mvp-deployer 当普通 app 通过平台自部署**——会污染 `/opt/mvp-apps/`、`tasks.json` 留垃圾、PM2 中途 kill 自己导致 task 死锁。

误操作清理：
```bash
ssh claw@163.228.243.161 'rm -rf /opt/mvp-apps/mvp-deployer && pm2 restart mvp-deployer'
# 然后手动从 /opt/mvp-deployer/data/tasks.json 里删 project=="mvp-deployer" 的记录
```

## 2. Skill 分发唯一来源：sync-skill

mvp-deployer 项目仓库不再内置 `skill/` 目录或根 `SKILL.md`，运行时也不再提供 `/skill.zip` / `/install-instruction`。

主 skill 改完只更新 Hermes 本地这一份，然后发布到 sync-skill 仓库：

```bash
python3 ~/.hermes/skills/sync-skill/scripts/publish.py \
  ~/.hermes/skills/devops/mvp-deployer \
  -m "publish mvp-deployer"
```

不要恢复“三份 SKILL.md 同步”的旧模式。

## 3. 平台层故障（API 解决不了的）

| 症状 | 命令 |
|---|---|
| Deployer API 401 (改了 ecosystem 后) | `ssh claw@... 'pm2 delete mvp-deployer && pm2 start /opt/mvp-deployer/ecosystem.config.js && pm2 save'` |
| 端口 9800 EADDRINUSE（deployer 自己崩） | `ssh claw@... 'sudo fuser -k 9800/tcp; sleep 1; pm2 restart mvp-deployer'` |
| 🔥 root pm2 影子守护抢端口 | `ssh claw@... 'sudo pm2 delete all && sudo pm2 kill'`（`fuser -k` 治标，daemon 几分钟复活） |
| EACCES 写 `/tmp/mvp-uploads` 或 `/opt/mvp-apps/<x>` | `ssh claw@... 'sudo chown -R claw:claw /tmp/mvp-uploads /opt/mvp-apps/<project>'` |
| SQLite `SQLITE_READONLY` (data/ 被 root 覆盖) | `ssh claw@... 'sudo chown -R claw:claw /opt/mvp-apps/<project>/data && pm2 restart <project>'`（预防：zip 时 `-x 'data/*'`） |
| Caddy `duplicate ID 'mvp-route-<x>'` | 见 `references/caddy-recovery.md` |

诊断快查：
- 端口属主：`ssh claw@... 'lsof -i :<port>'` —— USER 列是 root 就是影子守护
- PM2 状态：`ssh claw@... 'pm2 list && pm2 logs <name> --lines 50 --nostream'`

## 4. 安全 Checklist（每次改主 SKILL.md 必跑）

- [ ] 文档里没有任何 token / API key / 密码（包括示例代码里的占位）
- [ ] 凭据只走 `~/.credentials/.env` 的 `MVP_DEPLOYER__TOKEN` 或 legacy `~/.credentials/mvp-deployer.env` 的 `DEPLOYER_TOKEN`
- [ ] 项目仓库没有重新引入 `skill/`、根 `SKILL.md`、`/skill.zip` 或 `/install-instruction`
- [ ] skill 更新后已通过 `sync-skill` 发布：
  ```bash
  python3 ~/.hermes/skills/sync-skill/scripts/publish.py ~/.hermes/skills/devops/mvp-deployer -m "publish mvp-deployer"
  ```
- [ ] 指纹扫描无泄漏：
  ```bash
  grep -RIf ~/.credentials/secret-fingerprints.txt ~/.hermes/skills/devops/mvp-deployer \
    && echo "❌ LEAK" || echo "✅ clean"
  ```
- [ ] `~/projects/mvp-deployer/.credentials` 已在 `.gitignore`
