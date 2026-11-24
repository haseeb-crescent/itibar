// Hover, focus or tap a term for its plain-English definition (assets/glossary.json, from config/glossary.yaml).
let request;

export function glossary(root) {
  request ??= fetch(`${root}assets/glossary.json`).then(response => {
    if (!response.ok) throw new Error(String(response.status));
    return response.json();
  });
  return request;
}

const root = document.body.dataset.root;
const tip = document.createElement("div");
tip.className = "term-tip";
tip.setAttribute("role", "tooltip");
tip.id = "term-tip";
tip.hidden = true;
document.body.append(tip);
let current = null;
let hideTimer = 0;

async function show(anchor, sticky = false) {
  clearTimeout(hideTimer);
  const data = await glossary(root).catch(() => null);
  const entry = data?.terms?.[decodeURIComponent(anchor.hash.slice(1))];
  if (!entry) return false;
  current = anchor;
  tip.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = entry.term;
  tip.append(title);
  if (entry.arabic) {
    const ar = document.createElement("bdi");
    ar.lang = "ar";
    ar.dir = "rtl";
    ar.textContent = ` ${entry.arabic}`;
    tip.append(ar);
  }
  const text = document.createElement("p");
  text.textContent = entry.short;
  tip.append(text);
  const more = document.createElement("a");
  more.href = anchor.href;
  more.textContent = "More in the glossary";
  tip.append(more);
  tip.hidden = false;
  tip.dataset.sticky = sticky ? "1" : "";
  anchor.setAttribute("aria-describedby", "term-tip");
  const box = anchor.getBoundingClientRect();
  const width = Math.min(320, window.innerWidth - 24);
  tip.style.width = `${width}px`;
  const left = Math.max(12, Math.min(box.left + window.scrollX, window.scrollX + window.innerWidth - width - 12));
  tip.style.left = `${left}px`;
  const below = box.bottom + window.scrollY + 8;
  tip.style.top = `${below}px`;
  return true;
}

function hide(now = false) {
  const close = () => {
    tip.hidden = true;
    current?.removeAttribute("aria-describedby");
    current = null;
  };
  if (now) close(); else hideTimer = setTimeout(close, 180);
}

document.addEventListener("mouseover", event => {
  const anchor = event.target.closest?.("a.term");
  if (anchor && anchor !== current && !tip.dataset.sticky) show(anchor);
  else if (!anchor && !event.target.closest?.(".term-tip") && current && !tip.dataset.sticky) hide();
});
document.addEventListener("focusin", event => {
  const anchor = event.target.closest?.("a.term");
  if (anchor) show(anchor);
  else if (!event.target.closest?.(".term-tip")) hide(true);
});
document.addEventListener("click", async event => {
  const anchor = event.target.closest?.("a.term");
  // A first tap on a touch screen shows the definition; a second tap follows the link.
  if (anchor && matchMedia("(hover: none)").matches && current !== anchor) {
    event.preventDefault();
    await show(anchor, true);
    return;
  }
  if (!event.target.closest?.(".term-tip") && !anchor) hide(true);
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !tip.hidden) hide(true);
});
