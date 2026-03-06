/**
 * Copy text to clipboard with fallback for non-secure contexts (HTTP, Edge on Windows, etc.).
 * Primary: navigator.clipboard.writeText (requires HTTPS or localhost).
 * Fallback: document.execCommand("copy") via a temporary textarea.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // Try the modern Clipboard API first
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Clipboard API failed (non-secure context, permission denied, etc.)
      // Fall through to legacy approach
    }
  }

  // Fallback: execCommand with a temporary textarea
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    // Prevent scrolling to bottom
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "-9999px";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}
