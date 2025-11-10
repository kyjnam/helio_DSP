"""
===============================================================================
File: fast_robust_clip.py
Description:
This script detects solar bursts in a 2D spectrogram using a highly 
efficient "bin and filter" method.

Algorithm:
1.  **Bin:** A large 2D spectrogram is binned down into a much smaller
    array (e.g., 200 freqs -> 40, 270k time steps -> 14k). This is
    done by averaging "super-pixels" (e.g., 5 freqs x 19 time steps).
    This step is extremely fast and preserves the signal of bursts.
2.  **Filter:** The fast and robust Median Absolute Deviation (MAD)
    filter is run on this new *small* array. This is also extremely fast.

This method is >100x faster than running the filter on the original
full-resolution data.
===============================================================================
"""

import numpy as np
from scipy.ndimage import median_filter
import os
import sys

def bin_spectrogram(array, freq_factor, time_factor):
    """
    Downsamples a 2D array by averaging blocks of (freq_factor, time_factor).
    
    Args:
        array (np.ndarray): The 2D (frequency, time) data.
        freq_factor (int): How many frequency bins to average together.
        time_factor (int): How many time steps to average together.

    Returns:
        np.ndarray: The new, smaller, binned array.
    """
    print(f"Original shape: {array.shape}")
    print(f"Binning by: ({freq_factor} freqs, {time_factor} time steps)")
    
    # --- 1. Trim Frequency Axis ---
    freq_trim = array.shape[0] % freq_factor
    if freq_trim > 0:
        array = array[:-freq_trim, :]
        
    # --- 2. Trim Time Axis ---
    time_trim = array.shape[1] % time_factor
    if time_trim > 0:
        array = array[:, :-time_trim]
        
    # --- 3. Reshape and Bin ---
    # (freq, time) -> (freq_chunks, freq_factor, time_chunks, time_factor)
    binned_shape = (array.shape[0] // freq_factor, freq_factor, 
                    array.shape[1] // time_factor, time_factor)
    
    # Reshape and then average over both the new axes (1 and 3)
    binned_array = array.reshape(binned_shape).mean(axis=(1, 3))
    
    print(f"New binned shape: {binned_array.shape}")
    return binned_array

def apply_robust_clip(spectrogram, window_size, sigma_threshold=3):
    """
    Applies a robust median clip (MAD) to the spectrogram.
    This version is fast and expects a 2D array.
    """
    if window_size % 2 == 0:
        raise ValueError("window_size must be an odd number.")
        
    print(f"Calculating rolling median with window size {window_size}...")
    # This optimized 2D filter is much faster than a Python loop
    rolling_median = median_filter(
        spectrogram, 
        size=(1, window_size), 
        mode='reflect'
    )
    
    print("Calculating rolling MAD...")
    difference = np.abs(spectrogram - rolling_median)
    
    rolling_mad = median_filter(
        difference, 
        size=(1, window_size), 
        mode='reflect'
    )
    
    print("Identifying outliers...")
    # 1.4826 makes MAD equivalent to 1 standard deviation
    sigma_equivalent = 1.4826 * rolling_mad
    sigma_equivalent[sigma_equivalent < 1e-6] = 1e-6 # Avoid div by zero
    
    is_outlier = difference > (sigma_threshold * sigma_equivalent)
    
    print("Done.")
    return is_outlier

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    
    # --- 1. Parameters to Tune ---
    
    # Path to your original, full-resolution data
    INPUT_FILE = "data/ALASKA-ANCHORAGE/ALASKA-ANCHORAGE_2024-07-20.npy"
    
    # binning 
    FREQ_BIN_FACTOR = 5  # group 5 frequency channels (200 -> 40)
    TIME_BIN_FACTOR = 10 
    """
    given 190 steps/min
    bin size    second(s) per bin   estimated runtime
    ========    =================   =================
    bin=3       ~1 second           very slow (~10-15 min)
    bin=10      ~3 seconds	        slow (~2-3 min)
    bin=19	    ~6 seconds	        fast (~20-30 seconds)
    bin=38      ~12 seconds         very fast (~10 seconds)
    """

    # filter settings
    WINDOW_MINUTES = 5.0 # the filter window size, in minutes
    SIGMA_THRESHOLD = 3  # n of n-sigma threshold
    
    # we assume 190 steps/min based on 951 steps / 5 min
    # (if this is wrong, change this number)
    STEPS_PER_MINUTE = 190 
    
    # calculate new window size
    # Convert 5-minute window to steps in the *binned* data
    original_window_steps = int(WINDOW_MINUTES * STEPS_PER_MINUTE)
    NEW_WINDOW_SIZE = int(original_window_steps / TIME_BIN_FACTOR)
    
    # ensure window is an odd number 
    # (because we need it to be symmetrical to have a center pixel)
    # (in order to look at N bins left and N bins right)
    if NEW_WINDOW_SIZE % 2 == 0:
        NEW_WINDOW_SIZE += 1
        
    print(f"<3-Sigma Burst Detector>")
    print(f"  Original window: {original_window_steps} steps")
    print(f"  Time bin factor: {TIME_BIN_FACTOR}")
    print(f"  New binned window: {NEW_WINDOW_SIZE} steps")

    # --- 3. Load Data ---
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file not found at {INPUT_FILE}")
        sys.exit(1)
        
    print(f"\nLoading data from {INPUT_FILE}...")
    spectrogram_data = np.load(INPUT_FILE)

    # --- 4. Bin Data ---
    binned_spectrogram = bin_spectrogram(spectrogram_data, FREQ_BIN_FACTOR, TIME_BIN_FACTOR)

    # --- 5. Apply Filter ---
    # We run the filter on the *small, binned* array
    outlier_mask = apply_robust_clip(binned_spectrogram, NEW_WINDOW_SIZE, SIGMA_THRESHOLD)

    # --- 6. Show Results ---
    total_points = binned_spectrogram.size
    total_outliers = np.sum(outlier_mask)
    percent_outliers = 100 * total_outliers / total_points

    print("\n--- Results (on binned data) ---")
    print(f"Total data points: {total_points}")
    print(f"Outliers detected: {total_outliers} ({percent_outliers:.2f}%)")

    # --- 7. Save Output Files ---
    print("\nSaving output files...")
    save_dir = os.path.dirname(INPUT_FILE)
    base_name = os.path.splitext(os.path.basename(INPUT_FILE))[0]

    # Add a suffix to show these are binned
    suffix = f"_binned_{FREQ_BIN_FACTOR}x{TIME_BIN_FACTOR}"

    # Define all output paths
    binned_path = os.path.join(save_dir, f"{base_name}{suffix}.npy")
    cleaned_path = os.path.join(save_dir, f"{base_name}{suffix}_cleaned.npy")
    mask_path = os.path.join(save_dir, f"{base_name}{suffix}_mask.npy")
    burst_path = os.path.join(save_dir, f"{base_name}{suffix}_bursts.npy")

    try:
        # Create the 'cleaned' and 'bursts' arrays from the binned data
        cleaned_data = np.copy(binned_spectrogram)
        cleaned_data[outlier_mask] = np.nan

        burst_data = np.full_like(binned_spectrogram, np.nan)
        burst_data[outlier_mask] = binned_spectrogram[outlier_mask]
        
        # save all four files
        print(f"Saving binned spectrogram to {binned_path}...")
        np.save(binned_path, binned_spectrogram)
        """
        new binned spectrogram 
        """
        
        print(f"Saving cleaned data to {cleaned_path}...")
        np.save(cleaned_path, cleaned_data)
        """
        burst detection removed noise display only
        for purposes of studying the quiet data
        T replaced with NaN
        """
        
        print(f"Saving outlier mask to {mask_path}...")
        np.save(mask_path, outlier_mask)
        """
        if above n-sigma, highlighted (T/F 1/0 binary map)
        """

        print(f"Saving burst data to {burst_path}...")
        np.save(burst_path, burst_data)
        """
        burst detection display only
        """

        print("\nFiles saved successfully")
    except Exception as e:
        print(f"Error saving files: {e}")
