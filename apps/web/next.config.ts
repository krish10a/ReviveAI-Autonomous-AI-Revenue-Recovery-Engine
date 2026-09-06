import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // In production, we don't need rewrites if we're hitting the API directly,
    // but if we do, point it to the deployed API URL
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
