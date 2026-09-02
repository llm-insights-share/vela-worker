// slide-15.js — Summary
const pptxgen = require("pptxgenjs");
const slideConfig = { type: "summary", index: 16, title: "要点回顾" };

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
  slide.addText("要点回顾", {
    x: 0.5, y: 0.3, w: 8, h: 0.45,
    fontSize: 28, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  const points = [
    { n: "01", t: "分工清晰", d: "agent 负责怎么干；worker 负责谁来干、干什么、如何派活与问责" },
    { n: "02", t: "一人一入口", d: "每名数字员工一个 COMPOSITE 入口 + 接待 SINGLE + 职责子 Agent" },
    { n: "03", t: "契约外化", d: "Worker Spec · Task 状态机 · Open API / Webhook 对接企业系统" },
    { n: "04", t: "零侵入", d: "仅通过 REST 适配复用 vela-agent，组织态与执行态边界分明" },
  ];
  points.forEach((p, i) => {
    const y = 0.95 + i * 0.95;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.5, y, w: 9.0, h: 0.85,
      fill: { color: i % 2 === 0 ? theme.bg : "F5F7FA" }, rectRadius: 0.08,
    });
    slide.addText(p.n, {
      x: 0.7, y: y + 0.2, w: 0.7, h: 0.45,
      fontSize: 18, fontFace: "Arial", color: theme.secondary, bold: true, margin: 0, valign: "middle",
    });
    slide.addText(p.t, {
      x: 1.5, y: y + 0.12, w: 7.7, h: 0.3,
      fontSize: 15, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
    });
    slide.addText(p.d, {
      x: 1.5, y: y + 0.45, w: 7.7, h: 0.3,
      fontSize: 12, fontFace: "Microsoft YaHei", color: theme.secondary, margin: 0,
    });
  });

  pageBadge(slide, pres, theme, 16);
  return slide;
}
module.exports = { createSlide, slideConfig };
