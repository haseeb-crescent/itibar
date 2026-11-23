import { arabic, el, link, readJson } from "./dom.js";

for (const details of document.querySelectorAll(".more-reports")) {
  const { role, pages } = details.dataset;
  const root = document.body.dataset.root;
  const status = details.querySelector(".more-status");
  const list = details.querySelector("ul");
  const pagination = details.querySelector(".pagination");
  const prev = pagination.querySelector("[data-prev]");
  const next = pagination.querySelector("[data-next]");
  const cache = new Map();
  let current = 0;
  let pending = false;

  async function load(page) {
    if (pending) return;
    pending = true;
    prev.disabled = next.disabled = true;
    status.textContent = "Loading report links…";
    try {
      if (!cache.has(page)) cache.set(page, await readJson(`./reports/${role}-${page}.json.gz`));
      const items = cache.get(page).map(([gid, opening]) => {
        const item = el("li");
        const anchor = link(`${root}reports/${gid}/`);
        anchor.append(opening ? arabic(opening) : el("span", "Report"), el("span", `#${gid}`, "quiet"));
        item.append(anchor);
        return item;
      });
      list.replaceChildren(...items);
      current = page;
      status.textContent = `More reports · Page ${current} of ${pages}`;
      pagination.hidden = Number(pages) === 1;
    } catch {
      status.textContent = "The report links could not load. Reopen the list to try again.";
    } finally {
      pending = false;
      prev.disabled = current <= 1;
      next.disabled = current === Number(pages);
    }
  }

  details.addEventListener("toggle", () => { if (details.open && !current) load(1); });
  prev.addEventListener("click", () => load(current - 1));
  next.addEventListener("click", () => load(current + 1));
}
