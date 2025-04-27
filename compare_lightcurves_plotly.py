#!/usr/bin/env python3
"""
Script to compare NuSTAR light curves across different parameters using Plotly.

Usage examples:
    python compare_lightcurves_bokeh.py --compare source_radius --obs 30001011009 --bin 0.1 --bkg 050-080
    python compare_lightcurves_bokeh.py --compare background --obs 30001011009 --src 15 --bin 0.1
    python compare_lightcurves_bokeh.py --compare binning --obs 30001011009 --src 15 --bkg 050-080
    python compare_lightcurves_bokeh.py --compare observations --src 15 --bkg 050-080 --bin 0.1
"""

import os
import sys
import glob
import argparse
import numpy as np
import pandas as pd

# Plotly imports (replacing Bokeh)
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    parser.add_argument('--output', help='Output file for the plot (PNG format)')
    parser.add_argument('--title', help='Custom title for the plot')
    
    # Optional arguments for additional analysis
    parser.add_argument('--stats', action='store_true', help='Include detailed statistics in the output')
    parser.add_argument('--normalize', action='store_true', help='Normalize light curves to their means for easier comparison')
    parser.add_argument('--list-all', action='store_true', help='List all found files instead of just the first few')
    
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

def hex_to_rgb(hex_color):
    """Convert hex color string or named color to RGB tuple with values from 0 to 1."""
    # Dictionary of named colors to RGB values (0-1 scale)
    colors = {
        'blue': (0, 0, 1),
        'red': (1, 0, 0),
        'green': (0, 0.5, 0),
        'purple': (0.5, 0, 0.5),
        'orange': (1, 0.65, 0),
        'brown': (0.65, 0.16, 0.16),
        'magenta': (1, 0, 1),
        'gray': (0.5, 0.5, 0.5),
        'olive': (0.5, 0.5, 0),
        'cyan': (0, 1, 1),
        'lightblue': (0.68, 0.85, 0.9),
        'salmon': (0.98, 0.5, 0.45),
        'lightgreen': (0.56, 0.93, 0.56),
        'plum': (0.87, 0.63, 0.87),
        'bisque': (1, 0.89, 0.77),
        'sandybrown': (0.96, 0.64, 0.38),
        'pink': (1, 0.75, 0.8),
        'lightgray': (0.83, 0.83, 0.83),
        'khaki': (0.94, 0.9, 0.55),
        'lightcyan': (0.88, 1, 1),
    }
    
    # Check if it's a named color first
    if hex_color.lower() in colors:
        return colors[hex_color.lower()]
    
    # Otherwise treat as hex
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)
        
    # Default fallback
    return (0.5, 0.5, 0.5)

