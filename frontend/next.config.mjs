/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
  // Redirect URL vecchi (pre-semplificazione) verso la home.
  async redirects() {
    return [
      { source: "/clusters", destination: "/", permanent: true },
      { source: "/clusters/:path*", destination: "/", permanent: true },
      { source: "/feed", destination: "/", permanent: true },
      { source: "/alerts", destination: "/", permanent: true },
      { source: "/coverage", destination: "/", permanent: true },
    ];
  },
};

export default nextConfig;
