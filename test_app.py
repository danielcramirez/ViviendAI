import unittest

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_customer_experience_renders_without_errors(self):
        app = AppTest.from_file("app.py", default_timeout=10).run()

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Visionario ViviendAI" in title.value for title in app.markdown))
        self.assertTrue(any(button.label == "Registrarte" for button in app.button))

    def test_legacy_rating_does_not_break_open_session(self):
        app = AppTest.from_file("app.py", default_timeout=10)
        app.session_state["show_form"] = True
        app.session_state["last_result"] = {
            "lead_code": "META-001",
            "duplicate": False,
            "rating": "TIBIO",
            "score": 65,
            "recommendation": "Continuar perfilación.",
            "crm_status": "SYNCED",
        }
        app.run()

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(
            any("Prioridad comercial: MEDIA" in block.value for block in app.markdown)
        )


if __name__ == "__main__":
    unittest.main()
