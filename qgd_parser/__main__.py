#------------------------------------------------------------------------------
# CHANGELOG:
# 2025-12-11: 0.0.1 - first version
# 2026-01-09: 0.1.0 - first published version

__version__ = '0.1.0'


# == IMPORTS ==================================================================

from parser import read_shimadzu_qgd
from pathlib import Path
import pandas as pd
import sys
from datetime import datetime

def main():
    """main function with directory management"""
    # Setup default directories
    input_dir = Path("input")
    output_dir = Path("output")
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    inputfname = input("Enter file path (or file name if file in ./input/): ").strip()
    while not inputfname:
        inputfname = input("Enter a valid file name: ").strip()

    # Ensure .qgd extension and check path
    input_path = input_dir / inputfname
    if input_path.suffix != ".qgd":
        input_path = input_path.with_suffix(".qgd")

    # Check if input file exists else Error and quit
    if not input_path.is_file():
        print(f"Error: File '{input_path}' not found in '{input_dir}' folder.")
        sys.exit(1)

    # Output naming
    outputfname = input("Enter output file path or file name (leave empty for ./output/input.csv): ").strip()
    if not outputfname:
        output_path = output_dir / f"{input_path.stem}.csv"
    else:
        output_path = output_dir / outputfname
        if output_path.suffix != ".csv":
            output_path = output_path.with_suffix(".csv")

    # Check if output exists, Warn, and handle Timestamp
    if output_path.exists():
        choice = input(f"Warning: '{output_path.name}' exists. Overwrite? (y/n): ").lower()
        if choice != 'y':
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Appends timestamp before the .csv extension
            output_path = output_path.with_stem(f"{output_path.stem}_{timestamp}")
            print(f"Saving to new path: {output_path}")

    # Format choices for converting
    inputwhat = input("Choose MS1 (default) or TIC: ").strip().upper()
    inputformat = input("Choose data format - wide (default) or long: ").strip().lower()

    inwhat = ["TIC"] if inputwhat == "TIC" else ["MS1"]
    data_fmt = "long" if inputformat == "long" else "wide"

    # Read QGD file with format options and convert to CSV
    result = read_shimadzu_qgd(str(input_path), what=inwhat, data_format=data_fmt)

    df_result = pd.DataFrame(result[f"{inwhat[0]}"])
    df_result.to_csv(f"{output_path}")
    print(f"Complete. File saved as {output_path}")


if __name__ == "__main__":
    main()