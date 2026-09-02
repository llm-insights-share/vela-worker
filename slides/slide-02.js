// slide-02.js — TOC
const pptxgen = require("pptxgenjs");

const slideConfig = { type: "toc", index: 2, title: "目录" };

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
    x: 0, y: 0, w: 0.18, h: 5.625, fill: { color: theme.primary },
  });

  slide.addText("CONTENTS", {
    x: 0.55, y: 0.35, w: 4, h: 0.3,
    fontSize: 12, fontFace: "Arial", color: theme.accent, bold: true, margin: 0, charSpacing: 2,
  });
  slide.addText("目录", {
    x: 0.55, y: 0.65, w: 8, h: 0.55,
    fontSize: 32, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  const items = [
    ["01", "定位与边界", "数字员工 vs Agent 运行时"],
    ["02", "总体架构", "接入层 · worker 核心 · agent 运行时"],
    ["03", "领域模型", "身份 / 职责 / 入口 COMPOSITE"],
    ["04", "规格与开放接口", "Worker Spec · Task · Webhook"],
    ["05", "IM 与 HITL", "会话路由 · 审批桥接"],
    ["06", "集成与演进", "适配层 · 治理 · 路线图"],
  ];

  items.forEach((it, i) => {
    const col = i < 3 ? 0 : 1;
    const row = i % 3;
    const x = 0.55 + col * 4.6;
    const y = 1.5 + row * 1.1;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y, w: 4.3, h: 0.95,
      fill: { color: theme.bg }, rectRadius: 0.08,
    });
    slide.addText(it[0], {
      x: x + 0.2, y: y + 0.2, w: 0.7, h: 0.55,
      fontSize: 22, fontFace: "Arial", color: theme.secondary, bold: true, margin: 0, valign: "middle",
    });
    slide.addText(it[1], {
      x: x + 1.0, y: y + 0.18, w: 3.0, h: 0.35,
      fontSize: 16, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
    });
    slide.addText(it[2], {
      x: x + 1.0, y: y + 0.52, w: 3.0, h: 0.3,
      fontSize: 12, fontFace: "Microsoft YaHei", color: theme.secondary, margin: 0,
    });
  });

  pageBadge(slide, pres, theme, 2);
  return slide;
}

module.exports = { createSlide, slideConfig };
