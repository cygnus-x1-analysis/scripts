#!/usr/bin/env python3
"""
run_nupipeline.py  –  parallel NuSTAR pipeline launcher with smart resume

Before running:
    $ conda activate xray-env
    $ heainit     # sets HEADAS, PATH, etc.
    $ caldbinit   # sets CALDB

Usage examples
    python run_nupipeline.py                 # jobs = auto (Ncpu//2)
    python run_nupipeline.py -j 4            # 4 workers
"""

from __future__ import annotations
import argparse
import json
import logging
import multiprocessing as mp
import os
import pathlib
import re
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

from tqdm.auto import tqdm


# ------------------------------------------------------------------
# helper: does this OBSID need a (re)run?
# ------------------------------------------------------------------
_FINISH_RE = re.compile(r"Finished nupipeline for (\d+)")


def _needs_rerun(obsid: str, cfg: dict) -> bool:
    """
    Return True if the observation should be (re)processed:

        • log file missing
        • or log file does NOT contain the finished marker
    """
    log_path = pathlib.Path(cfg["outdir_base"]) / f"{obsid}_out" / "nupipeline.log"
    if not log_path.is_file():
        return True

    try:
        # read just the last ~100 lines to search for the marker
        tail = log_path.read_text(errors="ignore").splitlines()[-100:]
        for line in reversed(tail):
            m = _FINISH_RE.search(line)
            if m and m.group(1) == obsid:
                return False          # completed earlier
    except OSError:
        pass                          # unreadable log → treat as failed
    return True


# ------------------------------------------------------------------
# worker wrapper
# ------------------------------------------------------------------
def _launch_one(args):
    """Run nupipe_one.sh for a single OBSID and return (obsid, exit‑code)."""
    obsid, cfg = args
    cmd = [
        "./nupipe_one.sh",
        obsid,
        cfg["indir_base"],
        cfg["outdir_base"],
        cfg.get("clobber", "no"),
        cfg.get("extra_args", ""),
    ]
    return obsid, subprocess.call(cmd)


# ------------------------------------------------------------------
# orchestrator
# ------------------------------------------------------------------
def main(cfg_path: str, job_setting: str | int = "auto") -> None:
    # --------------------------------------------------------------
    # environment sanity check
    # --------------------------------------------------------------
    missing = [v for v in ("HEADAS", "CALDB") if v not in os.environ]
    if missing:
        sys.exit(
            f"Error: {', '.join(missing)} not defined – did you run heainit/caldbinit?"
        )

    # --------------------------------------------------------------
    # read JSON config
    # --------------------------------------------------------------
    cfg_file = pathlib.Path(cfg_path)
    if not cfg_file.exists():
        sys.exit(f"Config file '{cfg_file}' not found.")
    cfg = json.loads(cfg_file.read_text())
    obsids: list[str] = cfg["observations"]

    # --------------------------------------------------------------
    # worker pool size
    # --------------------------------------------------------------
    if job_setting == "auto":
        max_workers = max(1, mp.cpu_count() // 2)
    elif job_setting == "off":
        max_workers = 1
    else:
        max_workers = int(job_setting)

    # --------------------------------------------------------------
    # logging setup
    # --------------------------------------------------------------
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.info(
        "Request: %d OBSIDs   •   %d worker process(es)", len(obsids), max_workers
    )

    # --------------------------------------------------------------
    # decide which OBSIDs to queue
    # --------------------------------------------------------------
    worklist: list[str] = []
    for obs in obsids:
        if _needs_rerun(obs, cfg):
            outdir = pathlib.Path(cfg["outdir_base"]) / f"{obs}_out"
            if outdir.is_dir():
                shutil.rmtree(outdir)          # wipe partial run
            worklist.append(obs)
            logging.info("↺  queued   %s", obs)
        else:
            logging.info("✓  skipped  %s  (already finished)", obs)

    if not worklist:
        logging.info("Nothing to do – all OBSIDs already finished.")
        return

    # --------------------------------------------------------------
    # parallel dispatch
    # --------------------------------------------------------------
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_launch_one, (obs, cfg)): obs for obs in worklist
        }
        for fut in tqdm(
            as_completed(futures),
            total=len(futures),
            desc="nupipeline jobs",
            unit="obs",
        ):
            obs = futures[fut]
            rc = fut.result()[1]
            if rc:
                logging.error("OBSID %s exited with code %d", obs, rc)
            else:
                logging.info("OBSID %s finished OK", obs)


# ------------------------------------------------------------------
# CLI entry‑point
# ------------------------------------------------------------------
if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Run multiple NuSTAR nupipeline jobs in parallel (with resume)."
    )
    p.add_argument("-c", "--config", default="obslist.json",
                   help="JSON configuration file (default: obslist.json)")
    p.add_argument("-j", "--jobs", default="auto",
                   help="'auto', 'off', or an integer worker count (default: auto)'")
    args = p.parse_args()
    main(args.config, args.jobs)
