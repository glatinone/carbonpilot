// Capture live CarbonPilot app screens (dashboard, upload, insights, simulator
// start + constraint-search result, actions, japac) via CDP on port 9223.
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = process.env.CDP_PORT || 9223;
const BASE = "https://rakazo-civo.tail1b51ed.ts.net:8443";
const OUT = process.argv[2] || path.join(__dirname, "..", "assets", "captures");
fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function getTargets() {
  return new Promise((res, rej) => {
    http.get(`http://127.0.0.1:${PORT}/json`, (r) => {
      let d = "";
      r.on("data", (c) => (d += c));
      r.on("end", () => res(JSON.parse(d)));
    }).on("error", rej);
  });
}

async function main() {
  const targets = await getTargets();
  const page = targets.find((t) => t.type === "page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const mid = ++id;
      pending.set(mid, { res, rej });
      ws.send(JSON.stringify({ id: mid, method, params }));
    });
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? p.rej(new Error(JSON.stringify(msg.error))) : p.res(msg.result);
    }
  };
  await new Promise((res) => (ws.onopen = res));
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });

  const ev = async (expr) =>
    (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result?.value ?? null;
  const shot = async (name) => {
    const s = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, name), Buffer.from(s.data, "base64"));
    console.log("saved", name);
  };
  const goto = async (route, wait = 4000) => {
    await send("Page.navigate", { url: BASE + route });
    await sleep(wait);
  };

  await goto("/", 5000);
  console.log("dash:", (await ev("document.body.innerText")).slice(0, 120).replace(/\n/g, " | "));
  await shot("01-dashboard.png");

  await goto("/upload/");
  await shot("02-upload.png");

  await goto("/insights/");
  await shot("03-insights.png");

  await goto("/simulator/", 5000);
  await shot("04-simulator-before.png");

  // Constraint search: 15% min reduction (default) + 0 max cost increase.
  const before = await ev(`JSON.stringify(Array.from(document.querySelectorAll('input[type=number]')).map(e=>e.value))`);
  console.log("number inputs before:", before);
  await ev(`(() => {
    const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    const nums = Array.from(document.querySelectorAll('input[type=number]'));
    if (nums[0]) { set.call(nums[0], '15'); nums[0].dispatchEvent(new Event('input', {bubbles:true})); nums[0].dispatchEvent(new Event('change', {bubbles:true})); }
    if (nums[1]) { set.call(nums[1], '0');  nums[1].dispatchEvent(new Event('input', {bubbles:true})); nums[1].dispatchEvent(new Event('change', {bubbles:true})); }
    return nums.length;
  })()`);
  await sleep(600);
  await ev(`(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Find scenarios');
    if (btn) { btn.click(); return 'clicked'; }
    return 'no button';
  })()`);
  await sleep(9000); // engine enumerates 2,098 combinations
  let after = await ev("document.body.innerText");
  const i = after.toLowerCase().indexOf("feasible");
  console.log("result region:", i >= 0 ? after.slice(Math.max(0, i - 300), i + 400).replace(/\n+/g, " | ") : "no feasible text found");
  await shot("05-simulator-result.png");

  await goto("/actions/");
  await shot("06-actions.png");

  await goto("/japac/");
  await shot("07-japac.png");

  ws.close();
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(1); });