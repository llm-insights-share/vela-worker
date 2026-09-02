// slide-07.js — Domain model / COMPOSITE
const pptxgen = require("pptxgenjs");
const slideConfig = { type: "content", index: 8, title: "领域模型" };

function pageBadge(slide, pres, theme, n) {
  slide.addShape(pres.shapes.OVAL, {
    x: 9.3, y: 5.1, w: 0.4, h: 0.4, fill: { color: theme.accent },
  });
  slide.addText(String(n), {
    x: 9.3, y: 5.1, w: 0.4, h: 0.4,
    fontSize: 12, fontFace: "Arial", color: "FFFFFF", bold: true,
    align: "center", valign: "middle", margin: 0,
  });
}

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: "FFFFFF" };
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.12, fill: { color: theme.primary },
  });
  slide.addText("数字员工运行时模型：入口 COMPOSITE + 子 Agent", {
    x: 0.5, y: 0.3, w: 9, h: 0.45,
    fontSize: 20, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  // Entry box
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 2.5, y: 0.95, w: 5, h: 0.85,
    fill: { color: theme.primary }, rectRadius: 0.08,
  });
  slide.addText("入口 Agent  COMPOSITE\nentry_agent_id · memory · Coordinator", {
    x: 2.5, y: 0.95, w: 5, h: 0.85,
    fontSize: 13, fontFace: "Microsoft YaHei", color: "FFFFFF",
    align: "center", valign: "middle", margin: 0,
  });

  // arrows down via lines
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 4.95, y: 1.8, w: 0.1, h: 0.35, fill: { color: theme.accent },
  });

  const children = [
    { x: 0.45, t: "基础接待\nSINGLE", d: "寒暄/介绍/拒答\nreception_agent_id" },
    { x: 3.55, t: "职责 Agent\nSINGLE × N", d: "模板克隆实例\nWorkerDutyAgent" },
    { x: 6.65, t: "专业能力绑定", d: "Skills / Tools / KB\n治理与 HITL" },
  ];
  children.forEach((c) => {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: c.x, y: 2.25, w: 2.9, h: 1.55,
      fill: { color: theme.bg }, rectRadius: 0.08,
    });
    slide.addText(c.t, {
      x: c.x + 0.15, y: 2.4, w: 2.6, h: 0.65,
      fontSize: 14, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0, align: "center",
    });
    slide.addText(c.d, {
      x: c.x + 0.15, y: 3.1, w: 2.6, h: 0.55,
      fontSize: 11, fontFace: "Microsoft YaHei", color: theme.secondary, margin: 0, align: "center",
    });
  });

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.5, y: 4.05, w: 9, h: 0.85,
    fill: { color: "F5F7FA" }, rectRadius: 0.08,
  });
  slide.addText([
    { text: "请求统一进入口：", options: { bold: true } },
    { text: "IM / Task / OpenAPI / Push → entry COMPOSITE → Coordinator 按关键词与角色描述分派。", options: { breakLine: true } },
    { text: "组织侧：", options: { bold: true } },
    { text: "Role.duty_ids → 入职克隆；追加/移除职责原地同步 composition（避免同名 409）。" },
  ], {
    x: 0.7, y: 4.15, w: 8.6, h: 0.7,
    fontSize: 12, fontFace: "Microsoft YaHei", color: theme.secondary, margin: 0,
  });

  pageBadge(slide, pres, theme, 8);
  return slide;
}
module.exports = { createSlide, slideConfig };
