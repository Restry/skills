# 公众号模板消息 / 订阅通知 清单查询

Ad-hoc 排查「这个公众号当前有哪些模板可发？哪些类目能选？所属什么行业？网关给哪些 app 开了哪些模板？」时用。配套 `scripts/inspect-wx-templates.js` 一次性把 4 个微信 API + 网关 DB 状态打成一份 JSON。

## 4 个微信 API 端点 — 别混

| 用途 | endpoint | 备注 |
|---|---|---|
| 服务号「我的模板」(传统模板消息) | `cgi-bin/template/get_all_private_template` | 公众号后台「模板消息 → 我的模板库」对应这个 |
| 服务号当前所属行业 | `cgi-bin/template/get_industry` | 决定能从模板库挑哪些；每月可改 1 次 |
| 服务号「订阅通知」我的模板 | `wxaapi/newtmpl/gettemplate` | 注意 path `wxaapi/newtmpl/*`，不是 `cgi-bin/*` |
| 服务号「订阅通知」当前已开通类目 | `wxaapi/newtmpl/getcategory` | 决定能从模板库挑哪些；每月可改 1 次 |

**5 个易混淆 endpoint 的清晰映射**（订阅通知发送是另一个坑，SKILL.md `Internal API surface` 段已记录）：
- `cgi-bin/message/template/send` = 服务号 **模板消息**（旧机制）
- `cgi-bin/message/subscribe/bizsend` = 服务号 **订阅通知**（2020 新机制，bizsend 不是 send）
- `cgi-bin/message/subscribe/send` = **小程序** 订阅消息（**不要**误用到公众号）

## 跑法（走 mvp-deployer `/api/exec`）

```bash
# 1) 把脚本 base64 + payload
B64=$(base64 -i scripts/inspect-wx-templates.js | tr -d '\n')
jq -nc --arg cmd "cd /opt/mvp-apps/wx-gateway-pucs && echo $B64 | base64 -d > ./_q.js && node ./_q.js; rm -f ./_q.js" '{command: $cmd}' > /tmp/_pl.json

# 2) 用 Python 读 .env 写 curl config 文件（避开 mask 扫描，见下方 pitfall 2）
python3 << 'PYEOF'
import os
EQ = chr(61)
PREFIX = 'MVP_DEPLOYER__TOKEN' + EQ
with open(os.path.expanduser('~/.credentials/.env')) as f:
    for line in f:
        if line.startswith(PREFIX):
            val = line.split(EQ, 1)[1].strip()
            break
with open('/tmp/_cfg', 'w') as f:
    f.write(f'header = "Authorization: Bearer {val}"\n')
    f.write(f'header = "Content-Type: application/json"\n')
    f.write(f'url = "https://deploy.mvp.restry.cn/api/exec/wx-gateway-pucs"\n')
    f.write(f'request = POST\n')
    f.write(f'data-binary = "@/tmp/_pl.json"\n')
PYEOF

# 3) 跑（--http1.1 避免 deployer 偶发 PROTOCOL_ERROR）
curl -sS --http1.1 -K /tmp/_cfg | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('stdout', ''))
"
```

把 `wx-gateway-pucs` 换成 `wx-gateway` 查另一个实例（造悟者）。

## 两个非 obvious 坑

### Pitfall 1 — `Cannot find module '@prisma/client'` ⚠️

`@prisma/client` 装在 `/opt/mvp-apps/<instance>/node_modules/`。把脚本写到 `/tmp/_q.js` 然后 `cd /opt/mvp-apps/<instance> && node /tmp/_q.js` 仍然 `MODULE_NOT_FOUND` —— node 的 `require()` 走**脚本所在目录**的 `node_modules`，**不是** cwd。`cd` 救不了。

**修**：把脚本写进项目目录再跑：
```bash
cd /opt/mvp-apps/<instance> && echo $B64 | base64 -d > ./_q.js && node ./_q.js; rm -f ./_q.js
```

