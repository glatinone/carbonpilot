// Capture deterministic HTML animation to frames via Chrome CDP.
// Usage: node capture_frames.js <file-url> <fps> <t_end> <outdir> [WxH] [fmt] [quality]
// Chrome must be running with --remote-debugging-port (default 9222, env CDP_PORT).
const http = require("http");
const fs = require("fs");
const path = require("path");

const [url, fpsS, endS, outdir, size, fmt, qS] = process.argv.slice(2);
const fps = parseInt(fpsS, 10);
const tEnd = parseFloat(endS);
const [W, H] = (size || "1920x1080").split("x").map(Number);
const format = fmt || "png";
const quality = qS ? parseInt(qS, 10) : 85;
fs.mkdirSync(outdir, { recursive: true });

function getTargets(port) {
  return new Promise((res, rej) => {
    http.get(`http://127.0.0.1:${port}/json`, (r) => {
      let d = "";
      r.on("data", (c) => (d += c));
      r.on("end", () => res(JSON.parse(d)));
    }).on("error", rej);
  });
}

async function main() {
  const port = parseInt(process.env.CDP_PORT || "9222", 10);
  const targets = await getTargets(port);
  const page = targets.find((t) => t.type === "page");
  if (!page) throw new Error("no page target on port " + port);
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
      if (msg.error) p.rej(new Error(JSON.stringify(msg.error)));
      else p.res(msg.result);
    }
  };
  await new Promise((res) => (ws.onopen = res));

  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", {
    width: W, height: H, deviceScaleFactor: 1, mobile: false,
  });
  await send("Page.navigate", { url });
  await new Promise((res) => setTimeout(res, 2500)); // let fonts/layout settle

  const total = Math.floor(tEnd * fps);
  const t0 = Date.now();
  for (let i = 0; i <= total; i++) {
    const t = i / fps;
    await send("Runtime.evaluate", {
      expression: `window.__setTime(${t})`,
      returnByValue: true,
    });
    const shot = await send("Page.captureScreenshot", format === "jpeg"
      ? { format: "jpeg", quality }
      : { format: "png" });
    const ext = format === "jpeg" ? "jpg" : "png";
    fs.writeFileSync(path.join(outdir, `f_${String(i).padStart(6, "0")}.${ext}`),
      Buffer.from(shot.data, "base64"));
    if (i % 300 === 0) {
      const el = ((Date.now() - t0) / 1000).toFixed(0);
      console.log(`frame ${i}/${total} elapsed ${el}s`);
    }
  }
  const el = ((Date.now() - t0) / 1000).toFixed(0);
  console.log(`DONE ${total + 1} frames in ${el}s`);
  ws.close();
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(1); });
