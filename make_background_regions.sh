#!/usr/bin/env bash
# make_background_regions.sh  <OBS_OUT_DIR>  <r_in_arcsec>  <r_out_arcsec>
# ------------------------------------------------------------------
# • Hard‑coded background centre (edit BKG_RA / BKG_DEC as needed)
# • Writes bkgrndA.reg / bkgrndB.reg NEXT TO EACH *_cl.evt
# • Reports annulus area in NuSTAR pixels (12.3″/pix).
# ------------------------------------------------------------------

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <OBS_OUT_DIR> <r_in_arcsec> <r_out_arcsec>"
  exit 1
fi

OBS_DIR=$(realpath "$1")
RIN_ARC=$2
ROUT_ARC=$3
PIX_SCALE=12.3
RIN_PIX=$(awk "BEGIN{printf \"%.4f\", $RIN_ARC/$PIX_SCALE}")
ROUT_PIX=$(awk "BEGIN{printf \"%.4f\", $ROUT_ARC/$PIX_SCALE}")
ANN_PIX=$(awk "BEGIN{printf \"%.2f\", 3.1415926536*($ROUT_PIX^2-$RIN_PIX^2)}")

# set your desired background centre here (deg)
BKG_RA=299.590307
BKG_DEC=35.201634

echo "▶ Annulus r_in=${RIN_ARC}\" (≈${RIN_PIX} pix), r_out=${ROUT_ARC}\" (≈${ROUT_PIX} pix) → area ≈ ${ANN_PIX} pix²"

for EVT in "${OBS_DIR}"/nu*{A,B}01_cl.evt; do
  [[ -f "$EVT" ]] || continue
  DET=$(grep -oE 'A01|B01' <<<"$(basename "$EVT")" | cut -c1)
  EVT_DIR=$(dirname "$EVT")
  REG="${EVT_DIR}/bkgrnd${DET}.reg"

  cat > "$REG" <<EOF
# Region file format: DS9 version 4.1
global color=red width=1
fk5
annulus(${BKG_RA},${BKG_DEC},${RIN_ARC}.000",${ROUT_ARC}.000")
EOF
  echo "  • wrote $REG"
done
