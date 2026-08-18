import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Fix: Turbopack resolves modules starting from the parent CPET_system directory
  // (because it has no package.json). Explicitly alias tailwindcss and
  // @tailwindcss/postcss to their absolute paths inside web_dashboard/node_modules.
  turbopack: {
    resolveAlias: {
      tailwindcss: path.resolve(__dirname, "node_modules/tailwindcss"),
    },
  },
  // Keep webpack fix too (for non-Turbopack contexts)
  webpack(config) {
    config.resolve.modules = [
      path.resolve(__dirname, "node_modules"),
      "node_modules",
    ];
    return config;
  },
};

export default nextConfig;
