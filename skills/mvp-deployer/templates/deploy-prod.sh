#!/usr/bin/env bash
# {{PROJECT}} → prod ({{HOST}}) 一键部署脚本
#
# 用法:
#   ./scripts/deploy-prod.sh            # 走完整链路
#   ./scripts/deploy-prod.sh --dry-run  # 只打 zip + 生 manifest, 不上传
#
# 复制到项目 scripts/deploy-prod.sh 后改 4 处：{{PROJECT}} / {{HOST}} / {{PORT}} / EXTRA_ZIP_EXCLUDE
#
# 前置:
#   1. ~/.credentials/.env 含 MVP_DEPLOYER__TOKEN=...
#   2. jq / zip / python3
#
# 做什么（9 步，每步都是踩过的坑）：
#   1. 前置检查(token/jq/zip/git 干净度)
#   2. 从 prod exec cat .env 抓现网 env 回灌 → 避免 manifest.env 全量覆盖丢 key (铁律 2)
#   3. 打 zip 排 node_modules/.next/uploads/data/pnpm-workspace + 项目专属 legacy
#   4. 生 manifest (smokeDisabled=true 铁律 5, preserveData, postDeploy)
#   5. POST /api/deploy 拿 taskId (铁律 1)
#   6. 轮询 status/phase 直到 succeeded/failed
#   7. smoke 3 个 URL
#   8. 从 /api/status 拉 pm2 状态
#   9. exit 0 成功 / 1 失败
#
# 为什么用 jq 而不是 python 解 response：deployer /api/deploy/tasks/<id> 的 logs
# 里 env value 常含 control character(比如 \x1b ANSI escape、\r)，python json.loads
# 直接抛 JSONDecodeError；jq 更宽容。
#
set -euo pipefail

# ============ 项目定值(改这里) ============
PROJECT="{{PROJECT}}"                       # e.g. image-studio
HOST="{{HOST}}"                             # e.g. design.mvp.restry.cn
PORT={{PORT}}                               # e.g. 3789
BUILD_CMD="pnpm install --no-frozen-lockfile && pnpm prisma generate && pnpm build"
RUN_CMD="pnpm start"
POST_DEPLOY="pnpm prisma migrate deploy"    # 无迁移 → 改成 ":" 或留空
PRESERVE_DATA='["data","public/uploads"]'   # JSON array
# 额外 zip 排除(每行一个 -x pattern)——比如 image-studio 的 legacy prompts 数字目录
EXTRA_ZIP_EXCLUDE=(
  # 'public/prompts/[0-9]*'
)
# smoke 路径(200 或 3xx 都算 OK；需登录的路由会 307，正常)
SMOKE_PATHS=("/" "/login")

# ============ 以下无需改动 ============
DEPLOYER="https://deploy.mvp.restry.cn"
ZIP="/tmp/${PROJECT}.zip"
MANIFEST="/tmp/${PROJECT}-manifest.json"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# 前置检查
[[ -f ~/.credentials/.env ]] || { echo "❌ ~/.credentials/.env 不存在" >&2; exit 1; }
set -a; source ~/.credentials/.env; set +a
[[ -n "${MVP_DEPLOYER__TOKEN:-}" ]] || { echo "❌ ~/.credentials/.env 缺 MVP_DEPLOYER__TOKEN" >&2; exit 1; }
command -v jq >/dev/null   || { echo "❌ brew install jq" >&2; exit 1; }
command -v zip >/dev/null  || { echo "❌ 缺 zip" >&2; exit 1; }

HEAD_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo NOGIT)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo NOGIT)
DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
echo "📦 ${PROJECT} 部署  branch=${BRANCH}  HEAD=${HEAD_SHA}  dirty=${DIRTY} files"
if [[ "$DIRTY" -gt 0 ]]; then
  echo "⚠️  工作区有未 commit 的改动 (zip 会打进去)"
  git status -s | head -10
  read -rp "继续? [y/N] " ans
  [[ "${ans:-N}" =~ ^[Yy]$ ]] || exit 1
fi

# HDR + trap 清理 (避 Hermes scrubber mask Bearer 字面)
HDR=$(mktemp); trap "rm -f $HDR $MANIFEST" EXIT
printf 'Authorization: Bearer %s\n' "$MVP_DEPLOYER__TOKEN" > "$HDR"

# 1) 拉现网 env 回灌 —— 铁律 2 的核心防线
echo ""
echo "🔑 从 prod exec 拉 .env 回灌..."
ENV_RAW=$(curl -sS -H @"$HDR" -X POST "${DEPLOYER}/api/exec/${PROJECT}" \
  -H "Content-Type: application/json" \
  -d '{"command":"cat .env","timeoutMs":10000}' | jq -r '.stdout // ""')
if [[ -z "$ENV_RAW" ]]; then
  # 首次部署没 prod .env — 允许空(需要脚本外部把 env 写好或用 vault inject 模板)
  echo "  ⚠️  prod 无 .env(首次部署?),env 将为空——需手工补 manifest.env"
  ENV_RAW=""
