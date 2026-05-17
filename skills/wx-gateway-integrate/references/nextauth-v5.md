# NextAuth v5 (Auth.js) 集成 wx-gateway

本文是 wx-gateway-integrate 的 NextAuth v5 专项参考。如果业务方用的不是 NextAuth/Auth.js（比如自己实现 session），不必读本文——回到 SKILL.md 主流程即可。

覆盖两块：①一般集成模式（session 字段映射、Credentials provider 写法、middleware 配合）；②业务方专属坑（cookie domain、JWT vs DB session、redirect 死循环、回调端口、生产 trustHost 等）。

---

## NextAuth v5 (Auth.js) 集成专项（**重要**）

skill 模板默认假设业务方"自管 session cookie"，但很多 Next.js 项目用 **NextAuth/Auth.js v5 jwt session**。这种项目接 wx-gateway 有 4 个特有坑（2026-04-28 echo 实战）：

### 1. finalize redirect 必须用 `process.env.NEXTAUTH_URL`，不是 `req.url`

mvp-deployer 用 caddy 反代到 `127.0.0.1:<port>`，next-server 看到的 `req.url` host 是 `localhost:<port>`。`new URL("/login", req.url)` 拼出 `https://localhost:3795/login`，浏览器跟着跳直接 ERR_CONNECTION_REFUSED。

```ts
const baseUrl = process.env.NEXTAUTH_URL ?? new URL(req.url).origin;
return NextResponse.redirect(new URL("/login?err=sig", baseUrl));
```

### 2. 不要"自管 session cookie"，直接接 NextAuth Credentials provider

加第二个 Credentials provider（id 区分），把 wx-gateway HMAC 校验放在 finalize route，校验通过后调 NextAuth `signIn("wx-finalize", { redirect:false, openid, unionid, nickname, avatarUrl })` 让 NextAuth 自己设 jwt session cookie。完全不用业务自家 session 表/cookie 中间件。

```ts
// auth.ts providers 数组追加
Credentials({
  id: "wx-finalize", name: "WeChat",
  credentials: { openid:{type:"text"}, unionid:{type:"text"}, nickname:{type:"text"}, avatarUrl:{type:"text"} },
  async authorize(input) {
    const openid = String(input?.openid ?? "");
    if (!openid) return null;
    const user = await upsertWechatUser({ openid, unionid: ..., nickname: ..., avatarUrl: ... });
    return { id: user.id, email: user.email, name: user.name, image: user.image };
  },
}),
```

### 3. jwt callback 必须按需查 DB 把 name/picture 回灌（**最容易漏**）

NextAuth jwt token 只在登录那一刻被写一次。**路径 A 第一次 finalize 只有 openid，token 里 name/picture 是 null**。OAuth 补全（路径 A 第二次或路径 B）后 ec_users.name/image 已更新，但 jwt token **不会自动刷新** —— 用户在 dashboard 永远看到空头像。

修法：jwt callback 检测到 token 缺 name/picture 时主动查 DB 一次回填：

```ts
async jwt({ token, user }) {
  if (user) {
    token.uid = user.id;
    token.name = user.name ?? null;
    token.picture = user.image ?? null;
  }
  if (token.uid && (!token.name || !token.picture)) {
    const fresh = await loadUserById(token.uid as string);
    if (fresh) {
      token.name = fresh.name ?? null;
      token.picture = fresh.image ?? null;
    }
  }
  return token;
},
async session({ session, token }) {
  if (token.uid && session.user) {
    session.user.id = token.uid as string;
    session.user.name = (token.name as string | null) ?? session.user.name;
    session.user.image = (token.picture as string | null) ?? session.user.image;
  }
  return session;
},
```

### 4. DB 调用必须放 `auth.ts`，不能放 `auth.config.ts`

NextAuth v5 的 middleware 在 **edge runtime** 加载 `auth.config.ts`。jwt/session callback 在 config 里 `import { db }` 会让 edge bundler 试图打 drizzle/prisma 进 edge bundle，pg/postgres 都用 node net/dns 直接炸。

正确分层：
- `auth.config.ts`：纯逻辑 callback（authorized 等），edge-safe，**不 import db**
- `auth.ts`：`NextAuth({ ...authConfig, callbacks: { ...authConfig.callbacks, jwt: jwtWithDb } })` 这里覆盖需要 DB 的 callback

### 5. /api/wx 路径必须加进 auth.config.ts public allowlist

否则 finalize 自己被 `authorized` callback 拦到 /login，永远走不到 HMAC 校验。

```ts
const isPublic = pathname.startsWith("/login") || pathname.startsWith("/api/auth") || pathname.startsWith("/api/wx");
```

---


---

