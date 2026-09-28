"""
Management command: load_constitution
Loads the core Constitution of Kenya 2010 Bill of Rights articles
directly as text, since the PDF uses a two-column layout that
pdfplumber cannot read correctly.

Usage:
    python manage.py load_constitution
    python manage.py load_constitution --overwrite
"""
from django.core.management.base import BaseCommand
from cases.models import Law

SOURCE_URL = "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/Constitution_of_Kenya_2010.pdf"
TITLE      = "Constitution of Kenya 2010"
CATEGORY   = "constitution"

ARTICLES = [
    {
        "section": "Article 19. Rights and fundamental freedoms",
        "content": (
            "(1) The Bill of Rights is an integral part of Kenya's democratic state and is the framework "
            "for social, economic and cultural policies.\n"
            "(2) The purpose of recognising and protecting human rights and fundamental freedoms is to "
            "preserve the dignity of individuals and communities and to promote social justice and the "
            "realisation of the potential of all human beings.\n"
            "(3) The rights and fundamental freedoms in the Bill of Rights—\n"
            "(a) belong to each individual and are not granted by the State;\n"
            "(b) do not exclude other rights and fundamental freedoms not in the Bill of Rights, but "
            "recognised or conferred by law, except to the extent that they are inconsistent with this "
            "Chapter; and\n"
            "(c) are subject only to the limitations contemplated in this Constitution."
        ),
    },
    {
        "section": "Article 20. Application of Bill of Rights",
        "content": (
            "(1) The Bill of Rights applies to all law and binds all State organs and all persons.\n"
            "(2) Every person shall enjoy the rights and fundamental freedoms in the Bill of Rights to "
            "the greatest extent consistent with the nature of the right or fundamental freedom.\n"
            "(3) In applying a provision of the Bill of Rights, a court shall—\n"
            "(a) develop the law to the extent that it does not give effect to a right or fundamental "
            "freedom; and\n"
            "(b) adopt the interpretation that most favours the enforcement of a right or fundamental "
            "freedom.\n"
            "(4) In interpreting the Bill of Rights, a court, tribunal or other authority shall promote—\n"
            "(a) the values that underlie an open and democratic society based on human dignity, "
            "equality, equity and freedom; and\n"
            "(b) the spirit, purport and objects of the Bill of Rights."
        ),
    },
    {
        "section": "Article 21. Implementation of rights and fundamental freedoms",
        "content": (
            "(1) It is a fundamental duty of the State and every State organ to observe, respect, "
            "protect, promote and fulfil the rights and fundamental freedoms in the Bill of Rights.\n"
            "(2) The State shall take legislative, policy and other measures, including the setting of "
            "standards, to achieve the progressive realisation of the rights guaranteed under Article 43.\n"
            "(3) All State organs and all public officers have the duty to address the needs of "
            "vulnerable groups within society, including women, older members of society, persons with "
            "disabilities, children, youth, members of minority or marginalised communities, and members "
            "of particular ethnic, religious or cultural communities."
        ),
    },
    {
        "section": "Article 26. Right to life",
        "content": (
            "(1) Every person has the right to life.\n"
            "(2) The life of a person begins at conception.\n"
            "(3) A person shall not be deprived of life intentionally, except to the extent authorised "
            "by this Constitution or other written law.\n"
            "(4) Abortion is not permitted unless, in the opinion of a trained health professional, "
            "there is need for emergency treatment, or the life or health of the mother is in danger, "
            "or if permitted by any other written law."
        ),
    },
    {
        "section": "Article 27. Equality and freedom from discrimination",
        "content": (
            "(1) Every person is equal before the law and has the right to equal protection and equal "
            "benefit of the law.\n"
            "(2) Equality includes the full and equal enjoyment of all rights and fundamental freedoms.\n"
            "(3) Women and men have the right to equal treatment, including the right to equal "
            "opportunities in political, economic, cultural and social spheres.\n"
            "(4) The State shall not discriminate directly or indirectly against any person on any "
            "ground, including race, sex, pregnancy, marital status, health status, ethnic or social "
            "origin, colour, age, disability, religion, conscience, belief, culture, dress, language "
            "or birth.\n"
            "(5) A person shall not discriminate directly or indirectly against another person on any "
            "of the grounds specified or contemplated in clause (4).\n"
            "(6) To give full effect to the realisation of the rights guaranteed under this Article, "
            "the State shall take legislative and other measures, including affirmative action "
            "programmes and policies designed to redress any disadvantage suffered by individuals or "
            "groups because of past discrimination."
        ),
    },
    {
        "section": "Article 28. Human dignity",
        "content": (
            "Every person has inherent dignity and the right to have that dignity respected and "
            "protected."
        ),
    },
    {
        "section": "Article 29. Freedom and security of the person",
        "content": (
            "Every person has the right to freedom and security of the person, which includes the "
            "right not to be—\n"
            "(a) deprived of freedom arbitrarily or without just cause;\n"
            "(b) detained without trial, except during a state of emergency, in which case the "
            "detention is subject to Article 58;\n"
            "(c) subjected to any form of violence from either public or private sources;\n"
            "(d) subjected to torture in any manner, whether physical or psychological;\n"
            "(e) subjected to corporal punishment; or\n"
            "(f) treated or punished in a cruel, inhuman or degrading manner."
        ),
    },
    {
        "section": "Article 31. Privacy",
        "content": (
            "Every person has the right to privacy, which includes the right not to have—\n"
            "(a) their person, home or property searched;\n"
            "(b) their possessions seized;\n"
            "(c) information relating to their family or private affairs unnecessarily required or "
            "revealed; or\n"
            "(d) the privacy of their communications infringed."
        ),
    },
    {
        "section": "Article 32. Freedom of conscience, religion, belief and opinion",
        "content": (
            "(1) Every person has the right to freedom of conscience, religion, thought, belief and "
            "opinion.\n"
            "(2) Every person has the right, either individually or in community with others, in public "
            "or in private, to manifest any religion or belief through worship, practice, teaching or "
            "observance, including observance of a day of worship.\n"
            "(3) A person may not be denied access to any institution, employment or facility, or the "
            "enjoyment of any right, because of the person's belief or religion.\n"
            "(4) A person shall not be compelled to act, or engage in any act, that is contrary to the "
            "person's belief or religion."
        ),
    },
    {
        "section": "Article 40. Protection of right to property",
        "content": (
            "(1) Subject to Article 65, every person has the right, either individually or in "
            "association with others, to acquire and own property—\n"
            "(a) of any description; and\n"
            "(b) in any part of Kenya.\n"
            "(2) Parliament shall not enact a law that permits the State or any person—\n"
            "(a) to arbitrarily deprive a person of property of any description or of any interest in, "
            "or right over, any property of any description; or\n"
            "(b) to limit, or in any way restrict the enjoyment of any right under this Article on "
            "the basis of any of the grounds specified or contemplated in Article 27(4).\n"
            "(3) The State shall not deprive a person of property of any description, or of any "
            "interest in, or right over, property of any description, unless the deprivation—\n"
            "(a) results from an acquisition of land or an interest in land or a conversion of an "
            "interest in land, or title to land, in accordance with Chapter Five; or\n"
            "(b) is for a public purpose or in the public interest and is carried out in accordance "
            "with this Constitution and any Act of Parliament that—\n"
            "(i) requires prompt payment in full, of just compensation to the person; and\n"
            "(ii) allows any person who has an interest in, or right over, that property a right of "
            "access to a court of law."
        ),
    },
    {
        "section": "Article 41. Labour relations",
        "content": (
            "(1) Every person has the right to fair labour practices.\n"
            "(2) Every worker has the right—\n"
            "(a) to fair remuneration;\n"
            "(b) to reasonable working conditions;\n"
            "(c) to form, join or participate in the activities and programmes of a trade union; and\n"
            "(d) to go on strike.\n"
            "(3) Every employer has the right—\n"
            "(a) to form and join an employers organisation; and\n"
            "(b) to participate in the activities and programmes of an employers organisation.\n"
            "(4) Every trade union and every employers' organisation has the right—\n"
            "(a) to determine its own administration, programmes and activities;\n"
            "(b) to organise; and\n"
            "(c) to form and join a federation.\n"
            "(5) Every trade union, employers' organisation and employer has the right to engage in "
            "collective bargaining."
        ),
    },
    {
        "section": "Article 43. Economic and social rights",
        "content": (
            "(1) Every person has the right—\n"
            "(a) to the highest attainable standard of health, which includes the right to health "
            "care services, including reproductive health care;\n"
            "(b) to accessible and adequate housing, and to reasonable standards of sanitation;\n"
            "(c) to be free from hunger, and to have adequate food of acceptable quality;\n"
            "(d) to clean and safe water in adequate quantities;\n"
            "(e) to social security; and\n"
            "(f) to education.\n"
            "(2) A person shall not be denied emergency medical treatment.\n"
            "(3) The State shall provide appropriate social security to persons who are unable to "
            "support themselves and their dependants."
        ),
    },
    {
        "section": "Article 45. Family",
        "content": (
            "(1) The family is the natural and fundamental unit of society and the necessary basis of "
            "social order, and shall enjoy the recognition and protection of the State.\n"
            "(2) Every adult has the right to marry a person of the opposite sex, based on the free "
            "consent of the parties.\n"
            "(3) Parties to a marriage are entitled to equal rights at the time of the marriage, "
            "during the marriage and at the dissolution of the marriage.\n"
            "(4) Parliament shall enact legislation that recognises—\n"
            "(a) marriages concluded under any tradition, or system of religious, personal or family "
            "law; and\n"
            "(b) any system of personal and family law under any tradition, or adhered to by persons "
            "professing a particular religion, to the extent that any such marriages or systems of "
            "law are consistent with this Constitution."
        ),
    },
    {
        "section": "Article 47. Fair administrative action",
        "content": (
            "(1) Every person has the right to administrative action that is expeditious, efficient, "
            "lawful, reasonable and procedurally fair.\n"
            "(2) If a right or fundamental freedom of a person has been or is likely to be adversely "
            "affected by administrative action, the person has the right to be given written reasons "
            "for the action.\n"
            "(3) Parliament shall enact legislation to give effect to the rights in clause (1) and "
            "that legislation shall—\n"
            "(a) provide for the review of administrative action by a court or, if appropriate, an "
            "independent and impartial tribunal; and\n"
            "(b) promote efficient administration."
        ),
    },
    {
        "section": "Article 49. Rights of arrested persons",
        "content": (
            "(1) An arrested person has the right—\n"
            "(a) to be informed promptly, in language that the person understands, of—\n"
            "(i) the reason for the arrest;\n"
            "(ii) the right to remain silent; and\n"
            "(iii) the consequences of not remaining silent;\n"
            "(b) to remain silent;\n"
            "(c) to communicate with an advocate, and other persons whose assistance is necessary;\n"
            "(d) not to be compelled to make any confession or admission that could be used in "
            "evidence against the person;\n"
            "(e) to be held separately from persons who are serving a sentence;\n"
            "(f) to be brought before a court as soon as reasonably possible, but not later than—\n"
            "(i) twenty-four hours after being arrested; or\n"
            "(ii) if the twenty-four hours ends outside ordinary court hours, or on a day that is not "
            "an ordinary court day, the end of the next court day;\n"
            "(g) at the first court appearance, to be charged or informed of the reason for the "
            "detention continuing, or to be released; and\n"
            "(h) to be released on bond or bail, on reasonable conditions, pending a charge or trial, "
            "unless there are compelling reasons not to be released.\n"
            "(2) A person shall not be remanded in custody for an offence if the offence is "
            "punishable by a fine only or by imprisonment for not more than six months."
        ),
    },
    {
        "section": "Article 50. Right to fair hearing",
        "content": (
            "(1) Every person has the right to have any dispute that can be resolved by the "
            "application of law decided in a fair and public hearing before a court or, if "
            "appropriate, another independent and impartial tribunal or body.\n"
            "(2) Every accused person has the right to a fair trial, which includes the right—\n"
            "(a) to be presumed innocent until the contrary is proved;\n"
            "(b) to be informed of the charge, with sufficient detail to answer it;\n"
            "(c) to have adequate time and facilities to prepare a defence;\n"
            "(d) to a public trial before a court established under this Constitution;\n"
            "(e) to have the trial begin and conclude without unreasonable delay;\n"
            "(f) to be present when being tried, unless the conduct of the accused person makes it "
            "impossible for the trial to proceed;\n"
            "(g) to choose, and be represented by, an advocate, and to be informed of this right "
            "promptly;\n"
            "(h) to have an advocate assigned to the accused person by the State and at State "
            "expense, if substantial injustice would otherwise result, and to be informed of this "
            "right promptly;\n"
            "(i) to remain silent, and not to testify during the proceedings;\n"
            "(j) to be informed in advance of the evidence the prosecution intends to rely on, and "
            "to have reasonable access to that evidence;\n"
            "(k) to adduce and challenge evidence;\n"
            "(l) to refuse to give self-incriminating evidence;\n"
            "(m) to have the assistance of an interpreter without payment if the accused person "
            "cannot understand the language used at the trial;\n"
            "(n) not to be convicted for an act or omission that at the time it was committed or "
            "omitted was not—\n"
            "(i) an offence in Kenya; or\n"
            "(ii) a crime under international law;\n"
            "(o) not to be tried for an offence in respect of an act or omission for which the "
            "accused person has previously been either acquitted or convicted;\n"
            "(p) to the benefit of the least severe of the prescribed punishments for an offence, "
            "if the prescribed punishment for the offence has been changed between the time that the "
            "offence was committed and the time of sentencing; and\n"
            "(q) if convicted, to appeal to, or apply for review by, a higher court as prescribed "
            "by law."
        ),
    },
    {
        "section": "Article 51. Rights of persons detained, held in custody or imprisoned",
        "content": (
            "(1) A person who is detained, held in custody or imprisoned under the law, retains all "
            "the rights and fundamental freedoms in the Bill of Rights, except to the extent that any "
            "particular right or fundamental freedom is clearly incompatible with the fact that the "
            "person is detained, held in custody or imprisoned.\n"
            "(2) A person who is detained or held in custody is entitled to petition for an order of "
            "habeas corpus.\n"
            "(3) Parliament shall enact legislation that—\n"
            "(a) provides for the humane treatment of persons detained, held in custody or "
            "imprisoned; and\n"
            "(b) takes into account the relevant international human rights instruments."
        ),
    },
    {
        "section": "Article 53. Rights of children",
        "content": (
            "(1) Every child has the right—\n"
            "(a) to a name and nationality from birth;\n"
            "(b) to free and compulsory basic education;\n"
            "(c) to basic nutrition, shelter and health care;\n"
            "(d) to be protected from abuse, neglect, harmful cultural practices, all forms of "
            "violence, inhuman treatment and punishment, and hazardous or exploitative labour;\n"
            "(e) to parental care and protection, which includes equal responsibility of the mother "
            "and father to provide for the child, whether or not the parents are, or have been, "
            "married; and\n"
            "(f) not to be detained, except as a measure of last resort, and when detained, to be "
            "held for the shortest appropriate period of time, separated from adults and in "
            "conditions that take account of the child's sex and best interests.\n"
            "(2) A child's best interests are of paramount importance in every matter concerning "
            "the child."
        ),
    },
    {
        "section": "Article 54. Rights of persons with disabilities",
        "content": (
            "(1) A person with any disability is entitled—\n"
            "(a) to be treated with dignity and respect and to be addressed and referred to in a "
            "manner that is not demeaning;\n"
            "(b) to access educational institutions and facilities for persons with disabilities "
            "that are integrated into society to the extent compatible with the interests of the "
            "person;\n"
            "(c) to reasonable access to all places, public transport and information;\n"
            "(d) to use Sign language, Braille or other appropriate means of communication; and\n"
            "(e) to access materials and devices to overcome constraints arising from the person's "
            "disability.\n"
            "(2) The State shall ensure the progressive implementation of the principle that at "
            "least five percent of the members of the public in elective and appointive bodies are "
            "persons with disabilities."
        ),
    },
    {
        "section": "Article 56. Minorities and marginalised groups",
        "content": (
            "The State shall put in place affirmative action programmes designed to ensure that "
            "minorities and marginalised groups—\n"
            "(a) participate and are represented in governance and other spheres of life;\n"
            "(b) are provided special opportunities in educational and economic fields;\n"
            "(c) are provided special opportunities for access to employment;\n"
            "(d) develop their cultural values, languages and practices; and\n"
            "(e) have reasonable access to water, health services and infrastructure."
        ),
    },
    {
        "section": "Article 57. Rights of older members of society",
        "content": (
            "The State shall take measures to ensure the rights of older persons—\n"
            "(a) to fully participate in the affairs of society;\n"
            "(b) to pursue their personal development;\n"
            "(c) to live in dignity and respect and be free from abuse; and\n"
            "(d) to receive reasonable care and assistance from their family and the State."
        ),
    },
]


class Command(BaseCommand):
    help = "Load Constitution of Kenya 2010 Bill of Rights articles into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Delete existing Constitution sections and reload all.',
        )

    def handle(self, *args, **options):
        overwrite = options['overwrite']

        if overwrite:
            deleted, _ = Law.objects.filter(title=TITLE).delete()
            self.stdout.write(f"Deleted {deleted} existing Constitution sections.")

        created = 0
        skipped = 0

        for art in ARTICLES:
            exists = Law.objects.filter(title=TITLE, section=art['section']).exists()
            if exists and not overwrite:
                skipped += 1
                continue

            Law.objects.create(
                title=TITLE,
                section=art['section'],
                content=art['content'],
                category=CATEGORY,
                source_url=SOURCE_URL,
                simple_swahili='',
                related_to='',
                embedding_json='',
            )
            created += 1
            self.stdout.write(f"  Created: {art['section'][:60]}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created {created} articles, skipped {skipped} (already exist).\n"
                f"Next: python manage.py build_embeddings"
            )
        )
