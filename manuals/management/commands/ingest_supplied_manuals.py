from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from machines.models import Machine
from manuals.ingestion import IngestionError, ingest_manual
from manuals.models import Manual


SUPPLIED_MANUALS = (
    ("M-HP200", "HP-200", "HP200_Operations_Rev1_0.pdf"),
    ("M-HP200", "HP-200", "HP200_Maintenance_Rev1_0.pdf"),
    ("M-AC90", "AC-90", "AC90_Operations_Maintenance_Rev1_0.pdf"),
)


class Command(BaseCommand):
    help = "Register and ingest the three supplied manufacturing manuals into ChromaDB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-dir",
            default="problem_statement/Manuals",
            help="Directory containing the supplied PDF manuals.",
        )

    def handle(self, *args, **options):
        source_dir = Path(options["source_dir"]).resolve()
        if not source_dir.is_dir():
            raise CommandError(f"Manual directory does not exist: {source_dir}")

        for machine_id, model_name, document_name in SUPPLIED_MANUALS:
            pdf_path = source_dir / document_name
            if not pdf_path.is_file():
                raise CommandError(f"Manual file does not exist: {pdf_path}")
            try:
                self._ingest_one(machine_id, model_name, document_name, pdf_path)
            except IngestionError as exc:
                raise CommandError(f"{document_name}: {exc}") from exc

    @transaction.atomic
    def _ingest_one(self, machine_id, model_name, document_name, pdf_path):
        machine, _ = Machine.objects.get_or_create(
            machine_id=machine_id,
            defaults={"model": model_name, "machine_name": model_name},
        )
        document_ids = {
            "HP200_Operations_Rev1_0.pdf": "HP-OPS-01",
            "HP200_Maintenance_Rev1_0.pdf": "HP-MNT-01",
            "AC90_Operations_Maintenance_Rev1_0.pdf": "AC-OM-01",
        }
        manual, created = Manual.objects.get_or_create(
            machine=machine,
            document_name=document_name,
            revision="1.0",
            defaults={
                "document_id": document_ids[document_name],
                "pdf_filename": document_name,
                "ingestion_status": Manual.IngestionStatus.PENDING,
            },
        )
        if created or not manual.file:
            with pdf_path.open("rb") as source:
                manual.file.save(document_name, File(source), save=False)
        manual.ingestion_status = Manual.IngestionStatus.PENDING
        manual.save()

        result = ingest_manual(
            manual.file.path,
            machine_id=machine.machine_id,
            manual_id=manual.pk,
            document_name=document_name,
            revision="1.0",
        )
        manual.ingestion_status = Manual.IngestionStatus.COMPLETE
        manual.save(update_fields=["ingestion_status"])
        self.stdout.write(
            self.style.SUCCESS(
                f"{document_name}: {result['chunks_created']} new chunks, "
                f"{result['chunks_total']} total"
            )
        )
