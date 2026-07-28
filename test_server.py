"""The SMS channel validates recipients and messages; the stub delivers deterministically."""

import contextlib
import io
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import server
from server import send


class SmsTest(unittest.TestCase):

    def test_a_valid_sms_is_sent(self):
        mid = send("+48555123456", "Paddock", "Race Friday 20:00")
        self.assertTrue(mid.startswith("stub-"))

    def test_the_same_message_gets_the_same_stub_id(self):
        self.assertEqual(send("+48555123456", "a", "b"), send("+48555123456", "a", "b"))

    def test_a_non_phone_recipient_is_refused(self):
        for bad in (None, "", "555-123", "alice@example.com", "0048555123456"):
            with self.assertRaises(ValueError):
                send(bad, "s", "b")

    def test_an_empty_or_oversized_message_is_refused(self):
        with self.assertRaises(ValueError):
            send("+48555123456", "", "")
        with self.assertRaises(ValueError):
            send("+48555123456", "", "x" * 1000)


class BoundaryTest(unittest.TestCase):
    """The HTTP edge: who may send, and what the log is allowed to say about it."""

    @classmethod
    def setUpClass(cls):
        server.API_KEY = "test-key"                       # as compose now configures it
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        server.API_KEY = None
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, payload, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request("POST", "/send", json.dumps(payload),
                           {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        response.read()
        connection.close()
        return response

    def test_a_send_without_the_api_key_is_refused(self):
        # this endpoint took a message from anything that could reach the port; the sibling mail
        # service has demanded a key all along
        message = {"to": "+48555123456", "subject": "Sign-in code", "body": "Your sign-in code is 123456"}

        self.assertEqual(401, self.post(message).status)
        self.assertEqual(401, self.post(message, {"X-Api-Key": "wrong"}).status)
        self.assertEqual(202, self.post(message, {"X-Api-Key": "test-key"}).status)

    def test_an_oversized_body_is_refused_before_it_is_read(self):
        self.assertEqual(413, self.post({"to": "+48555123456", "body": "x" * 9000},
                                        {"X-Api-Key": "test-key"}).status)

    def test_the_log_never_carries_the_code_or_the_whole_number(self):
        # the message security sends is 41 characters, so the 60-character excerpt this log used to
        # print contained the entire one-time code — next to the subscriber's full number, in Loki
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            send("+48555123456", "Sign-in code", "Your sign-in code is 123456")
        written = captured.getvalue()

        self.assertNotIn("123456", written, "the one-time code must never be logged")
        self.assertNotIn("+48555123456", written, "nor the full number")
        self.assertIn("***456", written, "the last three digits are enough to match a support call")


if __name__ == "__main__":
    unittest.main()
