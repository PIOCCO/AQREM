export const FOCUS_COMPOSER_EVENT = "aqrem-focus-composer";

export function dispatchFocusComposer() {
  window.dispatchEvent(new CustomEvent(FOCUS_COMPOSER_EVENT));
}
