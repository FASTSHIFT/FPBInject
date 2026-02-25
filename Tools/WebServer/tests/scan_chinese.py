#!/usr/bin/env python3

"""
Chinese Text Scanner for WebServer Project

Scans all .js and .html files in the WebServer directory for Chinese text.
Reports file paths, line numbers, and Chinese strings found.
"""

import os
import re


def find_chinese_text(content):
    """Find all Chinese text sequences in content."""
    # Match Chinese characters (CJK Unified Ideographs)
    chinese_pattern = r"[\u4e00-\u9fff]+"
    return re.findall(chinese_pattern, content)


def scan_file(file_path):
    """Scan a single file for Chinese text."""
    findings = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            chinese_texts = find_chinese_text(line)
            if chinese_texts:
                for chinese_text in chinese_texts:
                    findings.append(
                        {
                            "line": line_num,
                            "text": chinese_text.strip(),
                            "context": line.strip(),
                        }
                    )
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return findings


def scan_directory(root_dir):
    """Scan directory recursively for .js and .html files."""
    results = {}

    # Directories and files to exclude (i18n locale files are expected to have Chinese)
    exclude_dirs = {"locales", "node_modules", "__pycache__", ".git"}
    exclude_files = {
        "zh-CN.js",
        "zh-TW.js",
        "config_schema.py",
    }  # config_schema.py has language option labels

    for root, dirs, files in os.walk(root_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            # Skip excluded files
            if file in exclude_files:
                continue

            if file.endswith((".js", ".html", ".py")):
                file_path = os.path.join(root, file)
                findings = scan_file(file_path)
                if findings:
                    results[file_path] = findings

    return results


def main():
    # Get the WebServer directory (parent of tests)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    webserver_dir = os.path.dirname(script_dir)

    print("Scanning for Chinese text in .js, .html, and .py files...")
    print(f"Directory: {webserver_dir}")
    print("-" * 60)

    results = scan_directory(webserver_dir)

    if not results:
        print("No Chinese text found in .js, .html, and .py files.")
        return

    total_files = len(results)
    total_findings = sum(len(findings) for findings in results.values())

    print(
        f"Found Chinese text in {total_files} files ({total_findings} total instances):"
    )
    print()

    for file_path, findings in results.items():
        rel_path = os.path.relpath(file_path, webserver_dir)
        print(f"📁 {rel_path} ({len(findings)} instances):")

        for finding in findings:
            print(f"  Line {finding['line']}: \"{finding['text']}\"")
            print(
                f"    Context: {finding['context'][:100]}{'...' if len(finding['context']) > 100 else ''}"
            )
        print()

    print("-" * 60)
    print(
        f"Summary: {total_files} files with Chinese text, {total_findings} instances total."
    )


if __name__ == "__main__":
    main()
