#!/usr/bin/env python3
"""Apply the zh-CN dictionary to ProxUI sources.

Replacement is deliberately narrow so nothing structural can break:
  * HTML text nodes      >text<          - only exact (whitespace-normalised) matches
  * static HTML attrs    title="..."     - never Alpine bindings (:attr / x-attr / @attr)
  * JS string literals   'x'  "x"  `x`   - only whole-literal matches

Nodes containing Jinja ({{ }} / {% %}) are never rewritten here; they are covered
by i18n/dict/special.json, which replaces longer snippets that keep the
placeholders intact.

Usage:
  python3 i18n/apply.py            # apply
  python3 i18n/apply.py --check    # dry run, report only
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")
JS_DIR = os.path.join(ROOT, "static", "js")
DICT_DIR = os.path.join(ROOT, "i18n", "dict")
JS_SKIP = {"alpine.min.js"}
ATTRS = ("placeholder", "title", "aria-label", "alt")

SCRIPT_RE = re.compile(r"(<(script|style)\b[^>]*>.*?</\2>)", re.S | re.I)
TEXT_RE = re.compile(r">([^<>]+)<")
ATTR_RE = re.compile(
    r'(?<![:@\w-])(' + "|".join(ATTRS) + r')\s*=\s*"([^"]*)"', re.I
)
LITERAL_RE = re.compile(
    r"""(?<![A-Za-z0-9_$.])(?:'([^'\\\n]{2,200})'|"([^"\\\n]{2,200})"|`([^`\\\n$]{2,200})`)"""
)


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def load_dict():
    d = {}
    dup = []
    if not os.path.isdir(DICT_DIR):
        return d, dup
    for name in sorted(os.listdir(DICT_DIR)):
        if not name.endswith(".json"):
            continue
        # special*.json are handled by their own passes and must never enter the
        # main dictionary: special.skeleton.json carries empty values and would
        # blank out any text node it matched.
        if name.startswith("special"):
            continue
        part = json.load(open(os.path.join(DICT_DIR, name), encoding="utf-8"))
        for k, v in part.items():
            if k in d and d[k] != v:
                dup.append((k, name))
            d[k] = v
    return d, dup


def apply_text(html, d, stats):
    def repl(m):
        raw = m.group(1)
        if "{{" in raw or "{%" in raw or "{#" in raw:
            return m.group(0)
        key = norm(raw)
        if key in d:
            lead = raw[: len(raw) - len(raw.lstrip())]
            trail = raw[len(raw.rstrip()):]
            new_raw = lead + d[key] + trail
            if new_raw == raw:
                return m.group(0)
            stats["text"] += 1
            return ">" + new_raw + "<"
        return m.group(0)

    return TEXT_RE.sub(repl, html)


def apply_attrs(html, d, stats):
    def repl(m):
        name, val = m.group(1), m.group(2)
        if "{{" in val or "{%" in val:
            return m.group(0)
        key = norm(val)
        if key in d:
            if d[key] == val:
                return m.group(0)
            stats["attr"] += 1
            return f'{name}="{d[key]}"'
        return m.group(0)

    return ATTR_RE.sub(repl, html)


def apply_literals(js, d, stats):
    def repl(m):
        a, b, c = m.group(1), m.group(2), m.group(3)
        val = a if a is not None else (b if b is not None else c)
        if val is None:
            return m.group(0)
        key = norm(val)
        if key not in d:
            return m.group(0)
        q = "'" if a is not None else ('"' if b is not None else "`")
        if d[key] == val:
            return m.group(0)
        stats["js"] += 1
        return q + d[key] + q

    return LITERAL_RE.sub(repl, js)


def apply_specials(text, specials, stats):
    """Longest-first literal replacement, for snippets that contain Jinja."""
    for src in sorted(specials, key=len, reverse=True):
        if src in text:
            n = text.count(src)
            text = text.replace(src, specials[src])
            stats["special"] += n
    return text


def process_html(path, d, specials, specials_js, stats, check):
    src = open(path, encoding="utf-8").read()
    out_parts = []
    # Split into script/style blocks (kept for literal translation) and the
    # remaining markup (text nodes + static attributes).
    for part in SCRIPT_RE.split(src):
        if not part:
            continue
        if SCRIPT_RE.fullmatch(part):
            if part.lstrip().lower().startswith("<script"):
                part = apply_literals(part, d, stats)
        else:
            part = apply_text(part, d, stats)
            part = apply_attrs(part, d, stats)
        out_parts.append(part)
    out = "".join(out_parts)
    out = apply_specials(out, specials, stats)
    out = apply_specials(out, specials_js, stats)
    if not check and out != src:
        open(path, "w", encoding="utf-8").write(out)


def process_js(path, d, specials_js, stats, check):
    src = open(path, encoding="utf-8").read()
    out = apply_literals(src, d, stats)
    out = apply_specials(out, specials_js, stats)
    if not check and out != src:
        open(path, "w", encoding="utf-8").write(out)


def main():
    check = "--check" in sys.argv
    d, dup = load_dict()
    specials_path = os.path.join(ROOT, "i18n", "dict", "special.json")
    specials = {}
    if os.path.exists(specials_path):
        specials = json.load(open(specials_path, encoding="utf-8"))

    specials_js_path = os.path.join(ROOT, "i18n", "dict", "special_js.json")
    specials_js = {}
    if os.path.exists(specials_js_path):
        specials_js = json.load(open(specials_js_path, encoding="utf-8"))

    print(f"dictionary entries: {len(d)}  specials: {len(specials)}  "
          f"specials_js: {len(specials_js)}")
    if dup:
        print(f"WARNING duplicate keys: {len(dup)}")
        for k, f in dup[:5]:
            print("   ", f, "|", k[:60])

    stats = {"text": 0, "attr": 0, "js": 0, "special": 0}
    for name in sorted(os.listdir(TEMPLATES)):
        if name.endswith(".html"):
            process_html(os.path.join(TEMPLATES, name), d, specials, specials_js, stats, check)
    for name in sorted(os.listdir(JS_DIR)):
        if name.endswith(".js") and name not in JS_SKIP:
            process_js(os.path.join(JS_DIR, name), d, specials_js, stats, check)

    print(f"replacements: text={stats['text']} attr={stats['attr']} "
          f"js={stats['js']} special={stats['special']}")
    if check:
        print("(dry run, nothing written)")

    # Coverage report against the extracted candidate set.
    cand_path = os.path.join(ROOT, "i18n", "candidates.json")
    if os.path.exists(cand_path):
        cand = json.load(open(cand_path, encoding="utf-8"))
        buckets = ["html_text", "html_attr", "js_string"]
        print("\n--- dictionary coverage of extracted strings ---")
        for b in buckets:
            keys = cand[b]
            hit = sum(1 for k in keys if norm(k) in d)
            print(f"  {b:10s} {hit:4d}/{len(keys):4d}  ({hit / len(keys) * 100:5.1f}%)")
        allk = [k for b in buckets for k in cand[b]]
        hit = sum(1 for k in allk if norm(k) in d)
        print(f"  {'TOTAL':10s} {hit:4d}/{len(allk):4d}  ({hit / len(allk) * 100:5.1f}%)")

        unused = [k for k in d if norm(k) not in {norm(x) for x in allk}]
        if unused:
            print(f"\n--- {len(unused)} dictionary keys never appear in sources ---")
            for k in unused[:10]:
                print("   ", k[:80])


if __name__ == "__main__":
    sys.exit(main())
