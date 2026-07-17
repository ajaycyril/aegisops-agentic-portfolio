import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typedRoutes: true,
  outputFileTracingIncludes: {
    "/api/agent-runs": ["./lib/agentic/policies/public-demo.wasm"],
  },
};

export default nextConfig;
