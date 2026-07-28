"""SMS channel microservice — one of the paddock's notification channels (e-mail and push are its
siblings). A tiny framework-free HTTP service, the same shape as the image encoder and race sim.

    POST /send   {"to": "+48555123456", "subject": "...", "body": "..."}  -> 202 {"status":"SENT"}
    GET  /health                                                          -> 200 {"status":"UP"}

By default it STUB-sends: the message is validated and logged, nothing leaves the box — so the
stack runs end to end with no telephony account. Point SMS_PROVIDER at a real gateway (e.g. twilio)
and give it credentials to send for real; the wire contract the paddock speaks never changes.
"""

import hmac
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
# The same guard the sibling mail service has had all along: only trusted callers may send. Without
# it this endpoint takes a message from anything that can reach the port — today the compose network
# (every container in the stack), and the README's own next step is "point SMS_PROVIDER at a real gateway
# and give it credentials", at which point an unauthenticated endpoint becomes a paid-SMS pump
# and a phishing channel ("Your sign-in code is ..." from the portal's own number).
API_KEY = os.environ.get("SMS_API_KEY")
# A request body this service has any business reading: every legitimate one is a short JSON object.
MAX_BODY_BYTES = 8192

# E.164-ish: a leading + and 8..15 digits. A phone number is a routing key, not free text.
E164 = re.compile(r"^\+[1-9]\d{7,14}$")
MAX_LEN = 480   # a few concatenated SMS segments


def masked(number):
    """A number reduced to what an operator needs to match a support call: the last three digits."""
    return "***" + number[-3:] if number and len(number) > 3 else "***"


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
        # Metadata only. This log used to carry the first 60 characters of the message, and the
        # message security sends is "Sign-in code: Your sign-in code is 123456" — 41 characters, so
        # the whole one-time code fitted, next to the subscriber's full number. Promtail ships every
        # container's stdout to Loki, where dev Grafana is an anonymous admin, so anyone with a
        # browser could read other people's sign-in codes faster than the SMS arrives.
        log("INFO", f"stub delivery to {masked(to)} ({len(text)} chars)")
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
        if API_KEY and not hmac.compare_digest(self.headers.get("X-Api-Key", ""), API_KEY):
            self._json(401, {"status": "UNAUTHORIZED"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._json(400, {"status": "BAD_REQUEST", "error": "invalid Content-Length"})
            return
        if length > MAX_BODY_BYTES:
            self._json(413, {"status": "REJECTED", "error": "body too large"})
            return
        try:
            payload = json.loads(self.rfile.read(max(0, length)) or b"{}")
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
