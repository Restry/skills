// Reference parser (JS) — 爸爸提供，作为 v4 Python 重写蓝本。
// 当前 gateway 是 v1 粗粒度问号检测；按 SKILL.md「Parser 设计原则」升级时翻译此版本。
//
// 三层规则（按命中优先级）：
//   1. 显式列表选项 A/B/C/D 或 1/2/3/4 或 a/b/c/d（兼容 -/+ 列表符 / . : 、 ) 分隔符）→ multi_choice
//   2. 行内「X 还是 Y？」→ multi_choice 两按钮
//   3. 末尾问句 + 动作关键词 → yes_no（白名单方案；本仓库倾向「信 prompt 取消白名单」，见 SKILL.md 坑 1）
//
// 预处理：先剥 markdown 噪音 `*_~`` 防止 `**A:**` 这种粗体破坏正则。
// 多选去重：用 Map 防正则重复匹配 / 同字母多次出现。
// 末问句兜底：从全文所有问句里取**最后一句**，即使后面跟着「期待回复」类废话仍能命中。

function parseActionableCard(text) {
  const result = {
    hasCard: false,
    type: null,
    questionText: '',
    options: []
  };
  if (!text) return result;

  // 【防御 1】预处理：移除加粗/斜体/code 反引号，屏蔽 markdown 干扰
  const cleanText = text.replace(/[*_`~]/g, '');

  // ──────────────────────────────────────────────
  // 规则 1：显式列表选项 (A/B/C/D, 1/2/3/4, a/b/c/d, 含列表符)
  // 兼容："- A:", "A.", "a)", "1、", "A："（中文冒号）
  // ──────────────────────────────────────────────
  const optionRegex = /(?:^|\n)\s*(?:[-+]\s*)?([A-Ea-e1-5])[.:：、)]\s*([^\n]+)/g;
  let match;
  const optionsMap = new Map();
  while ((match = optionRegex.exec(cleanText)) !== null) {
    const label = match[1].toUpperCase();
    optionsMap.set(label, { label, text: match[2].trim(), value: label });
  }
  const options = Array.from(optionsMap.values());

  if (options.length > 1) {
    result.hasCard = true;
    result.type = 'multiple_choice';
    result.options = options;
    const textBeforeOptions = cleanText.substring(0, cleanText.indexOf(options[0].text));
    const qMatch = textBeforeOptions.match(/([^。！？\n]*?[：:？?])(?=\s*$|\s*\n)/);
    result.questionText = qMatch ? qMatch[1].trim() : '请选择：';
    return result;
  }

  // ──────────────────────────────────────────────
  // 规则 2：行内「X 还是 Y？」
  // 容错："想做 A 呢，还是 B？" / "是 A, 还是 B"
  // ⚠️ 升级建议（见 SKILL.md 坑 2）：加长度对称校验
  //   - 单选项 ≤ 20 字 / 长度差 ≤ 15 字 / 含否定词 → 降级 yes_no
  // ──────────────────────────────────────────────
  const orPattern = /([^，。！？\n]+?)[，,\s]*还是\s*([^，。！？\n]+?)[？?]/;
  const orMatch = cleanText.match(orPattern);
  if (orMatch) {
    result.hasCard = true;
    result.type = 'multiple_choice';
    result.questionText = orMatch[0].trim();
    result.options = [
      { label: '选项 A', text: orMatch[1].trim(), value: 'A' },
      { label: '选项 B', text: orMatch[2].trim(), value: 'B' }
    ];
    return result;
  }

  // ──────────────────────────────────────────────
  // 规则 3：末尾 Yes/No 问句（取最后问句而非文本末尾，跳过废话尾巴）
  // ⚠️ 本仓库 SKILL.md 坑 1 倾向取消白名单 → 改成「末问句一律 yes_no」+ 始终带「💬 手动输入」按钮兜底
  // ──────────────────────────────────────────────
  const allQuestions = cleanText.match(/([^。！？\n]+[？?])/g);
  if (allQuestions && allQuestions.length > 0) {
    const lastQuestion = allQuestions[allQuestions.length - 1].trim();
    const actionKeywords = /(是否(需要|确认|同意|执行))|(确认|授权|执行).*?(吗|没问题)|(保留|删除|修改).*?(吗|？)|可以.*?(执行|操作).*?吗/;
    if (actionKeywords.test(lastQuestion)) {
      result.hasCard = true;
      result.type = 'yes_no';
      result.questionText = lastQuestion;
      result.options = [
        { label: '确认 / 执行', value: 'yes', style: 'primary' },
        { label: '取消 / 否',    value: 'no',  style: 'danger' }
      ];
      return result;
    }
  }

  return result;
}

module.exports = { parseActionableCard };
