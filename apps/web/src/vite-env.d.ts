/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEV_USER_ID?: string;
  readonly VITE_REQUIRE_AUTH?: "true" | "false";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
