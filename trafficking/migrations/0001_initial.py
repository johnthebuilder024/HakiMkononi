"""
Initial migration for the trafficking app.

Creates:
  - TraffickingReport
  - TraffickingSuspect
  - TraffickingAccessKey
  - TraffickingAliasAlert
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # ── TraffickingReport ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='TraffickingReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('story_raw', models.TextField(
                    help_text='Original story as submitted — any language')),
                ('story_lang', models.CharField(
                    default='unknown', max_length=10,
                    help_text='Detected language: sw / en / sheng / unknown')),
                ('county_of_origin', models.CharField(
                    blank=True, max_length=100,
                    help_text='County where trafficking occurred / victim is from')),
                ('approximate_date', models.CharField(
                    blank=True, max_length=50,
                    help_text="Approximate date as entered e.g. 'October 2026'")),
                ('is_urgent', models.BooleanField(
                    default=False,
                    help_text='Victim currently being held — requires immediate action')),
                ('reporter_contact', models.TextField(
                    blank=True,
                    help_text='Phone or email — optional, may be blank if anonymous')),
                ('is_anonymous', models.BooleanField(
                    default=True,
                    help_text='True if reporter chose not to provide contact')),
                ('report_type', models.CharField(
                    choices=[
                        ('labour',   'Labour Trafficking'),
                        ('sexual',   'Sexual Exploitation'),
                        ('domestic', 'Domestic Servitude'),
                        ('child',    'Child Trafficking'),
                        ('unknown',  'Unknown / Other'),
                    ],
                    default='unknown', max_length=20)),
                ('recruitment_method', models.CharField(
                    choices=[
                        ('social_media',   'Social Media (Facebook, WhatsApp, TikTok)'),
                        ('job_offer',      'Fake Job Offer'),
                        ('romance',        'Romance / Relationship'),
                        ('family_member',  'Family Member Involved'),
                        ('broker',         'Agent / Broker'),
                        ('unknown',        'Unknown'),
                    ],
                    default='unknown', max_length=30)),
                ('indicators', models.JSONField(
                    blank=True, default=list,
                    help_text='List of indicator codes extracted by AI')),
                ('victim_profile', models.CharField(
                    choices=[
                        ('adult_female', 'Adult Female'),
                        ('adult_male',   'Adult Male'),
                        ('minor_female', 'Minor (Female, under 18)'),
                        ('minor_male',   'Minor (Male, under 18)'),
                        ('unknown',      'Unknown'),
                    ],
                    default='unknown', max_length=20)),
                ('destination', models.CharField(
                    blank=True, max_length=200,
                    help_text="Destination country or county e.g. 'Dubai' or 'Nairobi'")),
                ('formal_report_en', models.TextField(
                    blank=True,
                    help_text='AI-generated formal report in English for DCI submission')),
                ('formal_report_sw', models.TextField(
                    blank=True,
                    help_text='AI-generated formal report in Swahili')),
                ('status', models.CharField(
                    choices=[
                        ('new',          '🆕 New — awaiting AI processing'),
                        ('processing',   '⏳ Processing'),
                        ('ready',        '✅ Ready for review'),
                        ('under_review', '👁️ Under review'),
                        ('actioned',     '⚡ Actioned'),
                        ('closed',       '🔒 Closed'),
                        ('false_report', '❌ False / Spam'),
                    ],
                    default='new', max_length=15)),
                ('status_note', models.TextField(
                    blank=True,
                    help_text='Internal note from reviewing partner')),
                ('reviewed_by', models.CharField(
                    blank=True, max_length=200,
                    help_text='Organisation that reviewed this report')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('has_linked_reports', models.BooleanField(
                    default=False,
                    help_text='True if a suspect alias in this report also appears in another')),
                ('ip_hash', models.CharField(
                    blank=True, max_length=64,
                    help_text='SHA256 of submitter IP — for rate limiting only')),
                ('reference_number', models.CharField(
                    blank=True, max_length=20, unique=True,
                    help_text='e.g. TIP-2026-0042')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Trafficking Report',
                'verbose_name_plural': 'Trafficking Reports',
                'ordering': ['-is_urgent', '-created_at'],
            },
        ),

        # ── TraffickingSuspect ────────────────────────────────────────────────
        migrations.CreateModel(
            name='TraffickingSuspect',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('report', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='suspects',
                    to='trafficking.traffickingreport')),
                ('alias', models.CharField(
                    max_length=300,
                    help_text='Exact alias as mentioned in the report')),
                ('alias_type', models.CharField(
                    choices=[
                        ('nickname',     'Nickname / Street name'),
                        ('phone',        'Phone number'),
                        ('facebook_name','Facebook / WhatsApp name'),
                        ('real_name',    'Real name'),
                        ('vehicle_plate','Vehicle plate'),
                        ('organisation', 'Organisation / Agency'),
                        ('unknown',      'Unknown type'),
                    ],
                    default='unknown', max_length=20)),
                ('alias_normalized', models.CharField(
                    blank=True, max_length=300,
                    help_text='Lowercase, stripped — used for cross-report matching')),
                ('county_context', models.CharField(
                    blank=True, max_length=100,
                    help_text='County where this person was operating, if known')),
                ('confidence', models.CharField(
                    choices=[
                        ('high',   'High — AI is confident this is a real identifier'),
                        ('medium', 'Medium — possible, needs review'),
                        ('low',    'Low — uncertain'),
                    ],
                    default='medium', max_length=10)),
                ('linked_to', models.ManyToManyField(
                    blank=True,
                    related_name='linked_to',
                    to='trafficking.traffickingsuspect',
                    help_text='Suspects from other reports with the same alias')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Suspect / Alias',
                'verbose_name_plural': 'Suspects / Aliases',
                'ordering': ['-created_at'],
            },
        ),

        # ── TraffickingAccessKey ──────────────────────────────────────────────
        migrations.CreateModel(
            name='TraffickingAccessKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('organisation', models.CharField(
                    max_length=200,
                    help_text="e.g. 'HAART Kenya', 'DCI Anti-HT Unit'")),
                ('tier', models.CharField(
                    choices=[
                        ('police',     '🚔 Police / DCI — full access'),
                        ('ngo',        '🤝 NGO Partner — full reports, no anonymous contact'),
                        ('researcher', '📊 Researcher — anonymised stats only'),
                    ],
                    max_length=15)),
                ('access_key_hash', models.CharField(
                    max_length=128,
                    help_text='SHA256 of the access key — never store plain text')),
                ('county_filter', models.CharField(
                    blank=True, max_length=100,
                    help_text='If set, this partner only sees reports from this county')),
                ('can_update_status', models.BooleanField(
                    default=True,
                    help_text='Can this partner update report status?')),
                ('email_alerts', models.EmailField(
                    blank=True,
                    help_text='Send urgent alerts and alias match alerts to this email')),
                ('active', models.BooleanField(default=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Partner Access Key',
                'verbose_name_plural': 'Partner Access Keys',
                'ordering': ['tier', 'organisation'],
            },
        ),

        # ── TraffickingAliasAlert ─────────────────────────────────────────────
        migrations.CreateModel(
            name='TraffickingAliasAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('alias', models.CharField(
                    max_length=300,
                    help_text='The alias that matched')),
                ('match_type', models.CharField(
                    choices=[
                        ('exact', 'Exact match — same normalized alias'),
                        ('fuzzy', 'Fuzzy match — similar alias (edit distance ≤ 2)'),
                        ('phone', 'Phone match — same number, different format'),
                    ],
                    default='exact', max_length=10)),
                ('report_new', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alias_alerts_new',
                    to='trafficking.traffickingreport',
                    help_text='The newer report that triggered the match')),
                ('report_previous', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alias_alerts_previous',
                    to='trafficking.traffickingreport',
                    help_text='The earlier report the alias was found in')),
                ('suspect_new', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alerts_as_new',
                    to='trafficking.traffickingsuspect')),
                ('suspect_previous', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alerts_as_previous',
                    to='trafficking.traffickingsuspect')),
                ('alert_sent', models.BooleanField(default=False,
                    help_text='Email alert sent to DCI/NGO')),
                ('alert_sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Alias Match Alert',
                'verbose_name_plural': 'Alias Match Alerts',
                'ordering': ['-created_at'],
            },
        ),
    ]
