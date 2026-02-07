import fitz  # PyMuPDF
import re
import argparse


def extract_section(pdf_path, keywords, start_page=None, end_page=None):
    doc = fitz.open(pdf_path)
    section_text = []
    found = False
    # Compile regex for any keyword
    if keywords:
        keyword_pattern = re.compile(
            "|".join([re.escape(k) for k in keywords]), re.IGNORECASE
        )
    else:
        keyword_pattern = None
    for i, page in enumerate(doc):
        # If start_page is specified, skip pages before it
        if start_page is not None and i < start_page:
            continue
        # If end_page is specified, stop after it
        if end_page is not None and i > end_page:
            break
        text = page.get_text()
        # If keywords provided, look for section start
        if keyword_pattern:
            if not found:
                if keyword_pattern.search(text):
                    found = True
            if found:
                section_text.append(f"--- Page {i+1} ---\n{text}")
        else:
            # No keywords, just extract page range
            section_text.append(f"--- Page {i+1} ---\n{text}")
    doc.close()
    return "\n".join(section_text)


def main():
    parser = argparse.ArgumentParser(
        description="Extract a section from a PDF file by keywords or page range."
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=[],
        help="Keywords to identify the section (optional)",
    )
    parser.add_argument(
        "--start-page", type=int, default=None, help="Start page (0-indexed)"
    )
    parser.add_argument(
        "--end-page", type=int, default=None, help="End page (0-indexed)"
    )
    parser.add_argument(
        "--preview", type=int, default=0, help="Number of characters to preview (0=all)"
    )
    args = parser.parse_args()

    section_content = extract_section(
        args.pdf_path, args.keywords, args.start_page, args.end_page
    )
    if section_content:
        print("==== Section Extracted ====")
        if args.preview > 0:
            print(section_content[: args.preview])
        else:
            print(section_content)
    else:
        print("Section not found.")


if __name__ == "__main__":
    main()
