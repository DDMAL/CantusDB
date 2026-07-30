from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class DataCheckReport(models.Model):
    file = models.FileField(upload_to="data_check_reports/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Data check report"
        verbose_name_plural = "Data check reports"

    def __str__(self) -> str:
        return f"Data check report — {self.created_at:%Y-%m-%d %H:%M}"


@receiver(post_delete, sender=DataCheckReport)
def delete_report_file(sender, instance: "DataCheckReport", **kwargs) -> None:
    # Connecting a post_delete receiver also disables Django's collector
    # fast-delete path, so this reliably fires for bulk admin deletes too.
    if instance.file:
        instance.file.delete(save=False)
