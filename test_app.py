import unittest

from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from agents.analista_perfilamiento import EXTRACTABLE_FIELDS


class StreamlitAppTests(unittest.TestCase):
    def test_customer_experience_renders_without_errors(self):
        app = AppTest.from_file("app.py", default_timeout=10).run()

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("VIVI · ViviendAI" in title.value for title in app.markdown))
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
            any("Precalificación técnica inicial: 65/100" in block.value for block in app.markdown)
        )

    def test_agent2_card_hidden_when_no_analysis_yet(self):
        """Agent 2 card should not appear before any analysis runs."""
        app = AppTest.from_file("app.py", default_timeout=10)
        app.session_state["show_form"] = True
        app.session_state["last_result"] = {
            "lead_code": "META-001",
            "duplicate": False,
            "rating": "ALTA",
            "score": 80,
            "crm_status": "SYNCED",
        }
        app.session_state["instagram_agent2_result"] = None
        app.session_state["instagram_profile"] = {
            "lead_code": "META-001",
            "project_origin": "Samán",
            "campaign_id": "CAMP-001",
            "customer_name": "Laura",
        }
        app.session_state["instagram_messages"] = [
            {"role": "assistant", "content": "¡Hola!"},
        ]
        app.run()

        self.assertEqual(len(app.exception), 0)
        # Should NOT contain Agent 2 card header
        agent2_card_found = any(
            "Analista de Perfilamiento" in block.value for block in app.markdown
        )
        self.assertFalse(agent2_card_found)

    def test_agent2_card_renders_with_cached_result(self):
        """Agent 2 card with score, priority, and recommended action."""
        scoring = {
            "propensity_score": 72,
            "priority": "MEDIA",
            "route": "COMPLETAR_PERFIL",
            "missing_fields": ["propósito de compra", "zona donde vive"],
            "recommended_action": "Completar datos faltantes y ofrecer simulación o visita.",
            "score_breakdown": {"intent": 10, "horizon": 5},
            "score_reasons": ["Razón 1"],
            "disclaimer": "Test disclaimer.",
            "score_version": "VIVI-1.0",
        }
        profile_complete = {
            "lead_code": "META-001",
            "project_origin": "Samán",
            "campaign_id": "CAMP-001",
            "customer_name": "Laura",
            "interest_origin_project": True,
            "purchase_purpose": "Vivir con mi familia",
            "lives_in": "Suba",
            "works_in": "Calle 80",
            "household_size": 3,
            "housing_dream": "Balcón",
            "accepts_advisor_contact": True,
            "profile_complete": True,
        }
        agent2_result = {
            "ok": True,
            "profile": profile_complete,
            "scoring": scoring,
            "diagnosis": "Lead que mantiene interés; ...",
            "schema_errors": [],
            "gemini_source": "GEMINI_AGENTE2",
            "crm_status": "SYNCED",
        }

        app = AppTest.from_file("app.py", default_timeout=10)
        app.session_state["show_form"] = True
        app.session_state["last_result"] = {
            "lead_code": "META-001",
            "duplicate": False,
            "rating": "ALTA",
            "score": 80,
            "crm_status": "SYNCED",
        }
        app.session_state["instagram_agent2_result"] = agent2_result
        app.session_state["instagram_profile"] = profile_complete
        app.session_state["instagram_messages"] = [
            {"role": "assistant", "content": "¡Hola!"},
            {"role": "user", "content": "Sí, me interesa"},
        ]
        app.run()

        self.assertEqual(len(app.exception), 0)
        combined_md = " ".join(b.value for b in app.markdown)
        self.assertIn("Analista de Perfilamiento", combined_md)
        self.assertIn("72/100", combined_md)
        self.assertIn("MEDIA", combined_md)
        self.assertIn("Acción recomendada", combined_md)
        self.assertIn("Campos faltantes", combined_md)
        self.assertIn("Ficha del Sueño", combined_md)
        self.assertIn("Lead que mantiene interés", combined_md)
        self.assertIn("propósito de compra", combined_md)
        self.assertIn("zona donde vive", combined_md)
        self.assertIn("GEMINI_AGENTE2", combined_md)
        self.assertIn("COMPLETAR_PERFIL", combined_md)
        self.assertIn("SYNCED", combined_md)
        # Persistencia: hereda de get_storage_status() — local si no hay Supabase
        self.assertIn("Persistencia", combined_md)

    def test_agent2_persistencia_shows_error_on_storage_warning(self):
        """When storage_warning is present, Persistencia shows error badge."""
        scoring = {
            "propensity_score": 50,
            "priority": "MEDIA",
            "route": "COMPLETAR_PERFIL",
            "missing_fields": [],
            "recommended_action": "Completar perfil.",
            "score_breakdown": {},
            "score_reasons": [],
            "disclaimer": "Test.",
            "score_version": "VIVI-1.0",
        }
        app = AppTest.from_file("app.py", default_timeout=10)
        app.session_state["show_form"] = True
        app.session_state["last_result"] = {
            "lead_code": "META-001",
            "duplicate": False,
            "rating": "ALTA",
            "score": 80,
            "crm_status": "SYNCED",
            "storage_warning": "Supabase no respondió, se usó solo SQLite",
        }
        app.session_state["instagram_agent2_result"] = {
            "ok": True,
            "profile": {"lead_code": "META-001"},
            "scoring": scoring,
            "diagnosis": "...",
            "schema_errors": [],
            "gemini_source": "GEMINI_AGENTE2",
            "crm_status": "SYNCED",
        }
        app.session_state["instagram_profile"] = {
            "lead_code": "META-001",
            "project_origin": "Samán",
            "campaign_id": "CAMP-001",
        }
        app.session_state["instagram_messages"] = [
            {"role": "assistant", "content": "¡Hola!"},
        ]
        app.run()

        self.assertEqual(len(app.exception), 0)
        combined = " ".join(b.value for b in app.markdown)
        self.assertIn("Persistencia", combined)
        self.assertIn("ERROR DE SINCRONIZACIÓN", combined)

    def test_agent2_error_is_graceful(self):
        """Error state shows informational message, not crash."""
        app = AppTest.from_file("app.py", default_timeout=10)
        app.session_state["show_form"] = True
        app.session_state["last_result"] = {
            "lead_code": "META-001",
            "duplicate": False,
            "rating": "ALTA",
            "score": 80,
            "crm_status": "SYNCED",
        }
        app.session_state["instagram_agent2_result"] = {
            "ok": False,
            "reply_warning": "Gemini no respondió",
            "gemini_source": None,
        }
        app.session_state["instagram_profile"] = {
            "lead_code": "META-001",
            "project_origin": "Samán",
        }
        app.session_state["instagram_messages"] = [
            {"role": "assistant", "content": "¡Hola!"},
        ]
        app.run()

        self.assertEqual(len(app.exception), 0)
        info_texts = [info.value for info in app.info]
        has_graceful = any(
            "Agente 2 no disponible" in text for text in info_texts
        )
        self.assertTrue(has_graceful)

    def test_agent2_refresh_button_exists(self):
        """The 'Actualizar análisis' button should be present."""
        app = AppTest.from_file("app.py", default_timeout=10)
        app.session_state["show_form"] = True
        app.session_state["last_result"] = {
            "lead_code": "META-001",
            "duplicate": False,
            "rating": "ALTA",
            "score": 80,
            "crm_status": "SYNCED",
        }
        app.session_state["instagram_profile"] = {
            "lead_code": "META-001",
            "project_origin": "Samán",
            "campaign_id": "CAMP-001",
            "customer_name": "Laura",
        }
        app.session_state["instagram_messages"] = [
            {"role": "assistant", "content": "¡Hola!"},
            {"role": "user", "content": "Sí, me interesa"},
        ]
        app.run()

        self.assertEqual(len(app.exception), 0)
        refresh_buttons = [
            btn for btn in app.button
            if "Actualizar análisis" in btn.label
        ]
        self.assertGreaterEqual(len(refresh_buttons), 1)

    def test_agent2_routes_correct_source_label(self):
        """Different gemini_source values render correctly."""
        for source in ("GEMINI_AGENTE2", "FALLBACK_SIN_EXTRACCION", "SIN_HISTORIAL"):
            scoring = {
                "propensity_score": 50,
                "priority": "NUTRICIÓN",
                "route": "PERTENECER",
                "missing_fields": [],
                "recommended_action": "Mantener acompañamiento.",
                "score_breakdown": {},
                "score_reasons": [],
                "disclaimer": "Test.",
                "score_version": "VIVI-1.0",
            }
            app = AppTest.from_file("app.py", default_timeout=10)
            app.session_state["show_form"] = True
            app.session_state["last_result"] = {
                "lead_code": "META-001",
                "duplicate": False,
                "rating": "ALTA",
                "score": 80,
                "crm_status": "SYNCED",
            }
            app.session_state["instagram_agent2_result"] = {
                "ok": True,
                "profile": {"lead_code": "META-001"},
                "scoring": scoring,
                "diagnosis": "...",
                "schema_errors": [],
                "gemini_source": source,
                "crm_status": "SYNCED",
            }
            app.session_state["instagram_profile"] = {
                "lead_code": "META-001",
                "project_origin": "Samán",
                "campaign_id": "CAMP-001",
            }
            app.session_state["instagram_messages"] = [
                {"role": "assistant", "content": "¡Hola!"},
            ]
            app.run()

            self.assertEqual(len(app.exception), 0)
            combined = " ".join(b.value for b in app.markdown)
            self.assertIn(source, combined, f"Source {source} should appear in Agent 2 card")


if __name__ == "__main__":
    unittest.main()
