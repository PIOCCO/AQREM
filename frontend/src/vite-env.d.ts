/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BUILD_ID: string;
  readonly VITE_BUILD_TIME: string;
  readonly VITE_PRODUCT_V1: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
