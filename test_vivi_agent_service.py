import unittest

from vivi_agent_service import (
    _complete_reply,
    extract_budget,
    request_agent_reply,
    search_projects,
)


class ViviAgentServiceTests(unittest.TestCase):
    def test_finds_inari_for_chia_budget(self):
        projects = search_projects(location="Chía", budget=250_000_000)
        self.assertEqual([item["name"] for item in projects], ["Inari"])

    def test_finds_soacha_projects_in_budget(self):
        projects = search_projects(location="Soacha", budget=200_000_000)
        self.assertEqual(
            [item["name"] for item in projects],
            ["La Macarena", "Monguí"],
        )

    def test_extracts_budget_in_millions(self):
        self.assertEqual(extract_budget("Tengo 250 millones"), 250_000_000)

    def test_catalog_question_does_not_call_gemini(self):
        result = request_agent_reply(
            {
                "message": "¿Qué proyectos hay en Chía con 250 millones?",
                "profile": {},
            }
        )
        self.assertEqual(result["source"], "CATALOGO_DETERMINISTICO")
        self.assertIn("Inari", result["reply"])
        self.assertTrue(result["reply"].endswith(("?", ".", "!")))

    def test_incomplete_reply_is_closed(self):
        result = _complete_reply("¡Excelente elección, D! En")
        self.assertEqual(result, "¡Excelente elección, D!")


if __name__ == "__main__":
    unittest.main()
