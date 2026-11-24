// Matches itibar.lists.normalize v1. Parity is tested against Python.
const DIACRITICS = /[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]/g;
const SPACE = /[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/;
const NON_ARABIC = /[^ء-ي\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/g;
const LETTERS = { أ: "ا", إ: "ا", آ: "ا", ٱ: "ا", ى: "ي", ة: "ه", ؤ: "و", ئ: "ي" };
const DIGITS = "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹";

export function normalizeArabic(text) {
  return (text || "").replace(DIACRITICS, "").replaceAll("ـ", "").replaceAll("ﷺ", " ")
    .replace(/[أإآٱىةؤئ]/g, c => LETTERS[c]).replace(NON_ARABIC, " ")
    .split(SPACE).filter(Boolean).join(" ");
}

export function normalizeDigits(text) {
  return text.replace(/[٠-٩۰-۹]/g, digit => String(DIGITS.indexOf(digit) % 10));
}

export function bookKey(text) {
  return normalizeArabic(text) || text.toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "")
    .replace(/['’ʾʿ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
}

export function shard(key, count) {
  let number = 0;
  for (const letter of String(key)) number = (number * 31 + letter.codePointAt(0)) % count;
  return number;
}

// Matches itibar.site.search.english_tokens v1. Parity is tested against Python.
const STOP = new Set(`a an the and or but of to in on at by for with from into onto is are was were be been being it its
that this these those as me my mine i you your yours he his him she her hers they them their we us our not no will
shall would should do does did has have had about upon all so then there which who whom what when where while than
also very just o oh`.split(/\s+/));

export function stem(word) {
  if (word.length > 4 && word.endsWith("ies")) word = word.slice(0, -3) + "y";
  else if (word.length > 3 && word.endsWith("s") && !word.endsWith("ss")) word = word.slice(0, -1);
  if (word.length > 5 && word.endsWith("ing")) word = word.slice(0, -3);
  else if (word.length > 4 && word.endsWith("ed")) word = word.slice(0, -2);
  return word;
}

export function englishTokens(text) {
  return (text || "").toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "").replace(/[ʿʾ'’‘`]/g, "")
    .split(/[^a-z0-9]+/).filter(word => word && !STOP.has(word)).map(stem);
}
