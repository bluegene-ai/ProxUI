#!/usr/bin/env python3
"""Extract translatable English UI strings from ProxUI sources (v2).

Key correctness rules learned from the first pass:
  * Jinja expressions may sit *inside* a text node. Replacing such a node would
    delete the placeholder, so those nodes are flagged and excluded.
  * Wrapped paragraphs contain newlines + indentation; keys are normalised so
    the dictionary stays readable and matching is not whitespace-brittle.
  * Alpine bindings (`:title=`, `x-text=`) hold JS expressions, not copy.
  * Bare HTML entities are not copy.

Output: i18n/candidates.json  (+ printed statistics)
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")
JS_DIR = os.path.join(ROOT, "static", "js")
JS_SKIP = {"alpine.min.js"}

ATTRS = ("placeholder", "title", "aria-label", "alt")

ENTITY_ONLY = re.compile(r"^(&[a-zA-Z]+;|&#\d+;|\s|&[a-zA-Z]+;\s*)+$")
HAS_LETTER = re.compile(r"[A-Za-z]{2,}")

BAD = [
    re.compile(r"^https?://"),
    re.compile(r"\.(js|css|html|json|svg|png|jpe?g|woff2?)$", re.I),
    # Single-token identifiers. Only *lowercase* single words are treated as
    # code; a Capitalised single word is a legitimate UI label ("Containers",
    # "Running", "Stopped", "Nodes") and must not be filtered out.
    re.compile(r"^[a-z][A-Za-z0-9_$]*$"),
    re.compile(r"^[a-z]+[A-Z][A-Za-z0-9]*$"),
    re.compile(r"^[a-z0-9]+(-[a-z0-9]+)+$"),
    re.compile(r"^[A-Z0-9_]{2,}$"),
    re.compile(r"^#?[0-9a-fA-F]{3,8}$"),
    re.compile(r"^[\d\s.,:%/+\-]+$"),
    re.compile(r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$"),
]


def norm(s):
    """Collapse all whitespace runs to one space and trim."""
    return re.sub(r"\s+", " ", s).strip()


def is_ui(s):
    s = norm(s)
    if len(s) < 2 or not HAS_LETTER.search(s):
        return False
    if ENTITY_ONLY.match(s):
        return False
    if s in {"&amp;", "&gt;", "&lt;", "&nbsp;", "&quot;", "&middot;", "&mdash;", "&ldquo;", "&rdquo;"}:
        return False
    for p in BAD:
        if p.match(s):
            return False
    if "{{" in s or "{%" in s or "{#" in s:
        return False
    if re.match(r"^[+.,;:!?)\]]*$", s):
        return False
    return True


def extract_js_literals(src):
    out = []
    for a, b, c in re.findall(
        r"""(?<![A-Za-z0-9_$.])(?:'([^'\\\n]{2,200})'|"([^"\\\n]{2,200})"|`([^`\\\n$]{2,200})`)""",
        src,
    ):
        v = a or b or c
        if not v:
            continue
        v = norm(v)
        if not is_ui(v):
            continue
        if " " not in v and not re.search(r"[:.!?]$", v):
            continue
        if v.startswith((".", "/", "data:", "#", "@")):
            continue
        # Skip anything that looks like a JS expression rather than copy.
        if re.search(r"[=<>]|\+ \w|\.\w+\(", v):
            continue
        out.append(v)
    return out


def main():
    stats = {"html_text": 0, "html_text_jinja_skipped": 0, "html_attr": 0, "js_string": 0}
    html_text, html_attr, js_string = set(), set(), set()
    per_file = {}

    for name in sorted(os.listdir(TEMPLATES)):
        if not name.endswith(".html"):
            continue
        path = os.path.join(TEMPLATES, name)
        src = open(path, encoding="utf-8").read()

        scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", src, flags=re.S | re.I)
        body = re.sub(r"<script(?![^>]*\bsrc=)[^>]*>.*?</script>", "", src, flags=re.S | re.I)
        body = re.sub(r"<style.*?</style>", "", body, flags=re.S | re.I)
        body = re.sub(r"\{#.*?#\}", "", body, flags=re.S)

        local = 0
        for t in re.findall(r">([^<>]+)<", body):
            if "{{" in t or "{%" in t:
                if is_ui(t):
                    stats["html_text_jinja_skipped"] += 1
                continue
            if is_ui(t):
                html_text.add(norm(t))
                local += 1

        # Static attributes only: reject Alpine/JS bindings by looking at the
        # character immediately before the attribute name.
        for m in re.finditer(
            r"(?<![:@\w-])(placeholder|title|aria-label|alt)\s*=\s*\"([^\"]*)\"", body, flags=re.I
        ):
            v = m.group(2)
            if "{{" in v or "{%" in v or len(v) > 200:
                continue
            if is_ui(v):
                html_attr.add(norm(v))
                local += 1

        for blk in scripts:
            got = extract_js_literals(blk)
            js_string.update(got)
            local += len(got)

        per_file[f"templates/{name}"] = local

    for name in sorted(os.listdir(JS_DIR)):
        if not name.endswith(".js") or name in JS_SKIP:
            continue
        src = open(os.path.join(JS_DIR, name), encoding="utf-8").read()
        got = extract_js_literals(src)
        js_string.update(got)
        per_file[f"static/js/{name}"] = len(got)

    stats["html_text"] = len(html_text)
    stats["html_attr"] = len(html_attr)
    stats["js_string"] = len(js_string)

    data = {
        "html_text": sorted(html_text),
        "html_attr": sorted(html_attr),
        "js_string": sorted(js_string),
        "per_file": per_file,
        "stats": stats,
    }
    out = os.path.join(ROOT, "i18n", "candidates.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(json.dumps(stats, indent=1))
    print(f"unique total = {stats['html_text'] + stats['html_attr'] + stats['js_string']}")

    # Length distribution helps decide what still needs prose work.
    allstr = list(html_text) + list(html_attr) + list(js_string)
    buckets = {"<=30": 0, "31-70": 0, "71-140": 0, ">140": 0}
    for s in allstr:
        n = len(s)
        if n <= 30:
            buckets["<=30"] += 1
        elif n <= 70:
            buckets["31-70"] += 1
        elif n <= 140:
            buckets["71-140"] += 1
        else:
            buckets[">140"] += 1
    print("length buckets:", buckets)


if __name__ == "__main__":
    sys.exit(main())
