'''
Python Shimadzu QGD Parsing Script
Copyright (c) 2025 Markus Witzler

Heavily inspired and based upon the R script by Ethan Bass: https://doi.org/10.5281/zenodo.6792521.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import olefile
import struct
import numpy as np
import pandas as pd
from io import BytesIO
from typing import Literal, Union


def read_stream(path: str, stream_path: list[str]) -> bytes:
    with olefile.OleFileIO(path) as ole:
        stream = '/'.join(stream_path)
        if ole.exists(stream):
            return ole.openstream(stream).read()
        else:
            raise ValueError(f"Stream {stream} not found in {path}")


def read_retention_times(path: str) -> np.ndarray:
    raw = read_stream(path, ["GCMS Raw Data", "Retention Time"])
    rts = np.frombuffer(raw, dtype='<i4')  # 4-byte little-endian ints
    return rts


def read_spectrum_index(path: str) -> list[int]:
    """
    Reads the Spectrum Index stream from a Shimadzu QGD file for block size validation.
    Returns an array of position offsets.
    """
    raw = read_stream(path, ["GCMS Raw Data", "Spectrum Index"])
    f = BytesIO(raw)
    offsets = []

    while f.tell() < len(raw):
        offset = struct.unpack("<I", f.read(4))[0]
        offsets.append(offset)

    return offsets


def read_qgd_tic(path: str) -> dict:
    raw = read_stream(path, ["GCMS Raw Data", "TIC Data"])
    intensities = np.frombuffer(raw, dtype='<i8')  # 8-byte little-endian ints
    rts = read_retention_times(path)
    return {"retention_time_ms": rts, "intensity": intensities}


def read_ms_block(f, offset_i, offset_next=None, scan_index=None) -> np.ndarray:
    f.seek(offset_i)

    try:
        # Read 32-byte header
        header = f.read(32)
        if len(header) < 32:
            raise ValueError("Incomplete header")

        scan = struct.unpack('<i', header[0:4])[0] # 4 bytes little-endian scan number
        rt_ms = struct.unpack('<i', header[4:8])[0] # 4 bytes little-endian retention time, then skip 12 bytes
        n_bytes = struct.unpack('<H', header[20:22])[0] # 2 bytes for number of bytes in intensity values
        n_val = struct.unpack('<H', header[22:24])[0] # 2 bytes for amount of mz values, then skip 8 bytes

        expected_block_size = 32 + n_val * (2 + n_bytes)

        # If this is not the last scan, validate size against Spectrum Index
        if offset_next is not None:
            actual_block_size = offset_next - offset_i

            if expected_block_size != actual_block_size:
                # Try to deduce correct n_bytes
                data_size = actual_block_size - 32
                corrected = False

                for b in range(1, 6):  # allowed n_bytes
                    if data_size == n_val * (2 + b):
                        print(f"[ByteError corrected] Scan {scan}: corrected n_bytes from {n_bytes} → {b}")
                        n_bytes = b
                        corrected = True
                        break

                if not corrected:
                    raise ValueError(
                        f"[ParseError] Scan {scan}: cannot resolve block size mismatch.\n"
                        f"Expected size from header: {expected_block_size}, from index: {actual_block_size}.\n"
                        f"Check for corruption at offset {offset_i}."
                    )

        # Now read data block
        data_block = f.read(n_val * (2 + n_bytes))
        if len(data_block) < n_val * (2 + n_bytes):
            raise ValueError(f"Incomplete data block at scan {scan}")

        rows = []
        i = 0
        for _ in range(n_val):
            mz = struct.unpack('<H', data_block[i:i+2])[0] / 20.0 # 2 byte mz, scaled by 20, followed by intensity
            raw = data_block[i+2:i+2+n_bytes]

            if n_bytes == 4: #Shimadzu has a weird format, where sometimes in the header n_bytes is 1, but actually 4 bytes are used, but only 7 bits of the fourth byte.
                intensity = int.from_bytes(raw, byteorder='little') & 0x7FFFFFFF
            
            else:
                intensity = int.from_bytes(
                    data_block[i+2:i+2+n_bytes],
                    byteorder='little',
                    signed=False 
                )
            rows.append((scan, rt_ms, mz, intensity))
            i += 2 + n_bytes

        return np.array(rows)

    except Exception as e:
        print(f"[Error] Scan {scan_index or 'unknown'} at offset {offset_i}: {e}")
        return np.empty((0, 4))

def read_qgd_ms(path: str) -> np.ndarray:
    """
    Parses MS1 scan data from a Shimadzu QGD file using Spectrum Index
    for block size validation. Returns an array of [scan, rt, mz, intensity].
    """
    print(f"Preparing MS data...")
    raw_ms = read_stream(path, ["GCMS Raw Data", "MS Raw Data"])
    offsets = read_spectrum_index(path)

    f = BytesIO(raw_ms)
    all_blocks = []
    
    print(f"Reading MS data...")
    for i in range(len(offsets)):
        offset_i = offsets[i]
        offset_next = offsets[i + 1] if i < len(offsets) - 1 else None

        block = read_ms_block(f, offset_i, offset_next, scan_index=i)
        if block.shape[0] > 0:
            all_blocks.append(block)

    return np.vstack(all_blocks) if all_blocks else np.empty((0, 4))



def format_chromatogram(
    data: Union[dict, np.ndarray],
    data_format: Literal["long", "wide"] = "wide"
):
    """
    Formats the output from read_qgd.
    TICs are formatted as retention time in ms and min and total intensity. No long or wide format.
    MS1 data can be given as long or wide tables.
    Long: long table with rows displaying m/z values grouped by scan number
        Scan number, RT (ms), RT (min), m/z value, intensity
    Wide: pivoted table to have one row per scan/rt
        RT (min), RT(ms), total intensity (TIC), intensity for each (rounded) m/z value -> n
    """
    print(f"Formatting data...")
    if isinstance(data, dict):  # TIC
        return [{"rt / ms": rt, "rt / min": float(rt / 60000), "intensity": int(it)}
                for rt, it in zip(data["retention_time_ms"], data["intensity"])]

    else:  # MS1 data
        ms_data = [{"scan": int(s), "rt / ms": int(rt), "rt / min": float(rt / 60000), "mz": float(mz), "intensity": int(it)}
                    for s, rt, mz, it in data]
        if data_format == "long":
            return ms_data
        else:
            df_ms1 = pd.DataFrame(ms_data)
            df_ms1["mz_rounded"] = df_ms1["mz"].round().astype(int)
            df_ms1["rt / min"] = df_ms1["rt / min"].round(5)
            df_ms1["intensity"] = df_ms1["intensity"].astype(int)

            # Pivot to matrix (RT × m/z), intensity summed per bin
            pivot = df_ms1.pivot_table(
                index=["rt / min", "rt / ms"],
                columns="mz_rounded",
                values="intensity",
                aggfunc="sum"
            ).fillna(0).astype(int)

            # Calculate total intensity for each RT
            pivot["total_intensity"] = pivot.sum(axis=1)

            #move total intensity to column 2
            cols = pivot.columns.tolist()
            cols = [c for c in cols if c != "total_intensity"]
            pivot = pivot[["total_intensity"] + cols]
            return pivot

def read_shimadzu_qgd(
    path: str,
    what: list[str] = ["MS1", "TIC"],
    data_format: Literal["wide", "long"] = "wide"
) -> dict:
    result = {}
    if "TIC" in what:
        result["TIC"] = format_chromatogram(read_qgd_tic(path), data_format)
    if "MS1" in what:
        result["MS1"] = format_chromatogram(read_qgd_ms(path), data_format)
    return result
