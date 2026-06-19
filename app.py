import argparse
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path

import fitz
import pandas as pd
from tqdm import tqdm


BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
CONFIG_DIR = BASE_DIR / "config"

DEFAULT_PDF_FILE = UPLOADS_DIR / "input.pdf"

DOC_NO_RE = re.compile(
    r"\b\d+(?:\.\d+)+-\d{4}(?:-\d{2})?(?:[/_-]\d+)?\b"
)

INVALID_FILENAME_RE = re.compile(r'[<>:"/\\|?*]')
MAX_OUTPUT_FILENAME_LENGTH = 120
MAX_FILENAME_COMPONENT_LENGTH = 70
TRUNCATION_HASH_LENGTH = 8


def setup_directories():
    for folder in [UPLOADS_DIR, OUTPUT_DIR, REPORTS_DIR, LOGS_DIR, CONFIG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def setup_logging():
    setup_directories()

    log_file = LOGS_DIR / f"splitter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    return logging.getLogger("AI_PDF_SUBJECT_SPLITTER")


logger = setup_logging()


def clean_text(value):
    value = str(value or "")
    value = value.replace("\u25a0", " ")
    value = value.replace("▪", " ")
    value = value.replace("●", " ")
    value = value.replace("•", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_subject(value):
    value = clean_text(value)
    value = value.replace("&", "and")
    value = re.sub(r"[,:;]+", "", value)
    return value.strip(" .-")


def clean_filename(value):
    value = clean_text(value)
    value = INVALID_FILENAME_RE.sub("_", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .")


def truncate_filename(value, max_length):
    value = str(value or "")
    if len(value) <= max_length:
        return value
    if max_length <= 3:
        return value[:max_length]
    return value[: max_length - 3].rstrip() + "..."


def get_short_hash(value, length=TRUNCATION_HASH_LENGTH):
    digest = hashlib.sha1(str(value).encode("utf-8", errors="ignore")).hexdigest()
    return digest[:length]


def normalize_document_number(value):
    value = str(value or "").strip()
    match = DOC_NO_RE.search(value)

    if not match:
        return clean_text(value)

    doc_no = match.group(0).replace("_", "/")

    dash_suffix = re.match(r"^(.+-\d{2})-(\d+)$", doc_no)
    if dash_suffix:
        doc_no = f"{dash_suffix.group(1)}/{dash_suffix.group(2)}"

    return doc_no


def contains_document_number(value):
    return DOC_NO_RE.search(str(value or "")) is not None


def document_base_key(value):
    doc_no = normalize_document_number(value)
    match = re.search(r"\d+(?:\.\d+)+-\d{4}(?:-\d{2})?", doc_no)
    return match.group(0) if match else doc_no


def compact_key(value):
    return re.sub(r"\D", "", str(value or ""))


def filename_document_number(value):
    return normalize_document_number(value).replace("/", "_")


def unique_output_path(folder, filename):
    filename = clean_filename(filename)
    stem = Path(filename).stem
    suffix = Path(filename).suffix or ".pdf"
    candidate = f"{stem}{suffix}"
    counter = 1

    while (folder / candidate).exists():
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1

    return folder / candidate


def detect_subject_from_page(page, fallback):
    text = page.get_text("text")

    for line in text.splitlines():
        line = clean_subject(line)

        if len(line) < 5:
            continue

        if line.isdigit():
            continue

        if DOC_NO_RE.fullmatch(line):
            continue

        return line[:120]

    return fallback or "Unknown Subject"


def get_bookmarks(doc):
    toc = doc.get_toc()
    bookmarks = []

    for item in toc:
        if len(item) < 3:
            continue

        level, title, page = item[0], clean_text(item[1]), item[2]

        if page <= 0:
            continue

        bookmarks.append(
            {
                "level": level,
                "title": title,
                "page": page,
                "document_number": normalize_document_number(title),
                "base_key": document_base_key(title),
                "has_document_number": contains_document_number(title),
            }
        )

    return bookmarks


def get_contents_scan_pages(doc, bookmarks):
    if not bookmarks:
        return min(30, len(doc))

    first_bookmark_page = min(bookmark["page"] for bookmark in bookmarks)

    if first_bookmark_page > 1:
        return min(first_bookmark_page - 1, len(doc))

    return min(30, len(doc))


def looks_like_category(line):
    line = clean_text(line)

    if not line:
        return False

    if DOC_NO_RE.search(line):
        return False

    if len(line) > 80:
        return False

    if re.search(r"\d{2,}", line):
        return False

    if len(line.split()) > 8:
        return False

    words = re.findall(r"[A-Za-z]+", line)

    if not words:
        return False

    for word in words:
        if word.isupper():
            continue

        if word[0].isupper() and word[1:].islower():
            continue

        return False

    return True


def has_bullet(value):
    value = str(value or "").lstrip()
    return value.startswith(("■", "▪", "●", "•", "-", "*"))


def is_contents_header(line):
    return clean_text(line).lower() in {
        "subject document no",
        "subject document number",
        "subject",
        "document no",
        "document number",
        "contents",
        "index",
    }


def join_subject_parts(parts):
    cleaned_parts = []

    for part in parts:
        part = clean_subject(part)
        if part:
            cleaned_parts.append(part)

    return clean_subject(" ".join(cleaned_parts))


def add_contents_mapping(mapping, category, subject, document_number):
    category = clean_text(category)
    subject = clean_subject(subject)
    document_number = normalize_document_number(document_number)

    if not subject or not document_number:
        return

    data = {
        "Category": category or "Unknown Category",
        "Subject": subject,
        "Document Number": document_number,
        "Base Key": document_base_key(document_number),
    }

    keys = {
        document_number,
        document_base_key(document_number),
        compact_key(document_number),
        compact_key(document_base_key(document_number)),
    }

    for key in keys:
        if key:
            mapping[key] = data


def extract_contents_mapping(doc, bookmarks):
    mapping = {}
    scan_pages = get_contents_scan_pages(doc, bookmarks)
    current_category = "Unknown Category"
    current_main_category = ""
    current_sub_category = ""
    category_has_entries = False
    last_line_was_category = False
    pending_subject_parts = []
    last_document_key = ""

    logger.info("Scanning %s page(s) for contents/index data", scan_pages)

    for page_index in range(scan_pages):
        page = doc[page_index]
        text = page.get_text("text")

        for raw_line in text.splitlines():
            line = clean_text(raw_line)

            if not line:
                continue

            if is_contents_header(line):
                continue

            doc_match = DOC_NO_RE.search(line)

            if doc_match:
                document_number = normalize_document_number(doc_match.group(0))
                before_doc_no = clean_subject(line[:doc_match.start()])
                subject_parts = pending_subject_parts[:]

                if before_doc_no:
                    subject_parts.append(before_doc_no)

                subject = join_subject_parts(subject_parts)

                if not subject:
                    subject = document_number

                add_contents_mapping(
                    mapping=mapping,
                    category=current_category,
                    subject=subject,
                    document_number=document_number,
                )

                last_document_key = document_base_key(document_number)
                pending_subject_parts = []
                category_has_entries = True
                last_line_was_category = False
                continue

            cleaned_line = clean_subject(line)

            if not cleaned_line or cleaned_line.isdigit():
                continue

            if has_bullet(raw_line):
                pending_subject_parts = [cleaned_line]
                last_line_was_category = False
                continue

            if (
                last_document_key
                and pending_subject_parts == []
                and not looks_like_category(cleaned_line)
            ):
                for key in [last_document_key, compact_key(last_document_key)]:
                    if key in mapping:
                        mapping[key]["Subject"] = join_subject_parts(
                            [mapping[key]["Subject"], cleaned_line]
                        )
                last_document_key = ""
                continue

            if looks_like_category(cleaned_line) and not pending_subject_parts:
                if current_main_category and last_line_was_category and not category_has_entries:
                    current_sub_category = cleaned_line
                    current_category = join_subject_parts(
                        [current_main_category, current_sub_category]
                    )
                else:
                    current_main_category = cleaned_line
                    current_sub_category = ""
                    current_category = cleaned_line

                pending_subject_parts = []
                category_has_entries = False
                last_line_was_category = True
            else:
                pending_subject_parts.append(cleaned_line)
                last_line_was_category = False

    return mapping


def find_contents_match(mapping, bookmark):
    candidates = [
        bookmark["document_number"],
        bookmark["base_key"],
        compact_key(bookmark["document_number"]),
        compact_key(bookmark["base_key"]),
        compact_key(bookmark["title"]),
    ]

    for key in candidates:
        if key and key in mapping:
            return mapping[key]

    bookmark_digits = compact_key(bookmark["title"])

    for key, value in mapping.items():
        key_digits = compact_key(key)

        if key_digits and bookmark_digits and key_digits in bookmark_digits:
            return value

        if key_digits and bookmark_digits and bookmark_digits in key_digits:
            return value

    return None


def build_filename(category, subject, document_number):
    category = clean_filename(category or "Unknown Category")
    subject = clean_filename(clean_subject(subject or "Unknown Subject"))
    doc_no = clean_filename(filename_document_number(document_number)) or "unknown"

    base_name = f"{category}_{subject}_{doc_no}"
    max_body_length = MAX_OUTPUT_FILENAME_LENGTH - 4

    if len(base_name) > max_body_length:
        category_limit = min(len(category), MAX_FILENAME_COMPONENT_LENGTH, max_body_length // 3)
        subject_limit = min(len(subject), MAX_FILENAME_COMPONENT_LENGTH, max_body_length - category_limit - len(doc_no) - 1)
        subject_limit = max(subject_limit, 0)

        if len(category) > category_limit:
            category = truncate_filename(category, category_limit)

        if subject and len(subject) > subject_limit:
            subject = truncate_filename(subject, subject_limit)

        base_name = f"{category}_{subject}_{doc_no}" if subject else f"{category}_{doc_no}"

        if len(base_name) > max_body_length:
            short_hash = get_short_hash(f"{base_name}_{document_number}")
            allowed = max_body_length - len(short_hash) - 1
            prefix = truncate_filename(base_name, allowed)
            base_name = f"{prefix}_{short_hash}"

    filename = f"{base_name}.pdf"
    if len(filename) > MAX_OUTPUT_FILENAME_LENGTH:
        filename = truncate_filename(filename, MAX_OUTPUT_FILENAME_LENGTH - 4) + ".pdf"

    return filename


def split_pdf(pdf_file):
    pdf_file = Path(pdf_file)

    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_file}")

    setup_directories()

    logger.info("=" * 60)
    logger.info("AI PDF SUBJECT SPLITTER PRO")
    logger.info("=" * 60)
    logger.info("Input PDF: %s", pdf_file)

    doc = fitz.open(pdf_file)
    total_pages = len(doc)

    logger.info("PDF loaded successfully")
    logger.info("Total pages: %s", total_pages)

    bookmarks = get_bookmarks(doc)
    logger.info("Bookmarks found: %s", len(bookmarks))

    if not bookmarks:
        logger.warning("No bookmarks found. Nothing to split.")
        doc.close()
        return

    contents_mapping = extract_contents_mapping(doc, bookmarks)
    logger.info("Contents mapping entries found: %s", len(contents_mapping))

    split_bookmarks = [
        bookmark
        for bookmark in bookmarks
        if bookmark["has_document_number"]
    ]

    if not split_bookmarks:
        logger.warning(
            "No document-number bookmarks found. Falling back to all bookmarks."
        )
        split_bookmarks = bookmarks

    logger.info("Split bookmarks used: %s", len(split_bookmarks))

    report_rows = []

    for index, bookmark in enumerate(tqdm(split_bookmarks, desc="Splitting PDF", unit="file")):
        start_page = bookmark["page"]

        if index < len(split_bookmarks) - 1:
            end_page = split_bookmarks[index + 1]["page"] - 1
        else:
            end_page = total_pages

        if end_page < start_page:
            logger.warning(
                "Skipping invalid page range for bookmark %s: %s-%s",
                bookmark["title"],
                start_page,
                end_page,
            )
            continue

        try:
            page = doc[start_page - 1]
            match = find_contents_match(contents_mapping, bookmark)

            if match:
                category = match["Category"]
                subject = match["Subject"]
            else:
                category = "Unknown Category"
                subject = detect_subject_from_page(
                    page,
                    fallback=bookmark["document_number"] or bookmark["title"],
                )

            document_number = bookmark["document_number"] or bookmark["title"]
            output_name = build_filename(category, subject, document_number)
            output_path = unique_output_path(OUTPUT_DIR, output_name)

            new_pdf = fitz.open()
            new_pdf.insert_pdf(
                doc,
                from_page=start_page - 1,
                to_page=end_page - 1,
            )
            new_pdf.save(output_path)
            new_pdf.close()

            report_rows.append(
                {
                    "Category": category,
                    "Subject": subject,
                    "Document Number": document_number,
                    "Start Page": start_page,
                    "End Page": end_page,
                    "Page Count": end_page - start_page + 1,
                    "Output PDF Name": output_path.name,
                    "Output Path": str(output_path),
                }
            )

            logger.info(
                "Created: %s | Pages %s-%s",
                output_path.name,
                start_page,
                end_page,
            )

        except Exception as exc:
            logger.exception("Failed bookmark: %s | Error: %s", bookmark["title"], exc)

    report_file = REPORTS_DIR / f"Document_Index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    try:
        df = pd.DataFrame(report_rows)
        df.to_excel(report_file, index=False)

        logger.info("=" * 60)
        logger.info("PROCESS COMPLETED")
        logger.info("=" * 60)
        logger.info("PDFs saved in: %s", OUTPUT_DIR)
        logger.info("Excel report: %s", report_file)
        logger.info("Total PDFs created: %s", len(report_rows))

    except Exception as exc:
        logger.exception("Excel report generation failed: %s", exc)

    doc.close()


def main():
    parser = argparse.ArgumentParser(description="AI PDF Subject Splitter Pro")
    parser.add_argument(
        "--pdf",
        default=str(DEFAULT_PDF_FILE),
        help="Path to input PDF. Default: uploads/input.pdf",
    )
    args = parser.parse_args()
    split_pdf(args.pdf)


if __name__ == "__main__":
    main()
