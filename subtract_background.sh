#!/usr/bin/env bash
# subtract_background.sh  <products_base>  <pixel_areas.json>  <lightcurves_base>
# -----------------------------------------------------------------------------
# For each entry in pixel_areas.json, and for each bin-dir under lightcurves/,
# subtract scaled background from added_source.lc, writing final_LC_… under lightcurves/.
# -----------------------------------------------------------------------------

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <products_base> <pixel_areas.json> <lightcurves_base>"
  exit 1
fi

PROD_BASE=$(realpath "$1") # still needed for logfile checks, etc.
PAJSON=$(realpath "$2")    # scale-factor JSON
LC_BASE=$(realpath "$3")   # **where** added_*.lc live

# require jq
command -v jq >/dev/null 2>&1 || {
  echo "🔧 Please install jq to parse JSON" >&2
  exit 1
}

echo "▶ Subtracting background with scale factors from $PAJSON into $LC_BASE …"

jq -c '.[]' "$PAJSON" | while read -r REC; do
  OBSID=$(jq -r '.obsid' <<<"$REC")        # e.g. "10014001001"
  DET=$(jq -r '.det' <<<"$REC")            # "A" or "B"
  R_SRC=$(jq -r '.r_src_arcsec' <<<"$REC") # e.g. 15
  RIN=$(jq -r '.rin_arcsec' <<<"$REC")     # e.g. 50
  ROUT=$(jq -r '.rout_arcsec' <<<"$REC")   # e.g. 80
  SF=$(jq -r '.scale_factor' <<<"$REC")    # scale factor

  # Construct folder pattern without detector prefix - this matches the combined output folders
  FOLDER_PATTERN="src$(printf "%03d" "$R_SRC")_bkg$(printf "%03d-%03d" "$RIN" "$ROUT")"

  # **Search under lightcurves** for folders matching the pattern without detector prefix
  find "${LC_BASE}/${OBSID}" -type d -name "${FOLDER_PATTERN}_bin*" | while read -r BINDIR; do
    # Original products would be in a detector-prefixed directory, so construct the expected product path
    PROD_REL="${BINDIR##*/}"                                      # e.g. "src015_bkg050-080_bin0.005"
    LOG="${PROD_BASE}/${OBSID}/${DET}_${PROD_REL}/nuproducts.log" # Check original product log

    # Skip if original products weren't successfully completed
    [[ -f "$LOG" && $(grep -c "nuproducts done" "$LOG") -gt 0 ]] || continue

    # Get relative path for destination
    REL="${BINDIR#${LC_BASE}/${OBSID}/}" # e.g. "src015_bkg050-080_bin0.005"
    DEST_DIR="${LC_BASE}/${OBSID}/${REL}"
    mkdir -p "$DEST_DIR"

    SRC="$DEST_DIR/added_source.lc" # path to combined source LC
    BKG="$DEST_DIR/added_bkg.lc"    # path to combined background LC
    OUT="$DEST_DIR/final_LC_src${R_SRC}_bkg${RIN}-${ROUT}.lc"

    # skip if missing upstream artifacts
    if [[ ! -f "$SRC" || ! -f "$BKG" ]]; then
      echo "[${OBSID}/${REL}] missing added_source or added_bkg — skipping"
      continue
    fi
    # skip if already done
    if [[ -f "$OUT" ]]; then
      echo "  • [${OBSID}/${REL}] final LC exists — skipping"
      continue
    fi

    echo "  • [${OBSID}/${REL}] subtracting background (scale=$SF) → ${OUT##*/}"
    lcmath "$SRC" "$BKG" "$OUT" addsubr=no multi=1 multb="$SF" # subtract scaled background
  done
done

echo "✓ Background subtraction complete."
