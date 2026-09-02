// slide-09.js — Worker Spec + Open API
const pptxgen = require("pptxgenjs");
const slideConfig = { type: "content", index: 10, title: "Worker Spec & Open API" };

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
  slide.addText("Worker Spec 与任务契约", {
    x: 0.5, y: 0.3, w: 9, h: 0.4,
    fontSize: 22, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  const groups = [
    { t: "identity", d: "工号 D- · 部门 · ON_DUTY" },
    { t: "entry_agent", d: "COMPOSITE + reception" },
    { t: "capabilities", d: "duties[] 子 Agent · task_types" },
    { t: "governance", d: "L1–L4 · HITL · token/并发" },
  ];
  groups.forEach((g, i) => {
    const x = 0.5 + (i % 4) * 2.3;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: 0.9, w: 2.15, h: 1.15,
      fill: { color: i % 2 === 0 ? theme.bg : "F5F7FA" }, rectRadius: 0.08,
    });
    slide.addText(g.t, {
      x: x + 0.1, y: 1.05, w: 1.95, h: 0.35,
      fontSize: 13, fontFace: "Consolas", color: theme.secondary, bold: true, margin: 0, align: "center",
    });
    slide.addText(g.d, {
      x: x + 0.1, y: 1.45, w: 1.95, h: 0.45,
      fontSize: 12, fontFace: "Microsoft YaHei", color: theme.primary, margin: 0, align: "center",
    });
  });

  slide.addText("Open API（异步受理）", {
    x: 0.5, y: 2.25, w: 9, h: 0.35,
    fontSize: 16, fontFace: "Microsoft YaHei", color: theme.primary, bold: true, margin: 0,
  });

  slide.addText([
    { text: "POST /open/workers/{id}/tasks", options: { breakLine: true } },
    { text: "X-API-Key · task_types 白名单 · 201 {task_id}", options: { breakLine: true } },
    { text: "Webhook: ACCEPTED / NEED_HUMAN / COMPLETED / FAILED", options: { breakLine: true } },
    { text: "HMAC 签名 · 指数退避重试 · delivery_id 幂等" },
  ], {
    x: 0.5, y: 2.65, w: 4.5, h: 1.8,
    fontSize: 13, fontFace: "Consolas", color: theme.secondary, margin: 0,
  });

  // state machine mini
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.3, y: 2.55, w: 4.2, h: 2.15,
    fill: { color: theme.primary }, rectRadius: 0.1,
  });
  slide.addText("Task 状态机", {
    x: 5.5, y: 2.7, w: 3.8, h: 0.3,
    fontSize: 14, fontFace: "Microsoft YaHei", color: theme.light, bold: true, margin: 0,
  });
  slide.addText("RECEIVED → RUNNING\n→ NEED_HUMAN ⇄ RUNNING\n→ COMPLETED | FAILED\nQUEUED / CANCELED", {
    x: 5.5, y: 3.15, w: 3.8, h: 1.35,
    fontSize: 14, fontFace: "Consolas", color: "FFFFFF", margin: 0,
  });

  pageBadge(slide, pres, theme, 10);
  return slide;
}
module.exports = { createSlide, slideConfig };
