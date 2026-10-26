import unittest
import zipfile
import io
import json
import zip_service

class TestZipServiceContract(unittest.TestCase):
    def test_backup_zip(self):
        data = zip_service.create_backup_zip()
        self.assertIsInstance(data, bytes)
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            names = z.namelist()
            self.assertIn("manifest.json", names)
            self.assertIn("README_BACKUP.txt", names)
            manifest = json.loads(z.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["capabilities_verified"], "41/41")

    def test_code_bundle_zip(self):
        files = {"main.py": "print('hello')", "config.json": "{}"}
        data = zip_service.create_code_bundle_zip(files, "AppTest")
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            self.assertIn("main.py", z.namelist())
            self.assertIn("config.json", z.namelist())

if __name__ == "__main__":
    unittest.main()
