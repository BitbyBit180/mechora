from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inspections", "0002_inspection_assigned_to"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QualityIncident",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_id", models.CharField(db_index=True, max_length=64)),
                ("original_prediction", models.CharField(max_length=32)),
                ("model_version", models.CharField(blank=True, max_length=100)),
                ("summary", models.TextField(blank=True)),
                ("suggested_actions", models.JSONField(blank=True, default=list)),
                ("evidence_status", models.CharField(choices=[("Sufficient", "Sufficient"), ("Insufficient", "Insufficient")], default="Insufficient", max_length=20)),
                ("evidence_reason", models.TextField(blank=True)),
                ("source_references", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_incidents", to=settings.AUTH_USER_MODEL)),
                ("inspection", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="quality_incident", to="inspections.inspection")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="IncidentReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("Pending", "Pending"), ("Approved for follow-up", "Approved for follow-up"), ("Needs more information", "Needs more information")], default="Pending", max_length=40)),
                ("comment", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("incident", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="review", to="inspections.qualityincident")),
                ("reviewer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="quality_incident_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-reviewed_at"]},
        ),
    ]
