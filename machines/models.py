from django.db import models


class Machine(models.Model):
    machine_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name="Machine ID",
        help_text="Unique industrial machine identifier (e.g., M-HP200, M-AC90)",
    )
    model = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Model",
        help_text="Equipment model designation (e.g., HP-200, AC-90)",
    )
    machine_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Machine Name",
        help_text="Descriptive equipment name (e.g., Hydraulic forming press)",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Technical specifications, operating context, or factory location",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Registered At",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Last Updated",
    )

    class Meta:
        verbose_name = "Machine"
        verbose_name_plural = "Machines"
        ordering = ["machine_id"]

    def __init__(self, *args, **kwargs):
        # Compatibility with the RAG ingestion API, which calls this field
        # model_name while the admin schema exposes the shorter model field.
        model_name = kwargs.pop("model_name", None)
        if model_name is not None and not kwargs.get("model"):
            kwargs["model"] = model_name
        super().__init__(*args, **kwargs)

    @property
    def model_name(self):
        return self.model

    @model_name.setter
    def model_name(self, value):
        self.model = value

    def __str__(self):
        return f"{self.machine_id} - {self.machine_name} ({self.model})"
