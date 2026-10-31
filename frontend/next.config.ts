import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lets a production build run beside `npm run dev` without overwriting its .next folder.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
