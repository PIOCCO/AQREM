/** Line height must match `.chat-composer-input` (leading-6). */
export const COMPOSER_LINE_HEIGHT_PX = 24;

export function readComposerTextCapPx(textarea: HTMLTextAreaElement): number {
  const maxH = getComputedStyle(textarea).maxHeight;
  const n = Number.parseFloat(maxH);
  if (Number.isFinite(n) && n > 0) return n;
  return Math.min(150, window.innerHeight * 0.3);
}

export function measureClampedTextareaHeight(textarea: HTMLTextAreaElement): number {
  const cap = readComposerTextCapPx(textarea);
  const prev = textarea.style.height;
  textarea.style.height = "auto";
  const measured = Math.max(COMPOSER_LINE_HEIGHT_PX, textarea.scrollHeight);
  textarea.style.height = prev;
  return Math.min(measured, cap);
}

export function scrollTextareaCaretIntoView(textarea: HTMLTextAreaElement) {
  const cap = readComposerTextCapPx(textarea);
  if (textarea.clientHeight < cap - 1) return;
  textarea.scrollTop = textarea.scrollHeight;
}
