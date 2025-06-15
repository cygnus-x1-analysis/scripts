# Save this file as run_spectral_pipeline.py
# This is the final version, implementing massively parallel processing.
import os
import glob
import sys
import shutil
import subprocess
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

# --- USER CONFIGURATION ---
BASE_ANALYSIS_DIR = os.path.expanduser("testfolder/")
RESULTS_DIR = "automated_spectral_fits"
# Use all but one CPU core to keep the computer responsive.
N_PROCESSES = max(1, cpu_count() - 1)
WORKER_SCRIPT_NAME = "fitter_iterative.py"

# --- SCRIPT ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKER_SCRIPT_PATH = os.path.join(SCRIPT_DIR, WORKER_SCRIPT_NAME)

def process_obs(obsid):
    """
    Prepares workspace, runs worker, retrieves results, and cleans up.
    This function is executed by each parallel process for a single obsid.
    """
    workspace_dir = os.path.join(os.getcwd(), f"temp_fit_{obsid}")
    if os.path.exists(workspace_dir):
        shutil.rmtree(workspace_dir)
    os.makedirs(workspace_dir)

    try:
        # Find the specific directories for FPMA (_out2) and FPMB (_out3) data.
        dir_a_list = glob.glob(os.path.join(BASE_ANALYSIS_DIR, f"{obsid}_out2*"))
        dir_b_list = glob.glob(os.path.join(BASE_ANALYSIS_DIR, f"{obsid}_out3*"))

        if not dir_a_list or not dir_b_list:
            print(f"[{obsid}] ERROR: Could not find required _out2 or _out3 data directories.")
            return obsid, "Failed (Missing Data Dirs)"
            
        dir_a = dir_a_list[0]
        dir_b = dir_b_list[0]

        files_to_copy = [
            f"nu{obsid}A01_sr.pha", f"nu{obsid}A01_bk.pha", f"nu{obsid}A01_sr.rmf", f"nu{obsid}A01_sr.arf",
            f"nu{obsid}B01_sr.pha", f"nu{obsid}B01_bk.pha", f"nu{obsid}B01_sr.rmf", f"nu{obsid}B01_sr.arf"
        ]
        
        for fname in files_to_copy:
            source_paths = glob.glob(os.path.join(dir_a, fname)) + glob.glob(os.path.join(dir_b, fname))
            if source_paths:
                shutil.copy(source_paths[0], workspace_dir)
            else:
                return obsid, f"Failed (Missing File: {fname})"
        
        # Construct the command to call the worker script.
        command = [
            sys.executable, WORKER_SCRIPT_PATH,
            "--spec_a", f"nu{obsid}A01_sr.pha",
            "--spec_b", f"nu{obsid}B01_sr.pha",
            "--obsid", obsid,
        ]
        
        # Execute the command from within the temporary workspace directory.
        subprocess.run(command, check=True, cwd=workspace_dir, capture_output=True, text=True)

        # After the worker succeeds, retrieve the results from the workspace.
        os.makedirs(RESULTS_DIR, exist_ok=True)
        output_files = glob.glob(os.path.join(workspace_dir, "*.png")) + \
                       glob.glob(os.path.join(workspace_dir, "*.csv"))
        
        for f_path in output_files:
            shutil.move(f_path, os.path.join(RESULTS_DIR, os.path.basename(f_path)))
            
        return obsid, "Success"

    except subprocess.CalledProcessError as e:
        # If the worker script crashes, its output will be printed.
        print(f"\n--- FATAL ERROR processing {obsid} ---")
        print("--- The worker script crashed. See its full terminal output below: ---")
        print("\n--- STDOUT ---")
        print(e.stdout)
        print("\n--- STDERR ---")
        print(e.stderr)
        print("--- End of Worker Output ---")
        return obsid, "Failed (Worker Error)"
    except Exception as e:
        print(f"\n--- FATAL ERROR in manager script for {obsid}: {e} ---")
        return obsid, "Failed (Manager Error)"
        
    finally:
        # This block ALWAYS runs, ensuring the temporary workspace is deleted.
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)

def main():
    """
    The main function for the script.
    """
    print("--- Pipeline Step 5: Going Massively Parallel ---")

    if not os.path.exists(WORKER_SCRIPT_PATH):
        print(f"FATAL ERROR: The worker script '{WORKER_SCRIPT_NAME}' was not found.")
        sys.exit(1)

    try:
        all_obsids = sorted(list(set([d.split('_')[0] for d in os.listdir(BASE_ANALYSIS_DIR) if os.path.isdir(os.path.join(BASE_ANALYSIS_DIR, d))])))
    except FileNotFoundError:
        print(f"FATAL ERROR: The specified BASE_ANALYSIS_DIR does not exist: '{BASE_ANALYSIS_DIR}'")
        sys.exit(1)
    
    if not all_obsids:
        print(f"Error: No observation subdirectories found in '{BASE_ANALYSIS_DIR}'.")
    else:
        print(f"Found {len(all_obsids)} unique OBSIDs. Starting parallel processing...")
        os.makedirs(RESULTS_DIR, exist_ok=True)
        
        # --- [NEW LOGIC FOR STEP 5] ---
        # Use a multiprocessing Pool to process all OBSIDs in parallel.
        with Pool(processes=N_PROCESSES) as pool:
            # tqdm creates a live progress bar.
            # imap_unordered processes items as they complete, which is efficient.
            results = list(tqdm(pool.imap_unordered(process_obs, all_obsids), total=len(all_obsids)))
        # --- [END OF NEW LOGIC] ---

        print("\n--- All jobs complete. ---")
        success_count = sum(1 for r in results if r and r[1] == "Success")
        print(f"Summary: {success_count}/{len(all_obsids)} OBSIDs processed successfully.")
            
    print("\n--- Pipeline finished. ---")


if __name__ == "__main__":
    main()
