from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('attendance', '0011_employeeattendancereport_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='attendance',
                    name='attendance_type',
                    field=models.CharField(
                        blank=True,
                        choices=[('paid', 'Paid'), ('unpaid', 'Unpaid')],
                        max_length=10,
                        null=True,
                    ),
                ),
                migrations.AddField(
                    model_name='attendance',
                    name='updated_by',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='updated_attendances',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
