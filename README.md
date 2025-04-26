# NuSTAR Cygnus X-1 Light Curve Analysis

This repository contains a suite of scripts for automated processing of NuSTAR X-ray observations of Cygnus X-1, from raw data to background-subtracted light curves.

## Overview

The workflow follows these main steps:

1. **Data Preparation**: Run NuSTAR pipeline on raw observations
2. **Region Generation**: Create source and background regions 
3. **Product Extraction**: Run nuproducts to extract light curves with different parameters
4. **Lightcurve Combination**: Combine FPMA and FPMB detector data
5. **Background Subtraction**: Subtract scaled background from combined source data
6. **Analysis and Visualization**: Plot light curves with various tools

## Prerequisites

- HEASoft (including FTOOLS, XSPEC, and NuSTARDAS)
- Python 3.6+ with required packages:
  - numpy, matplotlib, astropy
  - bokeh, holoviews, datashader (for interactive plots)
- Data stored as per the configuration in `obslist.json`

## Configuration Files

### `obslist.json`

Defines observation IDs and paths:

```json
{
  "indir_base": "/path/to/raw/data",
  "outdir_base": "/path/to/pipeline/output",
  "observations": ["obsid1", "obsid2", ...]
}
```

### `region_cfg.json`

Defines analysis parameters:

```json
{
  "src_radii_arcsec": [15, 30, 45, ...],
  "bkg_annuli_arcsec": [[50, 80], [60, 120], ...],
  "bin_sizes_s": [0.005, 0.01, 0.1, ...],
  "pilow": 35,
  "pihigh": 1910,
  "products_base": "products"
}
```

## Workflow Steps

### 1. Initialize HEASoft Environment

Always start with:

```bash
$ heainit
$ caldbinit
```

### 2. Run NuSTAR Pipeline

Process raw data with:

```bash
$ python run_nupipeline.py
```

This script:
- Runs `nupipeline` on all observations in `obslist.json`
- Processes in parallel (auto-detects CPU cores)
- Intelligently resumes interrupted runs
- Output goes to `output/<obsid>_out/`

### 3. Generate Source and Background Regions

Create regions using:

```bash
$ python generate_regions.py
```

This script:
- Creates source circles and background annuli for all combinations in `region_cfg.json`
- Uses fixed Cygnus X-1 NED position (RA=299.590307°, Dec=35.201634°)
- Outputs regions to `output/<obsid>_out/` directory
- Generates `pixel_areas.json` with area calculations and scale factors

Alternative region scripts (manual versions):
- `make_source_regions.sh <output_dir> <radius_arcsec>`
- `make_background_regions.sh <output_dir> <r_in_arcsec> <r_out_arcsec>`
- `make_all_regions.sh <output_dir> <radius_arcsec>` (uses DS9 centroids)

### 4. Extract NuSTAR Products

Extract light curves with:

```bash
$ python run_nuproducts.py
```

This script:
- Runs for all detector/region/bin-size combinations 
- Processes in parallel
- Output goes to `products/<obsid>/<det>_src<N>_bkg<M>-<P>_bin<X>/`
- Each output directory contains detector-specific light curves (FPMA or FPMB)

### 5. Combine Detector Data

Combine FPMA and FPMB data:

```bash
$ ./combine_source_lightcurves.sh products lightcurves
$ ./combine_background_lightcurves.sh products lightcurves
```

These scripts:
- Find matching products from detectors A and B
- Add them together with `lcmath`
- Output goes to `lightcurves/<obsid>/<src_bkg_bin_combo>/`
- Creates `added_source.lc` and `added_bkg.lc` files

### 6. Background Subtraction

Subtract the background:

```bash
$ ./subtract_background.sh products pixel_areas.json lightcurves
```

This script:
- Uses scale factors from `pixel_areas.json`
- Subtracts scaled background from source data
- Creates final light curves with format `final_LC_src<N>_bkg<M>-<P>.lc`

### 7. Export to Text Format (Optional)

Convert FITS light curves to text:

```bash
$ ./export_to_text.sh lightcurves lightcurves_txt
```

This creates matching text files with columns: TIME(s), MJD, RATE(cts/s), ERROR(cts/s)

### 8. Visualization

Three plotting scripts are provided:

1. Static matplotlib plots:
```bash
$ python plot_lightcurve.py path/to/lightcurve.lc
```

2. Interactive Bokeh plots:
```bash
$ python plot_bokeh_lightcurve.py path/to/lightcurve.lc
```

3. Datashader-accelerated plots (for very large datasets):
```bash
$ python plot_datashader_lightcurve.py path/to/lightcurve.lc
```

## Output Directory Structure

```
├── output/                    # NuSTAR pipeline products
│   ├── <obsid>_out/           # Raw event files and regions
├── products/                  # NuProducts output
│   ├── <obsid>/
│       ├── A_src015_bkg050-080_bin0.1/  # FPMA products  
│       ├── B_src015_bkg050-080_bin0.1/  # FPMB products
├── lightcurves/               # Combined light curves
│   ├── <obsid>/
│       ├── src015_bkg050-080_bin0.1/    # Combined by detector
│           ├── added_source.lc          # FPMA+FPMB source
│           ├── added_bkg.lc             # FPMA+FPMB background
│           ├── final_LC_src15_bkg50-80.lc  # Background-subtracted
├── lightcurves_txt/           # Text-exported light curves
```

## Notes on Background Subtraction

Background subtraction uses a scaling factor to account for different extraction region sizes:

```
scale_factor = src_area / bkg_area
```

For a source circle and background annulus:
- Source area = π × (r_src / pixel_scale)²
- Background area = π × ((r_out / pixel_scale)² - (r_in / pixel_scale)²)

Where pixel_scale = 12.3 arcsec/pixel for NuSTAR.

## Example Usage

Complete workflow from start to finish:

```bash
# 1. Setup environment
$ heainit
$ caldbinit

# 2. Run pipeline on raw data
$ python run_nupipeline.py

# 3. Generate regions for all observations
$ python generate_regions.py

# 4. Extract light curves with all parameter combinations
$ python run_nuproducts.py

# 5. Combine detector data
$ ./combine_source_lightcurves.sh products lightcurves
$ ./combine_background_lightcurves.sh products lightcurves

# 6. Subtract background
$ ./subtract_background.sh products pixel_areas.json lightcurves

# 7. Export to text (optional)
$ ./export_to_text.sh lightcurves lightcurves_txt

# 8. Plot a specific light curve
$ python plot_lightcurve.py lightcurves/30001011009/src015_bkg050-080_bin0.1/final_LC_src15_bkg50-80.lc
```

## Data

Output data products(lightcurves_txt for now) are available at:
https://drive.google.com/drive/folders/1ODSKaAjrU3O6vhxu76xJ5b1-5p_nG27B

Not uploading all data, as its over a TeraByte in space. 