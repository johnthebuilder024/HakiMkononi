"""
Management command: learning_loop

Runs weekly. Reads the last 7 days of 👎 (thumbs-down) answers and:

1. Counts failures by law category (employment, land, criminal, etc.)
2. For categories with a high failure rate (>25%), logs a clear warning
   so you can investigate and fix the prompts or RAG boosting
3. Promotes human corrections (admin-entered correct_section) into the
   Law DB as new "Correction" entries — so RAG will return them next time
   someone asks a similar question
4. Generates Gemini embeddings for those new correction entries
5. Invalidates the RAG cache so corrections are live immediately

The learning loop does NOT auto-change the system prompt (that would require
human judgment). It surfaces the data so you can act, and immediately promotes
admin corrections into the live knowledge base.

Usage:
  python manage.py learning_loop            # last 7 days
  python manage.py learning_loop --days 14  # last 14 days
  python manage.py learning_loop --dry-run  # show what would happen, save nothing

Render cron (already in render.yaml):
  schedule: "0 3 * * 0"   # 3am Nairobi every Sunday
"""

import logging
from datetime import timedelta
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

# If this fraction of answers in a category are 👎, flag it as broken
FAILURE_RATE_THRESHOLD = 0.25   # 25%
# Minimum answers before we report on a category (avoids noise from 1 answer)
MIN_ANSWERS_TO_REPORT  = 3


