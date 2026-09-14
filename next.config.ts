import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ['127.0.0.1'],
  // Local CPU summary/STT calls have bounded server timeouts up to 120 seconds.
  experimental: { proxyTimeout: 130000 },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.BACKEND_INTERNAL_URL || 'http://127.0.0.1:8000'}/:path*` }];
  },
  // Keep Turbopack discovery inside this repository even when a parent folder
  // contains an unrelated package lockfile.
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
