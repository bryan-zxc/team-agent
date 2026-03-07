import nextConfig from "eslint-config-next";

export default [
  ...nextConfig,
  {
    rules: {
      // React 19 compiler rules — downgrade to warn while we incrementally
      // migrate patterns like ref-sync-during-render and setState-in-effects.
      "react-hooks/refs": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/immutability": "warn",
      // We use <img> for external avatar URLs and data URIs where next/image
      // optimisation isn't applicable.
      "@next/next/no-img-element": "warn",
    },
  },
];
