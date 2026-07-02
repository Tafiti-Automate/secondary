from django.db import migrations


def normalize_examination_flags(apps, schema_editor):
    Examination = apps.get_model("exams", "Examination")
    Examination.objects.filter(status="locked").update(locked=True, published=True)
    Examination.objects.filter(status="published").update(locked=False, published=True)
    Examination.objects.exclude(status__in=("published", "locked")).update(locked=False, published=False)


class Migration(migrations.Migration):
    dependencies = [("exams", "0005_uppersubjectresult_approved_at_and_more")]

    operations = [migrations.RunPython(normalize_examination_flags, migrations.RunPython.noop)]
