from django import forms


class StyledModelForm(forms.ModelForm):
    """Consistent, accessible styling for every portal form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-checkbox"
            elif isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs["class"] = "form-radio-group"
            else:
                field.widget.attrs["class"] = "form-control"
            if isinstance(field.widget, forms.DateInput):
                field.widget.input_type = "date"
            if not isinstance(field.widget, (forms.CheckboxInput, forms.FileInput, forms.Select, forms.SelectMultiple)):
                field.widget.attrs.setdefault("placeholder", field.label)


class DateRangeValidationMixin:
    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end <= start:
            self.add_error("end_date", "End date must be after the start date.")
        return cleaned
