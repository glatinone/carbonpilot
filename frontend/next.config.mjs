/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export: `next build` writes ./out, which the FastAPI backend serves
  // on the same port as the API. That gives a single-process demo — no Node
  // needed on the presenting machine once the UI has been built once.
  output: "export",
  images: { unoptimized: true },
  // Emits insights/index.html instead of insights.html so a plain static file
  // server (FastAPI's StaticFiles) resolves routes without rewrites.
  trailingSlash: true,
};

export default nextConfig;
