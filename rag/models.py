from django.conf import settings
from django.db import models


class RAGQueryLog(models.Model):
    STATUS_CHOICES = [
        ("ANSWERED", "Answered (Grounded)"),
        ("INSUFFICIENT", "Insufficient Evidence"),
        ("ERROR", "System Error"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rag_queries",
        verbose_name="Engineer / Operator",
    )
    machine = models.ForeignKey(
        "machines.Machine",
        on_delete=models.CASCADE,
        related_name="rag_queries",
        verbose_name="Target Machine",
    )
    question = models.TextField(
        verbose_name="Natural Language Question",
        help_text="Question submitted by user",
    )
    answer = models.TextField(
        blank=True,
        verbose_name="Generated Answer",
        help_text="Grounded response from RAG module",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ANSWERED",
        db_index=True,
        verbose_name="Query Status",
    )
    citations = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Verifiable Citations",
        help_text="Document, revision, page number, and passage references",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Queried At",
    )

    class Meta:
        verbose_name = "RAG Query Log"
        verbose_name_plural = "RAG Query Logs"
        ordering = ["-created_at"]

    def __str__(self):
        summary = self.question[:50] + ("..." if len(self.question) > 50 else "")
        return f"[{self.status}] {self.machine.machine_id}: {summary}"


class RAGDocumentChunk(models.Model):
    manual = models.ForeignKey(
        "manuals.Manual",
        on_delete=models.CASCADE,
        related_name="chunks",
        verbose_name="Source Manual",
    )
    machine = models.ForeignKey(
        "machines.Machine",
        on_delete=models.CASCADE,
        related_name="chunks",
        verbose_name="Target Machine",
    )
    page_number = models.PositiveIntegerField(
        verbose_name="PDF Page Number",
        help_text="1-based page number matching printed manual",
    )
    chunk_index = models.PositiveIntegerField(
        verbose_name="Chunk Index",
        help_text="Sequential index of passage within page",
    )
    passage_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="Passage ID",
        help_text="Deterministic chunk identifier",
    )
    chunk_text = models.TextField(
        verbose_name="Passage Text Content",
        help_text="Extracted text chunk indexed in vector space",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Indexed At",
    )

    class Meta:
        verbose_name = "RAG Document Chunk"
        verbose_name_plural = "RAG Document Chunks"
        ordering = ["manual", "page_number", "chunk_index"]
        unique_together = ("manual", "page_number", "chunk_index")

    def __str__(self):
        return f"{self.manual.document_id} - P.{self.page_number} #{self.chunk_index}"
