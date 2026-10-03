#!/usr/bin/env node
/**
 * Refuse to run `next build` while the dev server is live.
 *
 * `next dev` and `next build` share one `.next` directory. Building while dev
 * is running swaps the manifests underneath the server, which then answers 500
 * on every page — with a confusing "React Server Components bundler" error —
 * until it is restarted. This has bitten the demo twice.
 *
 * The single-port demo genuinely needs `next build`, so this is a check, not a
 * ban: it fails fast with instructions, and stays out of the way when nothing
 * is listening (CI, a fresh checkout, a stopped dev server).
 *
 * Wired as npm's `prebuild`, so `npm run build` is always protected.
 */
import net from 'node:net'

const HOST = '127.0.0.1'
const PORT = Number(process.env.CARBONPILOT_DEV_PORT || 3000)

// Escape hatch for the rare case where something else owns the port and you
// accept that a dev server on it will break.
if (process.env.ALLOW_BUILD_WITH_DEV === '1') {
  process.exit(0)
}

const socket = net.connect({ host: HOST, port: PORT })
let settled = false

function finish(code, message) {
  if (settled) return
  settled = true
  socket.destroy()
  if (message) {
    if (code === 0) console.log(message)
    else console.error(message)
  }
  process.exit(code)
}

socket.setTimeout(1500)
socket.on('connect', () =>
  finish(
    1,
    [
      '',
      `  Blocked: something is already listening on ${HOST}:${PORT}.`,
      '',
      '  If that is `npm run dev`, building now would break it: dev and build',
      '  share the .next directory, and the dev server would 500 until restarted.',
      '',
      '  Stop the dev server, then build. For the single-port demo:',
      '      npm run build',
      '      # then run the API, which serves frontend/out on the same port',
      '',
      '  To build anyway (the dev server on that port will break):',
      '      ALLOW_BUILD_WITH_DEV=1 npm run build',
      '',
    ].join('\n'),
  ),
)
socket.on('timeout', () => finish(0))
socket.on('error', () => finish(0)) // nothing listening — safe to build