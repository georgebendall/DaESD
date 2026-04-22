from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Compatibility wrapper for the full PostgreSQL demo marketplace seed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously seeded demo data first.",
        )

    def handle(self, *args, **options):
        call_command("seed_demo", reset=options["reset"])
