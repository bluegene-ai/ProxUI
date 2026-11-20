#!/usr/bin/env python3
"""End-to-end page render check without a real Proxmox host.

Boots the real Flask app with a throwaway data/config.toml, swaps the Proxmox
API for a permissive fake, then GETs every page route and reports:
  - HTTP status
  - number of Chinese characters in the rendered HTML
  - any exception text

Run from the repository root:  python3 i18n/verify_render.py
Exit code 0 means every route returned 200 (302 to /connect is reported).
"""

import os
import re
import sys
import io
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CONFIG = os.path.join(ROOT, "data", "config.toml")
TOML = """[[clusters]]
id = "test-cluster"
name = "Test Cluster"
incremental_vmid = false

    [[clusters.nodes]]
    host = "192.168.1.100"
    user = "root@pam"
    password = "testpass"
    verify_ssl = false
"""


class Fake:
    """Permissive stand-in for proxmoxer objects.

    Repeats itself for attribute access and iteration, and behaves like zero in
    arithmetic so templates that compute percentages or round() don't explode.
    """

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Fake()

    def __getitem__(self, key):
        return Fake()

    def __call__(self, *a, **k):
        return Fake()

    def __iter__(self):
        return iter([])

    def __len__(self):
        return 0

    def __bool__(self):
        return True

    def __str__(self):
        return "1"

    def __int__(self):
        return 1

    def __float__(self):
        return 1.0

    def __round__(self, n=None):
        return 1.0

    def __format__(self, spec):
        return "1"

    def _zero(self, *a):
        return Fake()

    __add__ = __radd__ = __sub__ = __rsub__ = _zero
    __mul__ = __rmul__ = __truediv__ = __rtruediv__ = _zero
    __lt__ = __le__ = __gt__ = __ge__ = lambda self, o: False
    __eq__ = lambda self, o: True
    __hash__ = lambda self: 0


PAGES = [
    "/", "/vms", "/tasks", "/storages", "/networks", "/isos-templates",
    "/cluster", "/maintenance", "/firewall", "/backups", "/connect",
    "/create",
    "/vm/test-node/100", "/vm/test-node/100/edit", "/vm/test-node/100/clone",
    "/node/test-node",
    "/tasks/test-node/UPID:test",
]


def main():
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    created = not os.path.exists(CONFIG)
    if created:
        open(CONFIG, "w", encoding="utf-8").write(TOML)

    # app.py defaults to the container path /app/data/config.toml; point it at
    # the throwaway config so config_file_exists is True and routes don't
    # redirect to /connect.
    os.environ["CONFIG_FILE_PATH"] = CONFIG

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        import app as proxui

    flask_app = proxui.app
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    fake = Fake()
    proxui.all_clusters.clear()
    proxui.all_clusters.update(
        {
            "test-cluster": {
                "id": "test-cluster",
                "name": "Test Cluster",
                "nodes": [
                    {
                        "host": "192.168.1.100",
                        "user": "root@pam",
                        "password": "testpass",
                        "verify_ssl": False,
                    }
                ],
            }
        }
    )
    proxui.current_cluster_id = "test-cluster"
    try:
        proxui.proxmox_nodes["test-node"] = fake
        proxui.cluster_nodes.append({"name": "test-node", "status": "online", "connection": fake})
    except Exception as exc:  # pragma: no cover
        print("setup warning:", exc)

    client = flask_app.test_client()
    rows = []
    for route in PAGES:
        try:
            r = client.get(route, follow_redirects=False)
            body = r.get_data(as_text=True)
            zh = len(re.findall(r"[\u4e00-\u9fa5]", body))
            note = ""
            if r.status_code in (301, 302):
                note = "redirect->" + (r.headers.get("Location") or "")
            elif "Traceback" in body or "jinja2.exceptions" in body:
                note = "TEMPLATE ERROR"
            rows.append((route, r.status_code, zh, note))
        except Exception as exc:
            rows.append((route, "EXC", 0, type(exc).__name__ + ": " + str(exc)[:60]))

    print(f"{'route':32s} {'code':6s} {'中文':>6s}  note")
    print("-" * 78)
    for route, code, zh, note in rows:
        print(f"{route:32s} {str(code):6s} {zh:6d}  {note}")

    ok = [r for r in rows if r[1] == 200]
    print("-" * 78)
    print(f"200 数: {len(ok)}/{len(rows)}；有中文的页面: {sum(1 for r in rows if r[2] > 0)}")
    if created:
        print(f"(已生成临时 {CONFIG}，git 已忽略 data/)")
    return 0 if len(ok) == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
