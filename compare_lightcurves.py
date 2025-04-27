#!/usr/bin/env python3
"""
Script to compare NuSTAR light curves across different parameters.

This script allows comparing light curves with:
- Different source extraction radii
- Different background regions
- Different time binnings
- Different observations

Usage examples:
    python compare_lightcurves.py --compare source_radius --obs 30001011009 --bin 0.1 --bkg 050-080
    python compare_lightcurves.py --compare background --obs 30001011009 --src 15 --bin 0.1
    python compare_lightcurves.py --compare binning --obs 30001011009 --src 15 --bkg 050-080
    python compare_lightcurves.py --compare observations --src 15 --bkg 050-080 --bin 0.1
"""

import os
import sys
import glob
import argparse
import numpy as np
import pandas as pd

# Bokeh imports
from bokeh.plotting import figure, save, show
from bokeh.layouts import column, row, gridplot
from bokeh.models import (
    ColumnDataSource, HoverTool, Span, Range1d, 
    Title, LinearAxis, CustomJS, Label, NumeralTickFormatter,
    Legend, LegendItem
)
from bokeh.io import output_file as bokeh_output_file

# HoloViews/Datashader imports - for handling large datasets efficiently
import holoviews as hv
from holoviews.operation.datashader import rasterize
import datashader as ds
hv.extension('bokeh')

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Compare NuSTAR light curves across different parameters.')
    
    parser.add_argument('--compare', required=True, choices=['source_radius', 'background', 'binning', 'observations'],
                        help='Type of comparison to make')
    
    parser.add_argument('--obs', help='Observation ID to use (e.g., 30001011009)')
    parser.add_argument('--src', help='Source radius in arcsec to use (e.g., 15)')
    parser.add_argument('--bkg', help='Background region to use (e.g., 050-080)')
    parser.add_argument('--bin', help='Time bin size in seconds to use (e.g., 0.1)')
    
    parser.add_argument('--lightcurves_dir', default='/media/kartikmandar/HDD/Cygnusx1_lightcurves/lightcurves_txt',
                        help='Base directory containing light curves text files')
    parser.add_argument('--output', help='Output file for the plot (HTML format)')
    parser.add_argument('--title', help='Custom title for the plot')
    
    # Optional arguments for additional analysis
    parser.add_argument('--stats', action='store_true', help='Include detailed statistics in the output')
    parser.add_argument('--normalize', action='store_true', help='Normalize light curves to their means for easier comparison')
    parser.add_argument('--use_datashader', action='store_true', help='Use datashader for rendering (recommended for large datasets)')
    
    return parser.parse_args()

def find_lightcurve_files(args):
    """Find light curve text files based on the comparison type and parameters."""
    base_dir = args.lightcurves_dir
    files = []
    
    if args.compare == 'source_radius':
        # Find light curves with different source radii
        if not args.obs or not args.bin or not args.bkg:
            print("Error: --obs, --bin, and --bkg are required for source_radius comparison")
            sys.exit(1)
            
        # Look for all source radii for this observation/bin/background
        # Adjust pattern to handle the different filename format for bkg in folders vs filenames
        pattern = os.path.join(base_dir, args.obs, f"src*_bkg{args.bkg}_bin{args.bin}", "final_LC_src*_bkg*.txt")
        files = glob.glob(pattern)
        
        # Filter to keep only files matching the correct background
        # In filenames, "050-080" becomes "50-80", so we need to handle this conversion
        bkg_adjusted = f"{int(args.bkg.split('-')[0])}-{int(args.bkg.split('-')[1])}"
        files = [f for f in files if f"bkg{bkg_adjusted}" in os.path.basename(f)]
        
    elif args.compare == 'background':
        # Find light curves with different background regions
        if not args.obs or not args.src or not args.bin:
            print("Error: --obs, --src, and --bin are required for background comparison")
            sys.exit(1)
            
        # Look for all background regions for this observation/source/bin
        pattern = os.path.join(base_dir, args.obs, f"src{int(args.src):03d}_bkg*_bin{args.bin}", f"final_LC_src{args.src}_bkg*.txt")
        files = glob.glob(pattern)
        
    elif args.compare == 'binning':
        # Find light curves with different time binnings
        if not args.obs or not args.src or not args.bkg:
            print("Error: --obs, --src, and --bkg are required for binning comparison")
            sys.exit(1)
            
        # Look for all bin sizes for this observation/source/background
        pattern = os.path.join(base_dir, args.obs, f"src{int(args.src):03d}_bkg{args.bkg}_bin*", "final_LC_src*.txt")
        
        # Filter to keep only files matching the correct source/background
        bkg_adjusted = f"{int(args.bkg.split('-')[0])}-{int(args.bkg.split('-')[1])}"
        src_adjusted = args.src
        files = glob.glob(pattern)
        files = [f for f in files if f"src{src_adjusted}_bkg{bkg_adjusted}" in os.path.basename(f)]
        
    elif args.compare == 'observations':
        # Find light curves from different observations
        if not args.src or not args.bkg or not args.bin:
            print("Error: --src, --bkg, and --bin are required for observations comparison")
            sys.exit(1)
            
        # Look for this src/bkg/bin across all observations
        pattern = os.path.join(base_dir, "*", f"src{int(args.src):03d}_bkg{args.bkg}_bin{args.bin}", "final_LC_src*.txt")
        
        # Filter to keep only files matching the correct source/background
        bkg_adjusted = f"{int(args.bkg.split('-')[0])}-{int(args.bkg.split('-')[1])}"
        src_adjusted = args.src
        files = glob.glob(pattern)
        files = [f for f in files if f"src{src_adjusted}_bkg{bkg_adjusted}" in os.path.basename(f)]
    
    if not files:
        print(f"No matching light curve files found using pattern.")
        if args.compare == 'source_radius':
            print(f"Hint: Try running 'find {base_dir}/{args.obs} -name \"*.txt\" | grep \"bkg\" | head' to see available files")
        sys.exit(1)
        
    return sorted(files)

