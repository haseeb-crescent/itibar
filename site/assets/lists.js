// "Show more" for browse lists: pages of [group, English title, Arabic opening, lines, grade].
import { el, link, readJson } from "./dom.js";

const root = document.body.dataset.root;
const list = document.querySelector("[data-list]");
const button = document.querySelector("[data-more]");
const status = button?.nextElementSibling;
const pages = Number(list?.dataset.pages || 0);
let next = 1;

button?.addEventListener("click", async () => {
  button.disabled = true;
  status.textContent = "Loading…";
  try {
    const rows = await readJson(`./list/${next}.json.gz`);
    for (const [gid, title, opening, lines, grade] of rows) {
      const item = el("li", "", "result");
      const heading = el("h3");
      const anchor = link(`${root}reports/${gid}/`, title || opening);
      if (!title) { anchor.lang = "ar"; anchor.dir = "rtl"; }
      heading.append(anchor);
      item.append(heading);
      if (title && opening) {
        const ar = el("p", opening, "ar");
        ar.lang = "ar";
        ar.dir = "rtl";
        item.append(ar);
      }
      const meta = el("p", "", "meta");
      meta.append(el("span", `${lines ?? 0} independent ${lines === 1 ? "line" : "lines"}`));
      if (grade) meta.append(el("span", `best chain ${grade} by the classical rules`));
      item.append(meta);
      list.append(item);
    }
    next += 1;
    status.textContent = "";
  } catch {
    status.textContent = "The list could not load.";
  } finally {
    button.disabled = false;
    button.hidden = next > pages;
  }
});
