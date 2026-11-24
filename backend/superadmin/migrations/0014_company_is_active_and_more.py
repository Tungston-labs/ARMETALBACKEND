from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('superadmin', '0013_company_basic_salary_percent_company_half_day_hours_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='company',
                    name='is_active',
                    field=models.BooleanField(default=True),
                ),
                migrations.AddField(
                    model_name='companysubscription',
                    name='amount_per_employee',
                    field=models.DecimalField(
                        decimal_places=2, default=0, max_digits=10
                    ),
                ),
                migrations.AddField(
                    model_name='companysubscription',
                    name='employee_count',
                    field=models.PositiveIntegerField(default=0),
                ),
            ],
        ),
    ]
