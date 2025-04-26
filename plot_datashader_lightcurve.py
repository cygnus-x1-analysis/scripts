#!/usr/bin/env python3
"""
Script to plot NuSTAR light curve data from a FITS file using HoloViews,
Datashader, and Bokeh for interactive and responsive plotting.
Usage: python plot_holoviews_lightcurve.py [path_to_lightcurve_file]
"""

import sys
import os
import numpy as np
import pandas as pd  # Using pandas is often convenient with HoloViews
from astropy.io import fits

# HoloViews / Datashader imports
import holoviews as hv
from holoviews.operation.datashader import rasterize
hv.extension('bokeh') # Set the backend to Bokeh

# Bokeh imports for specific customizations (hooks, models)
from bokeh.models import (
    HoverTool, Span, Range1d, Title, LinearAxis, CustomJS, Label, NumeralTickFormatter
)
# No need for figure, save, show, ColumnDataSource from bokeh.plotting
# No need for bokeh_output_file from bokeh.io

def plot_lightcurve_hv(lc_file):
    """
    Plot a NuSTAR light curve from a FITS file using HoloViews and Datashader.

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
            valid_mask = ~np.isnan(rate) & ~np.isnan(time) & ~np.isnan(error) # Ensure all are valid
            if not np.all(valid_mask):
                print(f"Warning: Found {np.sum(~valid_mask)} NaN values in data. Filtering them out.")
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

    # Prepare data for HoloViews (using Pandas DataFrame)
    df = pd.DataFrame({
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

    # --- HoloViews Plotting ---

    # Define tooltips for HoverTool
    tooltips = [
        ("MJD", "@mjd{0.00000}"),
        ("Hours", "@hours{0.00}"),
        ("Rate", "@rate{0,0.000} cts/s"),
        ("Error", "±@error{0,0.000} cts/s")
    ]
    hover = HoverTool(tooltips=tooltips)

    # Create HoloViews elements
    # Points element - kdims define position (x, y), vdims define associated values
    points = hv.Points(df, kdims=['mjd', 'rate'], vdims=['error', 'hours']).opts( # <--- CORRECTED LINE
        tools=[hover], # Attach hover tool here
        # alpha=0.7 # Alpha controlled by rasterize
        # size=5    # Size controlled by rasterize/pixel density
    )

    # Error bars element (as Segments for rasterization)
    # Create a DataFrame suitable for hv.Segments
    error_df = pd.DataFrame({
        'mjd0': df['mjd'], 'mjd1': df['mjd'],
        'lower': df['lower'], 'upper': df['upper']
    })
    error_segments = hv.Segments(error_df, kdims=['mjd0', 'lower', 'mjd1', 'upper']).opts(
        color='lightblue',
        line_width=1 # This might have less effect after rasterization
    )

    # Rasterize the points and error bars
    # Adjust width/height to match desired plot dimensions
    # cmap can be a single color or a colormap if aggregating
    rasterized_points = rasterize(points, cmap='blue', width=900, height=500, cnorm='linear', aggregator=ds.mean('rate'))
    rasterized_errors = rasterize(error_segments, cmap='lightblue', width=900, height=500)

    # Horizontal line for the mean rate
    mean_line_hv = hv.HLine(mean_rate).opts(
        color='red', line_dash='solid', line_width=2
    )

    # Overlay the elements: Rasterized errors first, then points, then mean line
    # Overlaying puts plots on the same axes
    main_plot = rasterized_errors * rasterized_points * mean_line_hv

    # Define plot title
    title_text = f"{target} (ObsID: {obsid})\n"
    title_text += f"Date: {date_obs}, Exp: {exposure:.1f} s, Bin: {bin_size:.3f} s\n{src_bkg_info}"

    # Define a hook function for Bokeh customizations HoloViews doesn't handle directly
    def customize_bokeh_fig(plot, element):
        fig = plot.state # Get the underlying Bokeh figure
        mjd_start = df['mjd'].iloc[0]
        mean_rate_val = df['rate'].mean() # Recalculate or ensure available

        # 1. Format main MJD axis (primary x-axis)
        fig.xaxis[0].formatter = NumeralTickFormatter(format="0.00000")

        # 2. Add secondary 'hours' x-axis below the main plot
        # Create a new range for the hours axis
        hours_range = Range1d(start=0, end=max(df['hours']))
        fig.extra_x_ranges = {"hours_range": hours_range}

        # Create the hours axis, linking it to the new range
        hours_axis = LinearAxis(x_range_name="hours_range", axis_label="Time (hours from start)")
        hours_axis.formatter = NumeralTickFormatter(format="0.00")
        fig.add_layout(hours_axis, 'below') # Add it below the plot

        # 3. Add CustomJS to link MJD zoom/pan to the hours axis display
        # This callback updates the hours axis when the MJD axis changes
        callback_to_hours = CustomJS(args=dict(hours_range=fig.extra_x_ranges['hours_range'],
                                               mjd_range=fig.x_range,
                                               mjd_start=mjd_start), code="""
            // Prevent infinite loops if ranges trigger each other
            if (!mjd_range.change_initiated_by) {
                hours_range.change_initiated_by = 'mjd'; // Mark initiator
                hours_range.start = (mjd_range.start - mjd_start) * 24.0;
                hours_range.end = (mjd_range.end - mjd_start) * 24.0;
                hours_range.change_initiated_by = null; // Reset flag
            }
        """)
        # Attach the callback to the MJD range start/end properties
        fig.x_range.js_on_change('start', callback_to_hours)
        fig.x_range.js_on_change('end', callback_to_hours)

        # Note: Interacting directly with the 'hours' axis to drive the MJD axis
        # is not implemented here, as secondary axes are often display-only.

        # 4. Add the mean rate label annotation
        mean_label = Label(
            x=5, y=5, x_units='screen', y_units='screen',
            text=f"Mean: {mean_rate_val:.3f} cts/s",
            text_color='red', text_font_size='10pt',
            background_fill_color='white', background_fill_alpha=0.7 # Add background
        )
        fig.add_layout(mean_label)

        # 5. Set initial MJD range (optional, HoloViews usually sets this automatically)
        # fig.x_range.start = df['mjd'].iloc[0]
        # fig.x_range.end = df['mjd'].iloc[-1]

        # 6. Trigger initial calculation for hours axis range based on initial MJD range
        # This ensures the hours axis shows the correct initial range
        callback_to_hours.execute(fig.x_range) # Pass the object the callback depends on

    # Apply final options to the combined plot, including the hook
    final_hv_plot = main_plot.opts(
        width=900,
        height=550, # Increase height slightly to accommodate the extra axis
        xlabel="Time (MJD)",
        ylabel="Count Rate (counts/s)",
        title=title_text,
        tools=['pan', 'wheel_zoom', 'box_zoom', 'reset', 'save'], # Hover added via points
        active_tools=['pan', 'wheel_zoom'],
        toolbar='above',
        show_grid=True,
        hooks=[customize_bokeh_fig], # Apply the customization hook
        # Set initial x-limits (optional, HoloViews usually infers this)
        # xlim=(df['mjd'].iloc[0], df['mjd'].iloc[-1])
    )

    # Save the plot using HoloViews saver
    html_output_file = os.path.splitext(lc_file)[0] + '_holoviews_bokeh.html'
    print(f"Saving interactive plot to: {html_output_file}")
    hv.save(final_hv_plot, html_output_file, backend='bokeh')

    # To display the plot in a browser or notebook when running the script:
    # show(final_hv_plot) # Need to import show from bokeh.io for this standalone script
    # Or just rely on hv.save opening it if the environment supports it.
    # For standalone scripts, explicitly using bokeh.io.show might be needed.
    from bokeh.io import show
    show(hv.render(final_hv_plot)) # Render HoloViews object to Bokeh model first


if __name__ == "__main__":
    # Use the command-line argument if provided, otherwise use the default file
    if len(sys.argv) > 1:
        lc_file = sys.argv[1]
    else:
        # Default file path (Update if necessary)
        lc_file = "/media/kartikmandar/HDD/Cygnusx1_lightcurves/lightcurves/30001011009/src015_bkg050-080_bin0.1/final_LC_src15_bkg50-80.lc"
        # Check if default exists, provide a message if not
        if not os.path.exists(lc_file):
             print(f"Default file not found: {lc_file}")
             print("Please provide a path to a FITS light curve file.")
             sys.exit(1) # Exit if default file is missing and none provided


    plot_lightcurve_hv(lc_file)