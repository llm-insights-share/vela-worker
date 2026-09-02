// slide-04.js — Positioning content
const pptxgen = require("pptxgenjs");

const slideConfig = { type: "content", index: 4, title: "系统定位" };

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

  slide.addText("系统定位：从「可调用能力」到「可派活员工」", {
    x: 0.5, y: 0.35, w: 9, h: 0.5,
    fontSize: 22, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  // left card - agent
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.5, y: 1.1, w: 4.3, h: 3.6,
    fill: { color: theme.bg }, rectRadius: 0.1,
  });
  slide.addText("vela-agent", {
    x: 0.75, y: 1.3, w: 3.8, h: 0.35,
    fontSize: 14, fontFace: "Arial", color: theme.secondary, bold: true, margin: 0,
  });
  slide.addText("怎么干", {
    x: 0.75, y: 1.7, w: 3.8, h: 0.45,
    fontSize: 28, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });
  slide.addText([
    { text: "SINGLE / COMPOSITE / WORKFLOW 执行体", options: { bullet: true, breakLine: true } },
    { text: "Skills · Tools · KB · Memory", options: { bullet: true, breakLine: true } },
    { text: "Coordinator 分派与汇总", options: { bullet: true, breakLine: true } },
    { text: "Sessions · HITL Approvals", options: { bullet: true, breakLine: true } },
    { text: "推理、工具调用、预算熔断", options: { bullet: true } },
  ], {
    x: 0.75, y: 2.35, w: 3.8, h: 2.1,
    fontSize: 13, fontFace: "Microsoft YaHei", color: theme.secondary, margin: 0,
  });

  // right card - worker
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.2, y: 1.1, w: 4.3, h: 3.6,
    fill: { color: theme.primary }, rectRadius: 0.1,
  });
  slide.addText("vela-worker", {
    x: 5.45, y: 1.3, w: 3.8, h: 0.35,
    fontSize: 14, fontFace: "Arial", color: theme.light, bold: true, margin: 0,
  });
  slide.addText("谁来干 / 干什么", {
    x: 5.45, y: 1.7, w: 3.8, h: 0.45,
    fontSize: 26, fontFace: "Microsoft YaHei", color: "FFFFFF", bold: true, margin: 0,
  });
  slide.addText([
    { text: "组织身份（工号 D- / 部门 / 在岗）", options: { bullet: true, breakLine: true } },
    { text: "职责库 · 角色 · 入口 COMPOSITE", options: { bullet: true, breakLine: true } },
    { text: "Task 状态机 · Open API · Webhook", options: { bullet: true, breakLine: true } },
    { text: "IM 会话 · HITL 桥接 · 推送", options: { bullet: true, breakLine: true } },
    { text: "零侵入：仅 REST 适配 vela-agent", options: { bullet: true } },
  ], {
    x: 5.45, y: 2.35, w: 3.8, h: 2.1,
    fontSize: 13, fontFace: "Microsoft YaHei", color: theme.bg, margin: 0,
  });

  pageBadge(slide, pres, theme, 4);
  return slide;
}

module.exports = { createSlide, slideConfig };
