@echo off
REM ============================================================
REM  HakiMkononi — Load ALL PDFs into the database
REM  Run from the project root:  load_all_pdfs.bat
REM
REM  Safe to re-run: each command skips a title that already
REM  exists.  Add --overwrite to any line to force re-load.
REM ============================================================

echo.
echo ============================================================
echo  HakiMkononi PDF Loader
echo ============================================================
echo.

REM ── CONSTITUTION ────────────────────────────────────────────
echo [1/44] Constitution of Kenya 2010
python manage.py load_pdf ^
  --pdf "data/Constitution of Kenya.pdf" ^
  --title "Constitution of Kenya 2010" ^
  --category constitution ^
  --url "https://kenyalaw.org/kl/index.php?id=398" ^
  --constitution
echo.

REM ── EMPLOYMENT ──────────────────────────────────────────────
echo [2/44] Employment Act 2007
python manage.py load_pdf ^
  --pdf "data/Employment Act.pdf" ^
  --title "Employment Act 2007" ^
  --category employment ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/EmploymentAct_No11of2007.pdf"
echo.

echo [3/44] National Social Security Fund Act 2013
python manage.py load_pdf ^
  --pdf "data/National Social Security Fund Act 2013.pdf" ^
  --title "National Social Security Fund Act 2013" ^
  --category employment ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/NationalSocialSecurityFundAct_No45of2013.pdf"
echo.

echo [4/44] Occupational Safety and Health Act 2007
python manage.py load_pdf ^
  --pdf "data/Occupational Safety and Health Act 2007.pdf" ^
  --title "Occupational Safety and Health Act 2007" ^
  --category employment ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/OccupationalSafetyAndHealthAct_No15of2007.pdf"
echo.

echo [5/44] Work Injury Benefits Act 2007
python manage.py load_pdf ^
  --pdf "data/Work Injury Benefits Act 2007.pdf" ^
  --title "Work Injury Benefits Act 2007" ^
  --category employment ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/WorkInjuryBenefitsAct_No13of2007.pdf"
echo.

REM ── CRIMINAL / POLICE ────────────────────────────────────────
echo [6/44] Criminal Procedure Code (Cap 75)
python manage.py load_pdf ^
  --pdf "data/Criminal Procedure Code.pdf" ^
  --title "Criminal Procedure Code (Cap 75)" ^
  --category criminal_procedure ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/CriminalProcedureCode_Cap75.pdf"
echo.

echo [7/44] Penal Code (Cap 63)
python manage.py load_pdf ^
  --pdf "data/Penal Code.pdf" ^
  --title "Penal Code (Cap 63)" ^
  --category criminal_procedure ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/PenalCode_Cap63.pdf"
echo.

echo [8/44] National Police Service Act 2011
python manage.py load_pdf ^
  --pdf "data/National Police Service Act.pdf" ^
  --title "National Police Service Act 2011" ^
  --category criminal_procedure ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/NationalPoliceServiceAct_No11Aof2011.pdf"
echo.

echo [9/44] Sexual Offences Act 2006
python manage.py load_pdf ^
  --pdf "data/Sexual Offences Act 2006.pdf" ^
  --title "Sexual Offences Act 2006" ^
  --category criminal_procedure ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/SexualOffencesAct_No3of2006.pdf"
echo.

REM ── FRAUD / CYBERCRIME ───────────────────────────────────────
echo [10/44] Computer Misuse and Cybercrimes Act 2018
python manage.py load_pdf ^
  --pdf "data/Computer Misuse and Cybercrimes.pdf" ^
  --title "Computer Misuse and Cybercrimes Act 2018" ^
  --category fraud ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/ComputerMisuseAndCybercrimesAct_No5of2018.pdf"
echo.

echo [11/44] Computer Misuse and Cybercrimes (Amendment) Act 2025
python manage.py load_pdf ^
  --pdf "data/Computer Misuse and Cybercrimes (Amendment) Act 2025.pdf" ^
  --title "Computer Misuse and Cybercrimes (Amendment) Act 2025" ^
  --category fraud ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/ComputerMisuseAndCybercrimesAmendmentAct2025.pdf"
echo.

echo [12/44] Hire Purchase Act (Cap 507)
python manage.py load_pdf ^
  --pdf "data/HirePurchase Act.pdf" ^
  --title "Hire Purchase Act (Cap 507)" ^
  --category fraud ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/HirePurchaseAct_Cap507.pdf"
echo.

REM ── LAND & SUCCESSION ────────────────────────────────────────
echo [13/44] Land Act 2012
python manage.py load_pdf ^
  --pdf "data/Land Act 2012.pdf" ^
  --title "Land Act 2012" ^
  --category land ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/LandAct_No6of2012.pdf"
echo.

echo [14/44] Land Registration Act 2012
python manage.py load_pdf ^
  --pdf "data/Land Registration Act 2012.pdf" ^
  --title "Land Registration Act 2012" ^
  --category land ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/LandRegistrationAct_No3of2012.pdf"
