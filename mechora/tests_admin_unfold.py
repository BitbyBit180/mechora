"""
Comprehensive Test Suite for MECHORA Administrator Authentication & Django Unfold Management System.

Tests:
1. Superuser authentication and Unfold dashboard rendering.
2. Invalid credential handling and rejection.
3. Standard user (/admin/ access denied).
4. Staff administrator with granular permission enforcement.
5. Secure session logout and subsequent route protection.
6. Real-time KPI metrics and dashboard callback accuracy.
7. Database integrity and registered model management.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from machines.models import Machine
from manuals.models import Manual
from rag.models import RAGQueryLog, RAGDocumentChunk
from mechora.admin_dashboard import dashboard_callback

User = get_user_model()


class MechoraAdminAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = "StrongAdminPass123!"

        # Superuser
        self.superuser = User.objects.create_superuser(
            username="mechora_admin",
            email="admin@mechora.industrial",
            password=self.password,
            first_name="Plant",
            last_name="Director",
        )

        # Standard User (Engineer / Non-staff)
        self.engineer_user = User.objects.create_user(
            username="engineer_jane",
            email="jane@mechora.industrial",
            password=self.password,
            is_staff=False,
            is_superuser=False,
        )

        # Staff Administrator (Limited permissions)
        self.staff_admin = User.objects.create_user(
            username="staff_supervisor",
            email="supervisor@mechora.industrial",
            password=self.password,
            is_staff=True,
            is_superuser=False,
        )

        # Assign only machine permissions to staff administrator
        machine_ct = ContentType.objects.get_for_model(Machine)
        view_machine_perm = Permission.objects.get(
            content_type=machine_ct, codename="view_machine"
        )
        self.staff_admin.user_permissions.add(view_machine_perm)

        # Seed test machines and manuals
        self.machine = Machine.objects.create(
            machine_id="M-TEST-01",
            model="TEST-100",
            machine_name="Test Pneumatic Press",
            description="Unit for automated validation.",
        )
        self.manual = Manual.objects.create(
            document_id="TEST-DOC-01",
            machine=self.machine,
            document_name="Test Operations Guide",
            revision="1.0",
            pdf_filename="test_guide.pdf",
            ingestion_status="completed",
        )
        self.rag_log = RAGQueryLog.objects.create(
            machine=self.machine,
            question="What is the test parameter?",
            answer="Test parameter is 42.",
            status="ANSWERED",
            citations=[{"page": 1, "passage": "Parameter 42"}],
        )

    def test_01_superuser_login_and_unfold_dashboard(self):
        """TEST 1: Superuser authenticates through /admin/ and Unfold UI renders."""
        login_success = self.client.login(
            username=self.superuser.username,
            password=self.password,
        )
        self.assertTrue(login_success, "Superuser failed to authenticate via Django auth.")

        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # Verify Unfold branding and header presence
        self.assertIn("MECHORA", content)
        self.assertIn("Industrial Management System", content)
        self.assertIn("Registered Machines", content)
        self.assertIn("Technical Manuals", content)

    def test_02_invalid_credentials_denied(self):
        """TEST 2: Invalid password or non-existent user must be rejected."""
        login_success = self.client.login(
            username=self.superuser.username,
            password="WrongPassword999!",
        )
        self.assertFalse(login_success, "Invalid credentials should be rejected.")

        # Admin index without auth should redirect to login
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_03_normal_user_denied_admin_access(self):
        """TEST 3: Non-staff user cannot access Django Administration."""
        # Non-staff user logs in
        login_success = self.client.login(
            username=self.engineer_user.username,
            password=self.password,
        )
        self.assertTrue(login_success)

        # Attempt to access /admin/
        response = self.client.get(reverse("admin:index"))
        # Non-staff users are redirected to login with next=/admin/ or denied
        if response.status_code == 302:
            self.assertIn("/admin/login/", response.url)
        else:
            # If Django displays the 'not authorized' login prompt
            content = response.content.decode("utf-8")
            self.assertIn("not authorized", content.lower())

    def test_04_staff_administrator_granular_permissions(self):
        """TEST 4: Staff administrator can only access authorized models."""
        self.client.login(
            username=self.staff_admin.username,
            password=self.password,
        )

        # Authorized model: Machine
        machine_resp = self.client.get(reverse("admin:machines_machine_changelist"))
        self.assertEqual(
            machine_resp.status_code, 200, "Staff admin should have access to Machine changelist."
        )

        # Unauthorized model: Manual (no view_manual permission)
        manual_resp = self.client.get(reverse("admin:manuals_manual_changelist"))
        self.assertEqual(
            manual_resp.status_code, 403, "Staff admin without view_manual permission must be forbidden."
        )

        # Unauthorized model: User (no view_user permission)
        user_resp = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(
            user_resp.status_code, 403, "Staff admin without view_user permission must be forbidden."
        )

    def test_05_admin_logout_and_session_termination(self):
        """TEST 5: Admin logout terminates session and protects administration routes."""
        self.client.login(
            username=self.superuser.username,
            password=self.password,
        )
        # Verify authenticated access
        resp_before = self.client.get(reverse("admin:index"))
        self.assertEqual(resp_before.status_code, 200)

        # Execute logout
        logout_resp = self.client.post(reverse("admin:logout"))
        self.assertIn(logout_resp.status_code, (200, 302))

        # Subsequent request must require re-authentication
        resp_after = self.client.get(reverse("admin:index"))
        self.assertEqual(resp_after.status_code, 302)
        self.assertIn("/admin/login/", resp_after.url)

    def test_06_dashboard_callback_live_metrics(self):
        """TEST 6: Dashboard callback returns accurate live database metrics."""
        from django.test import RequestFactory

        rf = RequestFactory()
        req = rf.get("/admin/")
        req.user = self.superuser

        context = dashboard_callback(req, {})
        self.assertIn("kpi_metrics", context)

        metrics = {m["title"]: m["value"] for m in context["kpi_metrics"]}
        self.assertGreaterEqual(metrics["Registered Machines"], 1)
        self.assertGreaterEqual(metrics["Technical Manuals"], 1)
        self.assertGreaterEqual(metrics["System Users"], 3)
        self.assertGreaterEqual(metrics["Staff Administrators"], 2)

    def test_07_database_integrity_and_model_admin(self):
        """TEST 7: Model administration changelists work with Unfold configuration."""
        self.client.login(
            username=self.superuser.username,
            password=self.password,
        )

        # Test changelists
        endpoints = [
            reverse("admin:machines_machine_changelist"),
            reverse("admin:manuals_manual_changelist"),
            reverse("admin:rag_ragquerylog_changelist"),
            reverse("admin:rag_ragdocumentchunk_changelist"),
            reverse("admin:auth_user_changelist"),
            reverse("admin:auth_group_changelist"),
        ]
        for url in endpoints:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Endpoint {url} failed to load.")

        # Verify database records persist correctly
        self.assertEqual(Machine.objects.filter(machine_id="M-TEST-01").count(), 1)
        self.assertEqual(Manual.objects.filter(document_id="TEST-DOC-01").count(), 1)
        self.assertEqual(RAGQueryLog.objects.filter(machine=self.machine).count(), 1)
