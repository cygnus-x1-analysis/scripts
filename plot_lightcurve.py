#!/usr/bin/env python3
"""
Script to plot NuSTAR light curve data from a FITS file.
Usage: python plot_lightcurve.py [path_to_lightcurve_file]
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.time import Time
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

def plot_lightcurve(lc_file):
    """
    Plot a NuSTAR light curve from a FITS file.
    
    Parameters:
    -----------
    lc_file : str
        Path to the light curve FITS file
    """
    # Check if file exists
    if not os.path.exists(lc_file):
        print(f"Error: File '{lc_file}' not found.")
        return
        
    try:
        # Open the FITS file
        with fits.open(lc_file) as hdul:
            print(f"FITS extensions available: {[ext.name for ext in hdul]}")
            
            # Get metadata from primary header
            primary_header = hdul[0].header
            obsid = primary_header.get('OBS_ID', 'Unknown')
            target = primary_header.get('OBJECT', 'Unknown')
            instrument = primary_header.get('INSTRUME', 'NuSTAR')
            exposure = primary_header.get('EXPOSURE', 0)
            bin_size = primary_header.get('TIMEDEL', 0)
            tstart = primary_header.get('TSTART', 0)
            tstop = primary_header.get('TSTOP', 0)
            
            # MJD reference from header (NuSTAR specific)
            mjdrefi = primary_header.get('MJDREFI', 0)
            mjdreff = primary_header.get('MJDREFF', 0)
            mjdref = mjdrefi + mjdreff
            
            date_obs = primary_header.get('DATE-OBS', '')
            
            print(f"Target: {target}, ObsID: {obsid}")
            print(f"Exposure: {exposure} s, Bin size: {bin_size} s")
            print(f"Observation start: {date_obs}")
            print(f"MJD reference: {mjdref}")
            
            # Get data from the RATE extension
            lc_data = hdul['RATE'].data
            print(f"Columns available: {lc_data.names}")
            
            # Extract key information
            time = lc_data['TIME']
            rate = lc_data['RATE']
            error = lc_data['ERROR']
            
            # Convert mission time to MJD
            mjd_times = mjdref + (time / 86400.0)  # Convert seconds to days
            
            # Calculate hours from start
            if len(time) > 0:
                time_offset = time - time[0]  # seconds from start
                time_hours = time_offset / 3600.0  # convert to hours
            else:
                time_hours = np.array([])
            
            print(f"Time range (MJD): {mjd_times[0]:.6f} - {mjd_times[-1]:.6f}")
            print(f"Time range (hours): 0.0 - {time_hours[-1]:.3f}")
                
    except Exception as e:
        print(f"Error reading FITS file: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Calculate basic statistics
    mean_rate = np.mean(rate)
    std_rate = np.std(rate)
    max_rate = np.max(rate)
    min_rate = np.min(rate)
    
    print(f"Mean count rate: {mean_rate:.3f} cts/s")
    print(f"Std deviation: {std_rate:.3f} cts/s")
    print(f"Range: {min_rate:.3f} - {max_rate:.3f} cts/s")
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot light curve with error bars using MJD for x-axis
    ax.errorbar(mjd_times, rate, yerr=error, fmt='o', markersize=3, 
                color='blue', ecolor='lightblue', capsize=0, alpha=0.7)
    
    # Add horizontal line at mean rate
    ax.axhline(y=mean_rate, color='red', linestyle='-', alpha=0.7, label=f'Mean: {mean_rate:.2f} cts/s')
    
    # Set labels for primary axis (MJD)
    ax.set_xlabel('Time (MJD)')
    ax.set_ylabel('Count Rate (counts/s)')
    
    # Format MJD x-axis to show appropriate precision
    mjd_formatter = FuncFormatter(lambda x, pos: f'{x:.5f}')
    ax.xaxis.set_major_formatter(mjd_formatter)
    
    # Adjust x-axis ticks to show reasonable number of points
    duration_days = mjd_times[-1] - mjd_times[0]
    if duration_days < 0.01:  # Less than ~15 minutes
        # For very short observations, show more precision
        plt.xticks(rotation=45)
    else:
        # For longer observations, calculate appropriate tick spacing
        tick_spacing = duration_days / 6  # Aim for ~6 ticks
        tick_start = np.floor(mjd_times[0] / tick_spacing) * tick_spacing
        tick_end = np.ceil(mjd_times[-1] / tick_spacing) * tick_spacing
        ticks = np.arange(tick_start, tick_end + tick_spacing, tick_spacing)
        ax.set_xticks(ticks)
        plt.xticks(rotation=45)
    
    # Create a secondary x-axis for hours from start
    def mjd_to_hours(x):
        # Convert MJD to hours from start
        return (x - mjd_times[0]) * 24.0  # days to hours
    
    def hours_to_mjd(x):
        # Convert hours from start to MJD
        return mjd_times[0] + (x / 24.0)  # hours to days
    
    secax = ax.secondary_xaxis('top', functions=(mjd_to_hours, hours_to_mjd))
    secax.set_xlabel('Time (hours from start)')
    
    # Format the hours with appropriate precision
    hours_formatter = FuncFormatter(lambda x, pos: f'{x:.2f}')
    secax.xaxis.set_major_formatter(hours_formatter)
    
    # Extract source and background info from filename
    filename = os.path.basename(lc_file)
    if "src" in filename and "bkg" in filename:
        src_bkg_info = filename.split('final_LC_')[1].split('.lc')[0]
    else:
        src_bkg_info = ""
    
    title = f"{target} (ObsID: {obsid})\n"
    title += f"Date: {date_obs}, Exp: {exposure:.1f} s, Bin: {bin_size:.3f} s\n{src_bkg_info}"
    plt.title(title)
    
    # Add grid and tight layout
    ax.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    
    # Save the plot
    output_file = os.path.splitext(lc_file)[0] + '_plot_dual_time.png'
    plt.savefig(output_file, dpi=300)
    print(f"Plot saved to: {output_file}")
    
    # Show the plot
    plt.show()

if __name__ == "__main__":
    # Use the command-line argument if provided, otherwise use the default file
    if len(sys.argv) > 1:
        lc_file = sys.argv[1]
    else:
        # Default file path
        lc_file = "/media/kartikmandar/HDD/Cygnusx1_lightcurves/lightcurves/30001011009/src015_bkg050-080_bin0.1/final_LC_src15_bkg50-80.lc"
    
    plot_lightcurve(lc_file)