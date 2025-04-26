#!/usr/bin/env python3
"""
Script to plot NuSTAR light curve data from a FITS file using Bokeh.
Usage: python plot_bokeh_lightcurve.py [path_to_lightcurve_file]
"""

import sys
import os
import numpy as np
from astropy.io import fits

# Bokeh imports
from bokeh.plotting import figure, save, show
from bokeh.layouts import column, gridplot
from bokeh.models import (
    ColumnDataSource, HoverTool, Span, Range1d, 
    Title, LinearAxis, CustomJS, Label, NumeralTickFormatter
)
from bokeh.io import output_file as bokeh_output_file

def plot_lightcurve(lc_file):
    """
    Plot a NuSTAR light curve from a FITS file using Bokeh.
    
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
            
            # Filter out NaN values
            valid_mask = ~np.isnan(rate)
            if not np.all(valid_mask):
                print(f"Warning: Found {np.sum(~valid_mask)} NaN values in rate data. Filtering them out.")
                time = time[valid_mask]
                rate = rate[valid_mask]
                error = error[valid_mask]
            
            # Check if we have any valid data left
            if len(time) == 0:
                print("Error: No valid data points after filtering NaN values.")
                return
            
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
    
    # Prepare data for Bokeh
    source = ColumnDataSource(data={
        'mjd': mjd_times,
        'hours': time_hours,
        'rate': rate,
        'error': error,
        'upper': rate + error,
        'lower': rate - error,
    })
    
    # Extract source and background info from filename
    filename = os.path.basename(lc_file)
    if "src" in filename and "bkg" in filename:
        src_bkg_info = filename.split('final_LC_')[1].split('.lc')[0]
    else:
        src_bkg_info = ""
    
    # Create figure for MJD plot
    tooltips = [
        ("MJD", "@mjd{0.00000}"),
        ("Hours", "@hours{0.00}"),
        ("Rate", "@rate{0,0.000} cts/s"),
        ("Error", "±@error{0,0.000} cts/s")
    ]
    
    # Create main figure with MJD x-axis
    p_mjd = figure(
        width=900, height=500,
        tools="pan,wheel_zoom,box_zoom,reset,save",
        active_drag="box_zoom",
        active_scroll="wheel_zoom",
        toolbar_location="above",
        x_axis_label="Time (MJD)",
        y_axis_label="Count Rate (counts/s)",
    )
    
    # Add hover tool
    hover = HoverTool(tooltips=tooltips, mode="vline")
    p_mjd.add_tools(hover)
    
    # Add error bars (use segments for vertical lines)
    p_mjd.segment(x0='mjd', y0='lower', x1='mjd', y1='upper', source=source, 
                  color='lightblue', line_width=1)
    
    # Add the data points (using scatter instead of circle due to deprecation warning)
    p_mjd.scatter(x='mjd', y='rate', source=source, size=5, color='blue', alpha=0.7)
    
    # Add horizontal line at mean rate
    mean_line = Span(location=mean_rate, dimension='width', line_color='red', 
                    line_dash='solid', line_width=2)
    p_mjd.add_layout(mean_line)
    
    # Add mean value as text annotation
    mean_label = Label(
        x=5, y=5, x_units='screen', y_units='screen',
        text=f"Mean: {mean_rate:.3f} cts/s", 
        text_color='red', text_font_size='10pt'
    )
    p_mjd.add_layout(mean_label)
    
    # Format x-axis ticks for MJD (5 decimal places)
    p_mjd.xaxis.formatter = NumeralTickFormatter(format="0.00000")
    
    # Add title
    title_text = f"{target} (ObsID: {obsid})\n"
    title_text += f"Date: {date_obs}, Exp: {exposure:.1f} s, Bin: {bin_size:.3f} s\n{src_bkg_info}"
    p_mjd.add_layout(Title(text=title_text, text_font_size="12pt"), "above")
    
    # Create a secondary figure with hours-from-start axis
    p_hours = figure(
        width=900, height=100,
        tools="pan,wheel_zoom,box_zoom,reset,save",
        active_drag="box_zoom", 
        active_scroll="wheel_zoom",
        toolbar_location=None,
        x_axis_label="Time (hours from start)",
        y_range=Range1d(start=0, end=1),  # Hide this axis area
    )
    
    # Hide y-axis for hours plot
    p_hours.yaxis.visible = False
    p_hours.grid.visible = False
    p_hours.outline_line_color = None
    
    # Format hours axis
    p_hours.xaxis.formatter = NumeralTickFormatter(format="0.00")
    
    # Link the ranges with a custom JS callback
    callback_to_hours = CustomJS(args=dict(p_mjd=p_mjd, p_hours=p_hours, mjd_start=mjd_times[0]), code="""
        const mjd_range = p_mjd.x_range;
        const hours_range = p_hours.x_range;
        hours_range.start = (mjd_range.start - mjd_start) * 24.0;
        hours_range.end = (mjd_range.end - mjd_start) * 24.0;
    """)
    
    callback_to_mjd = CustomJS(args=dict(p_mjd=p_mjd, p_hours=p_hours, mjd_start=mjd_times[0]), code="""
        const mjd_range = p_mjd.x_range;
        const hours_range = p_hours.x_range;
        mjd_range.start = mjd_start + hours_range.start / 24.0;
        mjd_range.end = mjd_start + hours_range.end / 24.0;
    """)
    
    p_mjd.x_range.js_on_change('start', callback_to_hours)
    p_mjd.x_range.js_on_change('end', callback_to_hours)
    p_hours.x_range.js_on_change('start', callback_to_mjd)
    p_hours.x_range.js_on_change('end', callback_to_mjd)
    
    # Set initial range for hours plot
    p_hours.x_range.start = 0
    p_hours.x_range.end = max(time_hours)
    
    # Initialize MJD plot range
    p_mjd.x_range.start = mjd_times[0]
    p_mjd.x_range.end = mjd_times[-1]
    
    # Arrange the plots
    layout = column(p_mjd, p_hours)
    
    # Save the plot - fixed the naming conflict here
    html_output_file = os.path.splitext(lc_file)[0] + '_bokeh.html'
    bokeh_output_file(html_output_file)
    save(layout)
    print(f"Interactive plot saved to: {html_output_file}")
    
    # Also show in browser
    show(layout)

if __name__ == "__main__":
    # Use the command-line argument if provided, otherwise use the default file
    if len(sys.argv) > 1:
        lc_file = sys.argv[1]
    else:
        # Default file path
        lc_file = "/media/kartikmandar/HDD/Cygnusx1_lightcurves/lightcurves/30001011009/src015_bkg050-080_bin0.1/final_LC_src15_bkg50-80.lc"
    
    plot_lightcurve(lc_file)