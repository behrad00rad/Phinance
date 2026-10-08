import io
import json
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .management.commands.update_gold_price import NoRedirect, fetch_gold_18k_price


class GoldPriceTransportTests(SimpleTestCase):
    def test_redirects_are_not_followed(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://example.com/"))

    @patch.dict("os.environ", {"NAVASAN_API_KEY": "dummy-test-key"})
    @patch("finance.management.commands.update_gold_price.build_opener")
    def test_key_is_sent_only_to_https_and_hidden_from_errors(self, build_opener):
        opener = build_opener.return_value
        opener.open.side_effect = OSError("request failed for https://api.navasan.tech/?api_key=dummy-test-key")
        with self.assertRaises(CommandError) as caught:
            fetch_gold_18k_price()
        request = opener.open.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://api.navasan.tech/"))
        self.assertNotIn("dummy-test-key", str(caught.exception))

    @patch.dict("os.environ", {"NAVASAN_API_KEY": "dummy-test-key"})
    @patch("finance.management.commands.update_gold_price.build_opener")
    def test_https_response_is_parsed(self, build_opener):
        payload = {"18ayar": {"value": "1000000", "timestamp": 1700000000}}
        build_opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
        price, updated_at = fetch_gold_18k_price()
        self.assertEqual(price, 1000000)
        self.assertEqual(int(updated_at.timestamp()), 1700000000)
