import { arabic, el, link, readJson } from "./dom.js";
import { mountGraph } from "./graph.js";
import { mountStory } from "./story.js";
import "./glossary.js";

const root = document.body.dataset.root;
const group = Number(document.querySelector(".report").dataset.group);
const LEVELS = ["", "Companion", "Highly trustworthy", "Trustworthy", "Truthful", "Truthful, errs", "Acceptable",
  "Unknown standing", "Weak", "Unknown", "Abandoned", "Accused of lying", "Liar"];

const story = document.querySelector("[data-story]");
if (story) {
  mountStory(story, root).catch(() => {
    story.querySelector("[data-story-canvas]").textContent = "The tree could not be drawn. The list below gives it in words.";
  });
}

// The specialists' tools: receipts and the full graph, built here because both need the script.
const RECEIPTS = [["all", "Independent lines and bottlenecks — everyone"], ["above_matruk", "Independent lines and bottlenecks — excluding abandoned narrators"],
  ["saduq_up", "Independent lines and bottlenecks — truthful and above"], ["thiqa_up", "Independent lines and bottlenecks — trustworthy only"],
  ["structure", "Number class, common links and dates"], ["grade-v1", "Best single chain (no corroboration)"],
  ["ibn_hajar", "Grade with corroboration — Ibn Ḥajar’s reading"], ["ibn_al_salah", "Grade with corroboration — Ibn al-Ṣalāḥ’s reading"]];
const tools = document.querySelector("[data-specialist-tools]");
if (tools) {
  const kappas = [...document.querySelectorAll("table.kappa td.n:nth-of-type(1)")].map(td => td.textContent.trim());
  const labels = ["Everyone", "Excluding abandoned", "Truthful and above", "Trustworthy only"];
  tools.innerHTML = `<h3>Receipts</h3><div class="receipts">${RECEIPTS.map(([key, label]) =>
    `<details class="receipt" data-receipt="${key}"><summary>${label}</summary><div class="receipt-content"></div></details>`).join("")}</div>
  <details class="full-graph" data-graph><summary>The full graph: every narrator <span class="quiet">(best on a larger screen)</span></summary>
  <div class="graph-viewport"><canvas tabindex="0" aria-label="Every narrator and link of this report" aria-describedby="graph-instructions"></canvas>
  <p class="graph-message" aria-live="polite">Loading the graph…</p>
  <div class="zoom-controls" aria-label="Graph zoom"><button type="button" data-zoom="in" aria-label="Zoom in">+</button><button type="button" data-zoom="out" aria-label="Zoom out">−</button><button type="button" data-zoom="fit">Fit</button></div></div>
  <div class="node-info" aria-live="polite" hidden></div>
  <div class="graph-options"><fieldset class="thresholds"><legend>Narrators counted</legend>${labels.map((label, i) =>
    `<label><input type="radio" name="threshold" value="${i}" data-kappa="${kappas[i] ?? ""}"${i ? "" : " checked"}><span>${label}</span></label>`).join("")}</fieldset>
  <label><input type="checkbox" data-off-route> Include narrators off every route</label>
  <button type="button" data-expand hidden>Show all narrators</button>
  <output class="kappa-display" aria-live="polite">κ <strong>${kappas[0] ?? ""}</strong></output><span class="graph-count quiet"></span></div>
  <p id="graph-instructions" class="quiet">Drag to pan; zoom with the buttons, a wheel or a pinch; select a node for details; arrow keys pan and [ ] step through nodes. Ringed: bottleneck. Square: common link.</p></details>`;
}

// The full graph (specialists): loaded when opened.
let graph;
const graphPanel = document.querySelector("[data-graph]");
graphPanel?.addEventListener("toggle", () => {
  if (!graphPanel.open || graph) return;
  graph = readJson("./graph.json.gz");
  mountGraph(graphPanel, graph).catch(() => {
    graphPanel.querySelector(".graph-message").textContent = "The graph could not load.";
  });
});

// Receipts: the stored steps, read from the report's record.
let record;
function readRecord() {
  record ??= readJson("./record.json.gz");
  return record;
}

function chainAnchor(id, gid = group) {
  const path = gid === group ? "" : `${root}reports/${gid}/`;
  return link(`${path}#chain-${id}`, `chain ${id}`);
}

