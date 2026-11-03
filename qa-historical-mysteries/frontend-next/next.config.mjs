const API = process.env.API_URL ?? "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // a single rule forwards /api/* to FastAPI (cookies and streamed answers included)
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
  // gzip would buffer the server-sent events and the answer would no longer appear word by word
  compress: false,
  experimental: { proxyTimeout: 120000 },
};

export default nextConfig;