def plot_lightcurve_comparison(lc_files, args):
    """Create comparison plot of multiple light curves using Plotly."""
    
    # Define plot colors
    colors = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'magenta', 'gray', 'olive', 'cyan']
    light_colors = ['lightblue', 'salmon', 'lightgreen', 'plum', 'bisque', 'sandybrown', 'pink', 'lightgray', 'khaki', 'lightcyan']
    
    # Create subplots: 2 rows (main plot + residuals), 1 column, shared x-axis
    fig = make_subplots(rows=2, cols=1, 
                       shared_xaxes=True,
                       subplot_titles=["Light Curve", "Residuals"],
                       vertical_spacing=0.1,
                       row_heights=[0.8, 0.2])
    
    # Track MJD range for secondary x-axis
    min_mjd = None
    first_mjd_start = None
    
    # Load and plot each light curve
    for i, lc_file in enumerate(lc_files):
        color_idx = i % len(colors)
        color = colors[color_idx]
        light_color = light_colors[color_idx]
        
        lc_data = load_lightcurve_from_text(lc_file)
        if not lc_data:
            continue
            
        comparison_value = extract_comparison_value(lc_file, args.compare)
        
        # Format the comparison value for display
        if args.compare == 'source_radius':
            label = f"{comparison_value} arcsec"
        elif args.compare == 'background':
            label = f"bkg {comparison_value}"
        elif args.compare == 'binning':
            if comparison_value < 1:
                label = f"{comparison_value*1000:.0f} ms"
            else:
                label = f"{comparison_value:.2f} s"
        elif args.compare == 'observations':
            label = f"ObsID {comparison_value}"
            
        # Add statistics to label if requested
        if args.stats:
            label += f" (mean={lc_data['mean_rate']:.2f}, σ={lc_data['std_rate']:.2f})"
        
        # Normalize if requested
        y_values = lc_data['rate'].copy()
        y_errors = lc_data['error'].copy()
        
        if args.normalize:
            y_values = y_values / lc_data['mean_rate']
            y_errors = y_errors / lc_data['mean_rate']
        
        # Downsample if too many points to avoid slow rendering
        max_points = 5000
        if len(y_values) > max_points:
            step = len(y_values) // max_points
            plot_indices = np.arange(0, len(y_values), step)
            print(f"  • Downsampling {lc_file} from {len(y_values)} to {len(plot_indices)} points for visualization")
            
            mjd_times = lc_data['mjd_times'][plot_indices]
            hours = lc_data['time_hours'][plot_indices]
            y_values = y_values[plot_indices]
            y_errors = y_errors[plot_indices]
        else:
            mjd_times = lc_data['mjd_times']
            hours = lc_data['time_hours']
        
        # Track the first MJD for hours calculations
        if min_mjd is None:
            min_mjd = mjd_times.min()
            first_mjd_start = min_mjd
            
        # Add error bars to main plot
        fig.add_trace(
            go.Scatter(
                x=mjd_times,
                y=y_values + y_errors,
                mode='lines',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip'
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=mjd_times,
                y=y_values - y_errors,
                mode='lines',
                line=dict(width=0),
                fill='tonexty',
                fillcolor=f'rgba{tuple(int(c * 255) for c in hex_to_rgb(light_color)) + (0.3,)}',
                showlegend=False,
                hoverinfo='skip'
            ),
            row=1, col=1
        )
        
        # Add main data points
        fig.add_trace(
            go.Scatter(
                x=mjd_times,
                y=y_values,
                mode='markers' if len(mjd_times) > 1000 else 'lines+markers',
                name=label,
                line=dict(color=color),
                marker=dict(color=color, size=4, opacity=0.7),
                hovertemplate=(
                    'MJD: %{x:.5f}<br>' +
                    'Hours: %{customdata:.2f}<br>' +
                    'Rate: %{y:.3f} cts/s<br>' +
                    '<extra></extra>'
                ),
                customdata=hours
            ),
            row=1, col=1
        )
        
        # Add mean line
        mean_value = 1.0 if args.normalize else lc_data['mean_rate']
        fig.add_shape(
            type="line",
            x0=mjd_times.min(),
            x1=mjd_times.max(),
            y0=mean_value,
            y1=mean_value,
            line=dict(color=color, dash="dash", width=1),
            row=1, col=1
        )
        
        # Plot residuals 
        residuals = y_values - mean_value if not args.normalize else (y_values - 1.0) * 100
        fig.add_trace(
            go.Scatter(
                x=mjd_times,
                y=residuals,
                mode='markers',
                marker=dict(color=color, size=3, opacity=0.5),
                showlegend=False,
                hovertemplate=(
                    'MJD: %{x:.5f}<br>' +
                    'Deviation: %{y:.3f}' + (' %' if args.normalize else '') +
                    '<extra></extra>'
                )
            ),
            row=2, col=1
        )
    
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
        
        title = f"Comparison of {comparison_name[args.compare]}"
        if title_parts:
            title += f" ({', '.join(title_parts)})"
    
    # Update layout with title and axis labels
    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            font=dict(size=16)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        height=800,
        width=1000,
        hovermode="closest",
        margin=dict(t=100)
    )
    
    # Style the axes
    fig.update_xaxes(
        title_text="Time (MJD)",
        row=2, col=1
    )
    
    fig.update_yaxes(
        title_text="Count Rate (counts/s)" if not args.normalize else "Normalized Count Rate",
        row=1, col=1
    )
    
    fig.update_yaxes(
        title_text="Deviation from Mean" if not args.normalize else "% Deviation from Mean",
        row=2, col=1
    )
    
    # Create output filename
    if args.output:
        output_file = args.output
        # If it doesn't end with .png or .html, add .png
        if not (output_file.lower().endswith('.png') or output_file.lower().endswith('.html')):
            output_file = f"{output_file}.png"
    else:
        # Create default output filename based on comparison parameters
        if args.compare == 'source_radius':
            filename = f"compare_src_obs{args.obs}_bin{args.bin}_bkg{args.bkg}.png"
        elif args.compare == 'background':
            filename = f"compare_bkg_obs{args.obs}_src{args.src}_bin{args.bin}.png"
        elif args.compare == 'binning':
            filename = f"compare_bin_obs{args.obs}_src{args.src}_bkg{args.bkg}.png"
        elif args.compare == 'observations':
            filename = f"compare_obs_src{args.src}_bkg{args.bkg}_bin{args.bin}.png"
        
        output_file = os.path.join(os.getcwd(), filename)
    
    # Export to PNG or HTML based on extension
    try:
        if output_file.lower().endswith('.html'):
            # Export interactive HTML version
            import plotly.io as pio
            pio.write_html(fig, output_file)
            print(f"Interactive plot saved to HTML: {output_file}")
        else:
            # Export static image (PNG)
            fig.write_image(output_file, scale=2)  # Higher scale for better resolution
            print(f"Plot saved to PNG: {output_file}")
    except Exception as e:
        print(f"Error saving plot: {e}")
        print("Make sure you have the kaleido package installed for PNG export:")
        print("  pip install kaleido")
        sys.exit(1)

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
    
    # Print file paths based on user preference
    if lc_files:
        if args.list_all:
            print("All files found:")
            for f in lc_files:
                print(f"  - {f}")
        else:
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
