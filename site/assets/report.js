import { arabic, el, link, readJson } from "./dom.js";
import { mountGraph } from "./graph.js";

const root = document.body.dataset.root;
const group = Number(document.querySelector(".report").dataset.group);
const graph = readJson("./graph.json.gz");
const panel = document.querySelector("[data-graph]");
mountGraph(panel, graph).catch(() => {
  panel.querySelector(".graph-message").textContent = "The bundle drawing could not load.";
});

function appendNode(parent, nodes, id) {
  const node = nodes.get(id);
  if (!node) {
    parent.append(el("code", id));
    return;
  }
  const name = arabic(node[1] || id);
  if (node[6] & 8) {
    const anchor = link(`${root}narrators/${id.slice(1)}/`);
    anchor.append(name);
    parent.append(anchor);
  } else parent.append(name);
}

function chainAnchor(id, gid = group) {
  const path = gid === group ? "" : `${root}reports/${gid}/`;
  return link(`${path}#chain-${id}`, `Chain ${id}`);
}

function stepsElement(steps, nodes) {
  const elements = el("ol", "", "steps");
  for (const step of steps) {
    const item = el("li");
    item.append(el("strong", step.check), el("p", step.rule));
    const result = el("p");
    result.append(el("span", "Result ", "quiet"));
    if (Array.isArray(step.result)) {
      for (const [i, id] of step.result.entries()) {
        if (i) result.append(", ");
        appendNode(result, nodes, id);
      }
      if (!step.result.length) result.append("None");
    } else if (step.result != null && typeof step.result !== "object") {
      result.append(String(step.result));
    } else if (step.result != null) {
      result.append(el("code", JSON.stringify(step.result)));
    } else result.append("Unassigned");
    item.append(result);
    const { routes, cut, sanad_id, ...rest } = step.data;
    if (sanad_id != null) item.append(chainAnchor(sanad_id));
    if (cut) {
      const minimumCut = el("p", "One minimum cut ");
      for (const [i, id] of cut.entries()) {
        if (i) minimumCut.append(", ");
        appendNode(minimumCut, nodes, id);
      }
      if (!cut.length) minimumCut.append("∅");
      item.append(minimumCut);
    }
    if (routes?.length) {
      const details = el("details");
      details.append(el("summary", "Vertex-disjoint paths and supporting chains"));
      details.append(el("p", "Each link cites one source chain that contains it. A path can join links from several chains."));
      const paths = el("ol", "", "routes-receipt");
      for (const route of routes) {
        const path = el("li");
        for (const [i, id] of route.nodes.entries()) {
          if (i) path.append(" · ", chainAnchor(route.sanads[i - 1]), " · ");
          appendNode(path, nodes, id);
        }
        paths.append(path);
      }
      details.append(paths);
      item.append(details);
    }
    for (const witness of rest.witnesses || rest.covered || []) {
      if (witness.witness_sanad != null) {
        const line = el("p");
        line.append(chainAnchor(witness.witness_sanad, witness.group ?? group), ` · ${witness.divergence}`);
        item.append(line);
      }
    }
    if (Object.keys(rest).length) {
      const evidence = el("details");
      evidence.append(el("summary", "Stored inputs"), el("pre", JSON.stringify(rest, null, 2)));
      item.append(evidence);
    }
    elements.append(item);
  }
  return elements;
}

let receipts;
for (const details of document.querySelectorAll("[data-receipt]")) {
  const content = details.querySelector(".receipt-content");
  details.addEventListener("toggle", async () => {
    if (!details.open || content.dataset.loaded) return;
    receipts ??= readJson("./receipts.json.gz");
    content.textContent = "Loading receipt…";
    try {
      const [data, layout] = await Promise.all([receipts, graph]);
      const nodes = new Map(layout.nodes.map(node => [node[0], node]));
      let steps = data[details.dataset.receipt];
      if (details.dataset.step !== undefined) steps = [steps[Number(details.dataset.step)]];
      content.replaceChildren(stepsElement(steps, nodes));
      content.dataset.loaded = "true";
    } catch {
      receipts = undefined;
      content.textContent = "The receipt could not load.";
    }
  });
}

