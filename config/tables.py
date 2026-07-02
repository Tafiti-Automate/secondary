from django.urls import reverse
from django.views.generic import ListView


def resolve_value(obj, path):
    if path == "__str__":
        return str(obj)
    value = obj
    bits = path.split("__")
    for index, bit in enumerate(bits):
        value = getattr(value, bit, "")
        if callable(value) and index == len(bits) - 1:
            value = value()
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return value if value not in (None, "") else "—"


class ModelTableView(ListView):
    template_name = "shared/model_list.html"
    context_object_name = "objects"
    paginate_by = 20
    columns = ()
    field_paths = ()
    page_title = "Records"
    eyebrow = "Academic management"
    create_url_name = None
    edit_url_name = None
    delete_url_name = None
    search_fields = ()
    filter_field = None

    def get_queryset(self):
        queryset = self.model.objects.filter(is_deleted=False)
        query = self.request.GET.get("q", "").strip()
        if query and self.search_fields:
            from django.db.models import Q
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(condition)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for obj in context["objects"]:
            rows.append({
                "object": obj,
                "values": [resolve_value(obj, field) for field in self.field_paths],
                "edit_url": reverse(self.edit_url_name, args=[obj.pk]) if self.edit_url_name else None,
                "delete_url": reverse(self.delete_url_name, args=[obj.pk]) if self.delete_url_name else None,
            })
        context.update({
            "rows": rows,
            "columns": self.columns,
            "page_title": self.page_title,
            "eyebrow": self.eyebrow,
            "create_url": reverse(self.create_url_name) if self.create_url_name else None,
        })
        return context
