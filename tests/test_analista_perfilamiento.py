from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the project root is on sys.path so imports work.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.analista_perfilamiento import (
    EXTRACTABLE_FIELDS,
    _count_profile_fields,
    _load_schema,
    _merge_extracted_profile,
    _validate_against_schema,
)


SCHEMA = _load_schema()


class TestProfileMerging(unittest.TestCase):
    """Agent 2 can merge extracted fields into an existing profile."""

    def test_merge_updates_non_none(self):
        profile = {"interest_origin_project": None, "lives_in": None}
        extracted = {"interest_origin_project": True, "lives_in": "Bogotá", "works_in": None}
        merged = _merge_extracted_profile(profile, extracted)
        self.assertIs(merged["interest_origin_project"], True)
        self.assertEqual(merged["lives_in"], "Bogotá")
        # works_in is None — should not override (was already None)
        self.assertIsNone(merged.get("works_in"))

    def test_merge_preserves_existing(self):
        profile = {"lives_in": "Chía", "works_in": "Bogotá"}
        extracted = {"lives_in": None, "works_in": None, "housing_dream": "Un apartamento con balcón"}
        merged = _merge_extracted_profile(profile, extracted)
        # None values from extraction should NOT overwrite existing values
        self.assertEqual(merged["lives_in"], "Chía")
        self.assertEqual(merged["works_in"], "Bogotá")
        self.assertEqual(merged["housing_dream"], "Un apartamento con balcón")

    def test_merge_empty_string_skipped(self):
        profile = {"lives_in": "Bogotá"}
        extracted = {"lives_in": ""}
        merged = _merge_extracted_profile(profile, extracted)
        self.assertEqual(merged["lives_in"], "Bogotá")


class TestFieldCounting(unittest.TestCase):
    """Agent 2 can count how many profile fields have meaningful values."""

    def test_empty_profile(self):
        self.assertEqual(_count_profile_fields({}), 0)

    def test_partial_profile(self):
        profile = {"lives_in": "Bogotá", "works_in": "Chía"}
        self.assertEqual(_count_profile_fields(profile), 2)

    def test_full_profile(self):
        profile = {
            "interest_origin_project": True,
            "purchase_purpose": "Crecer familiar",
            "lives_in": "Bogotá",
            "works_in": "Chía",
            "household_size": 4,
            "housing_dream": "Casa con jardín",
            "desired_features": ["parque", "3 habitaciones"],
            "accepts_advisor_contact": True,
        }
        self.assertEqual(_count_profile_fields(profile), 8)

    def test_none_and_empty_not_counted(self):
        profile = {
            "interest_origin_project": None,
            "lives_in": "",
            "works_in": [],
            "housing_dream": {},
            "accepts_advisor_contact": False,
        }
        # False is a meaningful value
        self.assertEqual(_count_profile_fields(profile), 1)


