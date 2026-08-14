from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from main_app.storage import private_media_storage


class DataCheckReport(models.Model):
    # Stored privately (not under MEDIA_ROOT) since reports may contain
    # unpublished data; download is only exposed through the admin.
    file = models.FileField(
        upload_to="data_check_reports/%Y/%m/", storage=private_media_storage
    )
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
    # Deferred to on_commit so a rolled-back transaction doesn't leave the
    # DB row restored but its file already gone.
    if instance.file:
        transaction.on_commit(lambda: instance.file.delete(save=False))
