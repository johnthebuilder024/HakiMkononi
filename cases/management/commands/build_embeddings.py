"""
Management command: python manage.py build_embeddings

Generates AI embeddings for all law sections that don't have one yet.
Run this after loading new law data via the PDF parser or admin.
"""

from django.core.management.base import BaseCommand
from cases.rag import build_embeddings_for_all_laws


class Command(BaseCommand):
    help = 'Build AI embeddings for all law sections that do not have one yet.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Rebuild embeddings for ALL law sections, even those that already have one.',
        )

    def handle(self, *args, **options):
        if options['all']:
            from cases.models import Law
            self.stdout.write("Clearing all existing embeddings...")
            Law.objects.all().update(embedding_json='')

        self.stdout.write("Building embeddings...")
        build_embeddings_for_all_laws()
        self.stdout.write(self.style.SUCCESS("Done! AI is now ready to answer questions."))