class TestSchemaValidation(unittest.TestCase):
    """Agent 2 validates extracted data against lead_profile.schema.json."""

    def test_valid_profile_no_errors(self):
        profile = {
            "lead_code": "LEAD-00001",
            "campaign_id": "CAMP-001",
            "project_origin": "Samán · VIS · Ricaurte",
            "interest_origin_project": True,
            "desired_features": ["balcón", "parque"],
            "consent": True,
            "profile_complete": False,
            "lives_in": "Bogotá",
            "works_in": "Chía",
            "household_size": 3,
            "purchase_purpose": "Independizarme",
        }
        errors = _validate_against_schema(profile, SCHEMA)
        self.assertEqual(errors, [])

    def test_missing_required_field(self):
        profile = {
            "lead_code": "LEAD-00001",
            "project_origin": "Samán",
            # missing: campaign_id, interest_origin_project, desired_features,
            #          consent, profile_complete
        }
        errors = _validate_against_schema(profile, SCHEMA)
        missing = [e for e in errors if "requerido" in e]
        self.assertGreaterEqual(len(missing), 1)

    def test_additional_property_rejected(self):
        profile = {
            "lead_code": "LEAD-00001",
            "campaign_id": "CAMP-001",
            "project_origin": "Samán",
            "interest_origin_project": True,
            "desired_features": [],
            "consent": True,
            "profile_complete": False,
            "gender": "male",  # not allowed by schema
        }
        errors = _validate_against_schema(profile, SCHEMA)
        self.assertTrue(any("no permitido" in e for e in errors))

    def test_enum_validation_purchase_horizon(self):
        profile = {
            "lead_code": "LEAD-00001",
            "campaign_id": "CAMP-001",
            "project_origin": "Samán",
            "interest_origin_project": True,
            "desired_features": [],
            "consent": True,
            "profile_complete": False,
            "purchase_horizon": "En una semana",  # invalid enum
        }
        errors = _validate_against_schema(profile, SCHEMA)
        self.assertTrue(any("no está en" in e for e in errors))

    def test_max_length_validation(self):
        profile = {
            "lead_code": "LEAD-00001",
            "campaign_id": "CAMP-001",
            "project_origin": "Samán",
            "interest_origin_project": True,
            "desired_features": [],
            "consent": True,
            "profile_complete": False,
            "housing_dream": "A" * 1001,  # maxLength is 1000
        }
        errors = _validate_against_schema(profile, SCHEMA)
        self.assertTrue(any("excede" in e and "1000" in e for e in errors))

    def test_lead_code_pattern(self):
        profile = {
            "lead_code": "INVALID-CODE",  # should match ^LEAD-[0-9]{5,}$
            "campaign_id": "CAMP-001",
            "project_origin": "Samán",
            "interest_origin_project": True,
            "desired_features": [],
            "consent": True,
            "profile_complete": False,
        }
        errors = _validate_against_schema(profile, SCHEMA)
        self.assertTrue(any("patrón" in e for e in errors))

    def test_score_range_validation(self):
        profile = {
            "lead_code": "LEAD-00001",
            "campaign_id": "CAMP-001",
            "project_origin": "Samán",
            "interest_origin_project": True,
            "desired_features": [],
            "consent": True,
            "profile_complete": False,
            "propensity_score": 150,  # max is 100
        }
        errors = _validate_against_schema(profile, SCHEMA)
        self.assertTrue(any("mayor que máximo" in e for e in errors))


class TestExtractionSchema(unittest.TestCase):
    """The extraction schema for Agent 2 covers all expected fields."""

    def test_extractable_fields_are_subset_of_schema(self):
        """Every EXTRACTABLE_FIELDS entry must exist in the main schema."""
        schema_props = set(SCHEMA.get("properties", {}).keys())
        for field in EXTRACTABLE_FIELDS:
            self.assertIn(field, schema_props, f"Campo '{field}' no está en el schema")

    def test_extractable_fields_are_meaningful(self):
        """EXTRACTABLE_FIELDS should not include attribution-only fields."""
        attribution_fields = {
            "lead_code", "customer_name", "telegram_chat_id", "channel",
            "campaign_id", "adset_id", "ad_id", "form_id",
            "utm_source", "utm_medium", "utm_campaign", "project_origin",
            "consent", "affiliation_type", "bedrooms", "max_monthly_payment",
            "household_income",
        }
        overlap = EXTRACTABLE_FIELDS & attribution_fields
        # interest_origin_project is extractable from conversation
        # project_origin comes from campaign attribution but may be confirmed in conversation
        allowed_overlap = {"interest_origin_project", "purchase_horizon",
                           "savings_range", "household_size"}
        unexpected = overlap - allowed_overlap
        self.assertEqual(
            unexpected, set(),
            f"Campos extractables inesperados (vienen de atribución): {unexpected}",
        )


