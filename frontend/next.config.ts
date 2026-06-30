import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16.2.6 currently emits a malformed generated route-types file in
  // this project (`.next/dev/types/routes.d.ts`). We run `tsc --noEmit`
  // separately for source type-checking and let `next build` focus on the
  // production bundle until the upstream generator is fixed/upgraded.
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
