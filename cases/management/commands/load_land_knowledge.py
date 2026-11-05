"""
Management command: load_land_knowledge

Loads land due diligence knowledge into the Law database.
These rows are used by RAG when classifying land_subtype='transaction'.

Content loaded:
  - Ardhisasa step-by-step guide (county by county where coverage exists)
  - Title deed format guide (pre-2012 green card vs post-2012 blue)
  - Land Control Board consent rules by land type
  - County-specific tenure rules (coastal leases, Nairobi, upcountry)
  - Common fraud patterns in Kenyan land transactions
  - LSK conveyancing checklist
  - Encumbrance glossary (caution, charge, caveat, restriction)
  - Rates clearance and stamp duty process

Usage:
    python manage.py load_land_knowledge
    python manage.py load_land_knowledge --overwrite
"""

from django.core.management.base import BaseCommand


LAND_KNOWLEDGE = [
    # ── Ardhisasa guide ────────────────────────────────────────────────────────
    {
        "title": "Ardhisasa Land Registry Search Guide",
        "section": "How to search land on Ardhisasa",
        "content": (
            "Ardhisasa (ardhisasa.go.ke) is the Ministry of Lands digital platform for land searches in Kenya. "
            "Currently covers Nairobi and expanding to other counties. "
            "\n\nStep-by-step search:"
            "\n1. Go to ardhisasa.go.ke"
            "\n2. Click 'Services' in the top navigation"
            "\n3. Under 'Land Search', click 'Search by Title Number'"
            "\n4. In the Title Number field, type the exact LR number (e.g. NAIROBI/BLOCK 24/123)"
            "\n5. Click Search"
            "\n\nResults interpretation:"
            "\nCLEAN — no encumbrances. Safe to proceed with normal legal steps."
            "\nCAUTION — someone has lodged a warning. This means there is a dispute. Do not pay until resolved."
            "\nCHARGE — the land is used as security for a loan. Bank has interest. Seller must discharge charge first."
            "\nCAVEAT — similar to caution, often from a court order or pending case."
            "\nRESTRICTION — transfer is blocked by court order or government requirement."
            "\n\nIf your county is not yet on Ardhisasa, you must visit the Lands Registry at Ardhi House, Nairobi "
            "or the relevant county Lands Registry for a manual search. The search costs KES 500."
            "\n\nAlways do an Ardhisasa or manual search BEFORE paying any deposit."
        ),
        "category": "land",
        "source_url": "https://ardhisasa.go.ke",
    },
    {
        "title": "Ardhisasa Land Registry Search Guide",
        "section": "LR Number format by county",
        "content": (
            "Kenyan land parcels have different LR number formats by county and land type:"
            "\n\nNAIROBI: NAIROBI/BLOCK 24/123 or L.R. NO. 209/3456"
            "\nKIAMBU: KIAMBU/KIAMBU MUNICIPALITY BLOCK 1/234 or LIMURU/234"
            "\nMOMBASA: MOMBASA/BLOCK I/123 or C.R. 1234 (Crown Grant — old coastal format)"
            "\nNAKURU: NAKURU MUNICIPALITY BLOCK 1/234"
            "\nKISUMU: KISUMU MUNICIPALITY BLOCK 1/234"
            "\nAGRICULTURAL (upcountry): KIAMBU/NDUMBERI/234 or MURANG'A/KIGUMO/123"
            "\n\nThe LR number is printed on the title deed, usually on the first page."
            "\nIf you cannot find it, ask the seller to show you the title deed and copy the number exactly."
            "\nSpelling matters — type it exactly as printed."
        ),
        "category": "land",
        "source_url": "https://ardhisasa.go.ke",
    },

    # ── Title deed formats ────────────────────────────────────────────────────
    {
        "title": "Kenyan Title Deed Format Guide",
        "section": "Pre-2012 Green Card vs Post-2012 Blue Title",
        "content": (
            "Kenya has two types of title deeds depending on when the land was registered:"
            "\n\nPRE-2012 — GREEN CARD (Grant or Certificate of Title)"
            "\n- Green or cream coloured, often landscape format"
            "\n- Issued under the Registration of Titles Act (Cap 281) or Government Lands Act"
            "\n- Shows: parcel number, registered proprietor, area, date of registration, encumbrances"
            "\n- Has embossed Land Registrar stamp and signature"
            "\n- Still valid — the law recognises both formats"
            "\n\nPOST-2012 — BLUE TITLE (Certificate of Ownership)"
            "\n- Blue coloured, issued under the Land Registration Act 2012"
            "\n- Shows: parcel number (new format), registered owner, area, date, encumbrances"
            "\n- Has Kenya coat of arms, Land Registrar stamp, and unique security features"
            "\n- Has a QR code or serial number for verification"
            "\n\nRED FLAGS in title deed format:"
            "\n- Smudged or missing Land Registrar stamp"
            "\n- Date of registration inconsistent with the format type"
            "\n- Owner name spelled differently than seller's ID"
            "\n- Encumbrances section shows entries the seller did not disclose"
            "\n- Parcel number format inconsistent with county"
            "\n- Missing serial number on post-2012 titles"
        ),
        "category": "land",
        "source_url": "https://kenyalaw.org",
    },

    # ── Land Control Board ────────────────────────────────────────────────────
    {
        "title": "Land Control Board Consent — Kenya",
        "section": "Which land transactions require LCB consent",
        "content": (
            "Under the Land Control Act (Cap 302), certain land transactions require consent from "
            "the Land Control Board (LCB) before they are valid."
            "\n\nLAND THAT REQUIRES LCB CONSENT:"
            "\n- Agricultural land anywhere in Kenya"
            "\n- A transaction is 'agricultural' if the land is used for farming, grazing, or is zoned agricultural"
            "\n- This includes most upcountry plots (shambas)"
            "\n\nLAND THAT DOES NOT REQUIRE LCB CONSENT:"
            "\n- Urban/town plots (Nairobi, Mombasa, Kisumu, Nakuru — within municipal boundaries)"
            "\n- Commercial property in town"
            "\n- Industrial property"
            "\n\nHOW TO GET LCB CONSENT:"
            "\n1. Apply to the local Land Control Board (at the sub-county Lands Office)"
            "\n2. Board meets on specific dates (usually monthly)"
            "\n3. Both buyer and seller must appear in person"
            "\n4. Board issues a consent certificate"
            "\n5. Consent must be obtained within 6 months of signing the sale agreement"
            "\n\nWARNING: A transfer of agricultural land WITHOUT LCB consent is VOID and has no legal effect. "
            "The buyer gets nothing even if they paid full price. "
            "Always confirm whether the land is agricultural before signing anything."
        ),
        "category": "land",
        "source_url": "https://kenyalaw.org",
    },

    # ── Conveyancing checklist ────────────────────────────────────────────────
    {
        "title": "Land Purchase Due Diligence Checklist Kenya",
        "section": "Complete buyer checklist before paying",
        "content": (
            "BEFORE YOU PAY ANY DEPOSIT — complete all of these:"
            "\n\n1. GET THE LR NUMBER from the seller. Do not pay without it."
            "\n2. ARDHISASA SEARCH — go to ardhisasa.go.ke and search the title number. "
            "Confirm: no caution, no charge, no caveat, no restriction."
            "\n3. VERIFY OWNER NAME — the registered proprietor on the title must match the seller's "
            "National ID or passport. Any difference = major red flag."
            "\n4. LAND CONTROL BOARD CONSENT — if agricultural land, confirm LCB consent is obtainable. "
            "Board must approve before transfer is valid."
            "\n5. SURVEY PLAN — get the official survey plan (beacon map) from the Survey of Kenya. "
            "Walk the land and confirm beacons match what you are being shown."
            "\n6. RATES CLEARANCE — get a rates clearance certificate from the county government. "
            "Outstanding land rates must be paid before transfer."
            "\n7. ADVOCATE CHECK — verify any advocate involved is on the LSK register: "
            "go to kenyalaw.org → LSK Members register → search by name."
            "\n8. STAMP DUTY — budget for stamp duty: 4% of land value for urban, 2% for rural. "
            "Paid to KRA before registration."
            "\n9. SALE AGREEMENT — have a conveyancing advocate draft the agreement. "
            "Never use an agreement written by the seller's agent only."
            "\n10. REGISTRATION — after all the above, the transfer is registered at the "
            "Lands Registry. The new title is issued in the buyer's name."
            "\n\nFOR LAND OVER KES 500,000: always use a conveyancing advocate. "
            "Their fee is regulated: 1.5% to 2% of land value (LSK Remuneration Order)."
        ),
        "category": "land",
        "source_url": "https://kenyalaw.org",
    },

    # ── Fraud patterns ────────────────────────────────────────────────────────
    {
        "title": "Common Land Fraud Patterns in Kenya",
        "section": "How to recognise land fraud before you pay",
        "content": (
            "These are the most common fraud patterns in Kenyan land transactions:"
            "\n\n1. FAKE TITLE DEED"
            "\nForged titles with wrong stamp, wrong serial number, or wrong parcel number format. "
            "Always verify on Ardhisasa or at the Lands Registry before paying."
            "\n\n2. DOUBLE ALLOCATION / DOUBLE SELLING"
            "\nSame land sold to two or more buyers. The first to register wins. "
            "Red flag: seller is in a hurry and pressuring quick payment."
            "\n\n3. SELLING LAND NOT OWNED"
            "\nSeller presents someone else's title. "
            "Always check the title owner name against the seller's ID."
            "\n\n4. CAUTION FRAUD"
            "\nSeller claims a registered caution has been lifted but shows no withdrawal document. "
            "Always verify on Ardhisasa that the caution is gone — seller's word is not enough."
            "\n\n5. AGENT FRAUD"
            "\nAgent collects deposit and disappears, or collects from multiple buyers. "
            "Never pay the agent — always pay into the seller's advocate's client account."
            "\n\n6. INFLATED PRICE THEN TITLE WITHHELD"
            "\nBuyer pays inflated price for land with hidden charges. "
            "Seller refuses to complete transfer. "
            "Always check for charges on the title before paying."
            "\n\n7. COASTAL LAND SCAMS"
            "\nOld Crown Grants and government leases on the coast have complex tenure. "
            "Coastal land near beaches often has multiple claimants. "
            "Extra caution needed — always use an advocate with coastal land experience."
            "\n\n8. FAMILY LAND WITHOUT CONSENT"
            "\nOne family member sells family/group ranch land without full consent of others. "
            "Check whether land is registered in one name or as community/family land."
        ),
        "category": "land",
        "source_url": "https://kenyalaw.org",
    },

    # ── Encumbrance glossary ──────────────────────────────────────────────────
    {
        "title": "Land Encumbrance Glossary Kenya",
        "section": "What caution, charge, caveat and restriction mean",
        "content": (
            "When you search a title on Ardhisasa or at the Lands Registry, you may see these entries:"
            "\n\nCAUTION"
            "\nMeaning: Someone has filed a warning that there is a dispute about this land. "
            "The cautioner is saying 'do not deal with this land without hearing from me first.' "
            "What to do: Do NOT buy until the caution is withdrawn. Ask the seller why it exists and get it lifted first."
            "\n\nCHARGE"
            "\nMeaning: The land is security for a loan (mortgage). A bank or lender has an interest in the land. "
            "What to do: The seller must get a discharge from the lender before transfer. "
            "Ask for a discharge letter from the bank. Do not pay until the charge is removed."
            "\n\nCAVEAT"
            "\nMeaning: Similar to a caution — someone claims an interest in the land that prevents transfer. "
            "Often used when there is a court case pending. "
            "What to do: Do not proceed until caveat is removed. May require a court order."
            "\n\nRESTRICTION"
            "\nMeaning: A court or government has blocked any dealings on the land. "
            "This is the most serious — often means government interest or an active injunction. "
            "What to do: Do not buy. Get a lawyer to investigate immediately."
            "\n\nEASEMENT / RIGHT OF WAY"
            "\nMeaning: Another person has a legal right to cross or use part of the land. "
            "This stays with the land — the buyer inherits it. "
            "Not necessarily a problem but must be disclosed."
        ),
        "category": "land",
        "source_url": "https://kenyalaw.org",
    },

    # ── County-specific rules ─────────────────────────────────────────────────
    {
        "title": "Kenya Land Tenure Rules by County",
        "section": "Nairobi, Coast, Upcountry agricultural — key differences",
        "content": (
            "Land tenure rules differ significantly by county in Kenya:"
            "\n\nNAIROBI COUNTY"
            "\n- Most plots are leasehold (government lease, typically 99 years)"
            "\n- No Land Control Board consent required for town plots"
            "\n- Rates are paid to Nairobi City County"
            "\n- Ardhisasa coverage is best here — most titles searchable online"
            "\n\nCOASTAL COUNTIES (Mombasa, Kilifi, Kwale, Lamu, Taita Taveta)"
            "\n- Complex tenure: mix of freehold, leasehold, old Crown Grants, and government land"
            "\n- Many coastal plots near the beach have overlapping claims"
            "\n- Old Crown Grants (C.R. numbers) are pre-independence titles — still valid"
            "\n- Extra caution needed: always use an advocate experienced in coastal land"
            "\n- Some beach land is subject to 60-metre Public Beach — no building allowed"
            "\n\nUPCOUNTRY AGRICULTURAL (Kiambu, Murang'a, Nakuru, Uasin Gishu, etc.)"
            "\n- Mostly freehold agricultural land"
            "\n- Land Control Board consent REQUIRED for all transactions"
            "\n- Rates paid to county government"
            "\n- Survey plan (beacon map) is essential — boundary disputes are common"
            "\n\nRIFT VALLEY / PASTORAL AREAS"
            "\n- Mix of individual titles and community land (group ranches)"
            "\n- Community Land Act 2016 governs group ranch transactions"
            "\n- Consent of the entire community required for group ranch sales"
            "\n\nFOR ALL COUNTIES: always verify at the local Lands Registry as Ardhisasa "
            "coverage outside Nairobi may be incomplete."
        ),
        "category": "land",
        "source_url": "https://kenyalaw.org",
    },

    # ── Stamp duty and costs ──────────────────────────────────────────────────
    {
        "title": "Land Transaction Costs in Kenya",
        "section": "Stamp duty, advocate fees, registration fees",
        "content": (
            "When buying land in Kenya, budget for these costs on top of the purchase price:"
            "\n\nSTAMP DUTY (paid to KRA)"
            "\n- Urban land: 4% of market value"
            "\n- Rural/agricultural land: 2% of market value"
            "\n- Example: KES 1,000,000 urban plot → KES 40,000 stamp duty"
            "\n- Assessed by government valuer — cannot be avoided"
            "\n\nADVOCATE FEES (LSK Remuneration Order 2014)"
            "\n- Sale agreement drafting: KES 5,000–15,000"
            "\n- Conveyancing (full transaction): 1.5% to 2% of land value (minimum KES 30,000)"
            "\n- Example: KES 1,000,000 plot → KES 15,000–20,000 in advocate fees"
            "\n\nLAND REGISTRY FEES"
            "\n- Title search: KES 500"
            "\n- Transfer registration: approximately KES 5,000"
            "\n- New title certificate: KES 2,000"
            "\n\nCOUNTY RATES CLEARANCE"
            "\n- Any outstanding rates must be paid in full"
            "\n- Get clearance certificate from county government"
            "\n\nSURVEY FEES (if buying agricultural land)"
            "\n- Beacon map from Survey of Kenya: KES 5,000–15,000"
            "\n\nTOTAL TRANSACTION COSTS: typically 5%–8% of purchase price"
            "\nAlways budget for these costs before agreeing to a price."
        ),
        "category": "land",
        "source_url": "https://kenyalaw.org",
    },

    # ── Swahili guide for Ardhisasa ──────────────────────────────────────────
    {
        "title": "Mwongozo wa Ardhisasa — Kutafuta Ardhi Kenya",
        "section": "Jinsi ya kutafuta ardhi kwenye Ardhisasa hatua kwa hatua",
        "content": (
            "Ardhisasa (ardhisasa.go.ke) ni mfumo wa mtandaoni wa Wizara ya Ardhi Kenya "
            "unaokuruhusu kutafuta hati za ardhi."
            "\n\nHATUA ZA KUTAFUTA:"
            "\n1. Nenda kwenye ardhisasa.go.ke"
            "\n2. Bonyeza 'Services' juu ya ukurasa"
            "\n3. Chini ya 'Land Search' bonyeza 'Search by Title Number'"
            "\n4. Katika sehemu ya Title Number, andika nambari ya LR kama ilivyo kwenye hati"
            "\n   Mfano: NAIROBI/BLOCK 24/123 au KIAMBU/001/234"
            "\n5. Bonyeza Search"
            "\n\nMAELEZO YA MATOKEO:"
            "\nSAFI — hakuna mzigo. Unaweza kuendelea na taratibu za kawaida za kisheria."
            "\nCAUTION — mtu ameweka onyo. Kuna ugomvi kuhusu ardhi hii. "
            "USILIPIZIE mpaka caution iondolewe."
            "\nCHARGE — ardhi imewekwa dhamana kwa mkopo wa benki. "
            "Muuzaji lazima alipie deni la benki kwanza."
            "\nCAVEAT — kama caution — mtu anadai haki kwenye ardhi. Usiendelee."
            "\nRESTRICTION — amri ya mahakama au serikali imezuia muamala. "
            "Hali mbaya zaidi — wasiliana na wakili haraka."
            "\n\nKAMA KAUNTI YAKO HAIPO ARDHISASA:"
            "Nenda Ofisi ya Ardhi ya Kaunti yako kwa utafutaji wa mikono. Ada ni KES 500."
            "\n\nUFANYE UTAFUTAJI KABLA ya kulipa amana yoyote."
        ),
        "category": "land",
        "source_url": "https://ardhisasa.go.ke",
    },
]


