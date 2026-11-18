"""Local-network transfer board. Requires only Python 3.12+.

Run from WSL:
  TRANSFER_PIN='your-own-pin' python3 app.py
"""
from __future__ import annotations

import html
import os
import secrets
import socket
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("TRANSFER_PORT", "8787"))
PIN = os.environ.get("TRANSFER_PIN", "transfer")
SESSION = secrets.token_urlsafe(24)
ITEMS: list[dict[str, object]] = []


def lan_ip() -> str:
    """Return the WSL VM's current LAN-facing address if available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def remove_expired() -> None:
    ITEMS[:] = [item for item in ITEMS if float(item["expires"]) > time.time()]


def is_web_link(value: str) -> bool:
    address = urlparse(value)
    return address.scheme in {"http", "https"} and bool(address.netloc)


class App(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        pass

    def get_form(self) -> dict[str, list[str]]:
        length = int(self.headers.get("Content-Length", 0))
        return parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)

    def signed_in(self) -> bool:
        cookies = SimpleCookie(self.headers.get("Cookie"))
        return cookies.get("transfer") is not None and cookies["transfer"].value == SESSION

    def respond(self, page: str, status: int = 200, cookie: str | None = None) -> None:
        payload = page.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(payload))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(payload)

    def go_home(self, cookie: str | None = None) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        elif self.signed_in():
            remove_expired()
            self.respond(board())
        else:
            self.respond(login())

    def do_POST(self) -> None:
        form = self.get_form()
        if self.path == "/login":
            if secrets.compare_digest(form.get("pin", [""])[0], PIN):
                self.go_home(f"transfer={SESSION}; HttpOnly; SameSite=Strict; Path=/")
            else:
                self.respond(login("That PIN is not right."), 401)
            return
        if not self.signed_in():
            self.go_home()
            return
        if self.path == "/add":
            content = form.get("content", [""])[0].strip()[:10000]
            label = form.get("label", [""])[0].strip()[:80]
            try:
                minutes = min(1440, max(1, int(form.get("minutes", ["60"])[0])))
            except ValueError:
                minutes = 60
            if content:
                remove_expired()
                ITEMS.insert(0, {"content": content, "label": label, "expires": time.time() + minutes * 60})
                del ITEMS[30:]
            self.go_home()
        elif self.path == "/clear":
            ITEMS.clear()
            self.go_home()
        else:
            self.send_error(404)


def page(body: str) -> str:
    return f"""<!doctype html><html lang='en'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Transfer board</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#10172b;color:#edf2ff;font:16px system-ui,-apple-system,Segoe UI,sans-serif}}main{{max-width:760px;margin:auto;padding:32px 18px 56px}}h1{{margin:0;font-size:28px}}h2{{margin:0;font-size:19px}}.sub,.meta{{color:#aebbd5}}.card{{background:#1b2540;border:1px solid #2e3d60;border-radius:16px;padding:20px;margin:16px 0}}label{{display:block;margin:12px 0 6px;color:#c1cce1;font-size:13px}}input,textarea,select{{width:100%;color:#fff;background:#111a2e;border:1px solid #405276;border-radius:10px;padding:11px;font:inherit}}textarea{{min-height:96px;resize:vertical}}button{{padding:11px 16px;border:0;border-radius:10px;background:#8ba5ff;color:#091126;font-weight:700;font:inherit;cursor:pointer}}button.secondary{{background:#3c4963;color:#fff}}.row{{display:flex;gap:10px;align-items:end}}.row>div{{flex:1}}.row button{{flex:0 0 auto}}.entry{{padding:16px 0;border-top:1px solid #32405f;overflow-wrap:anywhere}}.entry:first-child{{padding-top:0;border-top:0}}.label{{font-weight:700;margin-bottom:6px}}.content{{white-space:pre-wrap}}a{{color:#b8c7ff}}.notice{{color:#ffb8c0}}code{{background:#10192c;padding:2px 5px;border-radius:5px}}</style>
<main>{body}</main>"""


def login(error: str = "") -> str:
    message = f"<p class='notice'>{html.escape(error)}</p>" if error else ""
    return page(f"<h1>Transfer board</h1><p class='sub'>A private clipboard for this local network.</p><section class='card'><form method='post' action='/login'><label>Access PIN</label><input type='password' name='pin' autocomplete='current-password' autofocus required>{message}<p><button>Open board</button></p></form></section><p class='sub'>Use this only on a trusted network.</p>")


def board() -> str:
    entries: list[str] = []
    for item in ITEMS:
        content = str(item["content"])
        shown = (f"<a target='_blank' rel='noopener' href='{html.escape(content, quote=True)}'>{html.escape(content)}</a>"
                 if is_web_link(content) else f"<div class='content'>{html.escape(content)}</div>")
        heading = f"<div class='label'>{html.escape(str(item['label']))}</div>" if item["label"] else ""
        remaining = max(1, round((float(item["expires"]) - time.time()) / 60))
        entries.append(f"<article class='entry'>{heading}{shown}<div class='meta'>Expires in about {remaining} min</div></article>")
    current = "".join(entries) or "<p class='sub'>Nothing shared yet.</p>"
    return page(f"""<h1>Transfer board</h1><p class='sub'>Paste a link or text here, then open this page from your phone or tablet.</p>
<section class='card'><form method='post' action='/add'><label>Link or text</label><textarea name='content' placeholder='Paste a URL, note, code, or anything small' required></textarea><div class='row'><div><label>Optional label</label><input name='label' placeholder='e.g. Read later'></div><div><label>Keep for</label><select name='minutes'><option value='15'>15 minutes</option><option value='60' selected>1 hour</option><option value='240'>4 hours</option><option value='1440'>1 day</option></select></div><button>Add</button></div></form></section>
<section class='card'><div class='row'><div><h2>Shared now</h2></div><form method='post' action='/clear'><button class='secondary'>Clear all</button></form></div><div style='margin-top:18px'>{current}</div></section><p class='sub'>Entries are memory-only: they disappear when the program stops.</p>""")


if __name__ == "__main__":
    print(f"Transfer board started: http://{lan_ip()}:{PORT}")
    print("Use Ctrl+C to stop it.")
    ThreadingHTTPServer(("0.0.0.0", PORT), App).serve_forever()
