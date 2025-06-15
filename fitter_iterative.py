# Save this file as fitter_iterative.py
# This version now saves a separate plot for EVERY model it fits.
import os
import argparse
import sys
import csv
import matplotlib.pyplot as plt

# This block ensures PyXspec can be imported.
try:
    from xspec import *
except ImportError:
    print("FATAL ERROR: PyXspec not found. Make sure you have initialized HEASoft in your terminal.")
    sys.exit(1)


def setup_data_and_environment(spec_a: str, spec_b: str):
    """
    Sets up XSPEC, groups spectra, loads data and background, and sets ignore ranges.
    """
    print("--- Setting up XSPEC environment and data ---")
    
    # Set XSPEC environment options
    Xset.abund = "wilm"; Xset.xsect = "vern"; Xset.cosmo = "70 0 0.73"
    Fit.query = "no"
    Plot.device = "/null"

    # Load external models like relxill if they exist
    RELXILL_MODEL_PATH = os.path.expanduser("~/Downloads/relxill")
    if os.path.exists(RELXILL_MODEL_PATH):
        AllModels.lmod("relxill", RELXILL_MODEL_PATH); print("-> Successfully loaded relxill models.")
    else:
        print(f"-> WARNING: relxill model path not found at '{RELXILL_MODEL_PATH}'. Reflection models will fail.")
    
    # Group the data
    output_a = "outA.pha"
    output_b = "outB.pha"
    os.system(f'grppha infile="{spec_a}" outfile="{output_a}" comm="group min 20 & exit" chatter=0 clobber=yes')
    os.system(f'grppha infile="{spec_b}" outfile="{output_b}" comm="group min 20 & exit" chatter=0 clobber=yes')
    
    # Load data and background into correct data groups
    AllData.clear()
    AllData(f"1:1 {output_a} 2:2 {output_b}")
    print("Data files loaded into separate data groups.")

    s1 = AllData(1)
    s2 = AllData(2)
    s1.background = s1.background.fileName
    s2.background = s2.background.fileName
    print("Background files assigned correctly.")
    
    # Set plot device and ignore ranges
    Plot.xAxis = "keV"
    AllData.ignore("bad")
    AllData.ignore("**-3.0 79.0-**")
    print("--- Data setup complete ---")


def set_initial_parameters(model_object, model_string: str):
    """
    A helper function that knows how to set initial parameters for
    all the models we want to test.
    """
    if "tbabs" in model_string:
        model_object.TBabs.nH.values = "0.6, -1"
    if "constant" in model_string:
        model_object.constant.factor.values = "1, -1"

    if "powerlaw" in model_string:
        model_object.powerlaw.PhoIndex = 1.7
        model_object.powerlaw.norm = 1.0
    if "diskbb" in model_string:
        model_object.diskbb.Tin = 0.5
        model_object.diskbb.norm = 1.0
    if "bknpower" in model_string:
        model_object.bknpower.PhoIndx1 = 1.7
        model_object.bknpower.BreakE = 10.0
        model_object.bknpower.PhoIndx2 = 2.2
        model_object.bknpower.norm = 1.0
    if "nthComp" in model_string:
        model_object.nthComp.Gamma = 1.7
        model_object.nthComp.kT_e = 50
        if "diskbb" in model_object.componentNames:
            m1_diskbb = getattr(model_object, "diskbb")
            model_object.nthComp.kT_bb.link = f"p{m1_diskbb.Tin.index}"
        else: 
            model_object.nthComp.kT_bb = 0.1
        model_object.nthComp.inp_type = 1
    if "gaussian" in model_string:
        model_object.gaussian.LineE.values = "6.4, -1"
        model_object.gaussian.Sigma = 0.5
    if "simpl" in model_string:
        model_object.simpl.Gamma = 1.7
        model_object.simpl.FracSctr = 0.1
    if "pcfabs" in model_string:
        model_object.pcfabs.nH = 10.0
        model_object.pcfabs.CvrFract = 0.5
    if "relxillCp" in model_string or "relxilllpCp" in model_string:
        relxill_comp_name = "relxillCp" if "relxillCp" in model_object.componentNames else "relxilllpCp"
        relxill_comp = getattr(model_object, relxill_comp_name)
        relxill_comp.gamma = 2.0; relxill_comp.logxi = 3.1
        relxill_comp.a = "0.998, -1"; relxill_comp.Incl = "40.0, -1"
        relxill_comp.z = "0.0, -1"; relxill_comp.refl_frac = 1.0
        relxill_comp.kTe = 100
        if "relxilllpCp" in relxill_comp_name:
            relxill_comp.h = 10.0


def perform_fit_and_get_results(model_name: str, model_string: str):
    """
    Defines, fits, and calculates errors for a given model.
    Returns the final parameters and fit statistics as a list of dictionaries.
    """
    print(f"\n--- Fitting Model: {model_name} ({model_string}) ---")
    
    AllModels.clear()
    m = Model(model_string)
    
    m1 = AllModels(1)
    set_initial_parameters(m1, model_string)

    m2 = AllModels(2)
    for i in range(1, m1.nParameters + 1):
        if not m1(i).frozen:
            m2(i).link = m1(i)
    
    print("\nPerforming fit...")
    Fit.nIterations = 100
    Fit.perform()
    print("Fit complete.")
    AllModels.show()

    results = []
    m1_after = AllModels(1)
    dof = Fit.dof
    chi2 = Fit.statistic
    r_chi2 = chi2 / dof if dof > 0 else -1
    
    for comp_name in m1_after.componentNames:
        comp = getattr(m1_after, comp_name)
        for par_name in comp.parameterNames:
            p = getattr(comp, par_name)
            param_result = {
                "model_name": model_name,
                "chi2": f"{chi2:.2f}", "dof": dof, "r_chi2": f"{r_chi2:.3f}",
                "param_index": p.index, "param_name": p.name,
                "param_component": comp.name, "unit": p.unit,
                "value": p.values[0], "error": p.sigma
            }
            results.append(param_result)
        
    return results


