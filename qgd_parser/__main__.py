#------------------------------------------------------------------------------
# CHANGELOG:
# 2025-12-11: 0.0.1 - first version
# 2026-01-09: 0.1.0 - first published version
# 2026-01-12: 0.2.0 - change main dir management logic and add batch conversion, now using args in CLI
# 2026-01-14: 0.2.4 - minor bug fixes and output style

__version__ = '0.2.4'


# == IMPORTS ==================================================================

from parser import read_shimadzu_qgd
from pathlib import Path
import pandas as pd
import sys
from datetime import datetime
import argparse


def ensure_dir(path: Path) -> None:
    """Create directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def unique_output_path(output_dir: Path, stem: str, suffix: str = ".csv") -> Path:
    """
    Build an output path in output_dir using <stem><suffix>.
    If it already exists, append a timestamp (and, if needed, a counter) to avoid overwriting.
    """
    base = output_dir / f"{stem}{suffix}"
    if not base.exists():
        return base

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = output_dir / f"{stem}_{timestamp}{suffix}"
    if not candidate.exists():
        return candidate

    # Extremely rare: two runs create the same timestamped name; add a counter.
    counter = 2
    while True:
        candidate = output_dir / f"{stem}_{timestamp}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def convert_one(input_path: Path, output_dir: Path, what: str, data_format: str) -> Path:
    """
    Convert one .qgd file to CSV and return the written output path.
    """
    inwhat = ["TIC"] if what.upper() == "TIC" else ["MS1"]
    data_fmt = "long" if data_format.lower() == "long" else "wide"
    
    print(f"▶️ Loading {input_path.name}, with options {inwhat}, {data_fmt} ...")
    result = read_shimadzu_qgd(str(input_path), what=inwhat, data_format=data_fmt)

    # result key matches "MS1" or "TIC"
    df_result = pd.DataFrame(result[inwhat[0]])

    out_path = unique_output_path(output_dir, input_path.stem, suffix=".csv")
    df_result.to_csv(out_path, index=True)
    return out_path


def parse_args():
    """
    CLI interface:
      - Default: batch convert ./input/*.qgd -> ./output/
      - Optional: --input-dir, --output-dir
      - Optional: --file to convert a single file
      - Optional: --what (MS1/TIC), --format (wide/long)
    """
    parser = argparse.ArgumentParser(description="Convert Shimadzu .qgd files to CSV.")
    parser.add_argument("--input-dir", type=Path, default=Path("input"),
                        help="Folder containing .qgd files (default: ./input)")
    parser.add_argument("--output-dir", type=Path, default=Path("output"),
                        help="Folder for CSV outputs (default: ./output)")
    parser.add_argument("--file", type=str, default=None,
                        help="Convert a single file (name within input-dir or full path). If omitted, batch mode runs.")
    parser.add_argument("--what", choices=["MS1", "TIC"], default="MS1",
                        help="Which data to export (default: MS1)")
    parser.add_argument("--format", dest="data_format", choices=["wide", "long"], default="wide",
                        help="Output table format (default: wide)")
    return parser.parse_args()


def main():
    args = parse_args()

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    # Directory management
    ensure_dir(output_dir)
    ensure_dir(input_dir)  # keeps your previous behavior; also helps users discover where to put files

    # Determine mode: single-file if --file is provided, otherwise batch.
    if args.file:
        # Allow either a full path or a name relative to input_dir
        candidate = Path(args.file)
        input_path = candidate if candidate.is_file() else (input_dir / args.file)

        if input_path.suffix.lower() != ".qgd":
            input_path = input_path.with_suffix(".qgd")

        if not input_path.is_file():
            print(f"❌ Error: File '{input_path}' not found.")
            sys.exit(1)

        out_path = convert_one(input_path, output_dir, what=args.what, data_format=args.data_format)
        print(f"✅ Complete. File saved as {out_path}")
        return

    # Batch mode (default)
    qgd_files = sorted(input_dir.glob("*.qgd"))
    if not qgd_files:
        print(f"❌ No .qgd files found in '{input_dir}'.")
        return

    for input_path in qgd_files:
        try:
            out_path = convert_one(input_path, output_dir, what=args.what, data_format=args.data_format)
            print(f"✅ Converted: {input_path.name} -> {out_path.name}")
        except Exception as e:
            # Continue batch even if one file fails
            print(f"❌ Failed: {input_path.name} ({e})")

    print("🏆 Batch conversion complete.")


if __name__ == "__main__":
    main()