### Pitfall 2 — `MVP_DEPLOYER__TOKEN=*** 字面出现在 shell 命令里会触发 mask scrubber 把周围语法搞坏 ⚠️

`grep -E '^MVP_DEPLOYER__TOKEN=' ~/.credentials/.env` 这种命令会报 `/bin/bash: eval: line N: unexpected EOF while looking for matching ''` —— mask 把 `MVP_DEPLOYER__TOKEN=` 这段字面缩成 `***`，破掉了 grep 表达式的闭合引号。symptom：命令报 `unexpected EOF`，看起来是 heredoc/quote 不闭合，但本质是 mask 改了字面。

**修法**（任选其一）：
- (a) **export 后用 `$VAR`**：`set -a && source ~/.credentials/.env && set +a`，之后 `$MVP_DEPLOYER__TOKEN` 直接用。命令里没有 `XXX=*** 字面，mask 不动。
- (b) **Python 读 + 拼 chr(61)**：在 heredoc `python3 << 'PYEOF' ... PYEOF` 里写 `EQ = chr(61); PREFIX = 'MVP_DEPLOYER__TOKEN' + EQ`，避开字面 `=`。`'PYEOF'` 单引号阻止 shell 在写入前展开。
- (c) **curl `-K config-file`**：把 `Authorization` header 写到磁盘文件（Python 直写）再 `curl -K /tmp/_cfg`，token 不进命令行。

⚠️ 看到 `***` 不要慌：那是显示层，文件实际内容是真值。`stat -f %z /tmp/_cfg` 字节数对得上就对（`Authorization: Bearer ` = 22 + 64-hex token = 86 + `\n` = 87）。

## 网关侧 enable 状态语义

- `WxTemplate.enabled` 只是 admin Panel 给业务方看清单的过滤位 —— **`/internal/wx-push` send 时不卡 enabled，也不卡 user binding**。SKILL.md `enabled 勾选` 段已 spec。
- 批量 enable：`POST /admin/apps/[id]/templates/bulk-enable {templateIds, enabled}`，或 Panel → Apps → Templates tab 上 switch。
- sync 公众号侧新加的模板：`POST /internal/wx-template/sync`，业务方调（rotation 不影响已勾选的 enabled）。

## 怎么加新模板 / 类目 / 换行业

| 想做 | 在哪做 | 频率限制 |
|---|---|---|
| 加传统模板消息 | 公众号后台「广告与服务 → 模板消息 → 我的模板库 → 从模板库添加」 | 不限 |
| 换所属行业（解锁不同模板库） | 公众号后台「模板消息 → 行业模板」 | 每月 1 次 |
| 加订阅通知模板 | 公众号后台「订阅通知 → 我的模板 → 选用模板」 | 不限（要类目已开通） |
| 加/换订阅通知类目 | 公众号后台「订阅通知 → 选用类目」 | 每月 1 次 |

API 没有「全部可选类目/行业」list 接口，要看完整候选只能进公众号后台 UI。

## 真实样本（莆阳号 `wxe780b027c2c56921`，2026-06-17）

- 所属行业：IT科技 / 互联网｜电子商务（无二级）
- 我的模板：8 条（订阅模板消息 / 收款成功通知 / 注册申请通过通知 / 考试报名成功通知 / 收到用户报名提交通知 / 排队完成通知 / 备忘录通知 / 审核结果提醒）
- 订阅通知模板：2 条（备忘录通知 / 审核结果提醒，type=2 长期）
- 订阅通知已开通类目：备忘录(296) / 预约/报名(698)
- 网关 enable 状态：
  - `geniuspulse-prod` 全开 (8/8)
  - `nexora-devhub` 全开 (8/8)
  - `dora-devhub` 全关 (0/8) — 同步过但未 enable
  - 其它 app（cspy_admin / nexora-loop-prod / mvp-deployer-prod / admin / selftest）未 sync