def save_plot(model_name: str, model_string: str, r_chi2: float, output_plot_filename: str):
    """Generates and saves a plot of the current fit."""
    print(f"\nGenerating plot: {output_plot_filename}...")
    Plot("ldata resid")
    
    e1, r1, err1, res1 = Plot.x(1), Plot.y(1), Plot.yErr(1), Plot.y(1, 2)
    m1_vals = Plot.model(1)
    e2, r2, err2, res2 = Plot.x(2), Plot.y(2), Plot.yErr(2), Plot.y(2, 2)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    plt.subplots_adjust(hspace=0)
    title_text = f"Model: {model_name}\n" + r"$\chi^2_\nu$ = " + f"{r_chi2:.3f}"
    fig.suptitle(title_text, fontsize=16)

    ax1.set_xscale('log'); ax1.set_yscale('log')
    ax1.errorbar(e1, r1, yerr=err1, fmt='k.', label="Data (FPMA)")
    ax1.errorbar(e2, r2, yerr=err2, fmt='r.', label="Data (FPMB)")
    #ax1.plot(e1, m1_vals, 'b-')
    ax1.plot(_,m1_vals,'b-')
    ax1.set_ylabel("counts s$^{-1}$ keV$^{-1}$"); ax1.legend()
    ax1.grid(True, which='both', linestyle='--', alpha=0.6)

    ax2.axhline(0.0, color='b', linestyle='--')
    ax2.errorbar(e1, res1, yerr=err1, fmt='k.'); ax2.errorbar(e2, res2, yerr=err2, fmt='r.')
    ax2.set_xlabel("Energy (keV)"); ax2.set_ylabel("Residuals ($\sigma$)")
    ax2.grid(True, which='both', linestyle='--', alpha=0.6)

    ax1.set_xlim(2.8, 80)

    plt.savefig(output_plot_filename)
    plt.close()
    print(f"Saved fit plot to '{os.path.abspath(output_plot_filename)}'")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Multi-model XSPEC script with CSV output")
    parser.add_argument("--spec_a", required=True, help="Input FPMA PHA spectral file.")
    parser.add_argument("--spec_b", required=True, help="Input FPMB PHA spectral file.")
    parser.add_argument("--obsid", required=True, help="Observation ID for labeling the output.")
    args = parser.parse_args()

    setup_data_and_environment(args.spec_a, args.spec_b)
    
    models_to_try = [
        ("Absorbed_Powerlaw", "constant*tbabs*powerlaw"),
        ("Absorbed_Broken_Powerlaw", "constant*tbabs*bknpower"),
        ("Disk_plus_Powerlaw", "constant*tbabs*(diskbb+powerlaw)"),
        ("Disk_plus_Broken_Powerlaw", "constant*tbabs*(diskbb+bknpower)"),
        ("Disk_plus_Comptonization", "constant*tbabs*(diskbb+nthComp)"),
        ("Disk_plus_Comp_plus_Gauss", "constant*tbabs*(diskbb+nthComp+gaussian)"),
        ("Disk_plus_Scattering", "constant*tbabs*simpl(diskbb)"),
        ("Partial_Covering", "constant*tbabs*pcfabs*(diskbb+nthComp)"),
        ("Relativistic_Reflection", "constant*tbabs*relxillCp"),
        ("Lamppost_Reflection", "constant*tbabs*relxilllpCp"),
        ("Disk_plus_Powerlaw_plus_Gaussian", "constant*tbabs*(diskbb+powerlaw+gaussian)")
    ]
    
    all_results_for_csv = []

    # --- [IMPLEMENTED CHANGE] ---
    # The logic for finding the best fit has been removed.
    # We now call save_plot inside the loop for every successful fit.
    for model_name, model_string in models_to_try:
        try:
            results = perform_fit_and_get_results(model_name, model_string)
            all_results_for_csv.extend(results)
            
            # Get the reduced chi-squared for the plot title
            current_r_chi2 = float(results[0]['r_chi2'])
            
            # Generate a plot for this model
            # The plot filename is now unique for each model
            plot_filename = f"fit_plot_{model_name}_{args.obsid}.png"
            save_plot(model_name, model_string, current_r_chi2, plot_filename)
            
        except Exception as e:
            print(f"!!! CRITICAL ERROR fitting model {model_name}: {e}")
    # --- [END OF CHANGE] ---

    output_csv_filename = f"fit_results_{args.obsid}.csv"
    print(f"\n--- Writing all results to {output_csv_filename} ---")
    
    if all_results_for_csv:
        headers = all_results_for_csv[0].keys()
        with open(output_csv_filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_results_for_csv)
        print(f"Successfully saved results to {os.path.abspath(output_csv_filename)}")

    print("\nScript finished successfully.")
