import { arabic, el, link, readJson } from "./dom.js";
import { bookKey, normalizeArabic, normalizeDigits, shard } from "./normalizer.mjs";

const root = document.body.dataset.root;
const input = document.querySelector("#query");
const list = document.querySelector(".search-list");
const status = document.querySelector("#search-status");
const examples = document.querySelector(".search-examples");
const pagination = document.querySelector("#search-results .pagination");
const cache = new Map();
const perPage = 16;
let active = 0;
let timer;
let matches = [];
let page = 0;
let meta;

function asset(path) {
  if (!cache.has(path)) {
    if (cache.size >= 64) cache.delete(cache.keys().next().value);
    cache.set(path, readJson(`./index/${path}.json`).catch(error => {
      cache.delete(path);
      throw error;
    }));
  }
  return cache.get(path);
}

function citationQuery(text) {
  const match = /^(.*?)\s*#?([0-9]+)$/.exec(normalizeDigits(text).trim());
  if (!match) return null;
  return [bookKey(match[1]), String(Number(match[2]))];
}

async function citationMatches(query) {
  const [name, number] = query;
  const index = shard(number, meta.refs);
  const [reference, books] = await Promise.all([
    meta.reference_buckets.includes(index) ? asset(`refs/${index}`) : {}, asset("books"),
  ]);
  const refs = reference[number] || [];
  const hits = new Map();
  if ((!name || name === "report" || name === "group") && meta.document_buckets.includes(Math.floor(number / meta.docs))) {
    const bucket = await asset(`docs/${Math.floor(number / meta.docs)}`);
    if (bucket[number]) hits.set(Number(number), { id: Number(number), score: 4 });
  }
  for (const [book, id] of refs) {
    const [bookName, aliases] = books[book];
    const score = aliases.includes(name) ? 3 : aliases.some(alias => alias.includes(name)) ? 2 : 0;
    if (score > (hits.get(id)?.score || 0)) hits.set(id, { id, score, book, bookName, number });
  }
  const exactBook = [...hits.values()].some(hit => hit.score === 3);
  return [...hits.values()].filter(hit => !exactBook || hit.score >= 3).sort((a, b) => b.score - a.score || a.id - b.id);
}

async function arabicMatches(words) {
  const postings = await Promise.all(words.map(async word => {
    const index = shard(word, meta.tokens);
    const popular = meta.popular.indexOf(word);
    const encoded = popular !== -1 ? await asset(`terms/${popular}`) :
      meta.token_buckets.includes(index) ? (await asset(`tokens/${index}`))[word] : "";
    return decodePostings(encoded);
  }));
  postings.sort((a, b) => a.length - b.length);
  if (!postings[0]?.length) return [];
  let scores = new Map(postings[0].map(value => [Math.floor(value / 2), value & 1]));
  for (const posting of postings.slice(1)) {
    const next = new Map();
    for (const value of posting) {
      const id = Math.floor(value / 2);
      if (scores.has(id)) next.set(id, scores.get(id) + (value & 1));
    }
    scores = next;
    if (!scores.size) break;
  }
  return [...scores].map(([id, score]) => ({ id, score }))
    .sort((a, b) => b.score - a.score || Math.abs(a.id) - Math.abs(b.id) || b.id - a.id);
}

function decodePostings(encoded) {
  if (!encoded) return [];
  const bytes = atob(encoded);
  const values = [];
  let value = 0;
  let shift = 0;
  let previous = 0;
  for (let i = 0; i < bytes.length; i++) {
    const byte = bytes.charCodeAt(i);
    value |= (byte & 127) << shift;
    if (byte & 128) {
      shift += 7;
    } else {
      previous = values.length ? previous + value : (value & 1 ? -(value + 1) / 2 : value / 2);
      values.push(previous);
      value = 0;
      shift = 0;
    }
  }
  return values;
}

function hitCard(hit, entry) {
  const item = el("li");
  const kind = hit.id < 0 ? "narrators" : "reports";
  const path = `${root}${kind}/${Math.abs(hit.id)}/${hit.book ? `#book-${hit.book}` : ""}`;
  const anchor = link(path);
  anchor.className = "panel";
  const title = el("span", "", "hit-title");
  title.append(entry[0] ? arabic(entry[0]) : `Report ${hit.id}`);
  const detail = el("span", hit.id < 0 ? `Narrator ${-hit.id}` : `Report ${hit.id}`, "hit-type");
  if (hit.book) detail.append(" · ", arabic(hit.bookName), ` · no. ${hit.number}`);
  if (entry[1]) detail.append(" · ", arabic(entry[1]));
  anchor.append(title, detail);
  item.append(anchor);
  return item;
}

async function render(token) {
  const selection = matches.slice(page * perPage, (page + 1) * perPage);
  const ids = [...new Set(selection.map(hit => Math.floor(hit.id / meta.docs)))];
  const shards = await Promise.all(ids.map(async id => [id, await asset(`docs/${id}`)]));
  if (active !== token) return;
  const documents = new Map(shards);
  list.replaceChildren(...selection.map(hit => hitCard(hit, documents.get(Math.floor(hit.id / meta.docs))[hit.id])));
  const pages = Math.ceil(matches.length / perPage);
  pagination.hidden = pages <= 1;
  pagination.querySelector("span").textContent = `Page ${page + 1} of ${pages}`;
  pagination.querySelector("[data-prev]").disabled = page === 0;
  pagination.querySelector("[data-next]").disabled = page + 1 >= pages;
  status.textContent = matches.length
    ? `${matches.length.toLocaleString()} ${matches.length === 1 ? "result" : "results"}`
    : "No matches. Try a different name, a phrase, or a book and number.";
}

async function search(token) {
  const text = input.value.trim();
  examples.hidden = Boolean(text);
  list.replaceChildren();
  pagination.hidden = true;
  if (!text) {
    status.textContent = "Try a few words, a name, or a citation.";
    return;
  }
  status.textContent = "Searching…";
  try {
    meta ??= await asset("meta");
    const reference = citationQuery(text);
    const normalized = normalizeArabic(text);
    const found = reference ? await citationMatches(reference) :
      normalized ? await arabicMatches([...new Set(normalized.split(" "))]) : [];
    if (active !== token) return;
    matches = found;
    page = 0;
    await render(token);
  } catch {
    if (active === token) status.textContent = "The search index could not load. Try again.";
  }
}

function run(immediately = false) {
  clearTimeout(timer);
  const token = ++active;
  if (immediately) search(token);
  else timer = setTimeout(() => search(token), 100);
}

input.value = new URLSearchParams(location.search).get("q") || "";
asset("meta").catch(() => {});
input.addEventListener("input", () => run());
input.form.addEventListener("submit", event => {
  event.preventDefault();
  const url = new URL(location.href);
  url.searchParams.set("q", input.value);
  history.replaceState(null, "", url);
  run(true);
});
for (const [direction, offset] of [["prev", -1], ["next", 1]]) {
  pagination.querySelector(`[data-${direction}]`).addEventListener("click", () => {
    page += offset;
    render(++active).catch(() => { status.textContent = "The search results could not load."; });
    document.querySelector("#search-results").scrollIntoView({ block: "start" });
  });
}
run(true);
