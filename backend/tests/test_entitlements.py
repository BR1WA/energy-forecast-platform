import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.services.auth_service import hash_password, create_access_token
from app.entitlements import Tier

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


class TestEntitlements(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        # Create all tables
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        # Seed data
        self.admin_pass = "adminpassword"
        self.user_pass = "userpassword"

        # Create admin user
        self.admin_user = User(
            email="admin@example.com",
            password_hash=hash_password(self.admin_pass),
            full_name="Admin User",
            role="admin",
            subscription_tier=Tier.enterprise.name,
            is_active=True,
        )
        # Create normal free user
        self.free_user = User(
            email="free@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="Free User",
            role="viewer",
            subscription_tier=Tier.free.name,
            is_active=True,
        )
        self.db.add(self.admin_user)
        self.db.add(self.free_user)
        self.db.commit()

        # Generate tokens
        self.admin_token = create_access_token({"sub": str(self.admin_user.id)})
        self.free_token = create_access_token({"sub": str(self.free_user.id)})

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.free_headers = {"Authorization": f"Bearer {self.free_token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]

    def test_free_user_access_denied_on_pro_and_enterprise(self):
        # Free user -> 403 on analytics summary (pro feature)
        res = client.get("/api/v1/analytics/summary", headers=self.free_headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("This feature requires the 'pro' subscription tier or higher", res.json()["detail"])

        # Free user -> 403 on PDF report (pro feature)
        res = client.get("/api/v1/analytics/report/pdf", headers=self.free_headers)
        self.assertEqual(res.status_code, 403)

        # Free user -> 403 on multi-site (enterprise feature)
        res = client.get("/api/v1/multi-site", headers=self.free_headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("This feature requires the 'enterprise' subscription tier or higher", res.json()["detail"])

    def test_self_grant_upgrades_blocked(self):
        # User tries to self-upgrade via POST /api/v1/auth/subscription
        # Upgrades to 'pro' or 'enterprise' must return 403.
        res = client.post(
            "/api/v1/auth/subscription",
            headers=self.free_headers,
            json={"subscription_tier": "pro"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Upgrading to a paid tier is not available through self-service", res.json()["detail"])

        # However, a downgrade (cancellation) to 'free' is allowed (no-op here since they are already free)
        res = client.post(
            "/api/v1/auth/subscription",
            headers=self.free_headers,
            json={"subscription_tier": "free"},
        )
        self.assertEqual(res.status_code, 200)

    def test_simulated_checkout_upgrade_flow(self):
        # 1. Start checkout for 'pro' plan (which is simulated, status = pending)
        res = client.post(
            "/api/v1/billing/checkout",
            headers=self.free_headers,
            json={"tier": "pro"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("checkout_ref", data)
        self.assertEqual(data["tier"], "pro")
        self.assertEqual(data["status"], "pending")
        checkout_ref = data["checkout_ref"]

        # Before confirm, user tier is still free
        res = client.get("/api/v1/billing/entitlements", headers=self.free_headers)
        self.assertEqual(res.json()["subscription_tier"], "free")

        # 2. Confirm checkout (simulating webhook execution)
        res = client.post(
            "/api/v1/billing/checkout/confirm",
            headers=self.free_headers,
            json={"checkout_ref": checkout_ref},
        )
        self.assertEqual(res.status_code, 200)

        # After confirm, user should be 'pro'
        res = client.get("/api/v1/billing/entitlements", headers=self.free_headers)
        entitlements = res.json()
        self.assertEqual(entitlements["subscription_tier"], "pro")
        self.assertIn("analytics_summary", entitlements["features"])
        self.assertIn("pdf_export", entitlements["features"])
        self.assertNotIn("multi_site", entitlements["features"])

        # Update headers with new session (or check the db user directly)
        self.db.expire_all()
        pro_user = self.db.query(User).filter(User.id == self.free_user.id).first()
        self.assertEqual(pro_user.subscription_tier, "pro")

        # Pro user passes pro feature checks
        res = client.get("/api/v1/analytics/summary", headers=self.free_headers)
        self.assertEqual(res.status_code, 200)
        # Heatmap data must be gated (empty) for Pro users
        self.assertEqual(res.json()["heatmap_data"], [])

        # Admin (Enterprise) user should get non-empty heatmap data
        res_admin = client.get("/api/v1/analytics/summary", headers=self.admin_headers)
        self.assertEqual(res_admin.status_code, 200)
        self.assertNotEqual(res_admin.json()["heatmap_data"], [])

        # Pro user still blocked from enterprise feature (multi-site)
        res = client.get("/api/v1/multi-site", headers=self.free_headers)
        self.assertEqual(res.status_code, 403)

    def test_admin_grant_changes_entitlement(self):
        # Admin upgrades free user to enterprise via PUT /api/v1/admin/users/{id}
        res = client.put(
            f"/api/v1/admin/users/{self.free_user.id}",
            headers=self.admin_headers,
            json={"subscription_tier": "enterprise"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["subscription_tier"], "enterprise")

        # Verify free user can now access enterprise multi-site
        res = client.get("/api/v1/multi-site", headers=self.free_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("data", res.json())


if __name__ == "__main__":
    unittest.main()