echo.

echo [15/44] Community Land Act 2016
python manage.py load_pdf ^
  --pdf "data/Community Land Act.pdf" ^
  --title "Community Land Act 2016" ^
  --category land ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/CommunityLandAct_No27of2016.pdf"
echo.

echo [16/44] Land Control Act (Cap 302)
python manage.py load_pdf ^
  --pdf "data/Land Control Act.pdf" ^
  --title "Land Control Act (Cap 302)" ^
  --category land ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/LandControlAct_Cap302.pdf"
echo.

echo [17/44] Law of Succession Act (Cap 160)
python manage.py load_pdf ^
  --pdf "data/Law of Succession Act.pdf" ^
  --title "Law of Succession Act (Cap 160)" ^
  --category land ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/LawofSuccessionAct_Cap160.pdf"
echo.

echo [18/44] Widows and Children Pensions Act
python manage.py load_pdf ^
  --pdf "data/Widows and Childrens Pensions Act.pdf" ^
  --title "Widows and Childrens Pensions Act" ^
  --category land ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/WidowsAndChildrensPensionsAct.pdf"
echo.

REM ── LANDLORD & TENANT ────────────────────────────────────────
echo [19/44] Landlord and Tenant (Shops Hotels and Catering Establishments) Act
python manage.py load_pdf ^
  --pdf "data/Landlord and Tenant (Shops Hotels and Catering Establishments) Act.pdf" ^
  --title "Landlord and Tenant (Shops Hotels and Catering Establishments) Act" ^
  --category landlord_tenant ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/LandlordandTenantShopsHotelsandCateringEstablishmentsAct_Cap301.pdf"
echo.

echo [20/44] Rent Restriction Act (Cap 296)
python manage.py load_pdf ^
  --pdf "data/Rent Restriction Act.pdf" ^
  --title "Rent Restriction Act (Cap 296)" ^
  --category landlord_tenant ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/RentRestrictionAct_Cap296.pdf"
echo.

echo [21/44] Distress for Rent Act (Cap 293)
python manage.py load_pdf ^
  --pdf "data/Distress for Rent Act.pdf" ^
  --title "Distress for Rent Act (Cap 293)" ^
  --category landlord_tenant ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/DistressforRentAct_Cap293.pdf"
echo.

REM ── CHILDREN & FAMILY ────────────────────────────────────────
echo [22/44] Children Act 2022
python manage.py load_pdf ^
  --pdf "data/Children Act 2022.pdf" ^
  --title "Children Act 2022" ^
  --category children ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/ChildrenAct_No29of2022.pdf"
echo.

echo [23/44] Children Act (Cap 141) — older version
python manage.py load_pdf ^
  --pdf "data/Children Act.pdf" ^
  --title "Children Act (Cap 141)" ^
  --category children ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/ChildrenAct_Cap141.pdf"
echo.

echo [24/44] Marriage Act 2014
python manage.py load_pdf ^
  --pdf "data/Marriage Act 2014.pdf" ^
  --title "Marriage Act 2014" ^
  --category family ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/MarriageAct_No4of2014.pdf"
echo.

echo [25/44] Matrimonial Property Act 2013
python manage.py load_pdf ^
  --pdf "data/Matrimonial Property Act 2013.pdf" ^
  --title "Matrimonial Property Act 2013" ^
  --category family ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/MatrimonialPropertyAct_No49of2013.pdf"
echo.

echo [26/44] Protection Against Domestic Violence Act 2015
python manage.py load_pdf ^
  --pdf "data/Protection Against Domestic Violence Act 2015.pdf" ^
  --title "Protection Against Domestic Violence Act 2015" ^
  --category family ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/ProtectionAgainstDomesticViolenceAct_No2of2015.pdf"
echo.

echo [27/44] The Marriage (General) Rules
python manage.py load_pdf ^
  --pdf "data/The Marriage (General) Rules.pdf" ^
  --title "The Marriage (General) Rules" ^
  --category family ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/LegalNotices/2015/LN37_2015.pdf"
echo.

echo [28/44] The Marriage (Customary Marriage) Rules
python manage.py load_pdf ^
  --pdf "data/The Marriage (Customary Marriage) Rules.pdf" ^
  --title "The Marriage (Customary Marriage) Rules" ^
  --category family ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/LegalNotices/2015/LN36_2015.pdf"
echo.

echo [29/44] The Marriage (Hindu Marriage) Rules
python manage.py load_pdf ^
  --pdf "data/The Marriage (Hindu Marriage) Rules.pdf" ^
  --title "The Marriage (Hindu Marriage) Rules" ^
  --category family ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/LegalNotices/2015/LN38_2015.pdf"
echo.

