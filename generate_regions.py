#!/usr/bin/env python3
"""
generate_regions.py – build Cygnus X‑1 source & background DS9 regions
---------------------------------------------------------------------
• Reads obslist.json + region_cfg.json
• Uses fixed NED position (RA=299.590307°, Dec=35.201634°)
• For each cleaned event file (A/B) it:
    – writes source circles for every radius in src_radii_arcsec
    – writes background annuli for every (rin,rout) in bkg_annuli_arcsec
• Saves pixel areas and scale factors to pixel_areas.json
"""
from __future__ import annotations
import itertools
import json
import math
import pathlib
import sys

# -----------------------------------------------------------------------------------
# CONFIGURABLE CONSTANTS
# -----------------------------------------------------------------------------------
SRC_RA = 299.590307    # Cygnus X-1 NED RA (deg)
SRC_DEC = 35.201634    # Cygnus X-1 NED Dec (deg)
PIX_SCALE = 12.3       # arcsec per pixel for NuSTAR
# -----------------------------------------------------------------------------------

def circle_area(r_arc: float) -> float:
    """Compute pixel area of a circle with radius r_arc (arcsec)."""
    return math.pi * (r_arc / PIX_SCALE) ** 2

def annulus_area(rin_arc: float, rout_arc: float) -> float:
    """Compute pixel area of an annulus with inner/outer radii in arcsec."""
    rin_pix = rin_arc / PIX_SCALE
    rout_pix = rout_arc / PIX_SCALE
    return math.pi * (rout_pix**2 - rin_pix**2)

def write_ds9(fname: pathlib.Path, region_str: str, color: str) -> None:
    """Write a DS9 region file (FK5 coordinates)."""
    content = (
        "# Region file format: DS9 version 4.1\n"
        f"global color={color} width=1\n"
        "fk5\n"
        f"{region_str}\n"
    )
    fname.write_text(content)

def main() -> None:
    # Load configurations
    try:
        region_cfg = json.loads(pathlib.Path("region_cfg.json").read_text())
        obs_cfg    = json.loads(pathlib.Path("obslist.json").read_text())
    except FileNotFoundError as e:
        sys.exit(f"ERROR: missing config file {e.filename}")

    records: list[dict] = []

    for obs in obs_cfg["observations"]:
        outdir = pathlib.Path(obs_cfg["outdir_base"]) / f"{obs}_out"
        if not outdir.is_dir():
            print(f"⚠️ Skipping {obs}: output dir not found ({outdir})")
            continue

        # Explicitly handle both detectors A and B
        for det_tag in ("A01", "B01"):
            pattern = f"nu*{det_tag}_cl.evt"
            for evt in sorted(outdir.glob(pattern)):
                det = det_tag[0]  # 'A' or 'B'

                # 1) Source circle for each radius
                for r_src in region_cfg["src_radii_arcsec"]:
                    fname = evt.with_name(f"src_{det}_{r_src:03.0f}.reg")
                    region = f"circle({SRC_RA},{SRC_DEC},{r_src}\")"
                    write_ds9(fname, region, color="green")

                # 2) Background annulus for each (rin,rout)
                for rin, rout in region_cfg["bkg_annuli_arcsec"]:
                    fname = evt.with_name(f"bkg_{det}_{rin:03.0f}-{rout:03.0f}.reg")
                    region = f"annulus({SRC_RA},{SRC_DEC},{rin}\",{rout}\")"
                    write_ds9(fname, region, color="red")

                # 3) Record areas & scale factors for every combo
                for r_src, (rin, rout) in itertools.product(
                    region_cfg["src_radii_arcsec"],
                    region_cfg["bkg_annuli_arcsec"]
                ):
                    src_area = circle_area(r_src)
                    bkg_area = annulus_area(rin, rout)
                    records.append({
                        "obsid": obs,
                        "det": det,
                        "r_src_arcsec": r_src,
                        "rin_arcsec": rin,
                        "rout_arcsec": rout,
                        "src_area_pix": round(src_area, 3),
                        "bkg_area_pix": round(bkg_area, 3),
                        "scale_factor": round(src_area / bkg_area, 4),
                    })

    # Write out pixel areas and factors
    outpath = pathlib.Path("pixel_areas.json")
    outpath.write_text(json.dumps(records, indent=2))
    print(f"✓ Wrote {len(records)} entries to {outpath}")

if __name__ == "__main__":
    main()
