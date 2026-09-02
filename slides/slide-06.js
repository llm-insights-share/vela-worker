// slide-06.js — Architecture layers
const pptxgen = require("pptxgenjs");
const slideConfig = { type: "content", index: 6, title: "三层架构" };

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
  slide.addText("分层架构与核心模块", {
    x: 0.5, y: 0.3, w: 9, h: 0.45,
    fontSize: 22, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  const layers = [
    { y: 0.95, title: "接入层", desc: "IM 前台 · 管理后台 · 企业应用（OA/BPM）", c: theme.bg, tc: theme.primary },
    { y: 1.95, title: "vela-worker :8100", desc: "Directory · Task Center · IM · HITL Bridge · Open API · Push · Adapter", c: theme.secondary, tc: "FFFFFF" },
    { y: 2.95, title: "vela-agent :8000", desc: "Agents · Composition · Sessions · Skills/Tools/KB · HITL · Memory", c: theme.primary, tc: "FFFFFF" },
  ];
  layers.forEach((L) => {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.5, y: L.y, w: 9.0, h: 0.85,
      fill: { color: L.c }, rectRadius: 0.08,
    });
    slide.addText(L.title, {
      x: 0.7, y: L.y + 0.12, w: 8.5, h: 0.32,
      fontSize: 16, fontFace: "Microsoft YaHei", color: L.tc, bold: true, margin: 0,
    });
    slide.addText(L.desc, {
      x: 0.7, y: L.y + 0.45, w: 8.5, h: 0.3,
      fontSize: 12, fontFace: "Microsoft YaHei", color: L.tc === "FFFFFF" ? theme.light : theme.secondary, margin: 0,
    });
  });

  slide.addText("原则：worker 不修改 agent 源码；经 VelaAgentClient 调用 /api/v1/*", {
    x: 0.5, y: 4.05, w: 9, h: 0.35,
    fontSize: 13, fontFace: "Microsoft YaHei", color: theme.secondary, italic: true, margin: 0,
  });

  const mods = [
    ["Directory", "角色/职责/入职"],
    ["Task", "状态机/轮询"],
    ["IM", "会话/@路由"],
    ["HITL", "审批卡片桥"],
  ];
  mods.forEach((m, i) => {
    const x = 0.5 + i * 2.3;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: 4.45, w: 2.15, h: 0.5,
      fill: { color: theme.bg }, rectRadius: 0.06,
    });
    slide.addText(`${m[0]}  ${m[1]}`, {
      x, y: 4.45, w: 2.15, h: 0.5,
      fontSize: 11, fontFace: "Microsoft YaHei", color: theme.primary,
      align: "center", valign: "middle", margin: 0,
    });
  });

  pageBadge(slide, pres, theme, 6);
  return slide;
}
module.exports = { createSlide, slideConfig };
