"""Register and index the Round 3 product-scoped quality SOPs."""

import csv
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from machines.models import Machine
from manuals.ingestion import IngestionError, ingest_manual
from manuals.models import Manual


class Command(BaseCommand):
    help = "Register and index the Round 3 quality SOP PDFs with page provenance."

    def add_arguments(self, parser):
        parser.add_argument("--pack-dir", default="Round 3 Student Pack")

    def handle(self, *args, **options):
        pack = Path(options["pack_dir"]).resolve()
        mapping_path = pack / "product_sop_mapping.csv"
        sop_dir = pack / "SOPs"
        if not mapping_path.is_file() or not sop_dir.is_dir():
            raise CommandError(f"Round 3 pack is incomplete: {pack}")
        with mapping_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        machine_cache = {}
        for row in rows:
            pdf_path = sop_dir / row["pdf_filename"]
            if not pdf_path.is_file():
                raise CommandError(f"Mapped SOP is missing: {pdf_path}")
            product_id = row["product_id"]
            machine = machine_cache.get(product_id)
            if machine is None:
                machine, _ = Machine.objects.get_or_create(
                    # Product IDs are the scope used by the assistant and the
                    # existing Chroma metadata filter (for example P-PLATE01).
                    machine_id=product_id,
                    defaults={"model": product_id, "machine_name": f"Quality references for {product_id}"},
                )
                machine_cache[product_id] = machine
            with transaction.atomic():
                manual, _ = Manual.objects.get_or_create(
                    document_id=row["document_id"],
                    defaults={
                        "machine": machine,
                        "document_name": row["pdf_filename"],
                        "revision": row["revision"],
                        "pdf_filename": row["pdf_filename"],
                    },
                )
                manual.machine = machine
                manual.document_name = row["pdf_filename"]
                manual.revision = row["revision"]
                manual.pdf_filename = row["pdf_filename"]
                manual.ingestion_status = Manual.IngestionStatus.PROCESSING
                with pdf_path.open("rb") as source:
                    manual.file.save(row["pdf_filename"], File(source), save=False)
                manual.save()
                try:
                    result = ingest_manual(
                        manual.file.path,
                        machine_id=product_id,
                        manual_id=manual.pk,
                        document_name=row["pdf_filename"],
                        revision=row["revision"],
                    )
                except IngestionError as exc:
                    manual.ingestion_status = Manual.IngestionStatus.FAILED
                    manual.save(update_fields=["ingestion_status"])
                    raise CommandError(f"{row['document_id']}: {exc}") from exc
                manual.ingestion_status = Manual.IngestionStatus.COMPLETE
                manual.save(update_fields=["ingestion_status"])
            self.stdout.write(self.style.SUCCESS(f"{row['document_id']}: {result['chunks_total']} chunks indexed"))
