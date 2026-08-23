import DOMPurify from "dompurify";

let hooksInstalled = false;

function ensureHooks(): void {
  if (hooksInstalled) {
    return;
  }
  hooksInstalled = true;
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node instanceof HTMLAnchorElement) {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  });
}

export function sanitizeFeedHtml(html: string): string {
  ensureHooks();
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ["script", "iframe", "object", "embed", "form", "input", "button"],
  });
}

export function feedHtmlPlainText(html: string): string {
  const clean = sanitizeFeedHtml(html);
  const doc = new DOMParser().parseFromString(clean, "text/html");
  return (doc.body.textContent ?? "").replace(/\s+/g, " ").trim();
}
