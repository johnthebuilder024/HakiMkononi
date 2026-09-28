"""
Load all slang/vernacular keywords into the SlangKeyword database table.
Run once: python manage.py load_slang

After this you manage keywords entirely from the Django admin panel at /admin/
"""

from django.core.management.base import BaseCommand
from cases.models import SlangKeyword


KEYWORDS = [
    # ── Employment / Job ─────────────────────────────────────────────────────
    # English
    ('fired',            'employment', 'en',    'Dismissed from job'),
    ('dismissed',        'employment', 'en',    ''),
    ('redundancy',       'employment', 'en',    ''),
    ('retrenchment',     'employment', 'en',    ''),
    ('resign',           'employment', 'en',    ''),
    ('probation',        'employment', 'en',    ''),
    ('overtime',         'employment', 'en',    ''),
    ('salary',           'employment', 'en',    ''),
    ('wages',            'employment', 'en',    ''),
    ('employer',         'employment', 'en',    ''),
    ('employee',         'employment', 'en',    ''),
    ('termination',      'employment', 'en',    ''),
    ('contract',         'employment', 'en',    ''),
    # Swahili
    ('mwajiri',          'employment', 'sw',    'Employer'),
    ('mfanyakazi',       'employment', 'sw',    'Employee'),
    ('mshahara',         'employment', 'sw',    'Salary'),
    ('kuachishwa',       'employment', 'sw',    'Dismissed'),
    ('likizo',           'employment', 'sw',    'Leave'),
    ('mkataba',          'employment', 'sw',    'Contract'),
    ('mishahara',        'employment', 'sw',    'Wages'),
    ('malipo',           'employment', 'sw',    'Payment'),
    # Sheng
    ('boss',             'employment', 'sheng', 'Boss/employer in Sheng'),
    ('job',              'employment', 'sheng', 'Job/work in Sheng'),
    ('kulipwa',          'employment', 'sheng', 'To be paid'),
    ('alifutwa',         'employment', 'sheng', 'Was fired (Sheng)'),
    ('alifukuzwa',       'employment', 'sheng', 'Was fired (Sheng)'),
    ('nilifutwa',        'employment', 'sheng', 'I was fired'),
    ('nilifukuzwa',      'employment', 'sheng', 'I was fired'),
    ('alinifukuza',      'employment', 'sheng', 'He/she fired me'),
    ('hakulipa',         'employment', 'sheng', 'Did not pay'),
    ('hawakumulipa',     'employment', 'sheng', 'They did not pay'),

    # ── Criminal / Police / Arrest ───────────────────────────────────────────
    # English
    ('arrested',         'criminal', 'en',    ''),
    ('police',           'criminal', 'en',    ''),
    ('warrant',          'criminal', 'en',    ''),
    ('bail',             'criminal', 'en',    ''),
    ('detained',         'criminal', 'en',    ''),
    ('custody',          'criminal', 'en',    ''),
    ('rights',           'criminal', 'en',    'Rights not read'),
    ('handcuffed',       'criminal', 'en',    ''),
    ('locked up',        'criminal', 'en',    ''),
    ('cell',             'criminal', 'en',    'Police cell'),
    ('station',          'criminal', 'en',    'Police station'),
    # Swahili
    ('polisi',           'criminal', 'sw',    'Police in Swahili'),
    ('askari',           'criminal', 'sw',    'Officer/guard in Swahili'),
    ('afande',           'criminal', 'sw',    'Officer (respectful)'),
    ('dhamana',          'criminal', 'sw',    'Bail'),
    ('mashtaka',         'criminal', 'sw',    'Charges/prosecution'),
    ('kizuizini',        'criminal', 'sw',    'In detention'),
    ('kushikwa',         'criminal', 'sw',    'To be arrested'),
    ('kukamatwa',        'criminal', 'sw',    'To be arrested'),
    ('kushtakiwa',       'criminal', 'sw',    'To be charged'),
    ('gereza',           'criminal', 'sw',    'Prison'),
    # Sheng — police slang
    ('karao',            'criminal', 'sheng', 'Sheng for police officer'),
    ('karau',            'criminal', 'sheng', 'Sheng for police officer (variant)'),
    ('sanse',            'criminal', 'sheng', 'Sheng for police officer'),
    ('makarao',          'criminal', 'sheng', 'Sheng for police (plural)'),
    ('ma-karao',         'criminal', 'sheng', 'Sheng for police (plural)'),
    ('kanjo',            'criminal', 'sheng', 'City council officers'),
    # Sheng — arrest/detention
    ('amenishika',       'criminal', 'sheng', 'He/she arrested me'),
    ('walinishika',      'criminal', 'sheng', 'They arrested me'),
    ('wamenishika',      'criminal', 'sheng', 'They have arrested me'),
    ('kunishika',        'criminal', 'sheng', 'To arrest me'),
    ('seleli',           'criminal', 'sheng', 'Sheng for jail cell'),
    ('ndani ya seleli',  'criminal', 'sheng', 'Inside a cell'),
    ('lock-up',          'criminal', 'sheng', 'Police lock-up'),
    # Sheng — rights not read
    ('hawakusomea',      'criminal', 'sheng', 'They did not read me my rights'),
    ('hawakuambia',      'criminal', 'sheng', 'They did not tell me'),
    ('hawakunitajia',    'criminal', 'sheng', 'They did not mention to me'),
    ('rights zangu',     'criminal', 'sheng', 'My rights (Sheng mix)'),
    ('haki zangu',       'criminal', 'sheng', 'My rights'),
    ('miranda',          'criminal', 'any',   'Miranda rights reference'),

    # ── Land / Landlord / Tenant ─────────────────────────────────────────────
    # English
    ('landlord',         'land', 'en',    ''),
    ('tenant',           'land', 'en',    ''),
    ('eviction',         'land', 'en',    ''),
    ('rent',             'land', 'en',    ''),
    ('lease',            'land', 'en',    ''),
    ('title deed',       'land', 'en',    ''),
    ('lock out',         'land', 'en',    'Landlord locked out tenant'),
    # Swahili
    ('ardhi',            'land', 'sw',    'Land'),
    ('mpangaji',         'land', 'sw',    'Tenant'),
    ('pango',            'land', 'sw',    'Rent'),
    ('mmiliki',          'land', 'sw',    'Owner/landlord'),
    ('kiwanja',          'land', 'sw',    'Plot of land'),
    ('hati',             'land', 'sw',    'Title deed'),
    # Sheng
    ('amenifunga',       'land', 'sheng', 'Landlord locked me out'),
    ('alinifunga',       'land', 'sheng', 'Landlord locked me out'),
    ('kupigwa lock',     'land', 'sheng', 'Locked out'),
    ('kodi',             'land', 'sheng', 'Rent (Sheng/Swahili mix)'),
    ('mwenye nyumba',    'land', 'sw',    'House owner/landlord'),

    # ── Family / Marriage / Divorce ──────────────────────────────────────────
    # English
    ('divorce',          'family', 'en',    ''),
    ('marriage',         'family', 'en',    ''),
    ('custody',          'family', 'en',    'Child custody'),
    ('inheritance',      'family', 'en',    ''),
    ('succession',       'family', 'en',    ''),
    ('domestic violence','family', 'en',    ''),
    ('spouse',           'family', 'en',    ''),
    # Swahili
    ('talaka',           'family', 'sw',    'Divorce'),
    ('ndoa',             'family', 'sw',    'Marriage'),
    ('mirathi',          'family', 'sw',    'Inheritance'),
    ('urithi',           'family', 'sw',    'Inheritance/succession'),
    ('ulezi',            'family', 'sw',    'Child custody'),
    ('jeuri ya nyumbani','family', 'sw',    'Domestic violence'),
    # Sheng
    ('dem wangu',        'family', 'sheng', 'My girlfriend/wife (Sheng)'),
    ('buda wangu',       'family', 'sheng', 'My husband/man (Sheng)'),
    ('watoto wangu',     'family', 'sheng', 'My children'),
    ('mali yetu',        'family', 'sheng', 'Our shared property'),
    ('anaficha mali',    'family', 'sheng', 'Hiding shared assets'),
]


class Command(BaseCommand):
    help = 'Load all slang keywords into the SlangKeyword database table'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        skipped = 0

        for word, topic, language, notes in KEYWORDS:
            word_lower = word.lower().strip()
            obj, was_created = SlangKeyword.objects.update_or_create(
                word=word_lower,
                defaults={
                    'topic':    topic,
                    'language': language,
                    'notes':    notes,
                    'active':   True,
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done! Created: {created} | Updated: {updated} | "
            f"Total in DB: {SlangKeyword.objects.count()}"
        ))
        self.stdout.write(
            "You can now manage keywords at: http://127.0.0.1:8000/admin/cases/slangkeyword/"
        )
