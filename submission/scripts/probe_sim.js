// Probe the simulator page UI (constraint search) on CDP port 9223.
const http = require("http");
const PORT = process.env.CDP_PORT || 9223;
const BASE = "https://rakazo-civo.tail1b51ed.ts.net:8443";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
http.get(`http://127.0.0.1:${PORT}/json`, (r) => {
  let d = "";
  r.on("data", (c) => (d += c));
  r.on("end", async () => {
    const page = JSON.parse(d).find((t) => t.type === "page");
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    let id = 0; const pending = new Map();
    const send = (m, p = {}) => new Promise((res, rej) => {
      const mid = ++id; pending.set(mid, { res, rej });
      ws.send(JSON.stringify({ id: mid, method: m, params: p }));
    });
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && pending.has(msg.id)) {
        const p = pending.get(msg.id); pending.delete(msg.id);
        msg.error ? p.rej(new Error(JSON.stringify(msg.error))) : p.res(msg.result);
      }
    };
    await new Promise((res) => (ws.onopen = res));
    await send("Page.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
    await send("Page.navigate", { url: BASE + "/simulator/" });
    await sleep(4500);
    const ev = async (e) => (await send("Runtime.evaluate", { expression: e, returnByValue: true })).result?.value;
    const txt = await ev("document.body.innerText");
    // constraint section = text after 'FIND SCENARIOS' or near sliders end
    const idx = txt.toLowerCase().indexOf("constraint");
    console.log("== constraint section ==");
    console.log(txt.slice(Math.max(0, idx - 200), idx + 1400).replace(/\n{2,}/g, "\n"));
    console.log("== controls ==");
    console.log(await ev(`JSON.stringify(Array.from(document.querySelectorAll('input,textarea,button,select')).map(e=>({t:e.tagName,id:e.id||'',ph:e.placeholder||'',txt:(e.textContent||'').trim().slice(0,50),type:e.type||'',cls:(e.className||'').slice(0,60)})))`));
    ws.close(); process.exit(0);
  });
});