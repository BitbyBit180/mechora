import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from accounts.roles import assign_user_role
from products.models import Product

from .models import Inspection
from .services.inference import predict
from .services.validation import validate_image
from .services.integrity import verify_model_integrity


def image_file(name="sample.png", image_format="PNG", size=(128, 128)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (120, 120, 120)).save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{'jpeg' if image_format == 'JPEG' else 'png'}")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class InspectionWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.engineer = User.objects.create_user("engineer-phase2", password="StrongPass123!")
        assign_user_role(self.engineer, "Engineer")
        self.other_engineer = User.objects.create_user("other-engineer", password="StrongPass123!")
        assign_user_role(self.other_engineer, "Engineer")
        self.supervisor = User.objects.create_user("supervisor-phase2", password="StrongPass123!")
        assign_user_role(self.supervisor, "Supervisor")
        self.admin = User.objects.create_superuser("admin-phase2", password="StrongPass123!")
        self.product = Product.objects.get(product_code="P-PLATE01")

    def post_image(self, user, uploaded=None):
        self.client.force_login(user)
        return self.client.post("/api/inspections/", {"product_id": self.product.pk, "images": uploaded or image_file()})

    @patch("inspections.views.process_inspection.delay")
    def test_engineer_can_submit_and_only_sees_own_history(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_image(self.engineer)
        self.assertEqual(response.status_code, 201)
        item = Inspection.objects.get(submitted_by=self.engineer)
        self.assertEqual(item.status, Inspection.Status.QUEUED)
        delay.assert_called_once_with(item.pk)
        self.client.force_login(self.other_engineer)
        self.assertEqual(self.client.get("/api/inspections/").json()["inspections"], [])

    def test_invalid_inputs_are_failed_without_prediction(self):
        response = self.post_image(self.engineer, SimpleUploadedFile("bad.jpg", b"not an image", content_type="image/jpeg"))
        self.assertEqual(response.status_code, 201)
        item = Inspection.objects.get(submitted_by=self.engineer)
        self.assertEqual(item.status, Inspection.Status.FAILED)
        self.assertFalse(item.predicted_class)
        self.assertIn("valid image", item.failure_reason)

    def test_validation_limits(self):
        self.assertIsNone(validate_image(image_file("ok.jpg", "JPEG")))
        self.assertIn("minimum", validate_image(image_file(size=(32, 32))))
        self.assertIn("maximum", validate_image(image_file(size=(4097, 64))))
        self.assertIn("5 MiB", validate_image(SimpleUploadedFile("large.png", b"x" * (5 * 1024 * 1024 + 1))))

    def test_batch_accepts_mixed_validity_and_limits_size(self):
        self.client.force_login(self.engineer)
        files = [image_file("one.png"), SimpleUploadedFile("bad.png", b"bad", content_type="image/png")]
        with patch("inspections.views.process_inspection.delay"):
            response = self.client.post("/api/inspections/batch/", {"product_id": self.product.pk, "images": files})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Inspection.objects.filter(batch__isnull=False).count(), 2)
        self.assertEqual(Inspection.objects.filter(status=Inspection.Status.FAILED).count(), 1)
        too_many = [image_file(f"{i}.png") for i in range(11)]
        self.assertEqual(self.client.post("/api/inspections/batch/", {"product_id": self.product.pk, "images": too_many}).status_code, 400)

    def test_engineer_cannot_review_and_supervisor_review_is_separate(self):
        with patch("inspections.views.process_inspection.delay"):
            response = self.post_image(self.engineer)
        item = Inspection.objects.get(pk=response.json()["id"])
        item.status = Inspection.Status.COMPLETED
        item.predicted_class = "Defective"
        item.confidence = 0.9
        item.save()
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(f"/api/inspections/{item.inspection_id}/review/", {"reviewed_class": "Normal"}).status_code, 403)
        self.client.force_login(self.supervisor)
        response = self.client.post(f"/api/inspections/{item.inspection_id}/review/", data='{"reviewed_class":"Normal","comment":"Looks acceptable"}', content_type="application/json")
        self.assertEqual(response.status_code, 201)
        item.refresh_from_db()
        self.assertEqual(item.predicted_class, "Defective")
        self.assertEqual(item.review.reviewed_class, "Normal")
        response = self.client.post(
            f"/api/inspections/{item.inspection_id}/review/",
            data='{"reviewed_class":"Defective","comment":"Updated after second review"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        item.refresh_from_db()
        self.assertEqual(item.predicted_class, "Defective")
        self.assertEqual(item.review.reviewed_class, "Defective")
        self.assertEqual(item.review.review_status, Inspection.ReviewStatus.CONFIRMED)

    def test_supplied_inference_returns_model_version(self):
        result = predict("round2_resources/Samples/images/inspection_001.png")
        self.assertEqual(result["model_version"], "BIT-PLATE-CV-1.0")
        self.assertIn(result["predicted_class"], {"Normal", "Defective"})

    def test_inspection_details_persist_after_database_reload(self):
        with patch("inspections.views.process_inspection.delay"):
            response = self.post_image(self.engineer, image_file("persisted.png"))
        item = Inspection.objects.get(pk=response.json()["id"])
        item.predicted_class = "Defective"
        item.confidence = 0.875
        item.defect_probability = 0.875
        item.model_version = "BIT-PLATE-CV-1.0"
        item.save(update_fields=["predicted_class", "confidence", "defect_probability", "model_version"])

        reloaded = Inspection.objects.get(pk=item.pk)
        self.assertEqual(reloaded.product_id, self.product.pk)
        self.assertTrue(reloaded.image.name.endswith("persisted.png"))
        self.assertEqual(reloaded.original_filename, "persisted.png")
        self.assertEqual(reloaded.predicted_class, "Defective")
        self.assertEqual(reloaded.confidence, 0.875)
        self.assertEqual(reloaded.defect_probability, 0.875)
        self.assertEqual(reloaded.model_version, "BIT-PLATE-CV-1.0")
        self.assertEqual(reloaded.submitted_by_id, self.engineer.pk)
        self.assertIsNotNone(reloaded.created_at)

    def test_supplied_model_files_match_published_checksums(self):
        result = verify_model_integrity()
        self.assertTrue(result["valid"], result)
        self.assertGreaterEqual(result["checked"], 4)

    def test_prd_batch_alias_and_model_integrity_endpoint(self):
        self.client.force_login(self.supervisor)
        self.assertEqual(self.client.get("/api/batches/not-a-uuid/").status_code, 404)
        response = self.client.get("/api/inspections/model-integrity/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])

    def test_administrator_can_assign_inspection_to_engineer(self):
        with patch("inspections.views.process_inspection.delay"):
            response = self.post_image(self.engineer)
        item = Inspection.objects.get(pk=response.json()["id"])
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/api/inspections/{item.inspection_id}/assign/",
            data={"engineer_id": self.other_engineer.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.assigned_to_id, self.other_engineer.pk)

    @patch("inspections.admin.process_inspection.delay")
    def test_admin_can_create_assigned_inspection_from_admin_form(self, delay):
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/admin/inspections/inspection/add/",
                {
                    "product": self.product.pk,
                    "assigned_to": self.other_engineer.pk,
                    "image": image_file("admin-upload.png"),
                    "_save": "Save",
                },
                follow=False,
            )
        self.assertEqual(response.status_code, 302)
        item = Inspection.objects.latest("created_at")
        self.assertEqual(item.assigned_to_id, self.other_engineer.pk)
        self.assertEqual(item.submitted_by_id, self.admin.pk)
        delay.assert_called_once_with(item.pk)

    @patch("inspections.admin.process_inspection.delay")
    def test_admin_can_bulk_assign_images(self, delay):
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/admin/inspections/inspection/bulk-upload/",
                {
                    "product_id": self.product.pk,
                    "assigned_to": self.other_engineer.pk,
                    "images": [image_file("bulk-1.png"), image_file("bulk-2.png")],
                },
                follow=False,
            )
        self.assertEqual(response.status_code, 302)
        items = Inspection.objects.filter(original_filename__startswith="bulk-")
        self.assertEqual(items.count(), 2)
        self.assertEqual(items.filter(assigned_to=self.other_engineer).count(), 2)
        self.assertEqual(delay.call_count, 2)
