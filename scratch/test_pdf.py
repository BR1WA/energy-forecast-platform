import requests

def test_pdf():
    base_url = "http://localhost:8000/api/v1"
    
    # 1. Login
    login_data = {
        "email": "admin@energyforecast.com",
        "password": "admin123"
    }
    response = requests.post(f"{base_url}/auth/login", json=login_data)
    if response.status_code != 200:
        print("Login failed:", response.text)
        return
    
    token = response.json().get("access_token")
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # 2. Call PDF export
    resp = requests.get(f"{base_url}/analytics/report/pdf", headers=headers)
    print("PDF Response status:", resp.status_code)
    if resp.status_code == 200:
        content_type = resp.headers.get("Content-Type")
        print("Content Type:", content_type)
        if "application/pdf" in content_type:
            print("SUCCESS: PDF generated successfully! Byte length:", len(resp.content))
        else:
            print("FAILED: Content-Type is not application/pdf")
    else:
        print("FAILED to export PDF:", resp.text)

if __name__ == "__main__":
    test_pdf()