def extract_comparison_value(filepath, compare_type):
    """Extract the value being compared from the filepath."""
    basename = os.path.basename(filepath)
    dirname = os.path.basename(os.path.dirname(filepath))
    obsid = os.path.basename(os.path.dirname(os.path.dirname(filepath)))
    
    if compare_type == 'source_radius':
        # Extract source radius from the filename (e.g., final_LC_src15_bkg50-80.txt)
        return int(basename.split('_src')[1].split('_')[0])
        
    elif compare_type == 'background':
        # Extract background region from the filename
        return basename.split('_bkg')[1].split('.')[0]
        
    elif compare_type == 'binning':
        # Extract bin size from the directory name
        return float(dirname.split('_bin')[1])
        
    elif compare_type == 'observations':
        # Return the observation ID
        return obsid
        
    return None

def load_lightcurve_from_text(lc_file):
    """Load light curve data from a text file created by export_to_text.sh."""
    try:
        # The text files have a header line followed by data columns:
        # # TIME(s)    MJD    RATE(cts/s)    ERROR(cts/s)
        data = np.loadtxt(lc_file, skiprows=1)
        
        # Extract data columns
        time = data[:, 0]        # TIME(s)
        mjd_times = data[:, 1]   # MJD
        rate = data[:, 2]        # RATE(cts/s)
        error = data[:, 3]       # ERROR(cts/s)
        
        # Filter out NaN values if any exist
        valid_mask = ~np.isnan(rate) & ~np.isnan(time) & ~np.isnan(error)
        if not np.all(valid_mask):
            time = time[valid_mask]
            mjd_times = mjd_times[valid_mask]
            rate = rate[valid_mask]
            error = error[valid_mask]
        
        # Calculate hours from start
        if len(time) > 0:
            time_offset = time - time[0]  # seconds from start
            time_hours = time_offset / 3600.0  # convert to hours
        else:
            time_hours = np.array([])
        
        # Extract basic info from the filepath
        # Format: .../obsid/src015_bkg050-080_bin0.1/final_LC_src15_bkg50-80.txt
        dirname = os.path.basename(os.path.dirname(lc_file))  # e.g., src015_bkg050-080_bin0.1
        obsid = os.path.basename(os.path.dirname(os.path.dirname(lc_file)))
        bin_size = float(dirname.split('_bin')[1])
        exposure = time[-1] - time[0] if len(time) > 1 else 0
        
        # Calculate basic statistics
        mean_rate = np.mean(rate)
        std_rate = np.std(rate)
        max_rate = np.max(rate)
        min_rate = np.min(rate)
        
        return {
            'obsid': obsid,
            'exposure': exposure,
            'bin_size': bin_size,
            'time': time,
            'mjd_times': mjd_times,
            'time_hours': time_hours,
            'rate': rate,
            'error': error,
            'mean_rate': mean_rate,
            'std_rate': std_rate,
            'max_rate': max_rate,
            'min_rate': min_rate
        }
            
    except Exception as e:
        print(f"Error reading text file {lc_file}: {e}")
        return None

