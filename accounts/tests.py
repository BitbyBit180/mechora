"""
Comprehensive Role-Based Access Control & User Management Test Suite for MECHORA.

Validates:
TEST 1: Admin User Creation via Admin Panel
TEST 2: Engineer User Creation and Authentication
TEST 3: Supervisor User Creation and Authentication
TEST 4: Password Validation (Mismatch rejection & Secure hashing)
TEST 5: Password Field Visibility, Width, Styling & Toggle Widget
TEST 6: Role Permissions (Admin vs. Engineer vs. Supervisor)
TEST 7: Unauthorized Access Denial (Engineers and Supervisors blocked from User Management)
TEST 8: Preservation of Existing MECHORA Functionality
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.roles import (
    ROLE_ADMIN,
    ROLE_ENGINEER,
    ROLE_SUPERVISOR,
    assign_user_role,
    ensure_roles_and_permissions,
    get_user_role,
)
from machines.models import Machine
from manuals.models import Manual
from rag.models import RAGQueryLog
from mechora.admin_dashboard import dashboard_callback
from accounts.models import UserProfile

User = get_user_model()


class MechoraRoleBasedUserManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        ensure_roles_and_permissions()

        self.password = "StrongPass#2026!"

        # Superuser account (Highest-level system administrator)
        self.superuser = User.objects.create_superuser(
            username="root_admin",
            email="root@mechora.industrial",
            password=self.password,
            first_name="Root",
            last_name="Administrator",
        )

        # Existing operational records
        self.machine = Machine.objects.create(
            machine_id="M-HP200",
            model="HP-200",
            machine_name="Hydraulic forming press",
            description="High precision forming press.",
        )
        self.manual = Manual.objects.create(
            document_id="HP-OPS-01",
            machine=self.machine,
            document_name="HP200 Operations Manual",
            revision="1.0",
            pdf_filename="HP200_Operations_Rev1_0.pdf",
            ingestion_status="completed",
        )
        self.rag_log = RAGQueryLog.objects.create(
            machine=self.machine,
            question="What is operating pressure?",
            answer="Operating pressure is 210 bar.",
            status="ANSWERED",
            citations=[{"page": 2, "passage": "Operating pressure 210 bar"}],
        )

    def test_01_admin_user_creation(self):
        """TEST 1: Authorized administrator adds a new user with Admin role."""
        self.client.force_login(self.superuser)

        add_url = reverse("admin:auth_user_add")
        user_data = {
            "username": "plant_manager",
            "email": "manager@mechora.industrial",
            "first_name": "Marcus",
            "last_name": "Vance",
            "role": ROLE_ADMIN,
            "is_active": True,
            "password1": "SecureAdmin2026!",
            "password2": "SecureAdmin2026!",
        }

        response = self.client.post(add_url, user_data)
        self.assertIn(response.status_code, (200, 302))

        new_user = User.objects.filter(username="plant_manager").first()
        self.assertIsNotNone(new_user, "Admin user must be saved in the database.")
        self.assertEqual(new_user.email, "manager@mechora.industrial")
        self.assertTrue(new_user.is_staff, "Admin user must have is_staff=True.")
        self.assertFalse(new_user.is_superuser, "Admin user must not be superuser.")
        self.assertEqual(get_user_role(new_user), ROLE_ADMIN)

        # Verify permissions
        self.assertTrue(new_user.has_perm("auth.add_user"))
        self.assertTrue(new_user.has_perm("machines.add_machine"))
        self.assertTrue(new_user.has_perm("manuals.add_manual"))

    def test_02_engineer_user_creation_and_auth(self):
        """TEST 2: Create a new Engineer user and verify immediate authentication."""
        self.client.force_login(self.superuser)

        add_url = reverse("admin:auth_user_add")
        user_data = {
            "username": "eng_roberts",
            "email": "roberts@mechora.industrial",
            "first_name": "Clara",
            "last_name": "Roberts",
            "role": ROLE_ENGINEER,
            "is_active": True,
            "password1": "EngineerPass2026!",
            "password2": "EngineerPass2026!",
        }

        response = self.client.post(add_url, user_data)
        self.assertIn(response.status_code, (200, 302))

        engineer = User.objects.filter(username="eng_roberts").first()
        self.assertIsNotNone(engineer)
        self.assertEqual(get_user_role(engineer), ROLE_ENGINEER)
        self.assertTrue(engineer.is_staff)
        self.assertFalse(engineer.is_superuser)

        # Authenticate with credentials
        self.client.logout()
        login_success = self.client.login(username="eng_roberts", password="EngineerPass2026!")
        self.assertTrue(login_success, "Engineer must be able to authenticate immediately.")

    def test_03_supervisor_user_creation_and_auth(self):
        """TEST 3: Create a new Supervisor user and verify immediate authentication."""
        self.client.force_login(self.superuser)

        add_url = reverse("admin:auth_user_add")
        user_data = {
            "username": "sup_chen",
            "email": "chen@mechora.industrial",
            "first_name": "David",
            "last_name": "Chen",
            "role": ROLE_SUPERVISOR,
            "is_active": True,
            "password1": "SupervisorPass2026!",
            "password2": "SupervisorPass2026!",
        }

        response = self.client.post(add_url, user_data)
        self.assertIn(response.status_code, (200, 302))

        supervisor = User.objects.filter(username="sup_chen").first()
        self.assertIsNotNone(supervisor)
        self.assertEqual(get_user_role(supervisor), ROLE_SUPERVISOR)
        self.assertTrue(supervisor.is_staff)

        # Authenticate with credentials
        self.client.logout()
        login_success = self.client.login(username="sup_chen", password="SupervisorPass2026!")
        self.assertTrue(login_success, "Supervisor must be able to authenticate immediately.")

    def test_04_password_validation_and_secure_hashing(self):
        """TEST 4: Password validation rejects mismatches and stores hashed passwords."""
        self.client.force_login(self.superuser)

        add_url = reverse("admin:auth_user_add")

        # 1. Mismatch rejection
        mismatch_data = {
            "username": "mismatch_test",
            "email": "mismatch@mechora.industrial",
            "first_name": "Test",
            "last_name": "Mismatch",
            "role": ROLE_ENGINEER,
            "is_active": True,
            "password1": "SecurePass1234!",
            "password2": "DifferentPass9999!",
        }
        resp = self.client.post(add_url, mismatch_data)
        self.assertEqual(resp.status_code, 200, "Form must re-render with validation errors.")
        self.assertContains(resp, "The two password fields didn&#x27;t match.")
        self.assertFalse(User.objects.filter(username="mismatch_test").exists())

        # 2. Matching passwords
        matching_data = {
            "username": "matched_user",
            "email": "matched@mechora.industrial",
            "first_name": "Test",
            "last_name": "Matched",
            "role": ROLE_ENGINEER,
            "is_active": True,
            "password1": "SecurePass1234!",
            "password2": "SecurePass1234!",
        }
        resp_valid = self.client.post(add_url, matching_data)
        self.assertIn(resp_valid.status_code, (200, 302))

        user = User.objects.filter(username="matched_user").first()
        self.assertIsNotNone(user)
        # Verify password is not plain text and can be verified
        self.assertNotEqual(user.password, "SecurePass1234!")
        self.assertTrue(user.password.startswith("pbkdf2_"))
        self.assertTrue(user.check_password("SecurePass1234!"))

    def test_05_password_field_visibility_and_toggle(self):
        """TEST 5: Password fields render with Unfold styling, full width, and visibility toggle."""
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("admin:auth_user_add"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")

        # Scoped CSS and JS loaded
        self.assertIn("user_admin.css", content)
        self.assertIn("password_toggle.js", content)

        # Scoped wrappers and toggle buttons for both password fields
        self.assertIn('name="password1"', content)
        self.assertIn('name="password2"', content)
        self.assertIn("mechora-password-wrapper", content)
        self.assertIn("mechora-password-toggle-btn", content)
        self.assertIn("material-symbols-outlined", content)

        # Highlighted password fieldset container
        self.assertIn("mechora-password-section", content)

        # Role dropdown options
        self.assertIn('value="Admin"', content)
        self.assertIn('value="Engineer"', content)
        self.assertIn('value="Supervisor"', content)

    def test_06_role_permissions(self):
        """TEST 6: Verify Admin, Engineer, and Supervisor permissions."""
        admin_user = User.objects.create_user(
            username="admin_tester",
            email="admin_t@mechora.industrial",
            password=self.password,
        )
        assign_user_role(admin_user, ROLE_ADMIN)

        engineer_user = User.objects.create_user(
            username="engineer_tester",
            email="eng_t@mechora.industrial",
            password=self.password,
        )
        assign_user_role(engineer_user, ROLE_ENGINEER)

        supervisor_user = User.objects.create_user(
            username="supervisor_tester",
            email="sup_t@mechora.industrial",
            password=self.password,
        )
        assign_user_role(supervisor_user, ROLE_SUPERVISOR)

        # Admin: has user management and full model management
        self.assertTrue(admin_user.has_perm("auth.add_user"))
        self.assertTrue(admin_user.has_perm("auth.change_user"))
        self.assertTrue(admin_user.has_perm("machines.add_machine"))
        self.assertTrue(admin_user.has_perm("manuals.add_manual"))

        # Engineer: view only, NO user management
        self.assertTrue(engineer_user.has_perm("machines.view_machine"))
        self.assertTrue(engineer_user.has_perm("manuals.view_manual"))
        self.assertFalse(engineer_user.has_perm("auth.add_user"))
        self.assertFalse(engineer_user.has_perm("auth.change_user"))
        self.assertFalse(engineer_user.has_perm("machines.add_machine"))

        # Supervisor: view only, NO user management
        self.assertTrue(supervisor_user.has_perm("machines.view_machine"))
        self.assertTrue(supervisor_user.has_perm("manuals.view_manual"))
        self.assertFalse(supervisor_user.has_perm("auth.add_user"))
        self.assertFalse(supervisor_user.has_perm("auth.delete_user"))
        self.assertFalse(supervisor_user.has_perm("machines.add_machine"))

    def test_07_unauthorized_access_denied(self):
        """TEST 7: Engineers and Supervisors cannot access User Management via direct URL."""
        engineer_user = User.objects.create_user(
            username="eng_unauth",
            email="eng_u@mechora.industrial",
            password=self.password,
        )
        assign_user_role(engineer_user, ROLE_ENGINEER)

        supervisor_user = User.objects.create_user(
            username="sup_unauth",
            email="sup_u@mechora.industrial",
            password=self.password,
        )
        assign_user_role(supervisor_user, ROLE_SUPERVISOR)

        # Engineer denied
        self.client.force_login(engineer_user)
        resp_eng_list = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(resp_eng_list.status_code, 403, "Engineer must be denied access to User list.")

        resp_eng_add = self.client.get(reverse("admin:auth_user_add"))
        self.assertEqual(resp_eng_add.status_code, 403, "Engineer must be denied access to Add User.")

        # Supervisor denied
        self.client.force_login(supervisor_user)
        resp_sup_list = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(resp_sup_list.status_code, 403, "Supervisor must be denied access to User list.")

        resp_sup_add = self.client.get(reverse("admin:auth_user_add"))
        self.assertEqual(resp_sup_add.status_code, 403, "Supervisor must be denied access to Add User.")

    def test_08_existing_functionality_preserved(self):
        """TEST 8: Verify machines, manuals, dashboard, and RAG remain completely functional."""
        self.client.force_login(self.superuser)

        # Machines changelist
        resp_m = self.client.get(reverse("admin:machines_machine_changelist"))
        self.assertEqual(resp_m.status_code, 200)

        # Manuals changelist
        resp_doc = self.client.get(reverse("admin:manuals_manual_changelist"))
        self.assertEqual(resp_doc.status_code, 200)

        # RAG query log changelist
        resp_rag = self.client.get(reverse("admin:rag_ragquerylog_changelist"))
        self.assertEqual(resp_rag.status_code, 200)

        # Dashboard callback
        from django.test import RequestFactory
        rf = RequestFactory()
        req = rf.get("/admin/")
        req.user = self.superuser
        context = dashboard_callback(req, {})
        self.assertIn("kpi_metrics", context)

        # Database records
        self.assertTrue(Machine.objects.filter(machine_id="M-HP200").exists())
        self.assertTrue(Manual.objects.filter(document_id="HP-OPS-01").exists())
        self.assertTrue(RAGQueryLog.objects.filter(machine=self.machine).exists())


class PublicAuthenticationTests(TestCase):
    def setUp(self):
        ensure_roles_and_permissions()
        self.user = User.objects.create_user("supervisor_one", password="StrongPass#2026!")
        assign_user_role(self.user, ROLE_SUPERVISOR)

    def test_signup_creates_selected_operational_role(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new_engineer",
                "email": "engineer@example.com",
                "first_name": "New",
                "last_name": "Engineer",
                "role": ROLE_ENGINEER,
                "password1": "StrongPass#2026!",
                "password2": "StrongPass#2026!",
            },
        )
        self.assertRedirects(response, reverse("assistant:chat"))
        created = User.objects.get(username="new_engineer")
        self.assertEqual(get_user_role(created), ROLE_ENGINEER)
        self.assertEqual(created.profile.role, UserProfile.Role.ENGINEER)

    def test_signin_rejects_a_mismatched_role(self):
        response = self.client.post(
            reverse("signin"),
            {
                "username": self.user.username,
                "password": "StrongPass#2026!",
                "role": ROLE_ENGINEER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "selected role does not match")
