"""
Local Flood Detection — for satellite images you've already downloaded.

Works with either:
  - SAR imagery (e.g. Sentinel-1 GRD, single band, dB values) -> threshold-based
  - Optical imagery (e.g. Sentinel-2/Landsat, needs Green + NIR bands) -> NDWI

Usage examples:

  SAR mode (single-band before/after GeoTIFFs):
    python local_flood_detection.py --mode sar --before before.tif --after after.tif --output flood.tif

  Optical mode (multi-band GeoTIFFs, specify band indices for Green and NIR):
    python local_flood_detection.py --mode optical --before before.tif --after after.tif \\
        --green-band 3 --nir-band 4 --output flood.tif

Run with --help for all options.
"""

import argparse
import sys

import numpy as np
import rasterio
from scipy import ndimage


def read_band(path, band=1):
    with rasterio.open(path) as src:
        data = src.read(band).astype("float32")
        profile = src.profile
        nodata = src.nodata
    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)
    return data, profile


def check_alignment(profile_a, profile_b):
    if profile_a["crs"] != profile_b["crs"]:
        raise ValueError(
            "CRS mismatch between before/after images. Re-download both from the "
            "same source so they share a coordinate reference system."
        )
    if profile_a["width"] != profile_b["width"] or profile_a["height"] != profile_b["height"]:
        raise ValueError(
            "Image dimensions don't match between before/after. Make sure both "
            "images cover the same area at the same resolution."
        )


def detect_water_sar(band, threshold_db=-16):
    return band < threshold_db


def detect_water_optical(green, nir):
    """NDWI = (Green - NIR) / (Green + NIR); values > 0 typically indicate water."""
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = (green - nir) / (green + nir)
    return ndwi > 0


def clean_mask(mask, min_pixels=8):
    """Remove small isolated noise blobs from a boolean flood mask."""
    labeled, num = ndimage.label(mask)
    if num == 0:
        return mask
    sizes = ndimage.sum(mask, labeled, range(1, num + 1))
    keep = np.zeros_like(mask)
    for i, size in enumerate(sizes, start=1):
        if size >= min_pixels:
            keep |= labeled == i
    return keep


def save_mask(mask, profile, output_path):
    out_profile = profile.copy()
    out_profile.update(dtype="uint8", count=1, nodata=0)
    with rasterio.open(output_path, "w", **out_profile) as dst:
        dst.write(mask.astype("uint8"), 1)


def main():
    parser = argparse.ArgumentParser(description="Local satellite flood detection")
    parser.add_argument("--mode", choices=["sar", "optical"], default="sar",
                         help="sar = radar backscatter thresholding, optical = NDWI")
    parser.add_argument("--before", required=True, help="Path to 'before flood' GeoTIFF")
    parser.add_argument("--after", required=True, help="Path to 'after flood' GeoTIFF")
    parser.add_argument("--output", default="flood_result.tif", help="Output GeoTIFF path")
    parser.add_argument("--threshold-db", type=float, default=-16,
                         help="SAR mode: dB threshold below which pixels = water (default -16)")
    parser.add_argument("--green-band", type=int, default=3,
                         help="Optical mode: band index (1-based) for Green")
    parser.add_argument("--nir-band", type=int, default=4,
                         help="Optical mode: band index (1-based) for Near-Infrared")
    parser.add_argument("--min-pixels", type=int, default=8,
                         help="Minimum connected pixel count to keep (removes noise)")
    args = parser.parse_args()

    print(f"Reading before/after images ({args.mode} mode)...")

    if args.mode == "sar":
        before, profile_b = read_band(args.before, band=1)
        after, profile_a = read_band(args.after, band=1)
        check_alignment(profile_b, profile_a)

        water_before = detect_water_sar(before, args.threshold_db)
        water_after = detect_water_sar(after, args.threshold_db)

    else:  # optical
        with rasterio.open(args.before) as src:
            profile_b = src.profile
            green_b = src.read(args.green_band).astype("float32")
            nir_b = src.read(args.nir_band).astype("float32")
        with rasterio.open(args.after) as src:
            profile_a = src.profile
            green_a = src.read(args.green_band).astype("float32")
            nir_a = src.read(args.nir_band).astype("float32")
        check_alignment(profile_b, profile_a)

        water_before = detect_water_optical(green_b, nir_b)
        water_after = detect_water_optical(green_a, nir_a)

    print("Isolating new flood extent (after minus before)...")
    new_flood = water_after & ~water_before
    new_flood = np.nan_to_num(new_flood, nan=0).astype(bool)

    print(f"Removing noise blobs smaller than {args.min_pixels} pixels...")
    cleaned = clean_mask(new_flood, min_pixels=args.min_pixels)

    flooded_pixels = int(cleaned.sum())
    total_pixels = cleaned.size
    print(f"Flooded pixels: {flooded_pixels:,} / {total_pixels:,} "
          f"({100 * flooded_pixels / total_pixels:.2f}% of image area)")

    save_mask(cleaned, profile_a, args.output)
    print(f"\nSaved flood mask to: {args.output}")
    print("Open it in QGIS, ArcGIS, or any GIS viewer (1 = flooded, 0 = not flooded).")


if __name__ == "__main__":
    main()
