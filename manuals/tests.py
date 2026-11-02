from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from machines.models import Machine

from .models import Manual
from .tasks import ingest_manual_task


class ManualIngestionTaskTests(TestCase):
    def setUp(self):
        self.machine = Machine.objects.create(
            machine_id="M-HP200",
            model="HP-200",
            machine_name="Hydraulic forming press",
        )
        self.manual = Manual.objects.create(
            document_id="HP-ASYNC-01",
            machine=self.machine,
            document_name="HP200 Operations.pdf",
            revision="1.0",
            file=SimpleUploadedFile("HP200_Operations.pdf", b"pdf content"),
        )

    @patch("manuals.tasks.ingest_manual")
    def test_worker_marks_successful_ingestion_complete(self, ingest):
        ingest.return_value = {"chunks_created": 4, "chunks_total": 4}

        result = ingest_manual_task.run(self.manual.pk)

        self.manual.refresh_from_db()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.manual.ingestion_status, Manual.IngestionStatus.COMPLETE)
        ingest.assert_called_once()

    @patch("manuals.tasks.ingest_manual")
    def test_worker_marks_permanent_failure_failed(self, ingest):
        ingest.side_effect = RuntimeError("embedding service unavailable")

        with patch.object(ingest_manual_task, "max_retries", 0):
            result = ingest_manual_task.run(self.manual.pk)

        self.manual.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.manual.ingestion_status, Manual.IngestionStatus.FAILED)

    @patch("manuals.tasks.ingest_manual")
    def test_worker_stops_retrying_on_daily_embedding_quota(self, ingest):
        ingest.side_effect = RuntimeError("OpenRouter HTTP 429 free-models-per-day")

        result = ingest_manual_task.run(self.manual.pk)

        self.manual.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.manual.ingestion_status, Manual.IngestionStatus.FAILED)
        self.assertIn("daily limit", result["error"])

# Create your tests here.
