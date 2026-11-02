from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from django.test import TestCase

from accounts.roles import ROLE_ENGINEER, ROLE_SUPERVISOR, assign_user_role, ensure_roles_and_permissions
from manuals.models import Manual

from .models import Machine


class EngineerMachineShowcaseTests(TestCase):
    def setUp(self):
        ensure_roles_and_permissions()
        self.machine = Machine.objects.create(
            machine_id="M-HP200",
            model="HP-200",
            machine_name="Hydraulic forming press",
            description="High precision forming press.",
        )
        Manual.objects.create(
            document_id="HP-OPS-01",
            machine=self.machine,
            document_name="HP200 Operations Manual",
            revision="1.0",
            file="manuals/hp200.pdf",
            ingestion_status="completed",
        )
        user_model = get_user_model()
        self.engineer = user_model.objects.create_user("showcase_engineer", password="test-pass")
        assign_user_role(self.engineer, ROLE_ENGINEER)
        self.supervisor = user_model.objects.create_user("showcase_supervisor", password="test-pass")
        assign_user_role(self.supervisor, ROLE_SUPERVISOR)
        self.admin = user_model.objects.create_superuser("showcase_admin", password="test-pass")

    def test_engineer_sees_showcase_and_manuals(self):
        self.client.force_login(self.engineer)
        dashboard = self.client.get("/assistant/")
        manuals = self.client.get("/engineer/machines/M-HP200/manuals/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Manufacturing Manual Assistant")
        self.assertEqual(manuals.status_code, 200)
        self.assertContains(manuals, "HP200 Operations Manual")

    def test_supervisor_cannot_access_engineer_manuals(self):
        self.client.force_login(self.supervisor)
        dashboard = self.client.get("/assistant/", follow=True)
        manuals = self.client.get("/engineer/machines/M-HP200/manuals/")
        self.assertNotContains(dashboard, "Machine showcase")
        self.assertContains(dashboard, "Question history")
        self.assertEqual(manuals.status_code, 403)

    def test_machine_api_filters_engineer_machines_and_admin_can_register(self):
        self.client.force_login(self.engineer)
        response = self.client.get("/api/machines/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["machines"][0]["machine_id"], "M-HP200")

        self.client.force_login(self.supervisor)
        response = self.client.post(
            "/api/machines/",
            {"machine_id": "M-AC90", "model": "AC-90"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.post(
            "/api/machines/",
            {"machine_id": "M-AC90", "model": "AC-90"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

    @patch("manuals.views.queue_manual_ingestion")
    def test_admin_manual_api_queues_upload_and_engineer_is_denied(self, queue_task):
        self.client.force_login(self.engineer)
        response = self.client.post(
            "/api/manuals/",
            {"machine_id": "M-HP200", "document_name": "new.pdf", "file": SimpleUploadedFile("new.pdf", b"pdf")},
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/manuals/",
                {"machine_id": "M-HP200", "document_name": "new.pdf", "revision": "1.0", "file": SimpleUploadedFile("new.pdf", b"pdf")},
            )
        self.assertEqual(response.status_code, 201)
        queue_task.assert_called_once()

# Create your tests here.
