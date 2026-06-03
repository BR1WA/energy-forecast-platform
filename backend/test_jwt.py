from jose import jwt
secret = "super-secret-key-change-in-production-2024"
token = jwt.encode({"sub": 1, "role": "admin", "type": "access"}, secret, algorithm="HS256")
try:
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    print(decoded)
except Exception as e:
    print("Error:", e)
