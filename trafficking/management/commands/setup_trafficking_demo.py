"""
Management command: setup_trafficking_demo

Creates demo data for showing HAART Kenya and DCI a working system.

Usage:
    python manage.py setup_trafficking_demo
    python manage.py setup_trafficking_demo --clear  # remove all demo data first

Creates:
    - 5 realistic Kenyan trafficking reports with suspects
    - 2 reports share the alias "Uncle James" → triggers alias match
    - 1 urgent report → triggers urgent flag
    - 3 partner access keys (police, ngo, researcher)
    - Processes alias matching between demo reports

After running:
    python manage.py setup_trafficking_demo

    Visit:
      /report-trafficking/dashboard/login/
      Police key:     printed to console
      NGO key:        printed to console
      Researcher key: printed to console
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


DEMO_REPORTS = [
    {
        "story": (
            "I was looking for work in Nairobi. A man called Uncle James contacted me "
            "on Facebook and said there was a domestic work job in Dubai paying KES 80,000 "
            "a month. He paid for my ticket. When I arrived at JKIA he took my passport "
            "and ID saying he would 'keep them safe'. I was taken to a house in Dubai where "
            "I worked 18 hours a day with no pay. I was not allowed to leave or use a phone. "
            "After 4 months I managed to contact my sister who reported to the Kenya embassy."
        ),
        "aliases":  ["Uncle James", "Facebook: KenyaJobsGulf2025", "+254701234567"],
        "county":   "Nairobi",
        "date":     "August 2026",
        "urgent":   False,
        "type":     "labour",
        "recruit":  "social_media",
        "indicators": [
            "passport_confiscation", "unpaid_wages", "confinement",
            "phone_confiscated", "deceptive_job_offer", "transported_across_border"
        ],
        "profile":      "adult_female",
        "destination":  "Dubai",
    },
    {
        "story": (
            "My cousin in Kisumu was recruited by a man also known as Uncle James who "
            "promised her a cleaning job at a hotel in Mombasa. When she arrived the "
            "job did not exist. She was taken to a house with 5 other women and was "
            "forced to work in a bar. Her phone was taken. She called me from a "
            "customer's phone. His number is 0701234567. The house is somewhere in "
            "Mombasa near the old town, she thinks."
        ),
        "aliases":  ["Uncle James", "0701234567"],
        "county":   "Kisumu",
        "date":     "September 2026",
        "urgent":   True,   # still being held
        "type":     "sexual",
        "recruit":  "job_offer",
        "indicators": [
            "phone_confiscated", "confinement", "deceptive_job_offer",
            "multiple_victims_together", "movement_restriction"
        ],
        "profile":     "adult_female",
        "destination": "Mombasa",
    },
    {
        "story": (
            "My 15 year old daughter was befriended online by a man calling himself "
            "'Bae254'. He said he loved her and after 3 weeks asked her to come to "
            "Nairobi to meet him. She went without telling us. We found out from her "
            "friend. We have been to the police but they have not acted. We believe "
            "she is being used for sexual exploitation in Nairobi. Her last message "
            "was 'I am scared, I cannot leave, he has my phone'. Vehicle seen KBC 123X."
        ),
        "aliases":  ["Bae254", "KBC 123X"],
        "county":   "Nakuru",
        "date":     "October 2026",
        "urgent":   True,  # minor, currently held
        "type":     "sexual",
        "recruit":  "romance",
        "indicators": [
            "confinement", "phone_confiscated", "movement_restriction",
            "threats_violence", "transported_across_border"
        ],
        "profile":     "minor_female",
        "destination": "Nairobi",
    },
    {
        "story": (
            "I work for a domestic work agency called 'Gulf Star Agencies' on Moi Avenue "
            "Nairobi. I have seen at least 10 women sent to Saudi Arabia and Qatar this "
            "year who were told they would earn KES 60,000 but actually earn nothing. "
            "The agency takes their passports. The manager is a man called Kamau wa "
            "Githurai. I have his number: 0756789012. I am reporting anonymously because "
            "I fear losing my job."
        ),
        "aliases":  ["Gulf Star Agencies", "Kamau wa Githurai", "0756789012"],
        "county":   "Nairobi",
        "date":     "July 2026",
        "urgent":   False,
        "type":     "labour",
        "recruit":  "broker",
        "indicators": [
            "passport_confiscation", "unpaid_wages", "deceptive_job_offer",
            "false_promises", "recruited_for_domestic_work", "transported_across_border",
            "debt_bondage"
        ],
        "profile":     "adult_female",
        "destination": "Saudi Arabia",
    },
    {
        "story": (
            "Nilikutana na mwanamke anayeitwa Mama Salon karibu na kituo cha mabasi "
            "Kisumu. Aliniambia kuna kazi ya kupanga nywele Nairobi na mshahara wa "
            "shilingi 30,000 kwa mwezi. Nilikubali. Nikifika Nairobi niliwekwa pamoja "
            "na wasichana wengine 8 katika nyumba ndogo. Pasipoti na simu vilitwaliwa. "
            "Tulilazimishwa kukaa pale na watu waliokuja usiku. Baada ya wiki 2 mmoja "
            "wetu alikimbia na kutupigia simu."
        ),
        "aliases":  ["Mama Salon"],
        "county":   "Kisumu",
        "date":     "September 2026",
        "urgent":   False,
        "type":     "sexual",
        "recruit":  "job_offer",
        "indicators": [
            "passport_confiscation", "phone_confiscated", "confinement",
            "multiple_victims_together", "deceptive_job_offer", "movement_restriction"
        ],
        "profile":     "minor_female",
        "destination": "Nairobi",
    },
]


class Command(BaseCommand):
    help = "Load demo trafficking reports and partner access keys for HAART/DCI demo"

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing trafficking data before loading demo'
        )
        parser.add_argument(
            '--no-ai', action='store_true',
            help='Skip AI processing — just load raw reports (faster, no Groq needed)'
        )

    def handle(self, *args, **options):
        from trafficking.models import (
            TraffickingReport, TraffickingSuspect,
            TraffickingAccessKey, TraffickingAliasAlert,
        )
        from trafficking.ai import _normalize_alias, _find_alias_matches

        if options['clear']:
            TraffickingAliasAlert.objects.all().delete()
            TraffickingSuspect.objects.all().delete()
            TraffickingReport.objects.all().delete()
            TraffickingAccessKey.objects.all().delete()
            self.stdout.write("  🗑️  Cleared all existing trafficking data")

        # ── Create demo reports ────────────────────────────────────────────────
        self.stdout.write("\n📝 Creating demo reports...")
        created_reports = []

        for i, demo in enumerate(DEMO_REPORTS, 1):
            report = TraffickingReport.objects.create(
                story_raw        = demo['story'],
                story_lang       = 'sw' if i == 5 else 'en',
                county_of_origin = demo['county'],
                approximate_date = demo['date'],
                is_urgent        = demo['urgent'],
                reporter_contact = '',
                is_anonymous     = True,
                status           = TraffickingReport.STATUS_READY,
                report_type      = demo['type'],
                recruitment_method = demo['recruit'],
                indicators       = demo['indicators'],
                victim_profile   = demo['profile'],
                destination      = demo['destination'],
                formal_report_en = f"[Demo report {i} — run with Groq to generate formal report]",
                formal_report_sw = f"[Ripoti ya demo {i} — tumia Groq kupata ripoti rasmi]",
            )
            created_reports.append(report)
            self.stdout.write(f"  ✅ {report.reference_number} — {demo['type']} — {demo['county']}")

            # Create suspects
            for alias_text in demo['aliases']:
                TraffickingSuspect.objects.create(
                    report           = report,
                    alias            = alias_text,
                    alias_type       = _guess_alias_type(alias_text),
                    alias_normalized = _normalize_alias(alias_text),
                    confidence       = 'high',
                )

        # ── Run alias matching ─────────────────────────────────────────────────
        self.stdout.write("\n🔍 Running alias matching...")
        alerts_created = 0

        for report in created_reports:
            for suspect in report.suspects.all():
                matches = _find_alias_matches(suspect)
                for matched_suspect, match_type in matches:
                    # Link M2M
                    suspect.linked_to.add(matched_suspect)
                    matched_suspect.linked_to.add(suspect)

                    # Mark both reports
                    TraffickingReport.objects.filter(
                        pk__in=[report.pk, matched_suspect.report_id]
                    ).update(has_linked_reports=True)

                    # Create alert
                    if not TraffickingAliasAlert.objects.filter(
                        alias=suspect.alias,
                        report_new=report,
                        report_previous=matched_suspect.report,
                    ).exists():
                        TraffickingAliasAlert.objects.create(
                            alias            = suspect.alias,
                            match_type       = match_type,
                            report_new       = report,
                            report_previous  = matched_suspect.report,
                            suspect_new      = suspect,
                            suspect_previous = matched_suspect,
                        )
                        alerts_created += 1
                        self.stdout.write(
                            f"  ⚠️  MATCH: \"{suspect.alias}\" — "
                            f"{report.reference_number} ↔ {matched_suspect.report.reference_number}"
                        )

        # ── Create partner access keys ────────────────────────────────────────
        self.stdout.write("\n🔑 Creating demo partner access keys...")

        keys = [
            {
                'organisation':     'DCI Anti-Human Trafficking Unit (Demo)',
                'tier':             TraffickingAccessKey.TIER_POLICE,
                'can_update_status': True,
                'email_alerts':     '',
            },
            {
                'organisation':     'HAART Kenya (Demo)',
                'tier':             TraffickingAccessKey.TIER_NGO,
                'can_update_status': True,
                'email_alerts':     '',
            },
            {
                'organisation':     'IOM Kenya Research (Demo)',
                'tier':             TraffickingAccessKey.TIER_RESEARCHER,
                'can_update_status': False,
                'email_alerts':     '',
            },
        ]

        self.stdout.write("\n" + "=" * 65)
        self.stdout.write("DEMO ACCESS KEYS — share these with partners:")
        self.stdout.write("=" * 65)

        for key_data in keys:
            raw_key = TraffickingAccessKey.generate_key()
            TraffickingAccessKey.objects.create(
                organisation     = key_data['organisation'],
                tier             = key_data['tier'],
                access_key_hash  = TraffickingAccessKey.hash_key(raw_key),
                can_update_status = key_data['can_update_status'],
                email_alerts     = key_data['email_alerts'],
                active           = True,
            )
            tier_label = {
                'police':     '🚔 POLICE',
                'ngo':        '🤝 NGO',
                'researcher': '📊 RESEARCHER',
            }.get(key_data['tier'], key_data['tier'])

            self.stdout.write(f"\n{tier_label} — {key_data['organisation']}")
            self.stdout.write(f"  Access key: {raw_key}")
            self.stdout.write(
                f"  Login URL: https://hakimkononi.onrender.com"
                f"/report-trafficking/dashboard/login/"
            )

        self.stdout.write("\n" + "=" * 65)
        self.stdout.write(f"\n✅ Demo complete:")
        self.stdout.write(f"   {len(created_reports)} reports created")
        self.stdout.write(f"   {alerts_created} alias match alert(s) created")
        self.stdout.write(f"   3 partner access keys created")
        self.stdout.write(
            f"\n⚠️  Save the access keys above — they cannot be recovered.\n"
        )


def _guess_alias_type(alias: str) -> str:
    """Simple heuristic to guess alias type from the text."""
    import re
    a = alias.lower().strip()
    # Phone number
    if re.match(r'^[\+0-9\s\-\(\)]{9,15}$', alias):
        return 'phone'
    # Vehicle plate (Kenyan format: KAA 123A or KBC 123X)
    if re.match(r'^[kK][a-zA-Z]{2}\s*\d{3}[a-zA-Z]$', alias):
        return 'vehicle_plate'
    # Facebook / social media
    if 'facebook' in a or 'fb:' in a or 'instagram' in a or 'tiktok' in a:
        return 'facebook_name'
    # Contains 'agency', 'company', 'ltd', 'agencies'
    if any(w in a for w in ['agency', 'agencies', 'company', 'ltd', 'enterprises', 'tours']):
        return 'organisation'
    # Starts with common titles → probably a nickname
    if any(a.startswith(p) for p in ['uncle', 'mama', 'baba', 'auntie', 'mzee', 'bae']):
        return 'nickname'
    return 'unknown'
