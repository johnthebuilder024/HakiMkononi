# data/

Place your downloaded Kenyan law PDFs in this folder before running the loader.

## PDFs to add here:

| Filename (suggested) | Source |
|---|---|
| `constitution_2010.pdf` | https://kenyalaw.org/kl/index.php?id=398 |
| `employment_act_2007.pdf` | https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/EmploymentAct_No11of2007.pdf |
| `criminal_procedure_code.pdf` | https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/CriminalProcedureCode_Cap75.pdf |

## How to load them after placing here:

```bash
# 1. Load Constitution (use --constitution flag for Article-based parsing)
python manage.py load_pdf --pdf data/constitution_2010.pdf --title "Constitution of Kenya 2010" --category constitution --url "https://kenyalaw.org/kl/index.php?id=398" --constitution

# 2. Load Employment Act
python manage.py load_pdf --pdf data/employment_act_2007.pdf --title "Employment Act 2007" --category employment --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/EmploymentAct_No11of2007.pdf"

# 3. Load Criminal Procedure Code
python manage.py load_pdf --pdf data/criminal_procedure_code.pdf --title "Criminal Procedure Code (Cap 75)" --category criminal_procedure --url "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/CriminalProcedureCode_Cap75.pdf"

# 4. Build AI embeddings for everything loaded
python manage.py build_embeddings
```
