// One search box for English and Arabic over the static index written by src/itibar/site/search.py.
// Document ids follow how widely each report (or narrator) is carried, so ties go to the famous one.
import { el, link, readJson } from "./dom.js";
import { bookKey, englishTokens, normalizeArabic, normalizeDigits, shard } from "./normalizer.mjs";

const root = document.body.dataset.root;
const input = document.querySelector("#query");
const list = document.querySelector(".search-list");
const status = document.querySelector("#search-status");
const filters = document.querySelector(".search-filters");
const pagination = document.querySelector("#search-results .pagination");
const select = name => filters.querySelector(`[data-filter="${name}"]`);
const cache = new Map();
const perPage = 15;
const window_ = 600;   // filters apply to this many best matches
let active = 0;
let timer;
let found = { reports: [], narrators: [] };
let page = 0;
let meta;

function asset(path) {
  if (!cache.has(path)) {
    if (cache.size >= 96) cache.delete(cache.keys().next().value);
    cache.set(path, readJson(`${root}search/index/${path}.json`).catch(error => {
      cache.delete(path);
      throw error;
    }));
  }
  return cache.get(path);
}

function decodePostings(encoded) {
  if (!encoded) return [];
  const bytes = atob(encoded);
  const values = [];
  let value = 0, shift = 0, previous = 0;
  for (let i = 0; i < bytes.length; i++) {
    const byte = bytes.charCodeAt(i);
    value |= (byte & 127) << shift;
    if (byte & 128) { shift += 7; continue; }
    previous = values.length ? previous + value : (value & 1 ? -(value + 1) / 2 : value / 2);
    values.push(previous);
    value = 0;
    shift = 0;
  }
  return values;
}

async function postings(word) {
  const popular = meta.popular.indexOf(word);
  if (popular !== -1) return decodePostings(await asset(`terms/${popular}`));
  const index = shard(word, meta.tokens);
  if (!meta.token_buckets.includes(index)) return [];
  return decodePostings((await asset(`tokens/${index}`))[word]);
}

// Arabic: every word must match; more words in an opening rank higher; then the wider-carried report.
async function arabicMatches(words) {
  const lists = await Promise.all(words.map(postings));
  lists.sort((a, b) => a.length - b.length);
  if (!lists[0]?.length) return [];
  let scores = new Map(lists[0].map(v => [Math.floor(v / 2), v & 1]));
  for (const posting of lists.slice(1)) {
    const next = new Map();
    for (const v of posting) {
      const id = Math.floor(v / 2);
      if (scores.has(id)) next.set(id, scores.get(id) + (v & 1));
    }
    scores = next;
  }
  return [...scores].map(([id, head]) => ({ id, cover: words.length, head }));
}

// English: rank by how many of the query's words a document contains (most of them required).
async function englishMatches(words) {
  const lists = await Promise.all(words.map(postings));
  const scores = new Map();
  lists.forEach(posting => {
    for (const v of posting) {
      const id = Math.floor(v / 2);
      const entry = scores.get(id) || { id, cover: 0, head: 0 };
      entry.cover += 1;
      entry.head += v & 1;
      scores.set(id, entry);
    }
  });
  const need = words.length <= 2 ? words.length : Math.ceil(words.length * 0.6);
  return [...scores.values()].filter(hit => hit.cover >= need);
}

function order(hits, byHead) {
  return hits.sort((a, b) => b.cover - a.cover || (byHead ? b.head - a.head : 0) || Math.abs(a.id) - Math.abs(b.id));
}

async function citationMatches(name, number) {
  const index = shard(number, meta.refs);
  const [reference, books] = await Promise.all([
    meta.reference_buckets.includes(index) ? asset(`refs/${index}`) : {}, asset("books"),
  ]);
  const hits = new Map();
  for (const [book, id] of reference[number] || []) {
    const [, aliases] = books[book];
    const score = aliases.includes(name) ? 3 : aliases.some(alias => alias.includes(name)) ? 2 : 0;
    if (score && score > (hits.get(id)?.score || 0)) hits.set(id, { id, cover: score, head: 0, book, number });
  }
  return [...hits.values()];
}

async function bookMatches(text) {
  const key = bookKey(text);
  if (!key) return [];
  const books = await asset("books");
  return Object.entries(books).filter(([, [, aliases]]) => aliases.includes(key)).map(([id, [ar, , title]]) => ({ id, ar, title }));
}