fi
ENV_KEYS=$(printf '%s\n' "$ENV_RAW" | grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' || echo 0)
echo "  ✓ 拿到 ${ENV_KEYS} 个 env keys"

# 2) 打 zip
echo ""
echo "📦 打 zip..."
rm -f "$ZIP"
ZIP_EXCLUDES=(
  '.git/*' 'node_modules/*' '.next/*'
  '.env' '.env.*' '*.log'
  'public/uploads/*' 'data/*'
  '.DS_Store' '.turbo/*' 'test-results/*'
  '.claude/*'
  'pnpm-workspace.yaml'  # pnpm 10 会重建, 排除防 monorepo 误判 (pitfalls pnpm-workspace)
)
ZIP_EXCLUDES+=("${EXTRA_ZIP_EXCLUDE[@]}")
ZIP_ARGS=()
for x in "${ZIP_EXCLUDES[@]}"; do ZIP_ARGS+=(-x "$x"); done
zip -rq "$ZIP" . "${ZIP_ARGS[@]}"
echo "  ✓ ${ZIP} ($(du -h "$ZIP" | awk '{print $1}'))"

# 3) 生 manifest — env → JSON object,处理引号/control char
echo ""
echo "📝 生成 manifest..."
ENV_JSON=$(printf '%s\n' "$ENV_RAW" | python3 -c "
import sys, json
env = {}
for line in sys.stdin:
    s = line.strip()
    if not s or s.startswith('#') or '=' not in s:
        continue
    k, v = s.split('=', 1)
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('\"', \"'\"):
        v = v[1:-1]
    env[k.strip()] = v
print(json.dumps(env))
")
python3 - <<PY > "$MANIFEST"
import json
env = json.loads('''$ENV_JSON''')
m = {
    "project": "$PROJECT",
    "type": "node",
    "port": $PORT,
    "host": "$HOST",
    "build": "$BUILD_CMD",
    "run": "$RUN_CMD",
    "smokeDisabled": True,   # Next.js / 中间件重项目必开 (铁律 5)
    "env": env,
    "preserveData": json.loads('''$PRESERVE_DATA'''),
}
post = "$POST_DEPLOY".strip()
if post and post != ":":
    m["postDeploy"] = post
print(json.dumps(m))
PY
echo "  ✓ ${MANIFEST} (env=${ENV_KEYS} keys)"

if $DRY_RUN; then
  echo ""
  echo "🏁 --dry-run 完成. zip=${ZIP} manifest=${MANIFEST}"
  exit 0
fi

# 4) POST /api/deploy
echo ""
echo "🚀 上传..."
RESP=$(curl -sS -X POST "${DEPLOYER}/api/deploy" -H @"$HDR" \
  -F "file=@${ZIP}" \
  --form-string "manifest=$(cat $MANIFEST)")
TASK=$(echo "$RESP" | jq -r '.taskId // empty')
[[ -n "$TASK" ]] || { echo "❌ POST 无 taskId"; echo "$RESP" | head -c 500; exit 1; }
echo "  ✓ taskId=${TASK}"

# 5) 轮询
echo ""
echo "⏳ 轮询 task..."
LAST_PHASE=""
for i in $(seq 1 180); do
  S=$(curl -sS -H @"$HDR" "${DEPLOYER}/api/deploy/tasks/${TASK}")
  STATUS=$(echo "$S" | jq -r '.status // ""')
  PHASE=$(echo "$S" | jq -r '.phase // ""')
  if [[ "$PHASE" != "$LAST_PHASE" ]]; then
    printf "\n  [%3ds] status=%-10s phase=%s" "$((i*5))" "$STATUS" "$PHASE"
    LAST_PHASE=$PHASE
  else
    printf "."
  fi
  if [[ "$STATUS" == "succeeded" || "$STATUS" == "failed" ]]; then
    echo ""; echo ""
    if [[ "$STATUS" == "failed" ]]; then
      echo "❌ failed, 尾部日志:"
      echo "$S" | jq -r '.logs[-15:] | .[]' | tail -30
      exit 1
    fi
    break
  fi
  sleep 5
done
echo "  ✓ task ${TASK} succeeded"

# 6) smoke
echo ""
echo "🔎 smoke..."
FAIL=0
for path in "${SMOKE_PATHS[@]}"; do
  code=$(curl -sk -o /dev/null -w "%{http_code}" "https://${HOST}${path}")
  if [[ "$code" =~ ^(200|30[1-9])$ ]]; then
    echo "  ✓ ${code}  https://${HOST}${path}"
  else
    echo "  ❌ ${code}  https://${HOST}${path}"
    FAIL=$((FAIL+1))
  fi
done

# 7) pm2 状态
echo ""
curl -sS -H @"$HDR" "${DEPLOYER}/api/status" \
  | jq -r --arg p "$PROJECT" '.projects[] | select(.project==$p) | "  pm2 status=\(.pm2.status)  restarts=\(.pm2.restarts)  mem=\(.pm2.memory)"'

echo ""
if [[ $FAIL -eq 0 ]]; then
  echo "✅ 完成. HEAD=${HEAD_SHA} 已上线 https://${HOST}"
else
  echo "⚠️  部署成功但 ${FAIL} 个 smoke URL 不 OK"
  exit 1
fi
