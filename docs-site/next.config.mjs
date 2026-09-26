import { createMDX } from "fumadocs-mdx/next";

const withMDX = createMDX();

// The build is committed to `egrm/public/guide/` and ships with the app.
// Pages are served at `/guide` by egrm/utils/guide_page.py, which is the only
// thing that can resolve directory URLs like `/guide/docs/citizen/` to their
// index.html. Asset files need no such fallback, so they keep pointing at
// `/assets/egrm/guide/...` and are served straight off disk by nginx.
const BASE_PATH = "/guide";
const ASSET_PREFIX = "/assets/egrm/guide";

/** @type {import('next').NextConfig} */
const config = {
  output: "export",
  reactStrictMode: true,
  basePath: BASE_PATH,
  assetPrefix: ASSET_PREFIX,
  // Frappe serves these as plain files — there is no Next.js image optimiser
  // running in production, so the loader has to be a no-op.
  images: { unoptimized: true },
  // Emit `about/index.html` rather than `about.html`, so the static host
  // resolves directory-style URLs without extra nginx rules.
  trailingSlash: true,
};

export default withMDX(config);
