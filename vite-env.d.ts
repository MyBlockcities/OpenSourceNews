/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** Private/dev escape hatch only; visible in the public client bundle. */
  readonly VITE_API_BEARER_TOKEN?: string;
  readonly VITE_ALLOW_BROWSER_BEARER_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
