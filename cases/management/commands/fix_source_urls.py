"""
Management command: fix_source_urls
Replaces raw PDF download links with proper kenyalaw.org web-readable pages.

Usage:
    python manage.py fix_source_urls
"""
from django.core.management.base import BaseCommand
from cases.models import Law

URL_MAP = {
    # Old PDF link  →  New readable web page
    "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/CriminalProcedureCode_Cap75.pdf":
        "https://new.kenyalaw.org/akn/ke/act/1930/11/eng@2023-12-11",

    "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/EmploymentAct_No11of2007.pdf":
        "https://new.kenyalaw.org/akn/ke/act/2007/11/eng@2024-03-22",

    # Constitution — both the old PDF and the flag set by load_constitution command
    "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/Constitution_of_Kenya_2010.pdf":
        "https://new.kenyalaw.org/akn/ke/act/2010/constitution/eng@2010-09-03",

    # Catch any other old-style PDF paths for the same acts
    "http://www.kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/EmploymentAct2007.pdf":
        "https://new.kenyalaw.org/akn/ke/act/2007/11/eng@2024-03-22",
}


class Command(BaseCommand):
    help = "Replace raw PDF source_url links with readable kenyalaw.org web pages."

    def handle(self, *args, **options):
        total_updated = 0

        for old_url, new_url in URL_MAP.items():
            updated = Law.objects.filter(source_url=old_url).update(source_url=new_url)
            if updated:
                self.stdout.write(f"  {updated:3d} rows  {old_url[:60]}...")
                self.stdout.write(f"        → {new_url}")
            total_updated += updated

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {total_updated} law sections updated."
        ))
