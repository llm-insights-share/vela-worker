// slide-12.js — HITL bridge
const pptxgen = require("pptxgenjs");
const slideConfig = { type: "content", index: 13, title: "HITL 桥接" };

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
  slide.addText("HITL：agent 审批能力 × worker 组织触达", {
    x: 0.5, y: 0.3, w: 9, h: 0.4,
    fontSize: 20, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  const cols = [
    { t: "vela-agent", items: ["Approval 实体与策略", "NEED_HUMAN 挂起会话", "Resume 后继续执行"] },
    { t: "vela-worker", items: ["IM 审批卡片渲染", "人审回调 → resume", "推送 NEED_HUMAN 事件"] },
    { t: "企业触点", items: ["IM / 管理后台", "Webhook 通知业务系统", "审计与超时策略"] },
  ];
  cols.forEach((c, i) => {
    const x = 0.5 + i * 3.15;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: 0.95, w: 3.0, h: 3.5,
      fill: { color: i === 1 ? theme.primary : theme.bg }, rectRadius: 0.1,
    });
    const tc = i === 1 ? "FFFFFF" : theme.primary;
    const bc = i === 1 ? theme.light : theme.secondary;
    slide.addText(c.t, {
      x: x + 0.2, y: 1.2, w: 2.6, h: 0.4,
      fontSize: 16, fontFace: "Arial", color: tc, bold: true, margin: 0,
    });
    c.items.forEach((it, j) => {
      slide.addText("▸  " + it, {
        x: x + 0.2, y: 1.9 + j * 0.65, w: 2.6, h: 0.5,
        fontSize: 14, fontFace: "Microsoft YaHei", color: bc, margin: 0,
      });
    });
  });

  pageBadge(slide, pres, theme, 13);
  return slide;
}
module.exports = { createSlide, slideConfig };
