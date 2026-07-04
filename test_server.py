"""The SMS channel validates recipients and messages; the stub delivers deterministically."""

import unittest

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


if __name__ == "__main__":
    unittest.main()
