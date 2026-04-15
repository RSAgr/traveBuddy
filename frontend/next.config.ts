import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
      {
        protocol: "https",
        hostname: "places.googleapis.com",
      }
    ],
  },
  rewrites: async () => {
    return [
      {
        source: "/api/proxy/:path*",
        destination: "https://travebuddy.onrender.com/:path*",
      },
    ];
  },
};

export default nextConfig;
