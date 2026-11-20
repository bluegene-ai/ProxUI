#!/usr/bin/env python3
"""Browser-level smoke test: render pages in Chromium and compare two instances.

For every page it records console errors, uncaught page errors, failed requests,
and the visible text after JS has run (length + Chinese character count).

Usage:  python3 i18n/browser_check.py <port_a> <port_b> [label_a] [label_b]
The two instances must serve the same Proxmox data (e.g. baseline vs translated).
"""
import re
import sys
import json
from playwright.sync_api import sync_playwright

ROUTES = [
    "/", "/vms", "/tasks", "/storages", "/networks", "/isos-templates",
    "/cluster", "/maintenance", "/firewall", "/backups", "/connect",
    "/create", "/node/pve",
]


def visit(page, url):
    console_errors, page_errors, failed = [], [], []

    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text[:160])

    def on_pageerror(err):
        page_errors.append(str(err)[:160])

    def on_requestfailed(req):
        failed.append(f"{req.failure} {req.url[:80]}")

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("requestfailed", on_requestfailed)

    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1800)
    try:
        text = page.inner_text("body")
    except Exception:
        text = ""

    page.remove_listener("console", on_console)
    page.remove_listener("pageerror", on_pageerror)
    page.remove_listener("requestfailed", on_requestfailed)

    zh = len(re.findall(r"[\u4e00-\u9fa5]", text))
    en = len(re.findall(r"[A-Za-z]{3,}", text))
    return {
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed": failed,
        "text_len": len(text.strip()),
        "zh": zh,
        "en": en,
        "text": text,
    }


def main():
    port_a = sys.argv[1] if len(sys.argv) > 1 else "8081"
    port_b = sys.argv[2] if len(sys.argv) > 2 else "8080"
    label_a = sys.argv[3] if len(sys.argv) > 3 else f"port{port_a}"
    label_b = sys.argv[4] if len(sys.argv) > 4 else f"port{port_b}"

    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        for route in ROUTES:
            a = visit(page, f"http://127.0.0.1:{port_a}{route}")
            b = visit(page, f"http://127.0.0.1:{port_b}{route}")
            rows.append((route, a, b))
        browser.close()

    print(f"{'route':18s} {'JS错误':>9s} {'页面异常':>10s} {'文本长度':>13s} {'中文':>11s}")
    print(f"{'':18s} {'基线/后':>9s} {'基线/后':>10s} {'基线/后':>13s} {'基线/后':>11s}")
    print("-" * 78)
    total_err_a = total_err_b = 0
    for route, a, b in rows:
        ea = len(a["console_errors"]) + len(a["page_errors"])
        eb = len(b["console_errors"]) + len(b["page_errors"])
        total_err_a += ea
        total_err_b += eb
        print(
            f"{route:18s} {len(a['console_errors'])}/{len(b['console_errors']):<7d} "
            f"{len(a['page_errors'])}/{len(b['page_errors']):<8d} "
            f"{a['text_len']}/{b['text_len']:<11d} "
            f"{a['zh']}/{b['zh']:<9d}"
        )
    print("-" * 78)
    print(f"累计 JS 错误: 基线 {total_err_a}  ->  {label_b} {total_err_b}")

    print("\n=== 具体错误明细（仅非空项）===")
    shown = 0
    for route, a, b in rows:
        for kind in ("console_errors", "page_errors", "failed"):
            for tag, rec in ((label_a, a), (label_b, b)):
                for item in rec[kind]:
                    if shown < 24:
                        print(f"  [{tag}] {route} {kind}: {item}")
                        shown += 1
    if shown == 0:
        print("  （无）")

    out = f"browser_check_{port_a}_vs_{port_b}.json"
    json.dump([{"route": r, "a": {**a, "text": a["text"][:4000]},
                "b": {**b, "text": b["text"][:4000]}} for r, a, b in rows],
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n明细已写入 {out}")


if __name__ == "__main__":
    main()
