// slide-01.js — Cover
const pptxgen = require("pptxgenjs");

const slideConfig = {
  type: "cover",
  index: 1,
  title: "Vela·Worker 数字员工架构与设计",
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.primary };

  // decorative blocks
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 7.2, y: 0, w: 2.8, h: 5.625,
    fill: { color: theme.secondary },
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 8.4, y: 0, w: 1.6, h: 5.625,
    fill: { color: theme.accent },
  });

  slide.addText("TECHNICAL BRIEFING", {
    x: 0.55, y: 1.35, w: 6.4, h: 0.35,
    fontSize: 12, fontFace: "Arial",
    color: theme.light, bold: true, margin: 0, charSpacing: 3,
  });

  slide.addText("Vela·Worker\n数字员工架构与设计", {
    x: 0.55, y: 1.85, w: 6.5, h: 1.6,
    fontSize: 36, fontFace: "Microsoft YaHei",
    color: "FFFFFF", bold: true, margin: 0, valign: "top",
  });

  slide.addText("面向 AI 应用与开发专家 · 结合 vela-worker / vela-agent 实现", {
    x: 0.55, y: 3.65, w: 6.4, h: 0.4,
    fontSize: 14, fontFace: "Microsoft YaHei",
    color: theme.light, margin: 0,
  });

  slide.addText("v1.0  |  零侵入复用 Agent 运行时  |  2026", {
    x: 0.55, y: 5.05, w: 6.4, h: 0.3,
    fontSize: 12, fontFace: "Arial",
    color: theme.accent, margin: 0,
  });

  return slide;
}

if (require.main === module) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  const theme = {
    primary: "03045e", secondary: "0077b6", accent: "00b4d8",
    light: "90e0ef", bg: "caf0f8",
  };
  createSlide(pres, theme);
  pres.writeFile({ fileName: "slide-01-preview.pptx" });
}

module.exports = { createSlide, slideConfig };
