# AI PDF Subject Splitter Pro

## Overview

AI PDF Subject Splitter Pro is an intelligent PDF processing tool designed for large engineering manuals, technical documentation, OEM manuals, and BHEL turbine manuals.

The application automatically:

* Reads PDF bookmarks (TOC)
* Detects document start and end pages
* Splits large PDFs into individual document PDFs
* Extracts subject names and document numbers
* Generates meaningful filenames
* Creates Excel reports
* Organizes output files automatically

---

## Features

### Bookmark-Based PDF Splitting

Automatically identifies document boundaries using PDF bookmarks.

Example:

```text
5.1-0002-04_2 → Start Page 8
5.1-0003-01   → Start Page 10
```

Generated PDF:

```text
Pages 8-9
```

---

### Subject Detection

Extracts subject names from Contents/Index pages.

Example:

```text
DESCRIPTION
General description
5.1-0002-04/2
```

---

### Smart PDF Naming

Output filename format:

```text
<Category> - <Subject> - <DocumentNo>.pdf
```

Examples:

```text
DESCRIPTION - General description - 5.1-0002-04_2.pdf

Technical Data - Construction speed and Steam pressure - 5.1-0100-53_3.pdf

HP Turbine - Casing - 5.1-0210-01_3.pdf
```

---

### Excel Report Generation

Creates:

```text
Document_Index.xlsx
```

Columns:

* Category
* Subject
* Document Number
* Start Page
* End Page
* Total Pages
* Output File Name
* Output Path

---

### Automatic Features

* Invalid filename cleaning
* Duplicate filename handling
* Missing subject fallback
* Error handling
* Progress tracking
* Detailed logging

---

## Project Structure

```text
AI-PDF-Subject-Splitter-Pro/
│
├── app.py
├── requirements.txt
├── README.md
│
├── uploads/
│   └── turbine.pdf
│
├── output/
│
├── reports/
│
└── logs/
```

---

## Installation

Clone repository:

```bash
git clone https://github.com/yourusername/AI-PDF-Subject-Splitter-Pro.git
```

Move to project directory:

```bash
cd AI-PDF-Subject-Splitter-Pro
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Required Libraries

```bash
pip install pymupdf pandas openpyxl tqdm
```

---

## Usage

Place PDF inside:

```text
uploads/
```

Update path in app.py:

```python
PDF_FILE = r"uploads/turbine.pdf"
```

Run:

```bash
python app.py
```

---

## Example Output

```text
output/

DESCRIPTION - General description - 5.1-0002-04_2.pdf

DESCRIPTION - Fixed points - 5.1-0003-01.pdf

Technical Data - Construction speed and Steam pressure - 5.1-0100-53_3.pdf

Document_Index.xlsx
```

---

## Technologies Used

* Python
* PyMuPDF
* Pandas
* OpenPyXL
* TQDM
* Logging

---

## Use Cases

* BHEL Steam Turbine Manuals
* Technical Documentation
* Engineering Drawings
* OEM Manuals
* Industrial Documentation
* Power Plant Documentation

---

## Future Enhancements

* OCR Support
* AI Subject Detection
* Streamlit Web UI
* ZIP Export
* Batch PDF Processing
* Metadata Extraction

---

## Author

Abhishek Mishra

Python Developer | Data Analytics | PDF Automation | AI Tools
