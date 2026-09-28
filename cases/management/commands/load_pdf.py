"""
Management command: python manage.py load_pdf

Examples:
    python manage.py load_pdf --pdf data/constitution_2010.pdf --title "Constitution of Kenya 2010" --category constitution --url "https://kenyalaw.org/kl/index.php?id=398" --constitution

    python manage.py load_pdf --pdf data/employment_act_2007.pdf --title "Employment Act 2007" --category employment --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/EmploymentAct_No11of2007.pdf"
"""

from django.core.management.base import BaseCommand
from cases.pdf_parser import parse_pdf


CATEGORY_CHOICES = [
    'constitution', 'employment', 'landlord_tenant',
    'criminal_procedure', 'children', 'consumer', 'fraud', 'land', 'other'
]


class Command(BaseCommand):
    help = 'Load a Kenyan law PDF and split it into sections in the database.'

    def add_arguments(self, parser):
        parser.add_argument('--pdf', required=True, help='Path to the PDF file (e.g. data/employment_act_2007.pdf)')
        parser.add_argument('--title', required=True, help='Full name of the Act (e.g. "Employment Act 2007")')
        parser.add_argument('--category', required=True, choices=CATEGORY_CHOICES, help='Category of the law')
        parser.add_argument('--url', required=True, help='Source URL from kenyalaw.org')
        parser.add_argument('--constitution', action='store_true', help='Use Article-based parsing for the Constitution')
        parser.add_argument('--overwrite', action='store_true', help='Delete and re-create existing sections')

    def handle(self, *args, **options):
        count = parse_pdf(
            pdf_path=options['pdf'],
            act_title=options['title'],
            category=options['category'],
            source_url=options['url'],
            is_constitution=options['constitution'],
            overwrite=options['overwrite'],
        )
        if count > 0:
            self.stdout.write(self.style.SUCCESS(
                f"Created {count} sections. Now run: python manage.py build_embeddings"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "No new sections created. Use --overwrite to replace existing ones."
            ))
