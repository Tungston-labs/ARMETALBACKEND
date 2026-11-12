from django.core.management.base import BaseCommand
from user.models import User

class Command(BaseCommand):
    help = "Creates or updates an admin user with is_superadmin=True"

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, default="admin", help="Admin username (default: admin)")
        parser.add_argument("--email", type=str, default="admin@armetal.com", help="Admin email (default: admin@armetal.com)")
        parser.add_argument("--password", type=str, default="Admin@123", help="Admin password (default: Admin@123)")

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email}
        )

        user.email = email
        user.is_superadmin = True
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = "Created new" if created else "Updated existing"
        self.stdout.write(self.style.SUCCESS(
            f"Successfully {action} superadmin user:\n"
            f"  Username: {user.username}\n"
            f"  Email: {user.email}\n"
            f"  is_superadmin: {user.is_superadmin}\n"
            f"  is_superuser: {user.is_superuser}\n"
            f"  is_staff: {user.is_staff}\n"
            f"  Password: {password}"
        ))
