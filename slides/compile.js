// slides/compile.js
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "Vela Worker";
pres.title = "Vela·Worker 数字员工架构与设计";

const theme = {
  primary: "03045e",
  secondary: "0077b6",
  accent: "00b4d8",
  light: "90e0ef",
  bg: "caf0f8",
};

const SLIDE_COUNT = 16;
for (let i = 1; i <= SLIDE_COUNT; i++) {
  const num = String(i).padStart(2, "0");
  const slideModule = require(`./slide-${num}.js`);
  slideModule.createSlide(pres, theme);
}

const outDir = path.join(__dirname, "output");
fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, "presentation.pptx");

pres.writeFile({ fileName: outFile }).then(() => {
  console.log("Wrote", outFile);
}).catch((err) => {
  console.error(err);
  process.exit(1);
});
