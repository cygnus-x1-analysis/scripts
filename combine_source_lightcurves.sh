#!/usr/bin/env bash
# combine_source_lightcurves.sh  <products_base>  <lightcurves_base>
# -----------------------------------------------------------------------------
# For each products/<obsid>/A_src…_bkg…_bin…:
#   • finds the matching B_src… folder
#   • checks both logs for "nuproducts done"
#   • runs lcmath A01_sr.lc + B01_sr.lc → lightcurves/<obsid>/<combo>/added_source.lc
# -----------------------------------------------------------------------------

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <products_base> <lightcurves_base>"
  exit 1
fi

PROD_BASE=$(realpath "$1")
LC_BASE=$(realpath "$2")

echo "▶ Combining FPMA+FPMB source LCs → $LC_BASE …"

for OBSDIR in "${PROD_BASE}"/*; do
  [[ -d "$OBSDIR" ]] || continue
  OBSID=$(basename "$OBSDIR")

  # iterate every A_… folder
  for ADIR in "$OBSDIR"/A_src*_*_bin*; do
    [[ -d "$ADIR" ]] || continue

    COMBO=$(basename "$ADIR")
    # strip leading "A_" → e.g. "src015_bkg050-080_bin0.005"
    COMBO=${COMBO#A_}
    BDIR="$OBSDIR/B_${COMBO}"

    # both detectors must exist
    if [[ ! -d "$BDIR" ]]; then
      echo "  ⚠️  [${OBSID}/${COMBO}] no matching B_… folder, skipping"
      continue
    fi

    # check that both are finished
    for D in "$ADIR" "$BDIR"; do
      if ! grep -q "nuproducts done" "$D/nuproducts.log" 2>/dev/null; then
        echo "  • [${OBSID}/${COMBO}] not finished in $(basename "$D") → skip"
        continue 2
      fi
    done

    # prepare target
    DEST_DIR="${LC_BASE}/${OBSID}/${COMBO}"
    mkdir -p "$DEST_DIR"
    OUT="$DEST_DIR/added_source.lc"

    # skip if already done
    if [[ -f "$OUT" ]]; then
      echo "  • [${OBSID}/${COMBO}] already exists → skipping"
      continue
    fi

    # locate the per‑detector source LCs
    A_LC="${ADIR}/nu${OBSID}A01_sr.lc"
    B_LC="${BDIR}/nu${OBSID}B01_sr.lc"
    if [[ ! -f "$A_LC" || ! -f "$B_LC" ]]; then
      echo "  ⚠️  [${OBSID}/${COMBO}] missing one of ${A_LC##*/},${B_LC##*/}"
      continue
    fi

    echo "  ✓ [${OBSID}/${COMBO}] combining → ${OUT##*/}"
    lcmath "$A_LC" "$B_LC" "$OUT" addsubr=yes multi=1 multb=1
  done
done

echo "✓ Source‑LC combination done."
