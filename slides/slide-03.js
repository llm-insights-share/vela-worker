// slide-03.js — Section divider: Positioning
const pptxgen = require("pptxgenjs");

const slideConfig = { type: "section-divider", index: 3, title: "定位与边界" };

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

  slide.addText("01", {
    x: 0.6, y: 1.7, w: 2, h: 0.6,
    fontSize: 48, fontFace: "Arial", color: theme.light, bold: true, margin: 0,
  });
  slide.addText("定位与边界", {
    x: 0.6, y: 2.4, w: 8, h: 0.7,
    fontSize: 40, fontFace: "Microsoft YaHei", color: "FFFFFF", bold: true, margin: 0,
  });
  slide.addText("Agent 是能力；数字员工是有组织身份、职责边界与问责口径的服务主体", {
    x: 0.6, y: 3.3, w: 8.5, h: 0.5,
    fontSize: 16, fontFace: "Microsoft YaHei", color: theme.bg, margin: 0,
  });

  pageBadge(slide, pres, theme, 3);
  return slide;
}

module.exports = { createSlide, slideConfig };
