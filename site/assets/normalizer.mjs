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
