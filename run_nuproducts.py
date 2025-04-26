#!/usr/bin/env python3
"""
run_nuproducts.py – parallel batch driver for NuSTAR nuproducts
----------------------------------------------------------------
Launches nuproducts for every (srcReg, bkgReg, bin) combination from
region_cfg.json, separately for FPMA (A) and FPMB (B).  Resumes safely.
"""
from __future__ import annotations
import argparse
import json
import logging
import multiprocessing as mp
import os
import pathlib
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from tqdm.auto import tqdm

# Regex to detect completion in log
FIN_RE = re.compile(r"^nuproducts done", re.M)

def _needs_rerun(outdir: pathlib.Path) -> bool:
    log = outdir / "nuproducts.log"
    return not (log.exists() and FIN_RE.search(log.read_text(errors="ignore")))

def _launch(args):
    obsid, det, cfg, comb = args
    r_src, rin, rout, binsize = comb

    # file setup
    stem   = f"nu{obsid}"
    evtdir = pathlib.Path(cfg["outdir_base"]) / f"{obsid}_out"
    src_reg = evtdir / f"src_{det}_{r_src:03.0f}.reg"
    bkg_reg = evtdir / f"bkg_{det}_{rin:03.0f}-{rout:03.0f}.reg"

    outdir = (
        pathlib.Path(cfg["products_base"]) / obsid /
        f"{det}_src{r_src:03d}_bkg{rin:03d}-{rout:03d}_bin{binsize}"
    )
    outdir.mkdir(parents=True, exist_ok=True)

    # skip if already done
    if not _needs_rerun(outdir):
        return obsid, det, comb, 0

    # run nuproducts
    log = outdir / "nuproducts.log"
    cmd = [
        "nuproducts",
        f"indir={evtdir}",
        f"instrument={'FPMA' if det=='A' else 'FPMB'}",
        f"steminputs={stem}",
        f"outdir={outdir}",
        f"srcregionfile={src_reg}",
        f"bkgregionfile={bkg_reg}",
        "bkgextract=yes",
        f"pilow={cfg['pilow']}",
        f"pihigh={cfg['pihigh']}",
        f"binsize={binsize}",
        "clobber=yes",
    ]
    rc = subprocess.call(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT)

    # mark completion
    if rc == 0:
        with open(log, "a") as fp:
            fp.write("\nnuproducts done\n")

    return obsid, det, comb, rc

def main() -> None:
    # load configs
    rcfg = json.loads(pathlib.Path("region_cfg.json").read_text())
    ocfg = json.loads(pathlib.Path("obslist.json").read_text())

    # ensure HEASoft is initialized
    if "HEADAS" not in os.environ or "CALDB" not in os.environ:
        sys.exit("Error: HEASoft not initialised – run heainit & caldbinit first")

    # prepare tasks
    combos = [
        (r_src, rin, rout, binsize)
        for r_src in rcfg["src_radii_arcsec"]
        for rin, rout in rcfg["bkg_annuli_arcsec"]
        for binsize in rcfg["bin_sizes_s"]
    ]
    tasks = [
        (obs, det, {**ocfg, **rcfg}, comb)
        for obs in ocfg["observations"]
        for det in ("A", "B")
        for comb in combos
    ]

    # logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    max_workers = max(1, mp.cpu_count() // 2)
    logging.info("Queued %d nuproducts jobs using %d workers", len(tasks), max_workers)

    # run in parallel, collect failures
    failures: list[tuple[str, str, tuple, int | str]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futs = { pool.submit(_launch, t): t for t in tasks }
        for fut in tqdm(as_completed(futs), total=len(futs), unit="job"):
            obsid, det, comb = futs[fut][:3]
            try:
                oid, detd, combd, rc = fut.result()
            except Exception as e:
                logging.error("%s %s %s raised exception: %s", obsid, det, comb, e)
                failures.append((obsid, det, comb, "exception"))
            else:
                r_src, rin, rout, binsize = combd
                if rc != 0:
                    logging.error(
                        "%s %s src%s bkg%s-%s bin%s failed (exit %s)",
                        oid, detd, r_src, rin, rout, binsize, rc
                    )
                    failures.append((oid, detd, combd, rc))
                else:
                    logging.info(
                        "%s %s src%s bkg%s-%s bin%s completed",
                        oid, detd, r_src, rin, rout, binsize
                    )

    # final exit status
    if failures:
        logging.error("Total failures: %d", len(failures))
        sys.exit(1)
    else:
        logging.info("All jobs finished successfully")
        sys.exit(0)

if __name__ == "__main__":
    main()
