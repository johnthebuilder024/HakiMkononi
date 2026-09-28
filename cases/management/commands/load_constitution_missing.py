"""
Management command: load_constitution_missing
Adds the 20 Constitution of Kenya 2010 articles that were not in
the original load_constitution command.

Usage:
    python manage.py load_constitution_missing
"""
from django.core.management.base import BaseCommand
from cases.models import Law

SOURCE_URL = "https://new.kenyalaw.org/akn/ke/act/2010/constitution/eng@2010-09-03"
TITLE      = "Constitution of Kenya 2010"
CATEGORY   = "constitution"

ARTICLES = [
    {
        "section": "Article 22. Enforcement of Bill of Rights",
        "content": (
            "(1) Every person has the right to institute court proceedings claiming that a right or "
            "fundamental freedom in the Bill of Rights has been denied, violated or infringed, or is "
            "threatened.\n"
            "(2) In addition to a person acting in their own interest, court proceedings under clause "
            "(1) may be instituted by—\n"
            "(a) a person acting on behalf of another person who cannot act in their own name;\n"
            "(b) a person acting as a member of, or in the interest of, a group or class of persons;\n"
            "(c) a person acting in the public interest; or\n"
            "(d) an association acting in the interest of one or more of its members.\n"
            "(3) The Chief Justice shall make rules providing for the court proceedings referred to in "
            "this Article, which shall satisfy the criteria that—\n"
            "(a) the rights of standing provided for in clause (2) are fully facilitated;\n"
            "(b) formalities relating to the proceedings, including commencement of the proceedings, "
            "are kept to the minimum, and in particular that the court shall, if necessary, entertain "
            "proceedings on the basis of informal documentation;\n"
            "(c) no fee may be charged for commencing the proceedings;\n"
            "(d) the court, while observing the rules of natural justice, shall not be unreasonably "
            "restricted by procedural technicalities; and\n"
            "(e) an organisation or individual with particular expertise may, with the leave of the "
            "court, appear as a friend of the court."
        ),
    },
    {
        "section": "Article 23. Authority of courts to uphold and enforce the Bill of Rights",
        "content": (
            "(1) The High Court has jurisdiction, in accordance with Article 165, to hear and determine "
            "applications for redress of a denial, violation or infringement of, or threat to, a right "
            "or fundamental freedom in the Bill of Rights.\n"
            "(2) Parliament shall enact legislation to give original jurisdiction in appropriate cases "
            "to subordinate courts to hear and determine applications for redress of a denial, "
            "violation or infringement of, or threat to, a right or fundamental freedom in the "
            "Bill of Rights.\n"
            "(3) In any proceedings brought under Article 22, a court may grant appropriate relief, "
            "including—\n"
            "(a) a declaration of rights;\n"
            "(b) an injunction;\n"
            "(c) a conservatory order;\n"
            "(d) a declaration of invalidity of any law that denies, violates, infringes, or threatens "
            "a right or fundamental freedom in the Bill of Rights and is not justified under Article 24;\n"
            "(e) an order for compensation; and\n"
            "(f) an order of judicial review."
        ),
    },
    {
        "section": "Article 24. Limitation of rights and fundamental freedoms",
        "content": (
            "(1) A right or fundamental freedom in the Bill of Rights shall not be limited except by "
            "law, and then only to the extent that the limitation is reasonable and justifiable in an "
            "open and democratic society based on human dignity, equality and freedom, taking into "
            "account all relevant factors, including—\n"
            "(a) the nature of the right or fundamental freedom;\n"
            "(b) the importance of the purpose of the limitation;\n"
            "(c) the nature and extent of the limitation;\n"
            "(d) the need to ensure that the enjoyment of rights and fundamental freedoms by any "
            "individual does not prejudice the rights and fundamental freedoms of others; and\n"
            "(e) the relation between the limitation and its purpose and whether there are less "
            "restrictive means to achieve the purpose.\n"
            "(2) Despite clause (1), a provision in legislation limiting a right or fundamental "
            "freedom—\n"
            "(a) in the case of a provision enacted or amended on or after the effective date, is not "
            "valid unless the legislation specifically expresses the intention to limit that right or "
            "fundamental freedom, and the nature and extent of the limitation;\n"
            "(b) shall not be construed as limiting the right or fundamental freedom unless the "
            "provision is clear and specific about the right or freedom to be limited and the nature "
            "and extent of the limitation; and\n"
            "(c) shall not limit the right or fundamental freedom so far as to derogate from its "
            "core or essential content.\n"
            "(3) The State or a person seeking to justify a particular limitation shall demonstrate "
            "to the satisfaction of the court—\n"
            "(a) the existence of a legitimate purpose for the limitation; and\n"
            "(b) that the limitation is necessary in an open and democratic society."
        ),
    },
    {
        "section": "Article 25. Fundamental rights and freedoms that may not be limited",
        "content": (
            "Despite any other provision in this Constitution, the following rights and fundamental "
            "freedoms shall not be limited—\n"
            "(a) freedom from torture and cruel, inhuman or degrading treatment or punishment;\n"
            "(b) freedom from slavery or servitude;\n"
            "(c) the right to a fair trial;\n"
            "(d) the right to an order of habeas corpus."
        ),
    },
    {
        "section": "Article 30. Use of language and participation in cultural life",
        "content": (
            "(1) Every person has the right to use the language, and to participate in the cultural "
            "life, of the person's choice.\n"
            "(2) A person belonging to a cultural or linguistic community has the right, with other "
            "members of that community—\n"
            "(a) to enjoy the person's culture and use the person's language; or\n"
            "(b) to form, join and maintain cultural and linguistic associations and other organs of "
            "civil society."
        ),
    },
    {
        "section": "Article 33. Freedom of expression",
        "content": (
            "(1) Every person has the right to freedom of expression, which includes—\n"
            "(a) freedom to seek, receive or impart information or ideas;\n"
            "(b) freedom of artistic creativity; and\n"
            "(c) academic freedom and freedom of scientific research.\n"
            "(2) The right to freedom of expression does not extend to—\n"
            "(a) propaganda for war;\n"
            "(b) incitement to violence;\n"
            "(c) hate speech; or\n"
            "(d) advocacy of hatred that—\n"
            "(i) constitutes ethnic incitement, vilification of others or incitement to cause harm; or\n"
            "(ii) is based on any ground of discrimination specified or contemplated in Article 27(4).\n"
            "(3) In the exercise of the right to freedom of expression, every person shall respect "
            "the rights and reputation of others."
        ),
    },
    {
        "section": "Article 34. Freedom and independence of the media",
        "content": (
            "(1) Freedom and independence of electronic, print and all other types of media is "
            "guaranteed, but does not extend to any expression specified in Article 33(2).\n"
            "(2) The State shall not—\n"
            "(a) exercise control over or interfere with any person engaged in broadcasting, the "
            "production of publications, or the dissemination of information by any medium; or\n"
            "(b) penalise any person for any opinion or view or the content of any broadcast, "
            "publication or dissemination.\n"
            "(3) Broadcasting and other electronic media have freedom of establishment, subject only "
            "to licensing procedures that—\n"
            "(a) are necessary to regulate the airwaves and other forms of signal distribution; and\n"
            "(b) are independent of control by government, political interests or commercial interests."
        ),
    },
    {
        "section": "Article 35. Access to information",
        "content": (
            "(1) Every citizen has the right of access to—\n"
            "(a) information held by the State; and\n"
            "(b) information held by another person and required for the exercise or protection of "
            "any right or fundamental freedom.\n"
            "(2) Every person has the right to the correction or deletion of untrue or misleading "
            "information that affects the person.\n"
            "(3) The State shall publish and publicise any important information affecting the nation."
        ),
    },
    {
        "section": "Article 36. Freedom of association",
        "content": (
            "(1) Every person has the right to freedom of association, which includes the right to "
            "form, join or participate in the activities of an association of any kind.\n"
            "(2) A person shall not be compelled to join an association of any kind.\n"
            "(3) Any legislation that requires registration of an association of any kind shall "
            "provide that—\n"
            "(a) registration may not be withheld or withdrawn unreasonably; and\n"
            "(b) there is a right to have a fair hearing before registration is withdrawn."
        ),
    },
    {
        "section": "Article 37. Assembly, demonstration, picketing and petition",
        "content": (
            "Every person has the right, peaceably and unarmed, to assemble, to demonstrate, to "
            "picket, and to present petitions to public authorities."
        ),
    },
    {
        "section": "Article 38. Political rights",
        "content": (
            "(1) Every citizen is free to make political choices, which includes the right—\n"
            "(a) to form, or participate in forming, a political party;\n"
            "(b) to participate in the activities of, or recruit members for, a political party; and\n"
            "(c) to campaign for a political party or cause.\n"
            "(2) Every citizen has the right to free, fair and regular elections based on universal "
            "suffrage and the free expression of the will of the electors for—\n"
            "(a) any elective public body or office established under this Constitution; and\n"
            "(b) any office of any political party of which the citizen is a member.\n"
            "(3) Every adult citizen has the right, without unreasonable restrictions—\n"
            "(a) to be registered as a voter;\n"
            "(b) to vote by secret ballot in any election or referendum; and\n"
            "(c) to be a candidate for public office, or office within a political party of which the "
            "citizen is a member and, if elected, to hold office."
        ),
    },
    {
        "section": "Article 39. Freedom of movement and residence",
        "content": (
            "(1) Every person has the right to move freely.\n"
            "(2) Every person has the right to leave Kenya.\n"
            "(3) Every citizen has the right to enter, remain in and reside anywhere in Kenya.\n"
            "(4) Every citizen has the right to a passport and other travel documents."
        ),
    },
    {
        "section": "Article 42. Environment",
        "content": (
            "Every person has the right to a clean and healthy environment, which includes the right—\n"
            "(a) to have the environment protected for the benefit of present and future generations "
            "through legislative and other measures, particularly those contemplated in Article 69; and\n"
            "(b) to have obligations relating to the environment fulfilled under Article 70."
        ),
    },
    {
        "section": "Article 44. Language and culture",
        "content": (
            "(1) Every person has the right to use the language of the person's choice.\n"
            "(2) A person belonging to a cultural or linguistic community has the right, with other "
            "members of that community—\n"
            "(a) to enjoy that person's culture and use that person's language; or\n"
            "(b) to form, join and maintain associations and other organs of civil society.\n"
            "(3) A person shall not compel another person to perform, observe or undergo any cultural "
            "practice or rite."
        ),
    },
    {
        "section": "Article 46. Consumer rights",
        "content": (
            "(1) Consumers have the right—\n"
            "(a) to goods and services of reasonable quality;\n"
            "(b) to the information necessary for them to gain full benefit from goods and services;\n"
            "(c) to the protection of their health, safety, and economic interests; and\n"
            "(d) to compensation for loss or injury arising from defects in goods or services.\n"
            "(2) Parliament shall enact legislation to provide for consumer protection and for fair, "
            "honest and decent advertising.\n"
            "(3) This Article applies to goods and services offered by the State or any private person."
        ),
    },
    {
        "section": "Article 48. Access to justice",
        "content": (
            "The State shall ensure access to justice for all persons and, if any fee is required, "
            "it shall be reasonable and shall not impede access to justice."
        ),
    },
    {
        "section": "Article 52. Interpretation of this Chapter",
        "content": (
            "(1) This Chapter—\n"
            "(a) does not deny the existence of any other rights or fundamental freedoms recognised or "
            "conferred by law, except to the extent that they are inconsistent with this Chapter; and\n"
            "(b) does not exclude, modify or abridge any other rights or fundamental freedoms unless "
            "the exclusion, modification or abridgement is expressly stated.\n"
            "(2) No provision of any Bill of Rights legislation may abridge a right or fundamental "
            "freedom provided for in the Bill of Rights."
        ),
    },
    {
        "section": "Article 55. Youth",
        "content": (
            "The State shall take measures, including legislative measures, to ensure that the youth—\n"
            "(a) access relevant education and training;\n"
            "(b) have opportunities to associate, be represented and participate in political, social, "
            "economic and other spheres of life;\n"
            "(c) access employment; and\n"
            "(d) are protected from harmful cultural practices and exploitation."
        ),
    },
    {
        "section": "Article 58. State of emergency",
        "content": (
            "(1) A state of emergency may be declared only under Article 132(4)(d) and only when—\n"
            "(a) the State is threatened by war, invasion, general insurrection, disorder, natural "
            "disaster or other public emergency; and\n"
            "(b) the declaration is necessary to meet the circumstances for which the emergency is "
            "declared.\n"
            "(2) A declaration of a state of emergency, and any legislation enacted or other action "
            "taken in consequence of the declaration, shall be effective only—\n"
            "(a) prospectively; and\n"
            "(b) for not longer than fourteen days from the date of the declaration, unless the "
            "National Assembly resolves to extend the declaration.\n"
            "(3) The National Assembly may extend a declaration of a state of emergency—\n"
            "(a) by resolution adopted—\n"
            "(i) following a public debate in the National Assembly; and\n"
            "(ii) by the votes of at least two-thirds of all the members of the National Assembly; and\n"
            "(b) for not longer than two months each time.\n"
            "(4) The indefinite detention without trial of any person is not permitted in a state of "
            "emergency.\n"
            "(5) A declaration of a state of emergency does not permit the indemnification of the "
            "State, or of any person, in respect of any unlawful act or omission."
        ),
    },
    {
        "section": "Article 59. Kenya National Human Rights and Equality Commission",
        "content": (
            "(1) There is established the Kenya National Human Rights and Equality Commission.\n"
            "(2) The functions of the Commission are—\n"
            "(a) to promote respect for human rights and develop a culture of human rights in the Republic;\n"
            "(b) to promote the protection, and observance of human rights in public and private institutions;\n"
            "(c) to monitor, investigate and report on the observance of human rights in all spheres of life;\n"
            "(d) to receive and investigate complaints about alleged abuses of human rights and take steps "
            "to secure appropriate redress where human rights have been violated;\n"
            "(e) on its own initiative or on the basis of complaints, to investigate or research a matter "
            "in respect of human rights, and make recommendations to improve the functioning of State "
            "organs; and\n"
            "(f) to act as the principal organ of the State in ensuring compliance with obligations under "
            "treaties and conventions relating to human rights."
        ),
    },
]


class Command(BaseCommand):
    help = "Add the 20 missing Constitution of Kenya 2010 articles to the database."

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        for art in ARTICLES:
            exists = Law.objects.filter(title=TITLE, section=art['section']).exists()
            if exists:
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
            self.stdout.write(f"  Added: {art['section'][:70]}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Added {created} articles, skipped {skipped} (already exist).\n"
            f"Next: python manage.py build_embeddings"
        ))
