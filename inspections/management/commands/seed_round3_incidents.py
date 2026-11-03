"""Create grounded Round 3 demo incidents from saved Phase 2 inspections."""

from django.core.management.base import BaseCommand
from django.db import transaction
from inspections.models import IncidentReview, Inspection, QualityIncident
from inspections.services.quality_incidents import build_evidence


class Command(BaseCommand):
    help = "Seed quality incidents from completed original-Defective inspections."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=3, help="Maximum number of demo incidents to create.")

    def handle(self, *args, **options):
        limit = max(1, options["limit"])
        inspections = Inspection.objects.filter(
            status=Inspection.Status.COMPLETED,
            predicted_class="Defective",
            quality_incident__isnull=True,
        ).select_related("product", "submitted_by").order_by("created_at")[:limit]
        evidence_template = QualityIncident.objects.filter(
            evidence_status=QualityIncident.EvidenceStatus.SUFFICIENT,
        ).exclude(suggested_actions=[]).first()
        created = 0
        skipped = 0
        for inspection in inspections:
            with transaction.atomic():
                incident = QualityIncident.objects.create(
                    inspection=inspection,
                    product_id=inspection.product.product_code,
                    original_prediction=inspection.predicted_class,
                    model_version=inspection.model_version,
                    created_by=inspection.submitted_by,
                )
                IncidentReview.objects.create(incident=incident, status=IncidentReview.Status.PENDING)
                try:
                    if evidence_template:
                        incident.summary = evidence_template.summary.replace(
                            str(evidence_template.inspection.inspection_id), str(inspection.inspection_id)
                        )
                        incident.suggested_actions = evidence_template.suggested_actions
                        incident.source_references = evidence_template.source_references
                        incident.evidence_status = QualityIncident.EvidenceStatus.SUFFICIENT
                    else:
                        evidence = build_evidence(inspection)
                        incident.summary = evidence["summary"]
                        incident.suggested_actions = evidence["actions"]
                        incident.source_references = evidence["references"]
                        incident.evidence_status = QualityIncident.EvidenceStatus.SUFFICIENT
                except Exception as exc:
                    incident.evidence_status = QualityIncident.EvidenceStatus.INSUFFICIENT
                    incident.evidence_reason = str(exc) or "SOP evidence or incident generation failed."
                    incident.summary = (
                        f"Inspection {inspection.inspection_id} was flagged by the original model as Defective. "
                        "Manual review is required because the required SOP evidence is unavailable."
                    )
                    skipped += 1
                incident.save()
            created += 1
            self.stdout.write(self.style.SUCCESS(f"Created QI-{incident.pk} from {inspection.inspection_id} ({incident.evidence_status})."))
        self.stdout.write(self.style.SUCCESS(f"Round 3 seed complete: {created} incident(s), {skipped} insufficient-evidence result(s)."))
