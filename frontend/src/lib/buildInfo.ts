/** Injected at production build time (see vite.config.ts). */
export function getUiBuildLabel(): string {
  const id = import.meta.env.VITE_BUILD_ID?.trim();
  const time = import.meta.env.VITE_BUILD_TIME?.trim();
  if (id && time) return `${id} · ${time.slice(0, 10)}`;
  if (id) return id;
  return import.meta.env.DEV ? "dev" : "unknown";
}
