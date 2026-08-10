import unittest
import json
from server import app

class TestServerAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_health_check(self):
        """Test GET /api/health endpoint status."""
        response = self.app.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "healthy")
        self.assertIn("rust_engine", data)
        self.assertIn("proxies_configured", data)

    def test_harvest_endpoint_validation(self):
        """Test POST /api/harvest with input bounds validation."""
        response = self.app.post(
            '/api/harvest',
            data=json.dumps({"country": "Germany", "occupation": "Nurse", "gender": "Female", "limit": 5}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertLessEqual(data["count"], 5)

if __name__ == "__main__":
    unittest.main()
