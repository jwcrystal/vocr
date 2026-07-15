#!/usr/bin/env python3
"""PaddleOCR-VL table output parser → markdown.

Usage:
  mlx_vlm.generate --model PaddlePaddle/PaddleOCR-VL-1.6 \
    --image IMG.png --prompt 'Table Recognition:' --max-tokens 4000 | \
    python3 /Users/jwang/bin/paddleocr_vl.py

Or pipe raw PaddleOCR-VL cell-marker text directly:
  echo '<fcel>cell1<lcel><nl><fcel>cell2<lcel><nl>' | python3 paddleocr_vl.py
"""

import re
import sys


def unescape_cell(text: str) -> str:
    """Convert literal escape sequences (\\n, \\t, \\\\, \\", \\') to actual chars."""
    escape_map = {
        "\\n": "\n",
        "\\t": "\t",
        "\\\\": "\\",
        '\\"': '"',
        "\\'": "'",
        "\\r": "",
    }
    for seq, char in escape_map.items():
        text = text.replace(seq, char)
    return text


def sanitize_for_markdown_cell(text: str) -> str:
    """Make cell content safe for markdown table cells."""
    # Unescape first
    text = unescape_cell(text)
    # Newlines → <br> (markdown tables don't support multi-line)
    text = text.replace("\n", "<br>")
    # Escape pipes (they break table structure)
    text = text.replace("|", "\\|")
    return text


def extract_rows(raw: str) -> tuple[list[list[str]], list[str]]:
    """Extract all table rows and plain-text lines from raw output.

    Collects cell-marker content across ALL physical lines into one
    unified row set, preventing fragmented tables with duplicate --- separators.
    """
    all_table_rows: list[list[str]] = []
    plain_lines: list[str] = []

    # Join all cell-marker content into one stream first
    cell_stream = ""
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "<fcel>" in line or "<lcel>" in line or "<ucel>" in line:
            cell_stream += " " + line
        else:
            plain_lines.append(line)

    if cell_stream:
        for row in cell_stream.split("<nl>"):
            row = row.strip()
            if not row:
                continue
            cells = re.findall(r"<fcel>(.*?)(?=<lcel>|<ucel>|<fcel>|<nl>|$)", row)
            cells = [sanitize_for_markdown_cell(c).strip() for c in cells if c.strip()]
            if cells:
                all_table_rows.append(cells)

    return all_table_rows, plain_lines


def build_markdown(table_rows: list[list[str]], plain_lines: list[str]) -> str:
    """Build markdown output from table rows and plain text lines."""
    lines = []

    # Plain text first (if any non-cell content)
    lines.extend(plain_lines)

    if not table_rows:
        return "\n".join(lines)

    # Determine column count
    max_cols = max(len(r) for r in table_rows)
    for r in table_rows:
        while len(r) < max_cols:
            r.append("")

    if max_cols == 1:
        for r in table_rows:
            lines.append(r[0])
    else:
        header = table_rows[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        for r in table_rows[1:]:
            lines.append("| " + " | ".join(r) + " |")

    return "\n".join(lines)


def parse_to_markdown(raw: str) -> str:
    table_rows, plain_lines = extract_rows(raw)
    return build_markdown(table_rows, plain_lines)


def main():
    raw = sys.stdin.read()
    # Strip the mlx_vlm.generate header/footer noise
    # Keep only lines between "Assistant:" and "===="
    if "Assistant:" in raw:
        start = raw.index("Assistant:") + len("Assistant:")
        rest = raw[start:]
        end = rest.index("==========") if "==========" in rest else len(rest)
        raw = rest[:end].strip()

    md = parse_to_markdown(raw)
    print(md)


if __name__ == "__main__":
    main()