class TestAnalyzePipeline(unittest.TestCase):
    """Agent 2's analyze_profile pipeline without hitting Gemini."""

    def test_analyze_without_history_returns_pending(self):
        """When there's no history and no profile, return PROFILE_PENDING."""
        from agents.analista_perfilamiento import analyze_profile

        result = analyze_profile(
            lead_id="LEAD-00001",
            channel="test",
            customer_name="Test User",
            project_origin="Samán · VIS · Ricaurte",
            campaign_id="CAMP-TEST",
            history="",
            profile={},
            force=False,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["crm_status"], "PROFILE_PENDING")
        self.assertIsNone(result["gemini_source"])

    def test_analyze_with_force_and_partial_profile(self):
        """Even without history, force=True should compute scoring on current profile."""
        from agents.analista_perfilamiento import analyze_profile

        profile = {
            "lives_in": "Bogotá",
            "works_in": "Chía",
            "purchase_purpose": "Inversión",
            "purchase_horizon": "En los próximos 6 meses",
            "interest_origin_project": True,
            "accepts_advisor_contact": True,
        }
        result = analyze_profile(
            lead_id="LEAD-00002",
            channel="test",
            customer_name="Test User 2",
            project_origin="Samán · VIS · Ricaurte",
            campaign_id="CAMP-TEST",
            history="",
            profile=profile,
            force=True,
        )
        self.assertTrue(result["ok"])
        self.assertIn("scoring", result)
        self.assertIn("diagnosis", result)
        self.assertGreaterEqual(result["scoring"]["propensity_score"], 0)

    def test_analyze_with_history_fallback_no_api_key(self):
        """Without GEMINI_API_KEY, analysis should fallback gracefully."""
        from agents.analista_perfilamiento import analyze_profile

        # Ensure GEMINI_API_KEY is not set
        with patch.dict(os.environ, {}, clear=True):
            profile = {"lives_in": "Bogotá"}
            result = analyze_profile(
                lead_id="LEAD-00003",
                channel="test",
                customer_name="Test User 3",
                project_origin="Samán · VIS · Ricaurte",
                campaign_id="CAMP-TEST",
                history="VIVI: Hola, ¿en qué municipio vives?\nUSUARIO: Vivo en Bogotá",
                profile=profile,
                force=False,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["gemini_source"], "FALLBACK_SIN_EXTRACCION")
        # Should still have scoring based on the profile we had
        self.assertIn("scoring", result)

    def test_crm_status_error_for_nonexistent_lead(self):
        """Saving a profile for a non-existent lead should fail gracefully."""
        from agents.analista_perfilamiento import analyze_profile

        with patch.dict(os.environ, {}, clear=True):
            result = analyze_profile(
                lead_id="LEAD-NONEXISTENT",
                channel="test",
                customer_name="Ghost",
                project_origin="Test Project",
                campaign_id="CAMP-TEST",
                history="",
                profile={},
                force=True,
            )
        self.assertTrue(result["ok"])
        # Should be an error since the lead doesn't exist in DB
        self.assertEqual(result["crm_status"], "ERROR")


class TestAnalyzeProfileIntegration(unittest.TestCase):
    """Integration checks for analyze_profile — requires DB init."""

    @classmethod
    def setUpClass(cls):
        from lead_service import init_db
        init_db()
        from make_service import load_local_env
        load_local_env()

    def test_diagnosis_consistency(self):
        """Scoring and diagnosis should be consistent for a given profile."""
        from agents.analista_perfilamiento import analyze_profile
        from profiling_service import calculate_propensity, build_diagnosis

        profile = {
            "interest_origin_project": True,
            "purchase_purpose": "Primera vivienda",
            "lives_in": "Bogotá",
            "works_in": "Bogotá",
            "household_size": 3,
            "housing_dream": "Apartamento de 3 alcobas con balcón",
            "desired_features": ["balcón", "parque", "3 alcobas"],
            "purchase_horizon": "En los próximos 6 meses",
            "savings_range": "Entre $3 y $10 millones",
            "accepts_advisor_contact": True,
            "accepts_appointment": True,
        }
        with patch.dict(os.environ, {}, clear=True):
            result = analyze_profile(
                lead_id="LEAD-INTEGRATION-01",
                channel="test",
                customer_name="Integration Test",
                project_origin="Samán · VIS · Ricaurte",
                campaign_id="CAMP-INTEGRATION",
                history="",
                profile=profile,
                force=True,
            )
        # Recalculate to verify consistency
        expected_scoring = calculate_propensity(result["profile"])
        expected_diagnosis = build_diagnosis(result["profile"], expected_scoring)

        self.assertEqual(
            result["scoring"]["propensity_score"],
            expected_scoring["propensity_score"],
        )
        self.assertIn("Propensión", result["diagnosis"])


if __name__ == "__main__":
    unittest.main()
