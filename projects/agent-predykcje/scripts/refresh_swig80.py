"""Standalone script: refresh the 'swig80' watchlist section from the GPW Benchmark PDF.

Run from the project directory (or anywhere):

    python scripts/refresh_swig80.py --pdf path/to/Portfele.pdf
    python scripts/refresh_swig80.py --url https://example.com/Portfele.pdf

The script parses the sWIG80 portfolio composition (rows with a price and
weight column; the reserve list is skipped), matches entries by ISIN, and
rewrites watchlist.yaml preserving the header comment and the 'stocks' /
'indices' sections. Verified symbols are never re-derived from tickers:
new entries get ``needs_symbol_verification: true`` instead.
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

import yaml
from pypdf import PdfReader

DEFAULT_WATCHLIST = Path(__file__).resolve().parent.parent / "watchlist.yaml"

# Main-table row: Lp ISIN Kod Kurs Liczba-akcji Udział. Reserve-list rows
# have no price/weight columns, so they never match.
ROW_RE = re.compile(
    r"^(\d{1,2})\s+([A-Z]{2}[A-Z0-9]{10})\s+([A-Z0-9.]+)\s+([\d,]+)\s+([\d ]+)\s+(\d+,\d+)",
    re.MULTILINE,
)


class _ArgumentParser(argparse.ArgumentParser):
    """argparse with Polish error prefix and exit code 1 instead of 2."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"błąd argumentów: {message}\n")


def parse_portfolio_pdf(pdf_path) -> list:
    """Return the sWIG80 rows from the GPW Benchmark PDF.

    Only pages whose header contains 'sWIG80' are parsed. Each row is
    ``{isin, kod, name}``; the name is the best-effort token from the PDF.
    """
    reader = PdfReader(str(pdf_path))
    rows = []
    for page in reader.pages:
        text = page.extract_text() or ""
        header = text.splitlines()[0] if text.splitlines() else ""
        if "sWIG80" not in header:
            continue
        for match in ROW_RE.finditer(text):
            rows.append(
                {"isin": match.group(2), "kod": match.group(3), "name": match.group(3)}
            )
    return rows


def update_entries(parsed: list, existing: list) -> list:
    """Merge parsed sWIG80 rows into the existing watchlist entries.

    Entries are matched by ISIN and ordered as in `parsed`. Existing
    entries keep their verified symbol/name/ticker (and any other flags);
    new rows get ``needs_symbol_verification: true`` instead of a derived
    symbol. Entries absent from `parsed` are dropped.
    """
    by_isin = {entry.get("isin"): entry for entry in existing if entry.get("isin")}
    updated = []
    for row in parsed:
        entry = by_isin.get(row["isin"])
        if entry is None:
            updated.append(
                {
                    "symbol": None,
                    "ticker": None,
                    "name": row["kod"],
                    "isin": row["isin"],
                    "needs_symbol_verification": True,
                }
            )
        else:
            updated.append(dict(entry))
    return updated


def _download_pdf(url: str) -> Path:
    """Download the PDF from `url` to a temporary file and return its path."""
    fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        with urllib.request.urlopen(url) as response, open(tmp_path, "wb") as out:
            shutil.copyfileobj(response, out)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise
    return Path(tmp_path)


def _load_watchlist(path) -> tuple:
    """Load watchlist.yaml, returning (header_comment_lines, data).

    Full-line comments at the top of the file are captured verbatim so
    they survive the rewrite; non-mapping documents raise yaml.YAMLError.
    """
    text = Path(path).read_text(encoding="utf-8")
    header_lines = []
    for line in text.splitlines():
        if line.startswith("#"):
            header_lines.append(line)
        elif not line.strip():
            continue
        else:
            break
    watchlist = yaml.safe_load(text)
    if not isinstance(watchlist, dict):
        raise yaml.YAMLError(
            "plik musi zawierać mapę z sekcjami 'stocks', 'indices' i 'swig80'"
        )
    return header_lines, watchlist


def _write_watchlist(path, watchlist: dict, header_lines: list) -> None:
    """Write the watchlist back, header comment first, other sections intact."""
    body = yaml.safe_dump(
        watchlist, allow_unicode=True, sort_keys=False, default_flow_style=False
    )
    Path(path).write_text(
        "".join(f"{line}\n" for line in header_lines) + body, encoding="utf-8"
    )


def main(argv) -> int:
    parser = _ArgumentParser(
        prog="refresh_swig80.py",
        description="Odświeża sekcję 'swig80' watchlisty na podstawie PDF GPW Benchmark.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pdf", metavar="PATH", help="ścieżka do PDF GPW Benchmark")
    source.add_argument(
        "--url",
        metavar="URL",
        help="adres URL PDF GPW Benchmark (pobrany do pliku tymczasowego)",
    )
    parser.add_argument(
        "--watchlist",
        metavar="PATH",
        default=DEFAULT_WATCHLIST,
        help=f"ścieżka do watchlist.yaml (domyślnie: {DEFAULT_WATCHLIST})",
    )
    args = parser.parse_args(argv)

    temp_pdf = None
    try:
        if args.url:
            temp_pdf = _download_pdf(args.url)
            pdf_path = temp_pdf
        else:
            pdf_path = Path(args.pdf)
        rows = parse_portfolio_pdf(pdf_path)
    except Exception as exc:
        print(f"Błąd pobierania/parsowania PDF: {exc}", file=sys.stderr)
        return 1
    finally:
        if temp_pdf is not None:
            temp_pdf.unlink(missing_ok=True)

    try:
        header_lines, watchlist = _load_watchlist(args.watchlist)
        watchlist["swig80"] = update_entries(rows, watchlist.get("swig80") or [])
        _write_watchlist(args.watchlist, watchlist, header_lines)
    except Exception as exc:
        print(f"Błąd aktualizacji watchlisty: {exc}", file=sys.stderr)
        return 1
    print(f"Zaktualizowano sekcję 'swig80': {len(rows)} wpisów w {args.watchlist}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