## NextAuth v5 业务方专属坑（**用 NextAuth 接 wx-gateway 必读**）

skill 默认 Prisma + 业务自管 cookie。**NextAuth v5 (jwt session) 接入差异**：

### 1. finalize 后如何登录？

不要在 finalize route 里手动 set cookie——直接用 NextAuth 自家流程：

**方案 A（推荐）**：finalize 内调 `signIn("wx-finalize", { redirect: false, openid, unionid, nickname, avatarUrl })`，让 NextAuth 自家 jwt session cookie 下发。然后 `NextResponse.redirect(absoluteUrl("/dashboard"))`。

需要在 `src/auth.ts` providers 里**追加**第二个 Credentials（id 区分原邮箱密码那条）：
```ts
Credentials({
  id: "wx-finalize",
  credentials: { openid: {}, unionid: {}, nickname: {}, avatarUrl: {} },
  async authorize(input) {
    const user = await upsertWechatUser({ ... });
    return { id: user.id, email: user.email, name: user.name, image: user.image };
  },
}),
```

⚠️ middleware/auth.config 必须把 `/api/wx` 加进 `isPublic` allowlist，否则 finalize 自己被拦到 /login。

### 2. OAuth 补全 name/image 后 session 不刷新（**最隐蔽的坑**）

**症状**：爸爸 PC 扫码登录成功（路径 A 第一次 finalize 仅 openid），然后点公众号会话里"完善头像昵称"链接走 OAuth（路径 A 第二次 finalize 带 nickname/avatar）。DB `ec_users.name/image` **已更新**，但页面刷新看到 session.user.name/image **还是空的**。

**根因**：NextAuth jwt session 把 user 字段缓存在 token 里。`authorize()` 只在用户**点登录按钮**那一次调用——OAuth 补全是 redirect 链路里的第二次 finalize，jwt callback 不会自动重读 DB。爸爸看到的 session.user 永远是第一次 finalize（name=null）的快照。

**修法**：`src/auth.config.ts` jwt callback 加按需 DB 刷新（不是无脑每次查）：
```ts
async jwt({ token, user }) {
  if (user) {  // 首次登录走 authorize 的路径
    token.uid = user.id;
    token.name = user.name ?? null;
    token.picture = user.image ?? null;
  }
  // 关键：token 已存在但 name/picture 空 → DB 读一次填回
  // OAuth 补全后用户下次访问任何页面就触发；填好后后续请求不再查 DB
  if (token.uid && (!token.name || !token.picture)) {
    const fresh = await loadUserById(token.uid as string);
    if (fresh) {
      token.name = fresh.name ?? null;
      token.picture = fresh.image ?? null;
    }
  }
  return token;
},
async session({ session, token }) {
  if (token.uid && session.user) {
    session.user.id = token.uid as string;
    session.user.name = (token.name as string | null) ?? session.user.name;
    session.user.image = (token.picture as string | null) ?? session.user.image;
  }
  return session;
},
```

`loadUserById` 写 `src/lib/wx/user-loader.ts`（server-only），单行 `db.select().from(ec_users).where(eq(ec_users.id, id))`。

**判别原则**：jwt callback 是 hot path（每次请求都过）。一定要 **`if (!token.name || !token.picture)` 守卫**——否则每个请求都 N+1 查 DB。一旦填好 token，后续请求 0 DB hit。

### 3. Dashboard UI 必须渲染 name/image，不能只渲染 email（**echo 2026-04-28 实战**）

jwt 回填只解决 **token 层**有数据，但如果 dashboard layout 用的是 `{session.user.email}` 这种只读 email 的组件，微信用户 `email=NULL` 仍然全空白。**接 wx-gateway 的项目从一开始就要：**

1. `session.user.image` 渲染 avatar（圆形 32px，`unoptimized` 否则 `next/image` 拒绝 thirdwx.qlogo.cn 域名）
2. `session.user.name` 主行；`session.user.email` 降级 fallback（`name || email || "微信用户"`）
3. 移动端如果 sidebar `hidden md:flex`，**顶部必须加单独 header** 放 logo + 用户徽章 + 退出，否则手机端完全看不到身份信息

抽 `<UserBadge name image email compact />` 组件，桌面 sidebar 底 + 移动 header 复用。一次写对，省得用户每次都来问"为什么右上角看不到头像"。

### 4. ec_users 表的 email NOT NULL 约束

NextAuth schema 默认 `email TEXT NOT NULL UNIQUE`。微信用户没邮箱：
- 选项 A：drizzle schema 把 email 改可空（PG 多个 NULL 不冲突，UNIQUE 还能用）
- 选项 B：upsert 时填占位 `wx_${openid}@wechat.local`

echo 选了 A（更干净，避免假 email 污染）。改完 generate + migrate。

