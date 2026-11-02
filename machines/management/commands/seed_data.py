import csv
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from machines.models import Machine
from manuals.models import Manual
from rag.models import RAGQueryLog, RAGDocumentChunk


class Command(BaseCommand):
    help = "Seeds initial machines and manuals from machine_manual_index.csv"

    def handle(self, *args, **options):
        csv_path = settings.BASE_DIR / "problem_statement" / "machine_manual_index.csv"
        if not csv_path.exists():
            self.stdout.write(self.style.WARNING(f"CSV file not found at {csv_path}"))
            return

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                machine, m_created = Machine.objects.get_or_create(
                    machine_id=row["machine_id"],
                    defaults={
                        "model": row["model"],
                        "machine_name": row["machine_name"],
                        "description": f"Industrial {row['machine_name']} ({row['model']}) registered in plant inventory.",
                    },
                )
                if m_created:
                    self.stdout.write(self.style.SUCCESS(f"Created Machine: {machine.machine_id}"))

                clean_title = row["pdf_filename"].replace(".pdf", "").replace("_", " ")
                manual, man_created = Manual.objects.get_or_create(
                    document_id=row["document_id"],
                    defaults={
                        "machine": machine,
                        "document_name": clean_title,
                        "revision": row["revision"],
                        "pdf_filename": row["pdf_filename"],
                        "file": f"manuals/{row['pdf_filename']}",
                        "ingestion_status": "completed",
                    },
                )
                if man_created:
                    self.stdout.write(self.style.SUCCESS(f"Created Manual: {manual.document_id}"))

        # Seed sample RAG queries to demonstrate grounded citations and status indicators
        hp200 = Machine.objects.filter(machine_id="M-HP200").first()
        ac90 = Machine.objects.filter(machine_id="M-AC90").first()

        if hp200 and not RAGQueryLog.objects.filter(machine=hp200).exists():
            RAGQueryLog.objects.create(
                machine=hp200,
                question="What does alarm E17 indicate on the HP-200 press?",
                answer="Alarm E17 indicates Hydraulic Fluid Over-Temperature (>65°C). Immediate action: Inspect heat exchanger circulation and ensure cooling circuit valve is 100% open.",
                status="ANSWERED",
                citations=[
                    {
                        "document_id": "HP-OPS-01",
                        "document_name": "HP200 Operations Rev1 0",
                        "revision": "1.0",
                        "page": 2,
                        "passage": "Alarm E17: Hydraulic Oil Temperature Exceeded (>65°C). Verify cooling water flow.",
                    }
                ],
            )

        if ac90 and not RAGQueryLog.objects.filter(machine=ac90).exists():
            RAGQueryLog.objects.create(
                machine=ac90,
                question="How often should the AC-90 air filter be inspected?",
                answer="The intake air filter element must be visually inspected every 250 operating hours or monthly, whichever comes first.",
                status="ANSWERED",
                citations=[
                    {
                        "document_id": "AC-OM-01",
                        "document_name": "AC90 Operations Maintenance Rev1 0",
                        "revision": "1.0",
                        "page": 1,
                        "passage": "Table 2.1: Air intake filter inspection interval: 250 operating hours / monthly.",
                    }
                ],
            )

        self.stdout.write(self.style.SUCCESS("MECHORA database seeded successfully."))
