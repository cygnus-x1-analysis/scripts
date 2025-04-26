#!/usr/bin/env bash
# make_source_regions.sh  <OBS_OUT_DIR>  <radius_arcsec>
# ------------------------------------------------------------------
# • Hard‑coded Cygnus X‑1 NED position (RA=299.590307°, Dec=35.201634°)
# • Writes srcA.reg / srcB.reg NEXT TO EACH *_cl.evt it finds
# • Prints NuSTAR‑pixel area using 12.3″/pixel.
# ------------------------------------------------------------------

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <OBS_OUT_DIR> <radius_arcsec>"
  exit 1
fi

OBS_DIR=$(realpath "$1")
RAD_ARC=$2
PIX_SCALE=12.3                                    # ″ pix⁻¹
RAD_PIX=$(awk "BEGIN{printf \"%.4f\", $RAD_ARC/$PIX_SCALE}")
AREA_PIX=$(awk "BEGIN{printf \"%.2f\", 3.1415926536*($RAD_PIX)^2}")

SRC_RA=299.590307
SRC_DEC=35.201634

echo "▶ Source radius = ${RAD_ARC}\" (≈ ${RAD_PIX} pix) → area ≈ ${AREA_PIX} pix²"

for EVT in "${OBS_DIR}"/nu*{A,B}01_cl.evt; do
  [[ -f "$EVT" ]] || continue
  DET=$(grep -oE 'A01|B01' <<<"$(basename "$EVT")" | cut -c1)
  EVT_DIR=$(dirname "$EVT")
  REG="${EVT_DIR}/src${DET}.reg"

  cat > "$REG" <<EOF
# Region file format: DS9 version 4.1
global color=green width=1
fk5
circle(${SRC_RA},${SRC_DEC},${RAD_ARC}.000")
EOF
  echo "  • wrote $REG"
done
