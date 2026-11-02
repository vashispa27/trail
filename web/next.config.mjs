/** @type {import('next').NextConfig} */
const nextConfig = {
  // The dashboard reads the bundled demo store from disk when no remote store is set.
  outputFileTracingIncludes: {
    "/repos/**/*": ["./demo-store/**/*"],
    "/repos": ["./demo-store/**/*"],
  },
};

export default nextConfig;
