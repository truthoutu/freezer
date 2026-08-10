import unittest
from pathlib import Path
import pandas as pd
from cleaner import CleanerPipeline

class TestCleanerPipeline(unittest.TestCase):
    def setUp(self):
        self.cleaner = CleanerPipeline(Path("dummy.json"))

    def test_ip_address_rejection(self):
        """Verify that IPv4 addresses like 45.38.107.97 are explicitly rejected."""
        phone, country = self.cleaner.normalize_phone_and_detect_country("45.38.107.97")
        self.assertEqual(phone, "")
        self.assertIn("Invalid", country)

        phone_valid, country_valid = self.cleaner.normalize_phone_and_detect_country("+49 170 98765432")
        self.assertEqual(phone_valid, "+49 170 98765432")
        self.assertEqual(country_valid, "Germany")

    def test_phone_normalization(self):
        """Test international phone normalization for US, AU, CH, DE."""
        # US / CA
        p_us, c_us = self.cleaner.normalize_phone_and_detect_country("2125550199")
        self.assertEqual(p_us, "+1 (212) 555-0199")
        self.assertEqual(c_us, "United States / Canada")

        # Australia
        p_au, c_au = self.cleaner.normalize_phone_and_detect_country("+61 412 345 678")
        self.assertEqual(p_au, "+61 4 1234 5678")
        self.assertEqual(c_au, "Australia")

        # Switzerland
        p_ch, c_ch = self.cleaner.normalize_phone_and_detect_country("+41 79 123 45 67")
        self.assertEqual(p_ch, "+41 79 123 4567")
        self.assertEqual(c_ch, "Switzerland")

    def test_gender_inference(self):
        """Test German and English female gender heuristics."""
        self.assertIn("Female", self.cleaner.infer_gender("Sarah Jenkins"))
        self.assertEqual(self.cleaner.infer_gender("Anna Müller", "Ärztin"), "Female")
        self.assertEqual(self.cleaner.infer_gender("Sabine Weber", "Krankenschwester"), "Female")

    def test_deduplication(self):
        """Test deduplication by phone number."""
        self.cleaner.df = pd.DataFrame([
            {"name": "Jane Doe", "phone": "2125550199", "occupation_context": "Nurse"},
            {"name": "Duplicate Jane", "phone": "+1 (212) 555-0199", "occupation_context": "Nurse"}
        ])
        cleaned = self.cleaner.clean()
        self.assertEqual(len(cleaned), 1)

if __name__ == "__main__":
    unittest.main()