const chains = document.querySelector("[data-chains]");
const filter = chains.querySelector("select");
const pages = chains.querySelector(".chain-pagination");
const status = chains.querySelector(".chain-status");
const rows = chains.querySelector(".chain-rows");
const size = 35;
let chainRequest;
let collection;
let page = 0;

function labelBook(book) {
  return filter.querySelector(`option[value="${book}"]`)?.textContent || `Book ${book}`;
}

function chainRow([id, book, no, grade, people]) {
  const row = el("article", "", "chain-row");
  row.id = `chain-${id}`;
  const header = el("header");
  header.append(arabic(labelBook(book)), el("span", `no. ${no ?? "unrecorded"}`),
    chainAnchor(id), el("span", "Source chain grade"));
  if (collection.grades[grade]) header.append(arabic(collection.grades[grade]));
  else header.append("Unrecorded");
  const content = el("p", "", "chain-links");
  content.lang = "ar";
  content.dir = "rtl";
  for (let i = 0; i < people.length; i += 2) {
    const rid = people[i];
    const [name, hasPage] = collection.people[rid];
    const word = collection.words[people[i + 1]];
    const part = el("span", "", "chain-part");
    const connector = el("span", word || "—", "chain-word");
    connector.lang = "ar";
    if (!word) connector.setAttribute("aria-label", "Transmission word unrecorded");
    part.append(connector, hasPage ? link(`${root}narrators/${rid}/`, name) : el("span", name));
    content.append(part);
  }
  row.append(header, content);
  return row;
}

function renderChains(target) {
  const chosen = filter.value;
  const selected = chosen ? collection.rows.filter(row => String(row[1]) === chosen) : collection.rows;
  const hit = target == null ? -1 : selected.findIndex(row => row[0] === target);
  if (hit >= 0) page = Math.floor(hit / size);
  const from = page * size;
  const to = Math.min(selected.length, (page + 1) * size);
  rows.replaceChildren(...selected.slice(from, to).map(chainRow));
  status.textContent = selected.length ? `Showing ${from + 1}–${to} of ${selected.length.toLocaleString()} chains` : "No recorded chains in this book.";
  pages.hidden = selected.length <= size;
  pages.querySelector("span").textContent = `Page ${page + 1} of ${Math.ceil(selected.length / size)}`;
  pages.querySelector("[data-prev]").disabled = page === 0;
  pages.querySelector("[data-next]").disabled = to === selected.length;
  if (hit >= 0) document.getElementById(`chain-${target}`).scrollIntoView({ block: "center" });
}

async function openChains(target) {
  if (!collection) status.textContent = "Loading the chains…";
  chainRequest ??= readJson("./chains.json.gz");
  try {
    collection = await chainRequest;
    if (target != null) {
      const hit = collection.rows.find(row => row[0] === target);
      if (hit && filter.value && String(hit[1]) !== filter.value) filter.value = "";
    }
    renderChains(target);
  } catch {
    chainRequest = undefined;
    status.textContent = "The chains could not load.";
  }
}

filter.addEventListener("change", () => { page = 0; openChains(); });
function stepPage(amount) {
  page += amount;
  renderChains();
  chains.scrollIntoView({ block: "start" });
}
pages.querySelector("[data-prev]").addEventListener("click", () => stepPage(-1));
pages.querySelector("[data-next]").addEventListener("click", () => stepPage(1));

function followHash() {
  const match = /^#chain-(\d+)$/.exec(location.hash);
  if (match) openChains(Number(match[1]));
  const book = /^#book-\d+$/.test(location.hash) && document.querySelector(location.hash);
  if (book) book.open = true;
}
window.addEventListener("hashchange", followHash);
followHash();
const observer = new IntersectionObserver(entries => {
  if (entries.some(entry => entry.isIntersecting)) {
    observer.disconnect();
    if (!collection) openChains();
  }
}, { rootMargin: "220px" });
observer.observe(chains);