function nodeName(id, names) {
  const name = names?.[id];
  if (name) return name.startsWith?.("<") ? el("span", id) : el("span", name);
  return el("code", id);
}

function stepsElement(steps) {
  const list = el("ol", "", "steps");
  for (const step of steps || []) {
    const item = el("li");
    item.append(el("strong", step.check), el("p", step.rule, "quiet"));
    const result = el("p");
    result.append(el("span", "Result: ", "quiet"));
    if (Array.isArray(step.result)) result.append(step.result.length ? step.result.join(", ") : "none");
    else if (step.result != null && typeof step.result !== "object") result.append(String(step.result));
    else if (step.result != null) result.append(el("code", JSON.stringify(step.result)));
    else result.append("unassigned");
    item.append(result);
    const { routes, sanad_id, ...rest } = step.data || {};
    if (sanad_id != null) item.append(el("p", "", "quiet"), chainAnchor(sanad_id));
    if (routes?.length) {
      const details = el("details");
      details.append(el("summary", `${routes.length} vertex-disjoint routes, each link citing a chain`));
      const paths = el("ol", "", "routes-receipt");
      for (const route of routes) {
        const path = el("li");
        route.nodes.forEach((id, i) => {
          if (i) path.append(" · ", chainAnchor(route.sanads[i - 1]), " · ");
          path.append(el("code", id));
        });
        paths.append(path);
      }
      details.append(paths);
      item.append(details);
    }
    for (const witness of rest.witnesses || rest.covered || []) {
      if (witness.witness_sanad != null) {
        const line = el("p");
        line.append("Witness ", chainAnchor(witness.witness_sanad, witness.group ?? group), ` (${witness.divergence})`);
        item.append(line);
      }
    }
    if (Object.keys(rest).length) {
      const evidence = el("details");
      evidence.append(el("summary", "Stored inputs"), el("pre", JSON.stringify(rest, null, 2)));
      item.append(evidence);
    }
    list.append(item);
  }
  return list;
}

function receiptSteps(data, key) {
  if (key === "grade-v1") return data.receipt;
  if (key === "ibn_hajar" || key === "ibn_al_salah") return data.receipt_v2?.[key];
  return data.receipt_structure?.[key];
}

for (const details of document.querySelectorAll("[data-receipt]")) {
  const content = details.querySelector(".receipt-content");
  details.addEventListener("toggle", async () => {
    if (!details.open || content.dataset.loaded) return;
    content.textContent = "Loading…";
    try {
      const data = await readRecord();
      content.replaceChildren(stepsElement(receiptSteps(data, details.dataset.receipt)));
      content.dataset.loaded = "true";
    } catch {
      record = undefined;
      content.textContent = "The receipt could not load.";
    }
  });
}

const download = document.querySelector("[data-download-record]");
download?.addEventListener("click", async event => {
  event.preventDefault();
  const data = await readRecord();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const anchor = el("a");
  anchor.href = URL.createObjectURL(blob);
  anchor.download = `itibar-report-${group}.json`;
  document.body.append(anchor);
  anchor.click();
  setTimeout(() => { URL.revokeObjectURL(anchor.href); anchor.remove(); }, 1000);
});

