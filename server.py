"""SMS channel microservice — one of the paddock's notification channels (e-mail and push are its
siblings). A tiny framework-free HTTP service, the same shape as the image encoder and race sim.

    POST /send   {"to": "+48555123456", "subject": "...", "body": "..."}  -> 202 {"status":"SENT"}
    GET  /health                                                          -> 200 {"status":"UP"}

By default it STUB-sends: the message is validated and logged, nothing leaves the box — so the
stack runs end to end with no telephony account. Point SMS_PROVIDER at a real gateway (e.g. twilio)
and give it credentials to send for real; the wire contract the paddock speaks never changes.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

SERVICE = "sms"

def log(level, message):
    """The stack's shared log line (observability/README.md in the aggregator repo): ISO
    time, level, cid/trace placeholders (this stdlib stack sets neither), service, message."""
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")
    print(f"{stamp} {level:<5} [cid=-] [trace=-] {SERVICE} - {message}", flush=True)


PROVIDER = os.environ.get("SMS_PROVIDER", "stub")
# E.164-ish: a leading + and 8..15 digits. A phone number is a routing key, not free text.
E164 = re.compile(r"^\+[1-9]\d{7,14}$")
MAX_LEN = 480   # a few concatenated SMS segments


def send(to, subject, body):
    """Deliver one SMS (or refuse it). Returns the provider's message id. Raises ValueError on a
    bad request. The stub provider logs; a real provider would call its gateway here."""
    if not to or not E164.match(to):
        raise ValueError(f"not a phone number in E.164 form: {to!r}")
    text = ((subject + ": ") if subject else "") + (body or "")
    if not text.strip():
        raise ValueError("empty message")
    if len(text) > MAX_LEN:
        raise ValueError(f"message too long ({len(text)} > {MAX_LEN})")
    if PROVIDER == "stub":
        log("INFO", f"stub delivery to {to}: {text[:60]!r}")
        return "stub-" + str(abs(hash((to, text))) % 10_000_000)
    raise ValueError(f"unknown SMS_PROVIDER: {PROVIDER}")   # real gateways plug in here


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self._json(200, {"status": "UP", "provider": PROVIDER})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/send":
            self._json(404, {"error": "not found"})
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            self._json(400, {"status": "BAD_REQUEST", "error": "invalid JSON"})
            return
        try:
            message_id = send(payload.get("to"), payload.get("subject"), payload.get("body"))
        except ValueError as bad:
            self._json(400, {"status": "REJECTED", "error": str(bad)})
            return
        self._json(202, {"status": "SENT", "channel": "sms", "id": message_id})

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        log("INFO", f"{self.command} {self.path}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8088"))
    log("INFO", f"sms channel listening on {port} (provider={PROVIDER})")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
