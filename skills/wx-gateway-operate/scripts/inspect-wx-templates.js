// Run from an authorized gateway project with its existing environment.
// See references/troubleshooting.md and references/deployment.md.
// Do not start the stopped pucs instance or print credentials.

const { PrismaClient } = require('@prisma/client');

(async () => {
  const p = new PrismaClient();
  const cache = await p.wxAccessTokenCache.findFirst({ orderBy: { expiresAt: 'desc' } });
  if (!cache || cache.expiresAt < new Date()) {
    console.error(JSON.stringify({ error: 'no_valid_token', cachePresent: Boolean(cache) }));
    process.exit(1);
  }
  const token = cache.accessToken;

  // 服务号「我的模板」(传统模板消息)
  // https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Template_Message_Interface.html
  const r1 = await fetch(
    `https://api.weixin.qq.com/cgi-bin/template/get_all_private_template?access_token=${token}`,
  );
  const wxTraditional = await r1.json();

  // 服务号当前所属行业（限定可发哪些行业的模板）
  const r2 = await fetch(
    `https://api.weixin.qq.com/cgi-bin/template/get_industry?access_token=${token}`,
  );
  const wxIndustry = await r2.json();

  // 服务号「订阅通知」我的模板
  // 注意 endpoint 在 wxaapi/newtmpl/* 而不是 cgi-bin/template/*
  // https://developers.weixin.qq.com/doc/offiaccount/Subscription_Messages/api.html
  const r3 = await fetch(
    `https://api.weixin.qq.com/wxaapi/newtmpl/gettemplate?access_token=${token}`,
  );
  const wxSubscribe = await r3.json();

  // 订阅通知当前已开通类目（公众号后台「订阅通知 → 选用类目」改，每月 1 次）
  const r4 = await fetch(
    `https://api.weixin.qq.com/wxaapi/newtmpl/getcategory?access_token=${token}`,
  );
  const wxSubscribeCategories = await r4.json();

  // 本网关侧已 sync 的模板表
  const localRows = await p.wxTemplate.findMany({
    orderBy: [{ appName: 'asc' }, { title: 'asc' }],
  });

  // 本实例所有 active app
  const apps = await p.app.findMany({
    where: { status: 'active' },
    select: {
      name: true,
      displayName: true,
      appBaseUrl: true,
      callbackUrl: true,
      paymentEnabled: true,
    },
  });

  console.log(
    JSON.stringify(
      {
        wx_my_templates: wxTraditional,
        wx_industry: wxIndustry,
        wx_subscribe_my_templates: wxSubscribe,
        wx_subscribe_categories: wxSubscribeCategories,
        local_wx_templates: localRows,
        apps,
        token_expires_at: cache.expiresAt,
      },
      null,
      2,
    ),
  );
  await p.$disconnect();
})().catch((e) => {
  console.error('ERR:', e.message);
  process.exit(1);
});
