import numpy as np
import gzip
import io
from astropy.io import fits
import os

def get_frequency_info_from_local_file(filepath):
    """
    Reads a local .fit.gz file and prints its frequency range.
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        return None

    try:
        print(f"Checking frequency info from: {filepath}...")
        
        # Open the local gzipped file in binary read mode
        with gzip.open(filepath, 'rb') as gz:
            # Read the gzipped content into a bytes buffer
            fits_content = io.BytesIO(gz.read())
            
            # Open the FITS data from the buffer
            with fits.open(fits_content) as hdul:
                header = hdul[0].header

                # Get the frequency keywords
                # NAXIS2 is frequency in these files
                freq_bins = header['NAXIS2']
                start_freq_mhz = header['CRVAL2']
                step_freq_mhz = header['CDELT2']
                
                # Calculate the end frequency
                # Freq = Start + (Bin_Index * Step)
                end_freq_mhz = start_freq_mhz + ((freq_bins - 1) * step_freq_mhz)

                print("\n--- Frequency Info ---")
                print(f"FITS Keywords:")
                print(f"  CRVAL2 (Start Freq): {start_freq_mhz} MHz")
                print(f"  CDELT2 (Step Freq):  {step_freq_mhz} MHz")
                print(f"  NAXIS2 (Num Bins):   {freq_bins}")
                
                print(f"\nCalculated Range:")
                print(f"  Bin 0 = {start_freq_mhz:.2f} MHz")
                print(f"  Bin {freq_bins - 1} = {end_freq_mhz:.2f} MHz")
                
                return start_freq_mhz, step_freq_mhz, freq_bins

    except Exception as e:
        print(f"Error checking file: {e}")
        return None

# --- Example Usage ---

# 1. SET THE PATH to your downloaded .fit.gz file
#    (Example path, change this to your actual file)
local_file = "/Users/jenny/umich/helio/dsp_25/data/ALASKA-ANCHORAGE/ALASKA-ANCHORAGE_20250720_000000_01.fit.gz"

# 2. RUN THE FUNCTION
get_frequency_info_from_local_file(local_file)