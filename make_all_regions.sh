#!/usr/bin/env bash
# make_all_regions.sh  <OBS_OUT_DIR>  <radius_arcsec>
# Auto‑generate DS9 region files (src/bkg) from Gaussian centroids

set -euo pipefail

OBS_DIR=$(realpath "$1")
RAD=${2:-120}   # radius in arcsec

for EVT in "${OBS_DIR}"/nu*{A,B}01_cl.evt; do
    [[ -e "$EVT" ]] || continue
    echo "→ Processing $(basename "$EVT")"

    # 1. Parse Gaussian-fit centroid (strip trailing comma/degree)
    read RA DEC <<<"$(
      python compute_centroids.py "$EVT" |
      awk '/Gaussian fit/ {
        gsub(/[°,]/,"",$8);    # strip comma+° from RA
        gsub(/°/,"",$11);      # strip ° from Dec
        print $8, $11
      }'
    )"
    if [[ -z $RA || -z $DEC ]]; then
        echo "ERROR: failed to parse centroid in $EVT" >&2
        exit 1
    fi

    # 2. Compute background RA = RA + 5′ (float math via bc -l) and same Dec
    RA_BKG=$(echo "$RA + 5.0/60.0" | bc -l)
    DEC_BKG=$DEC
    echo "DEBUG → RA=${RA}, DEC=${DEC}, RA_BKG=${RA_BKG}, DEC_BKG=${DEC_BKG}"

    # 3. Filenames (A or B detector)
    DET=$(grep -oE 'A01|B01' <<<"$EVT" | cut -c1)
    SRCREG="${OBS_DIR}/src${DET}.reg"
    BKGREG="${OBS_DIR}/bkgrnd${DET}.reg"

    # 4a. DS9 headless: write source region only
    ds9 -fits "$EVT" \
    -region system wcs \
    -region sky fk5 \
    -region format ds9 \
    -region command "circle $RA $DEC $RAD" \
    -region save "$SRCREG" \
    -exit

    # 4b. DS9 headless: write background region only
    ds9 -fits "$EVT" \
      -region system wcs \                        \
      -region sky fk5 \                           \
      -region format ds9 \                        \
      -region command "circle $RA_BKG $DEC_BKG $RAD" \
      -region save "$BKGREG"                      \
      -exit
done
