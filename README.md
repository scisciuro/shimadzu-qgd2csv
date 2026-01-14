# shimadzu-qgd2csv
A Python script to convert Shimadzu GC-MS `.qgd` files into `.csv` files for further processing. Provides TIC as well as TIC and individual m/z data.
It is inspired and partly based on the R script from Bass, E. (2025). chromConverter: Chromatographic File Converter. http://doi.org/10.5281/zenodo.6792521, read_shimadzu_qgd.R

# How it works
The script takes a `.qgd` file from Shimadzu GCMSsolution as input. It consists of several binary streams, some of which are used to parse the information into a .csv file.
The "GCMS Raw Data" storage in the `.qgd` file contains - among others - the following data streams:

## "Retention Time"
Contains all retention times (RT) in milliseconds, stored as 4-byte little-endian integers.

## "TIC Data"
Contains the total ion chromatogram intensity values, stored as 8-byte little-endian integers.

## "MS Raw Data"
Contains the individual MS scans: m/z intensities per retention time, all as little-endian integers. It consists of a 32 byte header and an array of m/z -- intensity pairs.
The header consists of:
- scan number (4-byte integer)
- retention time (4-byte integer)
- unknown (12-bytes)
- number of bytes in intensity values (2-byte integer)
- unknown (8-bytes)

The m/z values are encoded as 2-byte integers, scaled by a factor of 20. The intensities are unsigned integers, where the byte-length is defined in the header. It is usually 2 or 3. However in some cases (high intensities than show as cut-offs in the GCMSsolution), the byte length is given as 1, although the intensity block is actually of a 4-byte length. In this case, of the last byte, only half is used (format: `0x7FFFFFFF`). This is checked and accounted for in the data import.

This script comes with an `example.qgd`, which has one scan than needs correcting.

## "Spectrum Index"
Contains the start byte positions of each new MS scan (aka retention time) in the "MS Raw Data" stream. This is used to validate each scan's block length and correct for possible mismatches, especially for high intensities.

# Import options
The script is now controlled using the CLI. The default mode is "batch conversion" of .input/*.qgd to ./output/*.csv using "MS1" data and "wide" format.
- Optional: `--input-dir` and `--output-dir` <- specify input/output folder
- Optional: `--file` <- specify a sigle file for conversion (Path or filename in ./input/)
- Optional: `--what` <- Import **MS1** (default) or **TIC**: "MS1" contains data of all retention times, m/z values, and intensities, plus the TIC. "TIC" only has retention time and TIC.
- Optional: `--format` <- Format **long** or **wide** (default): "long" generates a "list" of m/z and intensity values, blocked by retention time/scan number. "wide" generates a table with the intensity values as one scan per row and retention time, TIC, and each m/z value as columns.

Retention times are given in milliseconds and minutes for further processing.
m/z values are rounded to full integers.

# Example output structures
From example.qgd.
Output as comma-separated file, shown here in tabulated form for clarity.
## TIC
||rt / ms|rt / min|intensity|
|---|---|---|---|
|0|90000|1.5|3410925|
|1|90100|1.5016666666666667|1407892|
|2|90200|1.5033333333333334|274104|
|3|90300|1.505|194665|
|...|...|...|...|
|7331|823100|13.718333333333334|258515|

## MS1 & wide (default)
`Preparing MS data...`
`Reading MS data...`
`[ByteError corrected] Scan 4212: corrected n_bytes from 1 → 4`
`Formatting data...`

|rt / min|rt / ms|total_intensity|35|36|37|...|400|
|---|---|---|---|---|---|---|---|
|1.5|90000|3410925|31082|30505|29757|...|586|
|1.50167|90100|1407892|12749|12505|12233|...|535|
|1.50333|90200|274104|1149|1051|1098|...|517|
|1.505|90300|194665|602|506|602|...|530|
|...|...|...|...|...|...|...|...|
|13.71833|823100|258515|484|532|491|...|533|

## MS1 & long
`Preparing MS data...`
`Reading MS data...`
`[ByteError corrected] Scan 4212: corrected n_bytes from 1 → 4`
`Formatting data...`
||scan|rt / ms|rt / min|mz|intensity|
|---|---|---|---|---|---|
|0|0|90000|1.5|35.1|31082|
|1|0|90000|1.5|36.15|30505|
|2|0|90000|1.5|37.15|29757|
|3|0|90000|1.5|38.15|29832|
|4|0|90000|1.5|39.05|29580|
|...|...|...|...|...|...|
|2683113|7331|823100|13.718333333333334|400.2|533|

---
# Changelog
- 2025-12-11: 0.0.1 - first version
- 2026-01-09: 0.1.0 - first published version
- 2026-01-14: 0.2.4 - changed file handling, added batch conversion, minor style tweaks

# Future steps
- options for metadata
