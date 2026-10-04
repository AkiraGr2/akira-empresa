import asyncio
import base64
import json
import os
import unittest
from unittest.mock import patch

import nexus


class FakeRequest:
    def __init__(self, payload):
        self._payload = payload
        self.headers = {}
        self.client = None

    async def json(self):
        return self._payload


def response_payload(response):
    return json.loads(response.body.decode("utf-8"))


class MultimediaEndpointRegressionTests(unittest.TestCase):
    def test_authenticated_pdf_endpoint_extracts_real_pdf(self):
        self.assertIsNotNone(nexus._fitz, "PyMuPDF must be installed for the PDF contract")

        doc = nexus._fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "AKIRA PDF E2E VERIFIED CONTENT")
        raw = doc.tobytes()
        doc.close()

        request = FakeRequest({
            "filename": "akira-e2e.pdf",
            "content_base64": base64.b64encode(raw).decode("ascii"),
        })

        with patch("nexus.get_session", return_value={
            "email": "e2e@example.test",
            "is_owner": False,
        }), patch("nexus.check_media_rate_limit", return_value=True):
            result = asyncio.run(nexus.extract_file(request))

        self.assertIsInstance(result, dict)
        self.assertTrue(result["ok"])
        self.assertIn("AKIRA PDF E2E VERIFIED CONTENT", result["text"])
        self.assertGreater(result["length"], 0)

    def test_pdf_endpoint_rejects_unauthenticated_request_before_parsing(self):
        request = FakeRequest({
            "filename": "akira-e2e.pdf",
            "content_base64": base64.b64encode(b"%PDF-FAKE").decode("ascii"),
        })

        with patch("nexus.get_session", return_value=None), patch("nexus.check_media_rate_limit") as limiter:
            result = asyncio.run(nexus.extract_file(request))

        self.assertEqual(result.status_code, 401)
        self.assertEqual(response_payload(result)["reason"], "auth_required")
        limiter.assert_not_called()

    def test_pdf_endpoint_rejects_non_pdf_signature(self):
        request = FakeRequest({
            "filename": "akira-e2e.pdf",
            "content_base64": base64.b64encode(b"not-a-pdf").decode("ascii"),
        })

        with patch("nexus.get_session", return_value={
            "email": "e2e@example.test",
            "is_owner": False,
        }), patch("nexus.check_media_rate_limit", return_value=True):
            result = asyncio.run(nexus.extract_file(request))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(response_payload(result)["reason"], "not_pdf")

    def test_runtime_capabilities_stay_free_only_and_image_disabled_without_double_opt_in(self):
        with patch.dict(
            os.environ,
            {
                "POLLINATIONS_API_KEY": "",
                "AKIRA_ENABLE_EXPERIMENTAL_IMAGE": "1",
            },
            clear=False,
        ):
            result = asyncio.run(nexus.runtime_capabilities())

        self.assertTrue(result["ok"])
        self.assertTrue(result["free_only_policy"])
        self.assertFalse(result["paid_api_enabled"])
        self.assertEqual(result["image"]["status"], "disabled")
        self.assertFalse(result["image"]["enabled"])
        self.assertTrue(result["image"]["requires_explicit_opt_in"])

    def test_runtime_capabilities_expose_experimental_image_only_after_double_opt_in(self):
        with patch.dict(os.environ, {"AKIRA_ENABLE_EXPERIMENTAL_IMAGE": "true"}, clear=False), \
             patch("nexus.get_pollinations_key", return_value="secret-test-only"):
            result = asyncio.run(nexus.runtime_capabilities())

        self.assertEqual(result["image"]["status"], "experimental")
        self.assertTrue(result["image"]["enabled"])
        self.assertFalse(result["image"]["free_guaranteed"])
        self.assertEqual(result["image"]["mode"], "server_proxy")
        serialized = json.dumps(result)
        self.assertNotIn("secret-test-only", serialized)


if __name__ == "__main__":
    unittest.main()
