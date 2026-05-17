# 微信图文消息（news）渲染规则

业务方用 news 类型回复菜单 click / 关注事件 / 主动推时，**微信前端的渲染规则有几条平台硬限制**——不是 bug 是产品规范，没法绕。

## 硬规则

### 1. 多图文：只有第 1 条 article 显示 description
- `articles[0]` → 大卡片：标题 + 封面图 + **description 摘要** + 跳转链接
- `articles[1..n]` → 小列表条：**只显示标题**（description 完全不渲染），左侧小缩略图（picUrl）

业务方往往把 description 给每条都填上，期望都展示——**白填**。

### 2. 单图文：description 也不展示在卡片上
- 单条 news 时，description 只在分享出去时作为摘要预览
- 卡片本身只显示 标题 + 大封面图（picUrl）
- 摘要只能挤进 title 里

### 3. articles 上限 8 条
- 超过被微信截断（不报错，悄悄丢）

### 4. picUrl 必须公网可达 + http(s)
- 内网 / localhost / 自签证书一律不渲染（显示空白封面）

## 典型踩坑：菜单点击列岗位/商品/活动列表

**症状**：业务方做了「点击菜单 → 列出 N 个岗位/活动/商品」，给每条都填了描述，发现只有第一条有摘要，其他全光秃秃只剩标题，候选人/用户体感「这是什么垃圾排版」。

**根因**：第 2 条起 description 微信前端不渲染，跟代码无关。

**正解套路**（推荐）：把第 1 条做成「门户卡」+ 描述说明，从第 2 条起列具体条目：

```ts
const articles = [
  // 第 1 条：门户卡（带描述、带封面）
  {
    title: 'XX 平台 · 现开放岗位',
    description: `目前开放 ${items.length} 个岗位，点击下方任一条目进入详情`,
    url: `${baseUrl}/list`,
    picUrl: `${baseUrl}/cover.jpg`,  // 必须公网可达
  },
  // 第 2+ 条：具体条目（description 留空反正不显示）
  ...items.slice(0, 7).map(item => ({
    title: item.name,
    description: '',
    url: `${baseUrl}/item/${item.id}`,
    picUrl: item.coverUrl || '',
  })),
];
```

## 诊断 checklist

如果用户反馈「为什么我的图文只有第一个有介绍」：
1. 看 articles 数组长度 > 1 吗？是 → 平台规则，不是 bug
2. 看 picUrl 是公网域名吗？localhost/内网 → 封面空白
3. 看 description 长度 ≤ 60 字符吗？太长被截断（不影响渲染但显示不全）
4. 看 articles.length ≤ 8 吗？超过部分悄悄丢

## 不要做的事

- 不要试图用 emoji / 换行 / 富文本绕开 description 限制——微信前端会过滤
- 不要每条都填 description 期待显示——平台不渲染
- 不要在 title 里塞太长的"伪描述"——超过 ~16 个汉字会截断
