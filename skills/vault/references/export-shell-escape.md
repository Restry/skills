# vault export → mvp-deployer Path A → .env 转义污染

## 触发症状(任一)

- `Database "<name>\" does not exist`(prisma 错误,DB 名末尾有反斜杠)
- `[apps] failed to parse APPS_JSON SyntaxError: Unexpected token '\\', "\\[\\{\\\"name"...`
- `.env: line N: $'xxx': command not found`(PM2 用 source .env 起进程时)
- PG `pg_database` 里出现孪生库:`<name>` + `<name>\`(hex 末尾 `5c`)

## 根因

`vault export -p <project>` 输出 `KEY=VAL` 时,VAL 里的 shell 元字符自动加 `\` 转义(为 `eval $(vault export)` 用)。但 mvp-deployer Path A 把 manifest.env 直接写进 `/opt/mvp-apps/<p>/.env` **不 unescape**,Next.js / Prisma / JSON.parse 看到带反斜杠就崩。

最隐蔽:`DATABASE_URL=...:/db_name\?schema=public` → prisma 把 `db_name\` 当库名 → 第一次连接 prisma migrate deploy **静默 createdb 一个名字带反斜杠的幽灵库**,prod 跑这个数月。某次部署解析对了 `?` → 连去"正确"名字的空库 → 看起来数据全没了(但其实在反斜杠库里)。

## 诊断 3 步

### 1. PG 看孪生库

通过 mvp-deployer `/api/exec` 跑(无需 SSH):

```js
const{PrismaClient}=require("@prisma/client");
const adminUrl=`postgresql://USER:PASS@127.0.0.1:5432/postgres`;
const p=new PrismaClient({datasources:{db:{url:adminUrl}}});
const dbs=await p.$queryRawUnsafe(`SELECT datname, pg_database_size(datname) AS sz FROM pg_database WHERE datname LIKE '<your_project>%'`);
for(const d of dbs){
  const hex=Buffer.from(d.datname,"utf8").toString("hex");
  console.log(d.datname, "sz=", Number(d.sz), "hex=", hex);
}
```

末尾 `5c` 即 `\`。

### 2. 判断哪个是真库 — 不能凭大小

**空库 migrate 一遍可能比业务库大**(我自己踩过)。唯一可靠判据:
- `SELECT MIN(started_at) FROM _prisma_migrations`(几天前 = 旧库)
- `SELECT COUNT(*) FROM "App"` / 主业务表非 0

### 3. 检查 manifest 和 .env 污染

```bash
grep -E '^DATABASE_URL|^APPS_JSON|^.*_SECRET' /opt/mvp-apps/<p>/.deploy-manifest.json
grep -E '^DATABASE_URL|^APPS_JSON' /opt/mvp-apps/<p>/.env
```

看到 `\?` `\[` `\{` `\,` `\#` `\$'...'` → 中招。

## 修复 7 步

### 1. 拨乱反正 DB 名

```js
// 终止两库连接
await p.$executeRawUnsafe(`SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='<name>' AND pid<>pg_backend_pid()`);
await p.$executeRawUnsafe(`SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='<name>\\' AND pid<>pg_backend_pid()`);
// 空库改名归档(留证至少 1 周,别 drop)
await p.$executeRawUnsafe(`ALTER DATABASE "<name>" RENAME TO "<name>_empty_<ts>"`);
// 真库改回干净名
await p.$executeRawUnsafe(`ALTER DATABASE "<name>\\" RENAME TO "<name>"`);
```

⚠️ **每次 rename 后立刻 `SELECT datname FROM pg_database` 验**——顺序错一步就把数据归档了,别凭 stdout 信任。

### 2. 修 .env + .deploy-manifest.json(批量 unescape)

先备份:`cp .deploy-manifest.json .deploy-manifest.json.bak.$(date +%s)`

```python
import json, re
m = json.load(open(".deploy-manifest.json"))
fixed = {}
for k, v in m["env"].items():
    if isinstance(v, str):
        nv = re.sub(r'\\([\[\]\{\}\?\=\"\,\#\!\$\&\(\)\*\;\<\>\^\`\|\\ ])', r'\1', v)
        m2 = re.match(r"^\$'(.*)'$", nv)
        if m2:
            try: nv = bytes(m2.group(1), "utf-8").decode("unicode_escape")
            except: pass
        fixed[k] = nv
    else:
        fixed[k] = v
m["env"] = fixed
json.dump(m, open(".deploy-manifest.json","w"), indent=2, ensure_ascii=False)
with open(".env","w") as f:
    for k, v in fixed.items(): f.write(f"{k}={v}\n")
```

### 3. PM2 重启 — 别用 `restart --update-env`

不可靠,prisma client 不重连。永远 `pm2 delete + pm2 start`。

### 4. 写 ecosystem.config.js,别 source .env

PM2 用 `source .env` 起进程时,shell **再次 parse**,JSON 里的 `[` `{` 被吃。让 PM2 直接读 JS object:

```python
import json
env = {}
for line in open(".env"):
    line = line.rstrip("\n")
    if not line or line.startswith("#") or "=" not in line: continue
    k, v = line.split("=", 1)
    if len(v)>=2 and v[0]==v[-1] and v[0] in ('"',"'"): v = v[1:-1]
    env[k] = v
eco = {"apps":[{
    "name": "<project>",
    "cwd": "/opt/mvp-apps/<project>",
    "script": "pnpm",
    "args": "start",
    "interpreter": "none",  # 不让 PM2 当 JS 跑
    "env": env
}]}
open("ecosystem.config.js","w").write("module.exports = " + json.dumps(eco, indent=2, ensure_ascii=False))
```

```bash
pm2 delete <name> 2>/dev/null || true
pm2 start ecosystem.config.js
```

### 5. 验进程内 env(`pm2 env` 不可靠)

```bash
PID=$(pm2 jlist 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); [print(x['pid']) for x in d if x['name']=='<project>']")
cat /proc/$PID/environ | tr '\0' '\n' | grep -E '^(APPS_JSON|DATABASE_URL|PORT)='
```

期望:无反斜杠,JSON 是真 JSON,DB URL 库名干净。

### 6. Smoke + 错误日志清空验

清空 `/home/claw/.pm2/logs/<p>-error.log`(用 `: > 文件名` 或 deploy host 自己的 truncate),发 1 个请求,5 秒后 tail 看,应空或只有 prisma update 提示。

### 7. 补缺的 prisma migration

库名拨正后,新 migration 还没 apply:

```bash
cd /opt/mvp-apps/<project> && pnpm prisma migrate deploy
```

## 预防

**首选(已落地)**:用 helper 脚本 `~/.hermes/skills/mvp-deployer/scripts/vault-to-manifest-env.py`,直接出干净 JSON 喂 mvp-deployer manifest.env:

```bash
# 标准用法 — 部署 wx-gateway-pucs:
ENV_JSON=$(python3 ~/.hermes/skills/mvp-deployer/scripts/vault-to-manifest-env.py wx-gateway-pucs)
MANIFEST=$(jq -n --argjson env "$ENV_JSON" '{project:"wx-gateway-pucs", type:"node", host:"wxmsg.mvp.restry.cn", port:3800, build:"pnpm install --frozen-lockfile && pnpm prisma generate && pnpm build", run:"pnpm start", postDeploy:"set -a; source .env; set +a; pnpm prisma migrate deploy", env:$env}')
curl -X POST https://deploy.mvp.restry.cn/api/deploy \
  -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
  -F "file=@/tmp/<project>.zip" \
  --form-string "manifest=$MANIFEST"
```

或 `--shell` 模式产 `export K=V` 行直接 source 到本地 shell。

脚本关键点(自己复刻时别漏):
- 必须 `subprocess.run(..., capture_output=True)` **不带 text=True**,然后 `result.stdout.decode("latin-1")` —— `vault export` 在 `$'...'` 引用里夹杂 raw 非 UTF-8 字节(实际是 UTF-8 字符的中间字节但混着 octal escape),text mode 会 UnicodeDecodeError 崩
- ANSI-C decoder 把 `cp < 256` 的字符当裸字节(`out.append(cp)`),不当字符 (不要 `.encode("utf-8")`),因为 vault 的 `$'Nexura M-h\216\206...'` 里 `M-h`(latin-1 0xE8) 是 UTF-8 序列的第一字节,要和后面的 `\216\206` 八进制字节合成完整 UTF-8 序列再 decode
- 先 try ANSI-C `$'...'` 模式,再 try `"..."`/`'...'` 包裹去外层,最后才 fallback 到 backslash-escape 处理(`$'...'` 内部的 `\` 是 ANSI-C 转义,不能当 shell escape 处理)
- subprocess timeout 至少 30s(本地 mac vault export 可能慢)

**根治路径**:也已修了 prod `/opt/mvp-deployer/lib/credentials.js` 的 `parseEnvFile` 加同样 unescape 逻辑(走 prefix-stripped credentials path 的项目自动受益)

**强制自查**:部署后立刻 `/api/exec` 跑 `grep '\\\\' .env` —— 命中即污染,立即修。

## smokePaths 别瞎填(踩过)

manifest 加 `smokePaths: ["/api/health"]` 时,**那条路径必须真的存在**,否则 deployer 探到 404 → 回滚整个部署。Next.js 项目默认没 `/api/health`。

**安全做法**:省略 `smokePaths`,只让 deployer 探默认 `/`(返 200 即过)。要业务级 smoke 自己 deploy 后 curl 验,别交给 deployer。

## 标准 deploy 完整命令(已验证可复现)

```bash
set -a; source ~/.credentials/.env; set +a
cd ~/projects/<project>
git push origin main && git archive HEAD --format=zip -o /tmp/<p>.zip   # 铁律:git archive,不要 zip .
python3 ~/.hermes/skills/mvp-deployer/scripts/vault-to-manifest-env.py <p> > /tmp/<p>_env.json
python3 -c "import json; env=json.load(open('/tmp/<p>_env.json')); m={'project':'<p>','type':'node','port':int(env['PORT']),'host':'<host>','run':'pnpm start','build':'pnpm install --frozen-lockfile && pnpm prisma generate && pnpm build','env':env,'postDeploy':'set -a; source .env; set +a; pnpm prisma migrate deploy'}; json.dump(m,open('/tmp/<p>_manifest.json','w'))"
MANIFEST=$(cat /tmp/<p>_manifest.json)
curl -sS -X POST https://deploy.mvp.restry.cn/api/deploy \
  -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
  -F "file=@/tmp/<p>.zip" -F "manifest=$MANIFEST"
# 然后轮询 /api/deploy/tasks/<taskId>,build phase 60-90s
```

## 反模式速查

1. NO 凭库大小猜哪个是旧库 — 必查 `_prisma_migrations.started_at` + 业务表 COUNT
2. NO `pm2 restart --update-env` — prisma client 不重连,永远 delete+start
3. NO `pm2 start "cmd"` 配合手动 source .env — shell 二次 parse,APPS_JSON 必炸
4. NO 信 `pm2 env <name>` 输出 — 不可靠,看 `/proc/<pid>/environ`
5. NO 没备份就改 .env / manifest
6. NO rename DB 后不立刻 `pg_database` 验
7. NO smoke 只 curl `/` — 必须 curl 一个读 prod DB 业务行的接口(如 `/admin/apps` 返非空 list),否则 prod DB 被刷成空库都看不出来

## Next.js 子坑:env 值被烘进 build artifact

修完 .env / ecosystem 重启后,**部分页面顶部 emoji / instance label 仍是旧的乱码**——这不是 env 没生效,是 Next.js App Router prerender 阶段(build 时)把 `process.env.INSTANCE_LABEL` 等值 baked 进 `.next/server/app/<route>.rsc` payload。

诊断:`grep -E 'instanceLabel|INSTANCE_' .next/server/app/<route>.rsc` 看到的就是当时 build 时的值。

修法:**必须 rebuild**,光 pm2 restart 没用。流程:

1. 修 .env 时要 quote 含空格 / 中文 / emoji 的值,否则 source .env 在 shell 里炸:
   `INSTANCE_LABEL='Nexura 莆阳'` (单引号 + 内部 ' 用 '\\'' 转义)
2. `set -a; source .env; set +a; echo "[$INSTANCE_LABEL]"` 验值能进 shell(不能被空格切了)
3. `pnpm build`
4. `grep -oE '"instanceLabel":"[^"]+"' .next/server/app/panel/users.rsc | head -1` 验 RSC payload 已用新值
5. `pm2 delete <project>; pm2 start ecosystem.config.js`

**预防**:写 .env 时凡含空格 / 非 ASCII / shell 元字符的值,自动单引号包裹:

```python
need_quote = any(c in v for c in [' ','#','&','|','<','>','(',')','*','?','!','$','`','[',']','{','}',';','\\']) or any(ord(c)>127 for c in v)
if need_quote and not v.startswith(("'",'"')):
    v = "'" + v.replace("'", "'\\''") + "'"
```

## 流程铁律(deploy 已有 prod 项目前)

1. **派 CC 改 schema 前**:第一步必须 `pnpm prisma migrate status` 对 prod 跑,diff 报回来 → 人工看了再决定动不动
2. **manifest.env 写 .env 前必须 diff 旧 .env**:任何 `DATABASE_URL` / `APP_ID` / `_SECRET` 字段差异必须停下来确认(尤其库名 / appid 这类"改了等于换数据库"的字段)
3. **deploy 后 smoke 必须含业务断言**:不只 `/` 200,要 curl 一个读 DB 业务接口返非空

## mvp-deployer rollback 二次污染陷阱

部署失败触发 auto-rollback 时,**mvp-deployer 把 PM2 env 重置成它推导的 "project-name-derived default"**,覆盖你手动修过的 .env 值。

**症状**:rollback 后业务接口返 500,err log 报 `Database "<project-name-with-hyphens>" does not exist`(中划线版本,而不是你修过的下划线 `wx_gateway_pucs`)。即使 `.env` 文件本身没被改(timestamp 还是修复时的),进程内的 env 已被 rollback 流程污染。

**根因**:rollback 调 PM2 restart 时通过自己的 manifest 环境注入,而不是读 disk 上的 `.env`。

**抢救**:pm2 delete + pm2 start ecosystem.config.js,让进程重新从 disk `.env` / ecosystem 读 env:

```bash
cd /opt/mvp-apps/<project>
pm2 delete <project> 2>&1 | tail -1
sleep 1
pm2 start ecosystem.config.js
sleep 6
PID=$(pm2 jlist | python3 -c "import json,sys; d=json.load(sys.stdin); [print(x['pid']) for x in d if x['name']=='<project>']")
cat /proc/$PID/environ | tr '\0' '\n' | grep DATABASE_URL  # verify clean
```

## mvp-deployer manifest 无 env 字段不会保留 .env(踩过)

直觉:省略 `manifest.env` → mvp-deployer 跳过 .env 重写 → 保留 prod 现有 .env。**错**。

实测:省略 manifest.env 后 deploy 时 `pnpm prisma migrate deploy` 在 postDeploy 阶段报 `Environment variable not found: DATABASE_URL`。说明 mvp-deployer 不为 postDeploy 命令注入 .env(它跑 postDeploy 的 shell 不 auto-source `.env`)。

**修法**:postDeploy 命令自己 source:

```jsonc
{
  "postDeploy": "set -a; source .env; set +a; pnpm prisma migrate deploy"
}
```

但即使这样,**走 mvp-deployer 部署仍然有 rollback 重置 PM2 env 的风险**(见上节)。

## 完全绕开 mvp-deployer 的安全 redeploy 路径

当 prod 已经被 vault escape 修过、不想触发 rollback 重置时,**不走 mvp-deployer**,直接 `/api/exec` 执行:

```bash
cd /opt/mvp-apps/<project>
git fetch origin main && git reset --hard origin/main   # 拉新代码
pnpm install --frozen-lockfile
pnpm prisma generate
pnpm build                                               # 等 60-90s
pm2 delete <project> 2>&1 | tail -1
pm2 start ecosystem.config.js                            # 用修过的 ecosystem,不走 .env source
```

要点:
- 用 git pull 而非 mvp-deployer zip,完全不碰 .env/ecosystem/manifest
- pnpm build 时间长(60-90s),`/api/exec` timeout 默认 60s 不够,设 `timeoutMs: 300000`
- 失败时不会 auto-rollback,你需要自己负责回退(`git reset --hard <prev hash>` + rebuild)

## 相关 skills

- `mvp-deployer` — Path A/B env 注入机制
- `vault` — 门神基础
- `vault-snapshot-deploy-pattern`
- `postgres-db-name-shell-escape-leak` — 类似 shell-escape DB 名污染
