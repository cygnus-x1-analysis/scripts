#!/usr/bin/env bash
# combine_background_lightcurves.sh  <products_base>  <lightcurves_base>
# -----------------------------------------------------------------------------
# Same logic as the source script, but for *_bk.lc → added_bkg.lc
# -----------------------------------------------------------------------------

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <products_base> <lightcurves_base>"
  exit 1
fi

PROD_BASE=$(realpath "$1")
LC_BASE=$(realpath "$2")

echo "▶ Combining FPMA+FPMB background LCs → $LC_BASE …"

for OBSDIR in "${PROD_BASE}"/*; do
  [[ -d "$OBSDIR" ]] || continue
  OBSID=$(basename "$OBSDIR")

  # iterate every A_… folder
  for ADIR in "$OBSDIR"/A_src*_*_bin*; do
    [[ -d "$ADIR" ]] || continue

    # strip leading "A_" → e.g. "src015_bkg050-080_bin0.005"
    COMBO=${ADIR##*/}; COMBO=${COMBO#A_}
    BDIR="$OBSDIR/B_${COMBO}"

    # both detectors must exist
    if [[ ! -d "$BDIR" ]]; then
      echo "  ⚠️  [${OBSID}/${COMBO}] no matching B_… folder → skip"
      continue
    fi

    # ensure both finished
    for D in "$ADIR" "$BDIR"; do
      if ! grep -q "nuproducts done" "$D/nuproducts.log" 2>/dev/null; then
        echo "  • [${OBSID}/${COMBO}] not finished in $(basename "$D") → skip"
        continue 2
      fi
    done

    # prepare destination
    DEST_DIR="${LC_BASE}/${OBSID}/${COMBO}"
    mkdir -p "$DEST_DIR"
    OUT="$DEST_DIR/added_bkg.lc"
    if [[ -f "$OUT" ]]; then
      echo "  • [${OBSID}/${COMBO}] exists → skip"
      continue
    fi

    # corrected filenames: use *_bk.lc
    A_LC="${ADIR}/nu${OBSID}A01_bk.lc"
    B_LC="${BDIR}/nu${OBSID}B01_bk.lc"
    if [[ ! -f "$A_LC" || ! -f "$B_LC" ]]; then
      echo "  ⚠️  [${OBSID}/${COMBO}] missing ${A_LC##*/} or ${B_LC##*/}"
      continue
    fi

    echo "  ✓ [${OBSID}/${COMBO}] combining → ${OUT##*/}"
    lcmath "$A_LC" "$B_LC" "$OUT" addsubr=yes multi=1 multb=1
  done
done

echo "✓ Background-LC combination done."
