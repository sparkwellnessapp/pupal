const path = require("path");
const { pathToFileURL } = require("url");
const { chromium } = require(process.env.PW_PATH);
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1540, height: 1200 } });
  const msgs = [];
  page.on("console", (m) => msgs.push(m.type() + ": " + m.text()));
  page.on("pageerror", (e) => msgs.push("pageerror: " + e.message));
  const file = process.argv[2] || "rtl_test.html";
  await page.goto(pathToFileURL(path.join(__dirname, file)).href);
  await page.waitForTimeout(3000);
  const defined = await page.evaluate(() => !!customElements.get("math-field"));
  const out = path.join(__dirname, file.replace(/\.html$/, ".png"));
  await page.screenshot({ path: out, fullPage: true });
  console.log("math-field defined:", defined, "->", out);
  console.log(msgs.slice(0, 8).join("\n"));
  await browser.close();
})();