echo [30/44] The Marriage (Muslim Marriage) Rules
python manage.py load_pdf ^
  --pdf "data/The Marriage (Muslim Marriage) Rules.pdf" ^
  --title "The Marriage (Muslim Marriage) Rules" ^
  --category family ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/LegalNotices/2015/LN39_2015.pdf"
echo.

echo [31/44] The Marriage (Matrimonial Proceedings) Rules
python manage.py load_pdf ^
  --pdf "data/The Marriage (Matrimonial Proceedings) Rules.pdf" ^
  --title "The Marriage (Matrimonial Proceedings) Rules" ^
  --category family ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/LegalNotices/2015/LN40_2015.pdf"
echo.

REM ── CONSUMER PROTECTION ──────────────────────────────────────
echo [32/44] Consumer Protection Act 2012
python manage.py load_pdf ^
  --pdf "data/Consumer Protection Act 2012.pdf" ^
  --title "Consumer Protection Act 2012" ^
  --category consumer ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/ConsumerProtectionAct_No46of2012.pdf"
echo.

REM ── DATA PROTECTION ──────────────────────────────────────────
echo [33/44] Data Protection Act 2019
python manage.py load_pdf ^
  --pdf "data/Data Protection Act.pdf" ^
  --title "Data Protection Act 2019" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/DataProtectionAct_No24of2019.pdf"
echo.

echo [34/44] Data Protection (General) Regulations
python manage.py load_pdf ^
  --pdf "data/The Data Protection (General) Regulations.pdf" ^
  --title "Data Protection (General) Regulations 2021" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/LegalNotices/2021/LN46_2021.pdf"
echo.

echo [35/44] Data Protection (General) Regulations (copy 2 — skip if duplicate)
python manage.py load_pdf ^
  --pdf "data/The Data Protection (General) Regulations (1).pdf" ^
  --title "Data Protection (General) Regulations 2021 (Rev)" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/LegalNotices/2021/LN46_2021.pdf"
echo.

echo [36/44] Data Protection (Civil Registration) Regulations
python manage.py load_pdf ^
  --pdf "data/The Data Protection (Civil Registration) Regulations.pdf" ^
  --title "Data Protection (Civil Registration) Regulations 2021" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/LegalNotices/2021/LN48_2021.pdf"
echo.

echo [37/44] Data Protection (Registration of Data Controllers and Processors) Regulations
python manage.py load_pdf ^
  --pdf "data/The Data Protection (Registration of Data Controllers and Data Processors) Regulations.pdf" ^
  --title "Data Protection (Registration of Data Controllers and Processors) Regulations 2021" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/LegalNotices/2021/LN47_2021.pdf"
echo.

REM ── OTHER ─────────────────────────────────────────────────────
echo [38/44] Fair Administrative Action Act 2015
python manage.py load_pdf ^
  --pdf "data/Fair Administrative Action Act 2015.pdf" ^
  --title "Fair Administrative Action Act 2015" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/FairAdministrativeActionAct_No4of2015.pdf"
echo.

echo [39/44] Basic Education Act 2013
python manage.py load_pdf ^
  --pdf "data/Basic Education Act.pdf" ^
  --title "Basic Education Act 2013" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/BasicEducationAct_No14of2013.pdf"
echo.

echo [40/44] Refugees Act 2021
python manage.py load_pdf ^
  --pdf "data/Refugees Act.pdf" ^
  --title "Refugees Act 2021" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/RefugeesAct_No4of2021.pdf"
echo.

echo [41/44] Elections Act 2011
python manage.py load_pdf ^
  --pdf "data/Elections Act.pdf" ^
  --title "Elections Act 2011" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/ElectionsAct_No24of2011.pdf"
echo.

echo [42/44] Traffic Act (Cap 403) — original
python manage.py load_pdf ^
  --pdf "data/Traffic Act Cap 403.pdf" ^
  --title "Traffic Act (Cap 403)" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/TrafficAct_Cap403.pdf"
echo.

echo [43/44] Traffic Act — revised edition
python manage.py load_pdf ^
  --pdf "data/Traffic Act.pdf" ^
  --title "Traffic Act (Revised)" ^
  --category other ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/TrafficAct_Cap403.pdf"
echo.

echo [44/44] Work Injury Benefits Act 2007 (already under employment — skip if duplicate)
REM  Already loaded as employment above — this line is a safety check only
python manage.py load_pdf ^
  --pdf "data/Work Injury Benefits Act 2007.pdf" ^
  --title "Work Injury Benefits Act 2007" ^
  --category employment ^
  --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/WorkInjuryBenefitsAct_No13of2007.pdf"
echo.

REM ── BUILD EMBEDDINGS ─────────────────────────────────────────
echo.
echo ============================================================
echo  All PDFs loaded. Now building AI embeddings...
echo  (This will take several minutes — do not close the window)
echo ============================================================
echo.
python manage.py build_embeddings

echo.
echo ============================================================
echo  DONE. All laws are in the database with embeddings.
echo ============================================================
pause
