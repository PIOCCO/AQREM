import { PRODUCT_V1 } from "./productV1";

export const APP_BUILD_ID = import.meta.env.VITE_BUILD_ID || "unknown";
export const APP_BUILD_TIME = import.meta.env.VITE_BUILD_TIME || "";

/** Short label for admin-only UI (e.g. account menu). */
export function adminBuildMarker(): string {
  return `UI ${APP_BUILD_ID} · ${PRODUCT_V1 ? "V1" : "Legacy"}`;
}
