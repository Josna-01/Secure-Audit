import requests, sys
sys.path.append('.')
from app import create_jwt

token = create_jwt(
    user_id="6247536e-4fe0-45f1-b87e-ebe51c96f34d",
    email="ancilla.souza2005@gmail.com",
    role="Admin",
    name="Ancilla"
)

headers = {"Authorization": f"Bearer {token}"}
r = requests.get("http://127.0.0.1:8000/blockchain/dashboard", headers=headers)
print("Status code:", r.status_code)
print("Response:", r.text)
