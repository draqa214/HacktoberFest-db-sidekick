import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: { proxyClientMaxBodySize: "20mb", proxyTimeout: 150_000 },
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: "http://127.0.0.1:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
