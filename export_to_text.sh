#!/usr/bin/env bash
# export_to_text.sh <lightcurves_base> <lightcurves_txt_base>
# -----------------------------------------------------------------------------
# For each final_LC_*.lc file under lightcurves/, extract data columns to a
# matching text file with the same structure in lightcurves_txt/.
# -----------------------------------------------------------------------------

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <lightcurves_base> <lightcurves_txt_base>"
    exit 1
fi

LC_BASE=$(realpath "$1")
LCTXT_BASE=$(realpath "$2")

# Create the root output directory if it doesn't exist
mkdir -p "$LCTXT_BASE"

# Create a temporary Python script to extract FITS data
TMP_SCRIPT=$(mktemp)
cat >"$TMP_SCRIPT" <<'EOF'
#!/usr/bin/env python3
"""
Script to extract NuSTAR light curve data from a FITS file to text.
Usage: python extract_script.py [path_to_lightcurve_file] [path_to_output_text_file]
"""

import sys
import os
import numpy as np
from astropy.io import fits

def extract_lightcurve_to_text(lc_file, txt_file):
    """
    Extract data from a NuSTAR light curve FITS file to a text file.
    
    Parameters:
    -----------
    lc_file : str
        Path to the light curve FITS file
    txt_file : str
        Path to the output text file
    """
    try:
        # Open the FITS file
        with fits.open(lc_file) as hdul:
            # Get data from the RATE extension
            lc_data = hdul['RATE'].data
            
            # Extract key information
            time = lc_data['TIME']
            rate = lc_data['RATE']
            error = lc_data['ERROR']
            
            # Filter out NaN values
            valid_mask = ~np.isnan(rate) & ~np.isnan(time) & ~np.isnan(error)
            if not np.all(valid_mask):
                time = time[valid_mask]
                rate = rate[valid_mask]
                error = error[valid_mask]
            
            # Get metadata from primary header
            primary_header = hdul[0].header
            mjdrefi = primary_header.get('MJDREFI', 0)
            mjdreff = primary_header.get('MJDREFF', 0)
            mjdref = mjdrefi + mjdreff
            
            # Convert mission time to MJD
            mjd_times = mjdref + (time / 86400.0)  # Convert seconds to days
            
            # Write data to text file
            with open(txt_file, 'w') as f:
                # Write header
                f.write("# TIME(s)\tMJD\tRATE(cts/s)\tERROR(cts/s)\n")
                
                # Write data rows
                for i in range(len(time)):
                    f.write(f"{time[i]:.6f}\t{mjd_times[i]:.8f}\t{rate[i]:.6f}\t{error[i]:.6f}\n")
                
            print(f"Extracted data from {lc_file} to {txt_file}")
            return True
            
    except Exception as e:
        print(f"Error processing {lc_file}: {e}")
        return False

if __name__ == "__main__":
    # Use the command-line arguments
    if len(sys.argv) != 3:
        print("Usage: python extract_script.py [path_to_lightcurve_file] [path_to_output_text_file]")
        sys.exit(1)
        
    lc_file = sys.argv[1]
    txt_file = sys.argv[2]
    
    success = extract_lightcurve_to_text(lc_file, txt_file)
    if not success:
        sys.exit(1)
EOF

# Make the script executable
chmod +x "$TMP_SCRIPT"

echo "▶ Exporting lightcurve FITS data to text files in $LCTXT_BASE ..."

# Find all the final lightcurve files
find "$LC_BASE" -type f -name "final_LC_*.lc" | while read -r LC_FILE; do
    # Get the relative path from LC_BASE
    REL_PATH="${LC_FILE#$LC_BASE/}"

    # Create the directory structure in the text output base
    TXT_DIR="$LCTXT_BASE/$(dirname "$REL_PATH")"
    mkdir -p "$TXT_DIR"

    # Set the output file name with .txt extension
    TXT_FILE="$LCTXT_BASE/${REL_PATH%.lc}.txt"

    # Skip if output file already exists
    if [[ -f "$TXT_FILE" ]]; then
        echo "  • $REL_PATH already exported — skipping"
        continue
    fi

    echo "  ✓ Exporting $REL_PATH → ${TXT_FILE##*/}"

    # Run the Python script to extract and convert data
    python3 "$TMP_SCRIPT" "$LC_FILE" "$TXT_FILE"

    # Check if the extraction was successful
    if [[ ! -f "$TXT_FILE" ]]; then
        echo "  ⚠️ Failed to extract data from $REL_PATH"
    fi
done

# Clean up the temporary script
rm -f "$TMP_SCRIPT"

echo "✓ Lightcurve data export complete."
