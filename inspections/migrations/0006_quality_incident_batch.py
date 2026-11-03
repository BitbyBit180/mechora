from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("inspections", "0005_persist_pending_incident_reviews")]
    operations = [migrations.CreateModel(
        name="QualityIncidentBatch",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("batch_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
            ("items", models.JSONField(default=list)),
            ("total_items", models.PositiveSmallIntegerField(default=0)),
            ("completed_items", models.PositiveSmallIntegerField(default=0)),
            ("failed_items", models.PositiveSmallIntegerField(default=0)),
            ("status", models.CharField(choices=[("queued", "Queued"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], db_index=True, default="queued", max_length=20)),
            ("error_reason", models.TextField(blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_incident_batches", to=settings.AUTH_USER_MODEL)),
        ],
        options={"ordering": ["-created_at"]},
    )]
