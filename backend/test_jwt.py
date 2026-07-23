import jwt
from app.config import get_settings
settings = get_settings()
secret = settings.JWT_SECRET_KEY
token = jwt.encode({"sub": "1", "role": "admin", "type": "access"}, secret, algorithm="HS256")
try:
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    print(decoded)
except Exception as e:
    print("Error:", e)
