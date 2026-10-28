const http = require("http"), fs = require("fs"), path = require("path");
const { chromium } = require(process.env.PW_PATH);
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf" };
const srv = http.createServer((req, res) => {
  const p = path.join(__dirname, decodeURIComponent(req.url.split("?")[0]));
  fs.readFile(p, (err, data) => {
    if (err) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { "content-type": types[path.extname(p)] || "application/octet-stream" });
    res.end(data);
  });
}).listen(0, async () => {
  const port = srv.address().port;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1140, height: 900 } });
  const msgs = [];
  page.on("console", (m) => msgs.push(m.type() + ": " + m.text()));
  page.on("pageerror", (e) => msgs.push("pageerror: " + e.message));
  await page.goto(`http://127.0.0.1:${port}/${process.argv[2]}`);
  await page.waitForFunction(() => window.__done === true, null, { timeout: 30000 }).catch(() => msgs.push("TIMEOUT waiting"));
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(__dirname, process.argv[2].replace(/\.html$/, ".png")), fullPage: true });
  console.log(await page.evaluate(() => document.getElementById("out")?.textContent));
  console.log(msgs.filter(m => !m.includes("DevTools")).slice(0, 6).join("\n"));
  await browser.close(); srv.close();
});
