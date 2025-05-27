import requests

def generate_receipt(user_data, stock_data):
    payload = {
        "user_email": user_data["email"],
        "stock_name": stock_data["name"],
        "quantity": stock_data["quantity"],
        "total": stock_data["total"]
    }

    response = requests.post("https://oi9ys5pgnd.execute-api.us-east-1.amazonaws.com/Prod/generate-receipt", json=payload)
    if response.ok:
        return response.json()["receipt_url"]
    else:
        raise Exception("Error generando la boleta")
