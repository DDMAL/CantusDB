from typing import Any

from django.contrib import admin
from django.forms import BaseInlineFormSet

from main_app.admin.base_admin import BaseModelAdmin
from main_app.cluster_structure import SegmentSpec, normalize_segments
from main_app.models import ChantCluster, ClusterSegment


class ClusterSegmentInlineFormSet(BaseInlineFormSet):
    """Validates a cluster's submitted segments as one list, not row by row.

    Shape and bounds rules come from the shared validator, so the admin cannot accept
    anything the composer would reject.
    """

    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return
        specs: list[dict[str, Any]] = []
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            specs.append(
                {
                    "start": form.cleaned_data.get("start"),
                    "end": form.cleaned_data.get("end"),
                    "element": form.cleaned_data.get("element"),
                    "text": form.cleaned_data.get("text") or "",
                }
            )
        normalize_segments(self.instance.base_token_count, specs)


class ClusterSegmentInline(admin.TabularInline):
    """Edit a cluster's segments alongside the cluster itself."""

    model = ClusterSegment
    formset = ClusterSegmentInlineFormSet
    extra = 0
    fields = ("order", "start", "end", "element", "text")
    ordering = ("order",)
    autocomplete_fields = ("element",)


@admin.register(ChantCluster)
class ChantClusterAdmin(BaseModelAdmin):
    inlines = (ClusterSegmentInline,)
    list_display = ("base_cantus_id", "chant", "segment_count")
    search_fields = (
        "base_cantus_id",
        "chant__id",
    )
    autocomplete_fields = ("chant",)
    # Frozen while segments exist (segment ranges index into it), so editing it here
    # would only ever raise. Re-anchoring means deleting the cluster and rebuilding it.
    readonly_fields = BaseModelAdmin.readonly_fields + ("base_text_hash",)

    @admin.display(description="segments")
    def segment_count(self, obj: ChantCluster) -> int:
        return obj.segments.count()

    def save_related(self, request, form, formsets, change) -> None:  # type: ignore[no-untyped-def]
        """Route admin edits through ``set_structure`` so there is one write path.

        The inline saves rows directly, but canonicalising the list (merging contiguous
        neighbours, renumbering ``order``) and refreshing the chant's cached full text are
        whole-cluster operations no per-row save can perform. Re-running set_structure
        over what was just saved does both.
        """
        super().save_related(request, form, formsets, change)
        cluster: ChantCluster = form.instance
        specs: list[SegmentSpec] = cluster.segment_specs()
        if specs:
            cluster.set_structure(specs)
