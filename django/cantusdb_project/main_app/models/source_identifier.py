from django.db import models

class SourceIdentifier(models.Model):
    class Meta:
        verbose_name = "Source Identifier"
        ordering = ('type',)

    OTHER = 1
    OLIM = 2
    ALTN = 3
    RISM_ONLINE = 4

    IDENTIFIER_TYPES = (
        (OTHER, 'Other catalogues'),
        (OLIM, 'olim (Former shelfmark)'),
        (ALTN, 'Alternative names'),
        (RISM_ONLINE, "RISM Online")
    )

    identifier = models.CharField(max_length=255)
    type = models.IntegerField(choices=IDENTIFIER_TYPES)
    note = models.TextField(blank=True, null=True)
    source = models.ForeignKey("Source",
                               related_name="identifiers",
                               on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.identifier}"

    @property
    def identifier_type(self):
        d = dict(self.IDENTIFIER_TYPES)
        return d[self.type]