class Command(BaseCommand):
    help = "Weekly learning loop: analyse 👎 answers, promote admin corrections into the law DB"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=7,
            help='Analyse answers from the last N days (default: 7)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would happen without saving anything'
        )

    def handle(self, *args, **options):
        from cases.models import Query, Law

        days    = options['days']
        dry_run = options['dry_run']
        since   = timezone.now() - timedelta(days=days)

        self.stdout.write(
            f"\n[learning_loop] Analysing last {days} days of feedback "
            f"(since {since.strftime('%Y-%m-%d %H:%M')} UTC)"
        )
        if dry_run:
            self.stdout.write("  DRY RUN — no changes will be saved\n")

        # ── 1. Load answered queries with feedback ─────────────────────────────
        qs = (
            Query.objects
            .filter(created_at__gte=since)
            .exclude(was_helpful=None)  # only queries with actual feedback
            .prefetch_related('laws_used')
        )

        total_with_feedback = qs.count()
        if total_with_feedback == 0:
            self.stdout.write(
                "[learning_loop] No feedback found in this period. "
                "Either no users gave feedback, or the period is too short."
            )
            return

        thumbs_up   = qs.filter(was_helpful=True).count()
        thumbs_down = qs.filter(was_helpful=False).count()
        overall_rate = round(thumbs_up / total_with_feedback * 100)

        self.stdout.write(
            f"\n📊 Overall satisfaction: {thumbs_up}/{total_with_feedback} helpful "
            f"({overall_rate}%) | {thumbs_down} 👎"
        )

        # ── 2. Break down 👎 by category ──────────────────────────────────────
        category_counts = defaultdict(lambda: {'up': 0, 'down': 0})

        for q in qs:
            # Determine the dominant category from laws_used
            categories = [law.category for law in q.laws_used.all()]
            if categories:
                # Use the most common category in this query's sources
                dominant = max(set(categories), key=categories.count)
            else:
                dominant = 'unknown'

            if q.was_helpful:
                category_counts[dominant]['up'] += 1
            else:
                category_counts[dominant]['down'] += 1

        self.stdout.write("\n📉 Failure rate by category:")
        broken_categories = []
        for cat, counts in sorted(category_counts.items()):
            total_cat = counts['up'] + counts['down']
            if total_cat < MIN_ANSWERS_TO_REPORT:
                continue
            fail_rate = counts['down'] / total_cat
            flag = " ⚠️  HIGH FAILURE — REVIEW NEEDED" if fail_rate > FAILURE_RATE_THRESHOLD else ""
            self.stdout.write(
                f"  {cat:20s}  👍 {counts['up']}  👎 {counts['down']}  "
                f"({round(fail_rate*100)}% fail){flag}"
            )
            if fail_rate > FAILURE_RATE_THRESHOLD:
                broken_categories.append((cat, round(fail_rate*100), counts['down']))

        if broken_categories:
            self.stdout.write("\n⚠️  Categories needing attention:")
            for cat, rate, n in broken_categories:
                self.stdout.write(
                    f"  • {cat}: {rate}% failure rate ({n} wrong answers in last {days} days)"
                )
            self.stdout.write(
                "\n  Action: Go to /dashboard/, review the 👎 answers for these categories,\n"
                "  add correct_section corrections, and re-run this command to promote them."
            )
        else:
            self.stdout.write("\n  ✅ All categories within acceptable failure rate.")

        # ── 3. Promote admin corrections into the law DB ──────────────────────
        # Any 👎 query where an admin entered a correct_section is treated as
        # a "ground truth" correction. We add it to the Law DB so RAG returns
        # the correct section next time someone asks a similar question.

        corrections_qs = Query.objects.filter(
            was_helpful=False,
            review_status='fixed',
        ).exclude(correct_section='').exclude(answer_law='')

        self.stdout.write(
            f"\n🔧 Admin corrections to promote: {corrections_qs.count()} entries"
        )

        promoted  = 0
        skipped   = 0

        for q in corrections_qs:
            # Use the original question as the content — RAG embeds it so
            # similar future questions match this correction
            correction_title   = q.correct_section.strip()[:200]
            correction_section = "Admin Correction"
            correction_content = (
                f"Correction: For the question '{q.story[:200]}', "
                f"the correct answer is: {q.correct_section.strip()}"
            )

            # Don't add duplicates
            already = Law.objects.filter(
                title=correction_title,
                section=correction_section,
                content__startswith=correction_content[:80],
            ).exists()

            if already:
                skipped += 1
                continue

            # Determine category from the laws_used on this query
            used_cats = [law.category for law in q.laws_used.all()]
            category  = max(set(used_cats), key=used_cats.count) if used_cats else 'other'

            if not dry_run:
                Law.objects.create(
                    title=correction_title,
                    section=correction_section,
                    content=correction_content[:2000],
                    category=category,
                    source_url='',  # internal correction — no external source
                )

            promoted += 1
            self.stdout.write(f"  + Promoted correction: {correction_title[:80]}")

        self.stdout.write(
            f"\n[learning_loop] Corrections: {promoted} promoted, {skipped} already existed"
        )

        # ── 4. Embed promoted corrections ─────────────────────────────────────
        if promoted > 0 and not dry_run:
            self.stdout.write("[learning_loop] Generating embeddings for promoted corrections...")
            try:
                import time as _time
                from cases.rag import embed_text, invalidate_law_cache

                unembedded = Law.objects.filter(embedding_json='').exclude(content='')
                count  = 0
                failed = 0

                for law in unembedded:
                    embed_input = f"{law.title} {law.section}: {law.content}"
                    try:
                        vec = embed_text(embed_input)
                        if vec:
                            law.set_embedding(vec)
                            law.save(update_fields=['embedding_json'])
                            count += 1
                            _time.sleep(0.2)
                    except Exception as e:
                        failed += 1
                        logger.warning(f"Embedding failed for Law #{law.pk}: {e}")

                self.stdout.write(
                    f"[learning_loop] Embedded {count} corrections ({failed} failed)"
                )

                # Invalidate cache so next query picks up the corrections immediately
                invalidate_law_cache()
                self.stdout.write("[learning_loop] ✅ RAG cache invalidated — corrections are live")

            except Exception as e:
                self.stderr.write(f"[learning_loop] Embedding error: {e}")

        # ── 5. Summary report ─────────────────────────────────────────────────
        self.stdout.write(f"""
╔══════════════════════════════════════════════════════════╗
║  HakiMkononi Learning Loop — Weekly Report               ║
╠══════════════════════════════════════════════════════════╣
║  Period:          Last {days} days                             
║  Total feedback:  {total_with_feedback}
║  Satisfaction:    {overall_rate}%  ({thumbs_up} 👍 / {thumbs_down} 👎)
║  Corrections promoted: {promoted}
║  Categories flagged:   {len(broken_categories)}
╚══════════════════════════════════════════════════════════╝
""")

        if broken_categories:
            self.stdout.write(
                "  Next step: review /dashboard/ for the flagged categories above.\n"
                "  Enter correct_section for bad answers, mark review_status = fixed,\n"
                "  then run: python manage.py learning_loop\n"
            )
