export function el(tag, text = "", className = "") {
  const element = document.createElement(tag);
  if (text !== "") element.textContent = text;
  if (className) element.className = className;
  return element;
}

export function arabic(text) {
  const element = el("bdi", text);
  element.lang = "ar";
  element.dir = "rtl";
  return element;
}

export function link(href, text) {
  const anchor = el("a", text);
  anchor.href = href;
  return anchor;
}

export async function readJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status}: ${url}`);
  if (url.endsWith(".gz")) {
    const stream = response.body.pipeThrough(new DecompressionStream("gzip"));
    return new Response(stream).json();
  }
  return response.json();
}
