# PrivGuard — AI Data Privacy Gateway

## 1. Project Overview
PrivGuard is a local, pre-LLM security and data privacy gateway designed to sanitize business evidence documents. It detects and redacts Personally Identifiable Information (PII) before allowing the text to be passed to any downstream AI or LLM process. It operates strictly on a fail-closed security model.

## 2. Problem
Business documents often contain sensitive PII. Passing these raw documents directly to an LLM creates a significant data exposure risk. A security layer is needed to identify, classify, and redact PII while preserving the original structure and semantic context of the document.

## 3. Solution
This application accepts PDF, DOCX, PPTX, and TXT files, extracts their text while retaining page/slide/paragraph location data, runs a hybrid PII detection engine (Regex, NER, Context Rules), redacts the findings using consistent semantic placeholders (e.g., `[PERSON_001]`), and strictly validates the output to ensure no PII remains.

## 4. Architecture
User
↓
File Upload
↓
File Classification
↓
Document Extraction (PyMuPDF, docx, pptx)
↓
Normalized Document (DocumentBlock)
↓
Hybrid PII Detection
├── Regex
├── NER (spaCy)
└── Context Rules
↓
PII Classification (Severity, Confidence)
↓
Exposure Report
↓
Redaction
↓
Post-Redaction Validation
↓
SAFE / BLOCKED
↓
Sanitized Content

## 5. Supported Formats
- **PDF**: Uses PyMuPDF. Preserves page boundaries and detects scanned pages.
- **DOCX**: Uses python-docx. Preserves paragraphs and tables.
- **PPTX**: Uses python-pptx. Preserves slides, text boxes, and tables.
- **TXT**: Preserves paragraphs.

## 6. PII Detection Methods
- **Regex**: Email, Phone, Credit Card, IP Address.
- **NER**: Uses spaCy `en_core_web_sm` to detect Person, Address, Date of Birth.
- **Context Rules**: Identifies structured PII like Employee ID, Government ID by analyzing surrounding text.

## 7. Redaction Approach
Replaces PII with semantic placeholders (e.g., `[EMAIL_001]`). The application ensures the same entity receives the same placeholder consistently within a document to preserve relationships for the downstream LLM.

## 8. Validation
After redaction, the sanitized text is rescanned by the PII detection engine. If any high-confidence PII remains, the document is immediately marked as BLOCKED.

## 9. Security Model
- **Fail-Closed**: If extraction, detection, redaction, or validation fails, or if PII remains, the document is BLOCKED.
- **Local Processing**: No data is sent to external APIs or LLMs.

## 10. Project Structure
- `app.py`: Streamlit Dashboard.
- `models/`: Data schemas (DocumentBlock, PIIFinding, etc.).
- `extractors/`: File parsers for PDF, DOCX, PPTX, TXT.
- `detection/`: Hybrid PII engine (regex, NER, context).
- `redaction/`: Redactor and Post-redaction validator.
- `reporting/`: Summary metrics and JSON/CSV generation.
- `tests/`: Pytest suite.

## 11. Installation
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Windows OCR (Tesseract) Setup:
`pytesseract` requires the Tesseract OCR engine binary on Windows:
1. Download the Windows installer from [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (e.g. `tesseract-ocr-w64-setup-5.x.x.exe`).
2. Install to the standard path: `C:\Program Files\Tesseract-OCR\`.
3. Ensure the installation folder is added to Windows PATH, or set the environment variable:
   ```cmd
   setx TESSERACT_CMD "C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```
4. **Fail-Closed Security Note**: If Tesseract is not installed or configured, the gateway does **not** assume documents are PII-free. Scanned pages and embedded images will generate explicit `OCR_UNAVAILABLE` uncertainty blocks so downstream security controls never release uninspected evidence.

## 12. Running the application
```bash
streamlit run app.py
```

## 13. Testing
```bash
python -m pytest tests/ -v
```

## 14. Architecture & Multimodal Extraction (Phase 1)
- **PDF**: Dual-stream extraction (native text with bounding boxes + 300 DPI page rendering + OCR pipeline + embedded images + document metadata).
- **DOCX**: Body paragraphs + structured table cells + section headers/footers + embedded screenshot OCR + core properties metadata.
- **PPTX**: Text frames + recursive grouped shape traversal (`MSO_SHAPE_TYPE.GROUP`) + structured tables + speaker notes + image OCR + presentation metadata.
- **TXT**: Multi-encoding fallback (UTF-8, Latin-1, CP1252) with paragraph metadata.
- **Traceability**: Normalized `DocumentBlock` preserves spatial coordinates (`bbox`), `is_ocr`, `ocr_confidence`, and hierarchical location identifiers.

