import unittest
from web_extractor import extract_tables_from_html, extract_json_ld_schemas, extract_rss_atom_feed, extract_structured_web

class TestWebExtractorContract(unittest.TestCase):
    def test_extract_tables_from_html(self):
        html_code = """
        <table>
          <tr><th>Lenguaje</th><th>Tipo</th><th>Uso</th></tr>
          <tr><td>Python</td><td>Dinámico</td><td>IA y Backend</td></tr>
          <tr><td>Rust</td><td>Estático</td><td>Sistemas y Rendimiento</td></tr>
        </table>
        """
        tables = extract_tables_from_html(html_code)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["headers"], ["Lenguaje", "Tipo", "Uso"])
        self.assertEqual(len(tables[0]["rows"]), 2)
        self.assertIn("| Python | Dinámico | IA y Backend |", tables[0]["markdown"])

    def test_extract_json_ld_schemas(self):
        html_code = """
        <html><head>
          <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "headline": "Arquitectura de IA 2026",
            "author": "Jhon Grimm"
          }
          </script>
        </head></html>
        """
        schemas = extract_json_ld_schemas(html_code)
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["@type"], "TechArticle")
        self.assertEqual(schemas[0]["author"], "Jhon Grimm")

    def test_extract_rss_feed(self):
        rss_code = """
        <rss version="2.0">
          <channel>
            <title>Noticias Tecnológicas</title>
            <item>
              <title>Lanzamiento Python 3.13</title>
              <link>https://python.org/news/313</link>
              <description>Novedades sobre el JIT y GIL libre.</description>
              <pubDate>Mon, 27 Oct 2026 12:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>
        """
        res = extract_rss_atom_feed(rss_code)
        self.assertTrue(res["ok"])
        self.assertEqual(res["feed_title"], "Noticias Tecnológicas")
        self.assertEqual(res["items_count"], 1)
        self.assertEqual(res["items"][0]["title"], "Lanzamiento Python 3.13")

    def test_extract_structured_web_unified(self):
        content = "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>"
        res = extract_structured_web(content)
        self.assertTrue(res["ok"])
        self.assertEqual(res["tables_count"], 1)

if __name__ == "__main__":
    unittest.main()