def plot_lightcurve_comparison_bokeh(lc_files, args):
    """Create comparison plot of multiple light curves using Bokeh."""
    
    # Define plot colors
    colors = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'magenta', 'gray', 'olive', 'cyan']
    light_colors = ['lightblue', 'salmon', 'lightgreen', 'plum', 'bisque', 'sandybrown', 'pink', 'lightgray', 'khaki', 'lightcyan']
    
    # Create figures for main plot and deviation/residual plot
    tooltips = [
        ("MJD", "@mjd{0.00000}"),
        ("Hours", "@hours{0.00}"),
        ("Rate", "@rate{0,0.000} cts/s"),
        ("Error", "±@error{0,0.000} cts/s")
    ]
    
    # Create main figure with MJD x-axis
    p_main = figure(
        width=900, height=500,
        tools="pan,wheel_zoom,box_zoom,reset,save",
        active_drag="box_zoom",
        active_scroll="wheel_zoom",
        toolbar_location="above",
        x_axis_label="Time (MJD)",
        y_axis_label="Count Rate (counts/s)" if not args.normalize else "Normalized Count Rate",
    )
    
    # Add hover tool
    hover = HoverTool(tooltips=tooltips, mode="vline")
    p_main.add_tools(hover)
    
    # Create residual plot
    p_residual = figure(
        width=900, height=200,
        tools="pan,wheel_zoom,box_zoom,reset,save",
        active_drag="box_zoom",
        active_scroll="wheel_zoom",
        toolbar_location=None,
        x_axis_label="Time (MJD)",
        y_axis_label="Deviation from Mean" if not args.normalize else "% Deviation from Mean",
        x_range=p_main.x_range,  # Link x-range with main plot
    )
    
    # Create a figure for hours display
    p_hours = figure(
        width=900, height=50,
        tools="pan,wheel_zoom,box_zoom,reset,save",
        active_drag="box_zoom",
        active
            ax1.axhline(y=lc_data['mean_rate'], color=color, linestyle='--', alpha=0.5)
        
        # Plot on secondary panel (Relative flux)
        if args.normalize:
            # For normalized view, show fractional difference from mean (in %)
            ax2.plot(lc_data['mjd_times'], (y_values - 1.0) * 100, '.', color=color, alpha=0.7, markersize=2)
        else:
            # For non-normalized, show absolute difference from mean
            ax2.plot(lc_data['mjd_times'], y_values - lc_data['mean_rate'], '.', color=color, alpha=0.7, markersize=2)
        
        # Track data ranges for axis limits
        all_times.extend(lc_data['mjd_times'])
        all_rates.extend(y_values)
        
        # Show statistics in legend if requested
        if args.stats:
            stats_text = f" (mean={lc_data['mean_rate']:.2f}, σ={lc_data['std_rate']:.2f})"
            legend_elements[-1].set_label(f"{legend_elements[-1].get_label()}{stats_text}")
    
    # Set axis labels
    if args.normalize:
        ax1.set_ylabel('Normalized Count Rate')
        ax2.set_ylabel('% Deviation from Mean')
    else:
        ax1.set_ylabel('Count Rate (counts/s)')
        ax2.set_ylabel('Deviation from Mean (counts/s)')
    
    ax1.set_xlabel('Time (MJD)')
    ax2.set_xlabel('Time (MJD)')
    
    # Format MJD x-axis to show appropriate precision
    for ax in [ax1, ax2]:
        mjd_formatter = FuncFormatter(lambda x, pos: f'{x:.5f}')
        ax.xaxis.set_major_formatter(mjd_formatter)
        plt.setp(ax.get_xticklabels(), rotation=45)
    
    # Set title based on the comparison type
    if args.title:
        title = args.title
    else:
        # Construct title based on fixed parameters
        title_parts = []
        
        if args.obs and args.compare != 'observations':
            title_parts.append(f"ObsID: {args.obs}")
        
        if args.src and args.compare != 'source_radius':
            title_parts.append(f"Source: {args.src} arcsec")
            
        if args.bkg and args.compare != 'background':
            title_parts.append(f"Background: {args.bkg}")
            
        if args.bin and args.compare != 'binning':
            title_parts.append(f"Bin: {args.bin} s")
            
        comparison_name = {
            'source_radius': 'Source Radius',
            'background': 'Background Region',
            'binning': 'Time Binning',
            'observations': 'Observations'
        }
        
        title = f"Comparison of {comparison_name[args.compare]}\n{', '.join(title_parts)}"
    
    ax1.set_title(title)
    
    # Add grid
    ax1.grid(True, alpha=0.3)
    ax2.grid(True, alpha=0.3)
    
    # Set axis limits with padding
    if all_times:
        time_range = max(all_times) - min(all_times)
        time_padding = time_range * 0.02
        ax1.set_xlim(min(all_times) - time_padding, max(all_times) + time_padding)
        ax2.set_xlim(min(all_times) - time_padding, max(all_times) + time_padding)
    
    if all_rates:
        rate_range = max(all_rates) - min(all_rates)
        rate_padding = rate_range * 0.05
        ax1.set_ylim(min(all_rates) - rate_padding, max(all_rates) + rate_padding)
    
    # Add legend
    ax1.legend(handles=legend_elements, loc='upper right')
    
    # Adjust layout
    plt.tight_layout()
    
    # Save the plot if output file is specified
    if args.output:
        plt.savefig(args.output, dpi=300)
        print(f"Plot saved to: {args.output}")
    
    # Show the plot
    plt.show()

def get_comparison_statistics(lc_files, args):
    """Generate detailed statistics for the comparison."""
    stats = []
    
    for lc_file in lc_files:
        lc_data = load_lightcurve_from_text(lc_file)
        if not lc_data:
            continue
            
        comparison_value = extract_comparison_value(lc_file, args.compare)
        
        # Calculate additional statistics
        rms_var = lc_data['std_rate'] / lc_data['mean_rate'] * 100  # RMS variability in percent
        
        # Signal-to-noise estimate (mean / mean_error)
        mean_error = np.mean(lc_data['error'])
        snr = lc_data['mean_rate'] / mean_error if mean_error > 0 else 0
        
        stats.append({
            'comparison_value': comparison_value,
            'mean_rate': lc_data['mean_rate'],
            'std_rate': lc_data['std_rate'],
            'min_rate': lc_data['min_rate'],
            'max_rate': lc_data['max_rate'],
            'rms_var': rms_var,
            'snr': snr,
            'exposure': lc_data['exposure'],
            'bin_size': lc_data['bin_size']
        })
    
    return stats

def print_comparison_statistics(stats, args):
    """Print comparison statistics to console."""
    print("\n--- Comparison Statistics ---")
    
    # Table header
    header_label = {
        'source_radius': 'Src Radius',
        'background': 'Bkg Region',
        'binning': 'Bin Size',
        'observations': 'ObsID'
    }[args.compare]
    
    header = f"{header_label:15s} | {'Mean Rate':10s} | {'Std Dev':10s} | {'RMS Var%':10s} | {'SNR':10s} | {'Min Rate':10s} | {'Max Rate':10s}"
    print(header)
    print("-" * len(header))
    
    # Sort by the comparison value
    stats.sort(key=lambda x: x['comparison_value'])
    
    # Print each row
    for stat in stats:
        value = stat['comparison_value']
        
        # Format value based on comparison type
        if args.compare == 'binning' and float(value) < 1:
            value = f"{float(value)*1000:.0f} ms"
        elif args.compare == 'background':
            value = f"{value}"
        elif args.compare == 'source_radius':
            value = f"{value} arcsec"
        
        print(f"{value:15s} | {stat['mean_rate']:10.3f} | {stat['std_rate']:10.3f} | {stat['rms_var']:10.2f} | {stat['snr']:10.2f} | {stat['min_rate']:10.3f} | {stat['max_rate']:10.3f}")

def main():
    """Main function to run the script."""
    args = parse_arguments()
    
    # Find light curve files based on the comparison type
    lc_files = find_lightcurve_files(args)
    print(f"Found {len(lc_files)} light curve files to compare.")
    
    # Print first few file paths for debugging
    if lc_files:
        print("First few files found:")
        for f in lc_files[:3]:
            print(f"  - {f}")
    
    # Calculate statistics
    stats = get_comparison_statistics(lc_files, args)
    
    # Print statistics if requested
    if args.stats:
        print_comparison_statistics(stats, args)
    
    # Create comparison plot
    plot_lightcurve_comparison(lc_files, args)

if __name__ == "__main__":
    main()