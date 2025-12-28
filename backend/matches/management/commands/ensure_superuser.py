import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Ensure a default superuser exists."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin"),
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin"),
        )
        parser.add_argument(
            "--email",
            default=os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com"),
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = options["username"]
        password = options["password"]
        email = options["email"]

        user = user_model.objects.filter(username=username).first()
        if user:
            if not user.is_superuser or not user.is_staff:
                user.is_superuser = True
                user.is_staff = True
                user.set_password(password)
                if email and not user.email:
                    user.email = email
                user.save(
                    update_fields=["is_superuser", "is_staff", "password", "email"]
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"Updated existing user '{username}' to superuser."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Superuser '{username}' already exists.")
                )
            return

        user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
