import unittest
import chart_service

class TestChartServiceContract(unittest.TestCase):
    def test_metrics_chart_generation(self):
        png = chart_service.create_metrics_chart("Prueba", ["Módulo 1", "Módulo 2"], [85.5, 99.2])
        self.assertIsInstance(png, bytes)
        self.assertGreater(len(png), 500)
        # PNG signature check: \x89PNG\r\n\x1a\n
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_roi_comparison_chart(self):
        png = chart_service.create_roi_comparison_chart("Sistema ERP", 3000.0, 750.0)
        self.assertIsInstance(png, bytes)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

if __name__ == "__main__":
    unittest.main()
