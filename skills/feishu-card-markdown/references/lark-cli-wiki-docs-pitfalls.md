# lark-cli wiki / docs / drive 操作踩坑集

> 用 lark-cli 操作飞书知识库 / 云文档 / drive 文件时反复遇到的坑。专门给"建知识库 + 灌内容 + 转移所有权 + 删文档"这套场景。

## 1. `lark-cli docs +update --content @file` 必须用**相对路径**

```bash
# ❌ 报 "invalid file path: --file must be a relative path within the current directory"
lark-cli docs +update ... --content @/tmp/foo.md

# ✅ 先 cp 到 cwd，跑完再删
cp /tmp/foo.md ./foo.md
lark-cli docs +update --api-version v2 --as user --doc <obj_token> \
  --command append --doc-format markdown --content @./foo.md
rm -f ./foo.md
```

CLI 安全限制，不接受绝对路径。

## 2. `lark-cli wiki spaces create` 没有 `--name` flag

文档/说明里写的 `--name "xxx"` 是骗人的。**只接受 `--data` JSON**：

```bash
lark-cli wiki spaces create --as user --yes \
  --data '{"name":"My Space","description":"..."}'
```

## 3. 建节点没有 `+node-create` 子命令包装

直接调原始 API：
```bash
lark-cli api POST /open-apis/wiki/v2/spaces/<space_id>/nodes --as user \
  --data '{"obj_type":"docx","node_type":"origin","title":"X","parent_node_token":"<parent>"}'
```
返回 `data.node.{node_token, obj_token, url}`。**obj_token 才是 docx 文档 ID**，node_token 是 wiki 节点 ID，两个别混。

## 4. Bot 当 owner 的文档 — API 删不掉、转不出去

经典死锁：
- bot 用 `docx +create` 建的文档，owner = bot (app)
- `DELETE /drive/v1/files/<token>?type=docx` 需要 `space:document:delete` scope，且**调用方必须是 owner**
  - bot 调：缺 scope（bot 的 scope set 跟 user 不一样，加了也常常被拒）
  - user 调：1062501 no permission（不是 owner）
- `POST /drive/v1/permissions/.../members/transfer_owner` 在 bot owner 场景下：
  - bot 调：缺 `docs:permission.member:transfer`（user scope，bot 没有）
  - user 调：1063002 Permission denied（user 不是当前 owner，无权转）

**真正可行的路**：
1. **用户手动在飞书 App 删** — 给 user 加 `full_access`（bot 能做）后让用户 UI 删除。**最快**。
2. **从一开始就以用户身份建文档**（device flow user token + `docx:document:create` user scope），永远别让 bot 当 owner。

记住：建任何"以后想让用户管理"的飞书云文档/知识库节点，**第一步就走 user token**，不要图省事用 bot 创建。

## 5. 飞书 device flow OAuth + 多 scope 一次到位

每加一个 scope 都让用户重跑 device flow 很烦。建议第一次 device flow 时**直接 `--domain all`** 把能要的全要，避免反复折腾。

```bash
lark-cli auth login --domain all --no-wait --json
# → verification_url + device_code，把 URL 发给用户
# 用户授权完：
lark-cli auth login --device-code <code>
```

**注意**：
- App 后台没勾的 scope，device flow 请求时会被忽略（不报错，未授予 list 里能看到）
- 个别 scope 飞书会"预禁用"（如 `vc:meeting.bot.join:write`），出现在"未被授予"列表里属正常，不影响其他 scope 授权成功
- `--domain all` 比手工列 100 个 scope 省事，但前提是 App 后台批量开通 JSON 里把这些 scope 都勾上发布过

## 6. 飞书开放平台「批量开通权限」JSON

爸爸偏好直接拿 JSON 贴到后台框，不要列 scope 名让他一个个勾。格式：

```json
{
  "scopes": {
    "tenant": [],
    "user": [
      "wiki:wiki",
      "wiki:space:write_only",
      "docx:document",
      "docx:document:create",
      "docx:document:write_only",
      "docx:document:readonly",
      "docs:permission.member:create",
      "docs:permission.member:transfer",
      "space:document:delete",
      "drive:file:upload",
      "drive:file:download"
    ]
  }
}
```

链接：`https://open.feishu.cn/app/<app_id>/auth` → 批量开通权限框 → 创建版本并发布。

**第一次开就多开**，宁可一次给一大坨（文档/知识库/drive/im/calendar/sheets/bitable 全套），别等用到了再回头要。