class Command(BaseCommand):
    help = "Load land due diligence knowledge base into the Law database"

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help='Delete and re-create existing land knowledge rows'
        )

    def handle(self, *args, **options):
        from cases.models import Law
        from cases.rag import invalidate_law_cache

        overwrite = options['overwrite']
        created   = 0
        skipped   = 0

        self.stdout.write(f"\n[load_land_knowledge] Loading {len(LAND_KNOWLEDGE)} land knowledge rows...")

        for item in LAND_KNOWLEDGE + LAND_KNOWLEDGE_V2:
            exists = Law.objects.filter(
                title=item['title'],
                section=item['section'],
            ).exists()

            if exists and not overwrite:
                skipped += 1
                continue

            if exists and overwrite:
                Law.objects.filter(title=item['title'], section=item['section']).delete()

            Law.objects.create(
                title      = item['title'],
                section    = item['section'],
                content    = item['content'],
                category   = item['category'],
                source_url = item['source_url'],
                # embedding generated by build_embeddings command
                embedding_json = '',
            )
            created += 1
            self.stdout.write(f"  ✅ {item['title']} — {item['section'][:60]}")

        self.stdout.write(
            f"\n[load_land_knowledge] Done — {created} created, {skipped} already existed"
        )

        if created > 0:
            self.stdout.write("\nNext step: run embeddings for new rows:")
            self.stdout.write("  python manage.py build_embeddings")
            self.stdout.write("\nOr build immediately:")

            answer = input("  Build embeddings now? (y/N) ").strip().lower()
            if answer == 'y':
                self.stdout.write("[load_land_knowledge] Building embeddings...")
                from cases.rag import embed_text
                import time
                unembedded = Law.objects.filter(embedding_json='').exclude(content='')
                count = 0
                for law in unembedded:
                    try:
                        vec = embed_text(f"{law.title} {law.section}: {law.content}")
                        if vec:
                            law.set_embedding(vec)
                            law.save(update_fields=['embedding_json'])
                            count += 1
                            time.sleep(0.2)
                    except Exception as e:
                        self.stderr.write(f"  Embedding failed for {law.pk}: {e}")

                invalidate_law_cache()
                self.stdout.write(f"[load_land_knowledge] ✅ Embedded {count} rows, cache reloaded")