// All chains.
const chains = document.querySelector("[data-chains]");
if (chains) {
  const bookFilter = chains.querySelector("[data-book]");
  const companionFilter = chains.querySelector("[data-companion]");
  const pages = chains.querySelector(".chain-pagination");
  const status = chains.querySelector(".chain-status");
  const rows = chains.querySelector(".chain-rows");
  const size = 30;
  let request;
  let collection;
  let books = {};
  let page = 0;

  const companionOf = row => row[4][row[4].length - 2];

  function bookName(id) {
    const book = books[id];
    return book ? (book[0] || book[1]) : `Book ${id}`;
  }

  function chainRow(row) {
    const [id, book, no, grade, people] = row;
    const item = el("li", "", "chain-row");
    item.id = `chain-${id}`;
    const head = el("p", "", "chain-head");
    head.append(el("strong", bookName(book)), ` no. ${no ?? "—"} · `, chainAnchor(id));
    if (collection.grades[grade]) {
      head.append(el("span", " · recorded in the dataset: ", "quiet"), arabic(collection.grades[grade]));
    }
    const strip = el("ol", "", "chain-line");
    strip.append(el("li", "the Prophet", "link-prophet"));
    for (let i = people.length - 2; i >= 0; i -= 2) {
      const rid = people[i];
      const [en, ar, hasPage, level] = collection.people[rid];
      const word = collection.words[people[i + 1]];
      const part = el("li");
      const name = hasPage ? link(`${root}narrators/${rid}/`, en || ar) : el("span", en || ar);
      if (!en) { name.lang = "ar"; name.dir = "rtl"; }
      name.title = ar;
      part.append(name);
      if (level > 0) part.append(el("span", LEVELS[level], `badge small lv${level}`));
      if (word) {
        const [raw, gloss] = word.split("|");
        const w = el("span", "", "word");
        const arWord = el("bdi", raw);
        arWord.lang = "ar";
        w.append(arWord);
        if (gloss) w.append(` ${gloss}`);
        part.append(w);
      }
      strip.append(part);
    }
    item.append(head, strip);
    return item;
  }

  function selected() {
    return collection.rows.filter(row => (!bookFilter.value || String(row[1]) === bookFilter.value)
      && (!companionFilter.value || String(companionOf(row)) === companionFilter.value));
  }

  function render(target) {
    const list = selected();
    const hit = target == null ? -1 : list.findIndex(row => row[0] === target);
    if (hit >= 0) page = Math.floor(hit / size);
    const from = page * size;
    const to = Math.min(list.length, (page + 1) * size);
    rows.replaceChildren(...list.slice(from, to).map(chainRow));
    rows.start = from + 1;
    status.textContent = list.length ? `Showing ${from + 1}–${to} of ${list.length.toLocaleString()} chains` : "No chain matches these filters.";
    pages.hidden = list.length <= size;
    pages.querySelector("span").textContent = `Page ${page + 1} of ${Math.max(1, Math.ceil(list.length / size))}`;
    pages.querySelector("[data-prev]").disabled = page === 0;
    pages.querySelector("[data-next]").disabled = to >= list.length;
    if (hit >= 0) document.getElementById(`chain-${target}`)?.scrollIntoView({ block: "center" });
  }

  function fillFilters() {
    const count = (key) => {
      const counts = new Map();
      for (const row of collection.rows) counts.set(key(row), (counts.get(key(row)) || 0) + 1);
      return [...counts].sort((a, b) => b[1] - a[1]);
    };
    for (const [id, n] of count(row => row[1])) {
      const option = el("option", `${bookName(id)} (${n})`);
      option.value = id;
      bookFilter.append(option);
    }
    for (const [rid, n] of count(companionOf)) {
      const [en, ar] = collection.people[rid] || [];
      const option = el("option", `${en || ar} (${n})`);
      option.value = rid;
      companionFilter.append(option);
    }
  }

  async function openChains(target) {
    if (!collection) status.textContent = "Loading the chains…";
    request ??= Promise.all([readJson("./chains.json.gz"), fetch(`${root}assets/books.json`).then(r => r.json()).catch(() => ({}))]);
    try {
      [collection, books] = await request;
      if (!bookFilter.options[1]) fillFilters();
      if (target != null) { bookFilter.value = ""; companionFilter.value = ""; }
      render(target);
    } catch {
      request = undefined;
      status.textContent = "The chains could not load.";
    }
  }

  for (const filter of [bookFilter, companionFilter]) filter.addEventListener("change", () => { page = 0; openChains(); });
  const step = amount => { page += amount; render(); chains.scrollIntoView({ block: "start" }); };
  pages.querySelector("[data-prev]").addEventListener("click", () => step(-1));
  pages.querySelector("[data-next]").addEventListener("click", () => step(1));
  const follow = () => {
    const match = /^#chain-(\d+)$/.exec(location.hash);
    if (match) openChains(Number(match[1]));
    const book = /^#book-\d+$/.test(location.hash) && document.querySelector(location.hash);
    if (book) book.closest("details").open = true;
  };
  window.addEventListener("hashchange", follow);
  follow();
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      observer.disconnect();
      if (!collection) openChains();
    }
  }, { rootMargin: "300px" });
  observer.observe(chains);
}
