from main import build_stocks_query

def test_price_range():
    # Prueba que el filtro de precio se construye correctamente con rango '10-50'
    query = build_stocks_query(price="10-50")
    assert "price" in query
    assert query["price"]["$gte"] == 10.0
    assert query["price"]["$lte"] == 50.0

def test_symbol_prefix():
    # Prueba que se construye una expresión regex correcta para el símbolo
    query = build_stocks_query(symbol="AAPL")
    assert "symbol" in query
    assert query["symbol"] == {"$regex": "^AAPL", "$options": "i"}