async function shardsFor(ids) {
  const keys = [...new Set(ids.map(id => Math.floor(id / meta.docs)))];
  const loaded = await Promise.all(keys.map(async key => [key, meta.document_buckets.includes(key) ? await asset(`docs/${key}`) : {}]));
  const map = new Map(loaded);
  return id => map.get(Math.floor(id / meta.docs))?.[id];
}

function gradeTerm(key) {
  return meta.grades[key] || null;
}

function reportCard(hit, doc) {
  const [gid, title, opening, chips, lines, trustworthy, grade, cls, , nBooks] = doc;
  const item = el("li", "", "result");
  const heading = el("h3");
  const anchor = link(`${root}reports/${gid}/${hit.book ? `#book-${hit.book}` : ""}`, title || opening || `Report ${gid}`);
  if (!title) { anchor.lang = "ar"; anchor.dir = "rtl"; }
  heading.append(anchor);
  item.append(heading);
  if (title && opening) {
    const ar = el("p", opening, "ar");
    ar.lang = "ar";
    ar.dir = "rtl";
    item.append(ar);
  }
  const info = el("p", "", "meta");
  if (hit.book) info.append(el("span", `${meta.books[hit.book] || "Book " + hit.book} no. ${hit.number}`));
  if (chips.length) info.append(el("span", chips.map(b => meta.books[b]).join(" · ") + (nBooks > chips.length ? ` +${nBooks - chips.length} more` : "")));
  const linesText = el("span");
  linesText.append(el("b", String(lines ?? 0)), ` independent ${lines === 1 ? "line" : "lines"}`);
  if (lines) linesText.append(` (${trustworthy} trustworthy only)`);
  info.append(linesText);
  const term = gradeTerm(grade);
  if (term) {
    const g = el("span");
    g.append("best chain ", el("b", term[0]), ` (${term[2]}) by the classical rules`);
    info.append(g);
  }
  if (cls && meta.classes[cls]) info.append(el("span", meta.classes[cls][0]));
  item.append(info);
  return item;
}

function narratorCard(doc) {
  const [rid, en, ar, died, cl, routes] = doc;
  const item = el("li", "", "result");
  const heading = el("h3");
  const anchor = link(`${root}narrators/${rid}/`, en || ar);
  if (!en) { anchor.lang = "ar"; anchor.dir = "rtl"; }
  heading.append(anchor);
  item.append(heading);
  if (en) {
    const arabic = el("p", ar, "ar");
    arabic.lang = "ar";
    arabic.dir = "rtl";
    item.append(arabic);
  }
  const info = el("p", "", "meta");
  if (died) info.append(el("span", `d. ${died} AH`));
  info.append(el("span", `on a line in ${routes.toLocaleString()} ${routes === 1 ? "report" : "reports"}`));
  if (cl) info.append(el("span", `common link in ${cl.toLocaleString()} ${cl === 1 ? "report" : "reports"}`));
  item.append(info);
  return item;
}

async function filtered() {
  const kind = select("kind").value;
  const hits = found[kind];
  if (kind === "narrators") return hits;
  const want = { topic: select("topic").value, book: select("book").value, grade: select("grade").value, cls: select("class").value };
  if (!want.topic && !want.book && !want.grade && !want.cls) return hits;
  const top = hits.slice(0, window_);
  const docs = await shardsFor(top.map(hit => hit.id));
  return top.filter(hit => {
    const doc = docs(hit.id);
    if (!doc) return false;
    const [, , , chips, , , grade, cls, topics] = doc;
    if (want.topic && !topics.includes(Number(want.topic))) return false;
    if (want.book && !chips.includes(Number(want.book))) return false;
    if (want.grade && gradeTerm(grade)?.[3] !== want.grade) return false;
    if (want.cls && !(cls || "").startsWith(want.cls)) return false;
    return true;
  });
}

async function render(token, books = []) {
  const hits = await filtered();
  const selection = hits.slice(page * perPage, (page + 1) * perPage);
  const docs = await shardsFor(selection.map(hit => hit.id));
  if (active !== token) return;
  const kind = select("kind").value;
  const items = [];
  if (page === 0 && kind === "reports") {
    for (const book of books) {
      const item = el("li", "", "result");
      const heading = el("h3");
      heading.append(link(`${root}browse/collections/${book.id}/`, `${book.title || book.ar} — the collection`));
      item.append(heading, el("p", "Every report in this book, in its order.", "meta"));
      items.push(item);
    }
  }
  for (const hit of selection) {
    const doc = docs(hit.id);
    if (doc) items.push(kind === "narrators" ? narratorCard(doc) : reportCard(hit, doc));
  }
  list.replaceChildren(...items);
  const pages = Math.ceil(hits.length / perPage);
  pagination.hidden = pages <= 1;
  pagination.querySelector("span").textContent = `Page ${page + 1} of ${pages}`;
  pagination.querySelector("[data-prev]").disabled = page === 0;
  pagination.querySelector("[data-next]").disabled = page + 1 >= pages;
  const other = kind === "reports" ? found.narrators.length : found.reports.length;
  status.textContent = hits.length
    ? `${hits.length.toLocaleString()} ${kind === "reports" ? (hits.length === 1 ? "report" : "reports") : (hits.length === 1 ? "narrator" : "narrators")}` +
      (other ? ` · ${other.toLocaleString()} ${kind === "reports" ? "narrators" : "reports"} also match (change “Show”)` : "")
    : "No matches. Try fewer words, another spelling, or the Arabic.";
}

let bookHits = [];
async function search(token) {
  const text = input.value.trim();
  list.replaceChildren();
  pagination.hidden = true;
  if (!text) return;
  status.textContent = "Searching…";
  try {
    meta ??= await asset("meta");
    fillFilters();
    filters.hidden = false;
    const citation = /^(.*?)\s*#?([0-9]+)$/.exec(normalizeDigits(text).trim());
    let hits = [];
    let byHead = false;
    if (citation && citation[1].trim()) hits = await citationMatches(bookKey(citation[1]), String(Number(citation[2])));
    else {
      const arabic = normalizeArabic(text);
      const words = arabic ? [...new Set(arabic.split(" "))] : [...new Set(englishTokens(text))];
      hits = words.length ? (arabic ? await arabicMatches(words) : await englishMatches(words)) : [];
      byHead = Boolean(arabic);
    }
    bookHits = citation ? [] : await bookMatches(text);
    if (active !== token) return;
    order(hits, byHead);
    found = { reports: hits.filter(hit => hit.id >= 0), narrators: hits.filter(hit => hit.id < 0) };
    if (!found.reports.length && found.narrators.length) select("kind").value = "narrators";
    else if (found.reports.length) select("kind").value = select("kind").value === "narrators" && found.narrators.length ? "narrators" : "reports";
    page = 0;
    await render(token, bookHits);
  } catch {
    if (active === token) status.textContent = "The search index could not load. Try again.";
  }
}

let filled = false;
function fillFilters() {
  if (filled) return;
  filled = true;
  for (const [id, en, ar] of meta.topics) select("topic").append(Object.assign(el("option", en || ar), { value: id }));
  for (const [id, name] of Object.entries(meta.books)) if (name) select("book").append(Object.assign(el("option", name), { value: id }));
  for (const [key, label] of [["gharib", "gharīb (one line)"], ["aziz", "ʿazīz (two lines)"], ["mashhur", "mashhūr (3–9)"], ["mutawatir", "mutawātir by count (10+)"]]) {
    select("class").append(Object.assign(el("option", label), { value: key }));
  }
}

function run(immediately = false) {
  clearTimeout(timer);
  const token = ++active;
  if (immediately) search(token);
  else timer = setTimeout(() => search(token), 150);
}

input.value = new URLSearchParams(location.search).get("q") || "";
input.addEventListener("input", () => run());
input.form.addEventListener("submit", event => {
  event.preventDefault();
  const url = new URL(location.href);
  url.searchParams.set("q", input.value);
  history.replaceState(null, "", url);
  run(true);
});
filters.addEventListener("change", () => { page = 0; render(++active, bookHits); });
for (const [direction, offset] of [["prev", -1], ["next", 1]]) {
  pagination.querySelector(`[data-${direction}]`).addEventListener("click", () => {
    page += offset;
    render(++active, bookHits);
    document.querySelector("#search-results").scrollIntoView({ block: "start" });
  });
}
if (input.value) run(true);
