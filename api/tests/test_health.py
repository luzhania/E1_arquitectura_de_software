import unittest
from main import build_stocks_query   # Asegúrate de que main.py esté en tu PYTHONPATH

class TestBuildStocksQuery(unittest.TestCase):

    def test_price_range(self):
        """
        Debe construir correctamente el filtro de precio
        cuando se pasa un rango '10-50'.
        """
        query = build_stocks_query(price="10-50")
        self.assertIn("price", query)
        self.assertEqual(query["price"]["$gte"], 10.0)
        self.assertEqual(query["price"]["$lte"], 50.0)

    def test_symbol_prefix(self):
        """
        Debe crear una expresión regular que busque por
        prefijo de símbolo (por ejemplo 'AAPL').
        """
        query = build_stocks_query(symbol="AAPL")
        self.assertIn("symbol", query)
        expected_regex = {"$regex": "^AAPL", "$options": "i"}
        self.assertEqual(query["symbol"], expected_regex)

if __name__ == "__main__":
    unittest.main()
