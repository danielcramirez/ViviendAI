import json
import unittest
from unittest.mock import patch

from make_service import request_vivi_reply


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"ok": True, "reply": "Hola desde VIVI"}).encode()

class _PlainTextResponse(_Response):
    def read(self):
        return "Hola desde Gemini en Make".encode()


class MakeServiceTests(unittest.TestCase):
    @patch("make_service.urlopen", return_value=_Response())
    @patch.dict("os.environ", {"MAKE_STREAMLIT_WEBHOOK_URL": "https://example.test/hook"})
    def test_returns_gemini_reply(self, mocked_urlopen):
        result = request_vivi_reply({"message": "Hola"})
        self.assertEqual(result["reply"], "Hola desde VIVI")
        self.assertTrue(mocked_urlopen.called)

    @patch("make_service.urlopen", return_value=_PlainTextResponse())
    @patch.dict("os.environ", {"MAKE_STREAMLIT_WEBHOOK_URL": "https://example.test/hook"})
    def test_accepts_plain_text_webhook_response(self, mocked_urlopen):
        result = request_vivi_reply({"message": "Hola"})
        self.assertEqual(result["reply"], "Hola desde Gemini en Make")


if __name__ == "__main__":
    unittest.main()
