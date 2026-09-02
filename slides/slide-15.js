// slide-14.js — Adapter + governance + roadmap
const pptxgen = require("pptxgenjs");
const slideConfig = { type: "content", index: 15, title: "适配与路线图" };

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
  slide.addText("零侵入适配与演进路径", {
    x: 0.5, y: 0.3, w: 9, h: 0.4,
    fontSize: 20, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.5, y: 0.9, w: 4.4, h: 3.9,
    fill: { color: theme.bg }, rectRadius: 0.1,
  });
  slide.addText("Adapter 原则", {
    x: 0.75, y: 1.1, w: 4, h: 0.35,
    fontSize: 16, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });
  slide.addText([
    { text: "不修改 vela-agent 源码", options: { bullet: true, breakLine: true } },
    { text: "VelaAgentClient → /api/v1/*", options: { bullet: true, breakLine: true } },
    { text: "Composition 原地更新避 409", options: { bullet: true, breakLine: true } },
    { text: "worker 持组织态与任务态", options: { bullet: true, breakLine: true } },
    { text: "agent 持执行态与审批态", options: { bullet: true, breakLine: true } },
    { text: "治理：L1–L4 · token · 并发", options: { bullet: true } },
  ], {
    x: 0.75, y: 1.6, w: 4, h: 2.9,
    fontSize: 13, fontFace: "Microsoft YaHei", color: theme.secondary, margin: 0,
  });

  const phases = [
    { p: "Now", d: "入口 COMPOSITE · 接待 · Open API · IM/HITL" },
    { p: "Next", d: "多 IM 通道 · 推送规则深化 · Spec 版本化" },
    { p: "Later", d: "跨员工协作 · 组织级编排 · 观测与成本闭环" },
  ];
  phases.forEach((ph, i) => {
    const y = 0.9 + i * 1.3;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 5.15, y, w: 4.35, h: 1.15,
      fill: { color: i === 0 ? theme.primary : "F5F7FA" }, rectRadius: 0.08,
    });
    slide.addText(ph.p, {
      x: 5.35, y: y + 0.18, w: 4, h: 0.3,
      fontSize: 14, fontFace: "Arial", color: i === 0 ? theme.light : theme.accent, bold: true, margin: 0,
    });
    slide.addText(ph.d, {
      x: 5.35, y: y + 0.52, w: 4, h: 0.45,
      fontSize: 13, fontFace: "Microsoft YaHei", color: i === 0 ? "FFFFFF" : theme.primary, margin: 0,
    });
  });

  pageBadge(slide, pres, theme, 15);
  return slide;
}
module.exports = { createSlide, slideConfig };
