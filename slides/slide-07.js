// slide-07.js — Section domain model
const pptxgen = require("pptxgenjs");
const slideConfig = { type: "section-divider", index: 7, title: "领域模型" };

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
  slide.background = { color: theme.secondary };
  slide.addText("03", {
    x: 0.6, y: 1.7, w: 2, h: 0.6,
    fontSize: 48, fontFace: "Arial", color: theme.light, bold: true, margin: 0,
  });
  slide.addText("领域模型", {
    x: 0.6, y: 2.4, w: 8, h: 0.7,
    fontSize: 40, fontFace: "Microsoft YaHei", color: "FFFFFF", bold: true, margin: 0,
  });
  slide.addText("身份 · 职责 · 入口 COMPOSITE · 接待与子 Agent", {
    x: 0.6, y: 3.3, w: 8.5, h: 0.5,
    fontSize: 16, fontFace: "Microsoft YaHei", color: theme.bg, margin: 0,
  });
  pageBadge(slide, pres, theme, 7);
  return slide;
}
module.exports = { createSlide, slideConfig };
