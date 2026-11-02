from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import UserProfile
from assistant.models import Question
from machines.models import Machine
from manuals.models import Manual


class AskEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("engineer", password="test-pass")
        UserProfile.objects.create(user=self.user, role=UserProfile.Role.ENGINEER)
        self.machine = Machine.objects.create(machine_id="M-HP200", model_name="HP-200")
        Manual.objects.create(
            machine=self.machine,
            document_name="HP200_Operations_Rev1_0.pdf",
            revision="1.0",
            file=SimpleUploadedFile("manual.pdf", b"pdf"),
            ingestion_status=Manual.IngestionStatus.COMPLETE,
            uploaded_by=self.user,
        )
        self.client.force_login(self.user)

    @patch("assistant.views.answer_question")
    def test_persists_structured_answer(self, answer_question):
        answer_question.return_value = {
            "status": "ANSWERED",
            "answer": "The manual says 4 bar [S1].",
            "sources": [{"source_id": "S1", "page_number": 1}],
        }
        response = self.client.post(
            "/api/assistant/ask/",
            {"machine_id": "M-HP200", "question": "What is the pressure?"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ANSWERED")
        self.assertEqual(Question.objects.get().status, Question.Status.ANSWERED)

    def test_unauthenticated_client_gets_401(self):
        self.client.logout()
        response = self.client.post(
            "/api/assistant/ask/", {}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)

    def test_chat_page_renders_for_authenticated_user(self):
        response = self.client.get("/assistant/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manufacturing Manual Assistant")

    def test_rename_chat(self):
        q = Question.objects.create(
            user=self.user,
            machine=self.machine,
            question_text="Original question text",
            status=Question.Status.ANSWERED,
        )
        response = self.client.post(
            f"/api/assistant/history/{q.pk}/rename/",
            {"title": "Renamed Title"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.title, "Renamed Title")
        self.assertEqual(q.display_title(), "Renamed Title")

    def test_delete_chat(self):
        q = Question.objects.create(
            user=self.user,
            machine=self.machine,
            question_text="To be deleted",
            status=Question.Status.ANSWERED,
        )
        response = self.client.delete(f"/api/assistant/history/{q.pk}/delete/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.filter(pk=q.pk).exists())

    def test_pin_chat(self):
        q = Question.objects.create(
            user=self.user,
            machine=self.machine,
            question_text="Pin question",
            status=Question.Status.ANSWERED,
        )
        response = self.client.post(f"/api/assistant/history/{q.pk}/pin/")
        self.assertEqual(response.status_code, 200)
        q.refresh_from_db()
        self.assertTrue(q.is_pinned)

    def test_history_returns_pinned_and_custom_title(self):
        q1 = Question.objects.create(
            user=self.user,
            machine=self.machine,
            question_text="First question",
            title="Custom Name",
            status=Question.Status.ANSWERED,
            is_pinned=True,
        )
        response = self.client.get("/api/assistant/history/")
        self.assertEqual(response.status_code, 200)
        history_items = response.json()["history"]
        self.assertEqual(len(history_items), 1)
        self.assertEqual(history_items[0]["title"], "Custom Name")
        self.assertTrue(history_items[0]["is_pinned"])
