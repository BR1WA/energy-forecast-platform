import unittest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User, Subscription
from app.services.auth_service import hash_password, create_access_token
from app.entitlements import Tier

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
from sqlalchemy.pool import StaticPool
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

class TestBillingAndEntitlements(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        # Seed data
        self.user_pass = "userpassword"
        self.user = User(
            email="billinguser@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="Billing User",
            role="viewer",
            subscription_tier=Tier.free.name,
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()

        # Generate tokens
        self.token = create_access_token({"sub": str(self.user.id)})
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]

    def test_get_entitlements(self):
        res = client.get("/api/v1/billing/entitlements", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["subscription_tier"], "free")
        self.assertIsInstance(data["features"], list)

    def test_get_subscription_initially_none(self):
        res = client.get("/api/v1/billing/subscription", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.json())

    def test_checkout_and_confirm_flow(self):
        # 1. Start checkout for Pro tier
        checkout_res = client.post(
            "/api/v1/billing/checkout",
            json={"tier": "pro"},
            headers=self.headers
        )
        self.assertEqual(checkout_res.status_code, 200)
        checkout_data = checkout_res.json()
        self.assertIn("checkout_ref", checkout_data)
        self.assertEqual(checkout_data["tier"], "pro")
        self.assertEqual(checkout_data["status"], "pending")

        ref = checkout_data["checkout_ref"]

        # User's tier should still be free (not confirmed yet)
        user_db = self.db.query(User).filter(User.id == self.user.id).first()
        self.assertEqual(user_db.subscription_tier, "free")

        # 2. Confirm checkout
        confirm_res = client.post(
            "/api/v1/billing/checkout/confirm",
            json={"checkout_ref": ref},
            headers=self.headers
        )
        self.assertEqual(confirm_res.status_code, 200)
        
        # User's tier should now be pro
        self.assertEqual(confirm_res.json()["subscription_tier"], "pro")
        
        # Verify active subscription
        sub_res = client.get("/api/v1/billing/subscription", headers=self.headers)
        self.assertEqual(sub_res.status_code, 200)
        sub_data = sub_res.json()
        self.assertIsNotNone(sub_data)
        self.assertEqual(sub_data["tier"], "pro")
        self.assertEqual(sub_data["status"], "active")

    def test_checkout_invalid_tier_fails(self):
        res = client.post(
            "/api/v1/billing/checkout",
            json={"tier": "free"},
            headers=self.headers
        )
        self.assertEqual(res.status_code, 422)  # Pydantic validation error since Free is not in PaidTier enum

    def test_cancel_subscription(self):
        # Setup active subscription first
        from app.services import billing_service
        billing_service.grant(self.db, self.user, Tier.pro)
        self.db.commit()

        # Verify it is active
        user_db = self.db.query(User).filter(User.id == self.user.id).first()
        self.assertEqual(user_db.subscription_tier, "pro")

        # Cancel
        res = client.post("/api/v1/billing/cancel", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["subscription_tier"], "free")

        # Check DB
        self.db.refresh(self.user)
        self.assertEqual(self.user.subscription_tier, "free")
