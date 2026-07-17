import unittest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.services.auth_service import hash_password, create_access_token

from sqlalchemy.pool import StaticPool
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

class TestWebSocketAuth(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        self.user_pass = "userpassword"
        self.user1 = User(
            email="user1@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="User One",
            role="user",
            is_active=True,
        )
        self.user2 = User(
            email="user2@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="User Two",
            role="user",
            is_active=True,
        )
        self.db.add(self.user1)
        self.db.add(self.user2)
        self.db.commit()

        self.token1 = create_access_token({"sub": str(self.user1.id)})
        self.token2 = create_access_token({"sub": str(self.user2.id)})

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]

    def test_alerts_ws_no_token(self):
        # Connecting with no token should fail
        with client.websocket_connect(f"/api/v1/alerts/ws/{self.user1.id}") as websocket:
            with self.assertRaises(WebSocketDisconnect) as context:
                websocket.receive_text()
            self.assertEqual(context.exception.code, 1008)

    def test_alerts_ws_invalid_token(self):
        with client.websocket_connect(f"/api/v1/alerts/ws/{self.user1.id}?token=invalid") as websocket:
            with self.assertRaises(WebSocketDisconnect) as context:
                websocket.receive_text()
            self.assertEqual(context.exception.code, 1008)

    def test_alerts_ws_mismatched_client_id(self):
        # User 1 tries to connect with User 2's client_id
        with client.websocket_connect(f"/api/v1/alerts/ws/{self.user2.id}?token={self.token1}") as websocket:
            with self.assertRaises(WebSocketDisconnect) as context:
                websocket.receive_text()
            self.assertEqual(context.exception.code, 1008)

    def test_alerts_ws_success(self):
        # Correct token and matching client_id
        with client.websocket_connect(f"/api/v1/alerts/ws/{self.user1.id}?token={self.token1}") as websocket:
            pass

    def test_smart_meter_ws_no_token(self):
        with client.websocket_connect("/api/v1/forecast/smart-meter/live-ws") as websocket:
            with self.assertRaises(WebSocketDisconnect) as context:
                websocket.receive_json()
            self.assertEqual(context.exception.code, 1008)

    def test_smart_meter_ws_success(self):
        with client.websocket_connect(f"/api/v1/forecast/smart-meter/live-ws?token={self.token1}") as websocket:
            data = websocket.receive_json()
            self.assertIn("voltage", data)
            self.assertIn("predictions", data)
