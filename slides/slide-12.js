// slide-11.js — IM routing + reception
const pptxgen = require("pptxgenjs");
const slideConfig = { type: "content", index: 12, title: "IM 路由与接待" };

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
  slide.addText("IM：统一进入口 COMPOSITE，不在 worker 侧拆职责", {
    x: 0.5, y: 0.3, w: 9, h: 0.4,
    fontSize: 20, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  const steps = [
    { n: "1", t: "用户 @员工", d: "IM 会话绑定 worker" },
    { n: "2", t: "注入上下文", d: "【近期对话】+【当前用户消息】" },
    { n: "3", t: "entry COMPOSITE", d: "Coordinator 分派子 Agent" },
    { n: "4", t: "接待 / 职责", d: "寒暄介绍 · 业务执行 · OOS 拒答" },
  ];
  steps.forEach((s, i) => {
    const x = 0.45 + i * 2.4;
    slide.addShape(pres.shapes.OVAL, {
      x: x + 0.85, y: 0.95, w: 0.45, h: 0.45,
      fill: { color: theme.secondary },
    });
    slide.addText(s.n, {
      x: x + 0.85, y: 0.95, w: 0.45, h: 0.45,
      fontSize: 14, fontFace: "Arial", color: "FFFFFF", bold: true,
      align: "center", valign: "middle", margin: 0,
    });
    if (i < 3) {
      slide.addShape(pres.shapes.RECTANGLE, {
        x: x + 1.4, y: 1.12, w: 1.7, h: 0.08, fill: { color: theme.light },
      });
    }
    slide.addText(s.t, {
      x, y: 1.55, w: 2.25, h: 0.35,
      fontSize: 14, fontFace: "Microsoft YaHei", color: theme.primary, bold: true,
      align: "center", margin: 0,
    });
    slide.addText(s.d, {
      x, y: 1.9, w: 2.25, h: 0.45,
      fontSize: 11, fontFace: "Microsoft YaHei", color: theme.secondary,
      align: "center", margin: 0,
    });
  });

  // two callouts
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.5, y: 2.55, w: 4.4, h: 2.2,
    fill: { color: theme.bg }, rectRadius: 0.1,
  });
  slide.addText("基础接待 SINGLE", {
    x: 0.75, y: 2.75, w: 4, h: 0.35,
    fontSize: 16, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });
  slide.addText("挂载在 COMPOSITE 首位\n自我介绍 · 能力边界说明\n职责外礼貌拒答（OOS）\n不抢业务职责关键词", {
    x: 0.75, y: 3.2, w: 4, h: 1.35,
    fontSize: 13, fontFace: "Microsoft YaHei", color: theme.secondary, margin: 0,
  });

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.1, y: 2.55, w: 4.4, h: 2.2,
    fill: { color: theme.primary }, rectRadius: 0.1,
  });
  slide.addText("为何需要接待子 Agent", {
    x: 5.35, y: 2.75, w: 4, h: 0.35,
    fontSize: 16, fontFace: "Microsoft YaHei", color: "FFFFFF", bold: true, margin: 0,
  });
  slide.addText("COMPOSITE 父级 system_prompt\n不参与 Coordinator 推理\n接待能力必须是可调度子 Agent\n现有员工可用「修复编排」补齐", {
    x: 5.35, y: 3.2, w: 4, h: 1.35,
    fontSize: 13, fontFace: "Microsoft YaHei", color: theme.bg, margin: 0,
  });

  pageBadge(slide, pres, theme, 12);
  return slide;
}
module.exports = { createSlide, slideConfig };
