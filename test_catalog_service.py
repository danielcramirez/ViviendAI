import json
import tempfile
import unittest
from pathlib import Path

from catalog_service import load_catalog


class CatalogServiceTests(unittest.TestCase):
    def test_groups_projects_and_scales_exported_prices(self):
        rows = [
            {
                "NOMBRE_PROYECTO": "Samán",
                "ETAPA": "ETAPA 1",
                "FEC_OPCION": "1/15/26",
                "FECHA_DESISTIMIENTO": "No",
                "Entidad Financiera compra": "Banco",
                "MEDIO": "Meta",
                "VLR_VIVIENDA": "2,000,000,000,000",
                "RANGO_EDAD": "20 - 35 años",
                "SEGMENTO_POBLACIONAL": "A",
            },
            {
                "NOMBRE_PROYECTO": "Samán",
                "ETAPA": "ETAPA 2",
                "FEC_OPCION": "2/15/26",
                "FECHA_DESISTIMIENTO": "2/20/26",
                "Entidad Financiera compra": "Colsubsidio",
                "MEDIO": "Meta",
                "VLR_VIVIENDA": "2,200,000,000,000",
                "RANGO_EDAD": "20 - 35 años",
                "SEGMENTO_POBLACIONAL": "A",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            project = load_catalog(path)[0]

        self.assertEqual(project["records"], 2)
        self.assertEqual(project["estimated_price_median"], 210_000_000)
        self.assertEqual(project["desistment_rate"], 50.0)
        self.assertEqual(project["stages"], ["ETAPA 1", "ETAPA 2"])


if __name__ == "__main__":
    unittest.main()
