#!/usr/bin/env bash
# One‑shot wrapper that assumes HEASoft is already initialised.

set -euo pipefail

OBSID="$1"
IN_DIR="$2/${OBSID}"
OUT_DIR="$3/${OBSID}_out"
CLOB="$4"
EXTRA="$5"

: "${HEADAS:?Environment variable HEADAS must be set.  Did you run heainit?}"
: "${CALDB:?Environment variable CALDB must be set.  Did you run caldbinit?}"

mkdir -p "${OUT_DIR}"
logfile="${OUT_DIR}/nupipeline.log"

(
  echo "[$(date)] Starting nupipeline for ${OBSID}"
  nupipeline indir="${IN_DIR}" \
             steminputs="nu${OBSID}" \
             outdir="${OUT_DIR}" \
             clobber="${CLOB}" ${EXTRA}
  echo "[$(date)] Finished nupipeline for ${OBSID}"
) &> "${logfile}"
