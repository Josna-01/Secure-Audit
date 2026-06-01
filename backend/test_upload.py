import requests

url = "http://localhost:8000/evidence/upload"
payload = {'case_id': 'dd2099c9-11c4-436b-a853-a2aba819e019', 'evidence_type': 'Image'}
files = [('file', ('test.jpg', b'fakeimagecontent', 'image/jpeg'))]
headers = {}
response = requests.request("POST", url, headers=headers, data=payload, files=files)
print(response.status_code)
print(response.text)