# ── Additional rows added after testing ──────────────────────────────────────
LAND_KNOWLEDGE_V2 = [
    {
        "title": "Land Sale Deposit Fraud and Recovery Kenya",
        "section": "What to do when seller takes deposit and disappears",
        "content": (
            "When you pay a deposit for land in Kenya and the seller disappears or refuses to give the title deed:"
            "\n\nYOUR LEGAL POSITION:"
            "\n- The sale agreement is a binding contract under the Law of Contract Act (Cap 23)"
            "\n- The seller is in breach of contract"
            "\n- You can sue for specific performance (force the seller to complete the sale)"
            "\n- You can sue for refund of the deposit plus interest and damages"
            "\n- If the seller acted with intent to defraud, this is a criminal offence under the Penal Code"
            "\n\nIMPORTANT — if you paid without a proper sale agreement:"
            "\n- You still have rights under unjust enrichment principles"
            "\n- You can demand return of the deposit as money paid under a failed contract"
            "\n\nSTEPS TO TAKE:"
            "\n1. Send a formal demand letter to the seller giving 14 days to complete the sale or refund"
            "\n2. File a complaint with the DCI (fraud) if the seller deliberately misrepresented the land"
            "\n3. File a civil suit in the High Court (Environment and Land Court) for:"
            "\n   a. Specific performance — court orders seller to transfer the land"
            "\n   b. Refund of deposit plus damages"
            "\n4. If the seller took your money knowing they could not deliver — file a criminal complaint for obtaining money by false pretences (Penal Code Section 317)"
            "\n\nEVIDENCE TO KEEP:"
            "\n- Your sale agreement or receipt"
            "\n- Any M-Pesa or bank transfer records"
            "\n- WhatsApp/SMS conversations with the seller"
            "\n- Photos of the land"
            "\n- Any witnesses to the payment"
            "\n\nNEVER pay a full purchase price before the title is searched and transferred. "
            "Always use a conveyancing advocate to hold deposit in escrow."
        ),
        "category": "land",
        "source_url": "https://kenyalaw.org",
    },
    {
        "title": "Contract Law — Deposit Recovery Kenya",
        "section": "Refund of deposit when contract fails or seller breaches",
        "content": (
            "Under the Law of Contract Act (Cap 23) and general contract principles in Kenya:"
            "\n\nWHEN YOU CAN RECOVER YOUR DEPOSIT:"
            "\n- Seller fails to deliver what was promised (breach by seller)"
            "\n- Sale does not proceed due to seller's default"
            "\n- Misrepresentation — seller lied about the land"
            "\n- Seller had no title to sell"
            "\n\nLEGAL REMEDIES:"
            "\n1. Rescission — cancel the contract and get your deposit back"
            "\n2. Damages — sue for the deposit plus any losses caused by the breach"
            "\n3. Specific performance — if you still want the land, court can order the seller to complete"
            "\n\nWHERE TO FILE:"
            "\n- Small Claims Court — if deposit is under KES 1 million"
            "\n- Environment and Land Court — for land-specific disputes"
            "\n- Magistrate Court — for smaller amounts"
            "\n\nLIMITATION: You must file within 6 years of the breach under the Limitation of Actions Act."
            "\n\nPRACTICAL STEPS:"
            "\n1. Write a demand letter: give 14 days to refund or complete"
            "\n2. Report to DCI if you believe you were deliberately defrauded"
            "\n3. File in court if no response"
        ),
        "category": "land",
        "source_url": "https://kenyalaw.org",
    },
]
