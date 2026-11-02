import csv
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from accounts.models import UserProfile
from accounts.roles import ROLE_ENGINEER, ROLE_SUPERVISOR, assign_user_role
from assistant.models import Question
from machines.models import Machine
from manuals.models import Manual
from rag.models import RAGQueryLog, RAGDocumentChunk


class Command(BaseCommand):
    help = "Seeds initial machines and manuals from machine_manual_index.csv"

    def handle(self, *args, **options):
        csv_path = settings.BASE_DIR / "problem_statement" / "machine_manual_index.csv"
        if not csv_path.exists():
            self.stdout.write(self.style.WARNING(f"CSV file not found at {csv_path}"))
        else:
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

        # Keep the demo usable even when the registration CSV is unavailable.
        fallback_machines = [
            ("M-HP200", "HP-200", "Hydraulic forming press"),
            ("M-AC90", "AC-90", "Air conditioning unit"),
        ]
        for machine_id, model, machine_name in fallback_machines:
            Machine.objects.get_or_create(
                machine_id=machine_id,
                defaults={
                    "model": model,
                    "machine_name": machine_name,
                    "description": f"Industrial {machine_name} ({model}) demo equipment.",
                },
            )

        User = get_user_model()
        demo_users = [
            ("eng_roberts", "EngineerPass2026!", ROLE_ENGINEER, "Engineer"),
            ("sup_chen", "SupervisorPass2026!", ROLE_SUPERVISOR, "Supervisor"),
        ]
        for username, password, role, profile_role in demo_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": profile_role, "email": f"{username}@mechora.local"},
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
            assign_user_role(user, role)
            UserProfile.objects.update_or_create(user=user, defaults={"role": profile_role})

        # Seed sample RAG queries to demonstrate grounded citations and status indicators
        hp200 = Machine.objects.filter(machine_id="M-HP200").first()
        ac90 = Machine.objects.filter(machine_id="M-AC90").first()
        engineer = User.objects.filter(username="eng_roberts").first()

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

        if hp200 and engineer and not Question.objects.filter(user=engineer, machine=hp200).exists():
            Question.objects.create(
                user=engineer,
                machine=hp200,
                question_text="What is the normal hydraulic pressure range?",
                answer_text="The normal forming-stage pressure range is 120 to 140 bar [S1].",
                status=Question.Status.ANSWERED,
                citations=[{"source_id": "S1", "document_name": "HP200 Operations Rev1 0", "revision": "1.0", "page_number": 1, "passage": "Normal hydraulic pressure: 120 to 140 bar during the forming stage."}],
            )
            Question.objects.create(
                user=engineer,
                machine=hp200,
                question_text="What is the replacement procedure for the main pump?",
                answer_text="The selected manuals do not provide enough evidence to answer this question.",
                status=Question.Status.INSUFFICIENT,
                citations=[],
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
