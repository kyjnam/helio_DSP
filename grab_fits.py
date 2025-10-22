# good morning!
import re
import gzip
import io
import os
import requests
import numpy as np
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from astropy.io import fits
from urllib.parse import urljoin
from tqdm import tqdm

def get_date_directory_url(year, month, day):
    """
    Constructs the URL for a specific year and month directory.

    Args:
        year (int): The year (e.g., 2024).
        month (int): The month (e.g., 5 for May).

    Returns:
        str: The formatted URL string.
    """
    # the base URL for the data archive
    base_url = "https://soleil.i4ds.ch/solarradio/data/2002-20yy_Callisto"
    
    # create the full directory URL
    directory_url = f"{base_url}/{year}/{month}/{day}"
    
    return directory_url

def get_files_for_day(year, month, day):
    """
    Finds available stations for a day, prompts the user to choose one,
    and returns all corresponding file URLs for that day.
    """
    # --- 1. Call your function to get the base directory URL ---

    # format the month & day to have a leading zero if needed (5 -> 05)
    month_str = str(month).zfill(2)
    day_str = str(day).zfill(2)

    base_url = "https://soleil.i4ds.ch/solarradio/data/2002-20yy_Callisto" # the base URL for the data archive
    dir_url = f"{base_url}/{year}/{month_str}/{day_str}/" # create the full directory URL

    date_to_match = f"{year}{month_str}{day_str}"
    

    try:
        response = requests.get(dir_url) # HTTP GET req
        response.raise_for_status() # check if the request was successful
        soup = BeautifulSoup(response.text, 'html.parser') # parse raw HTML content to bs4 soup object 
    except requests.RequestException as e: # bad URL, 404 error, etc
        return f"Error: Could not access the directory at {dir_url}. Details: {e}"

    # --- 2. Find all stations with data for the specified day ---
    station_names = set() # empty set to store the unique names of the radio stations
    files_for_day = [] # empty list to hold the filenames that match the target day
    file_pattern = re.compile(r"^([A-Z0-9\-_]+)_(\d{8})_.*\.fit\.gz$") # regex pattern to match filenames

    for link in soup.find_all('a'): # iterate over all <a> tags in the HTML (hyperlink) found by bs4 on page
        href = link.get('href') # get the destination of the link, which is stored in its 'href' attribute
        if href: # safety check to make sure the link has an href attribute before we process it
            match = file_pattern.match(href) # match re-compiled regular expression against the href filename, will return a 'match' object if the filename fits expected format
            if match: # if the filename matches the pattern
                station, date_str = match.groups()  # extract the captured parts from regex, group 1 is the station name, and group 2 is the 8-digit date string
                if date_str == date_to_match: # check if the date from the filename is the specific date we are searching for
                    station_names.add(station) # if it's the right date, add the station name to our set of unique stations
                    files_for_day.append(href) # also, add the full filename to our list of files for that day.

    if not station_names: # check if the 'station_names' set is empty after scanning all the links
        return f"No stations found with data for {year}-{month_str}-{day_str}." # if it is empty, it means no files matched our target date, function halted

    # --- 3. Prompt the user to choose a station ---
    sorted_stations = sorted(list(station_names)) # to display the stations in a predictable order, convert the 'set' to a 'list' and sort it alphabetically
    print(f"Stations with data available for {year}-{month_str}-{day_str}:") # print a header to let the user know what they are looking at.
    for i, station in enumerate(sorted_stations): # loop through the sorted list of stations, using enumerate to get both the index (i) and the station name.
        print(f"  {i + 1}: {station}")
    print("-" * 25)

    # --- 4. Get and validate user input ---
    choice = -1 # initialize the choice variable to an invalid value before the loop starts
    while True: # start an infinite loop that will only break when the user provides valid input
        try:
            user_input = input("Enter the number of the station to proceed: ")
            choice = int(user_input) # Convert the string from the user into an int, this will raise a ValueError if they type a word 
            if 1 <= choice <= len(sorted_stations): # check if the number entered is within the valid range of choices
                break
            else:
                print("Invalid number. Please try again.")
        except ValueError: # this block runs only if the int() conversion failed 
            print("That's not a number. Please try again.")

    selected_station = sorted_stations[choice - 1] # get the station name from the sorted list (subtract 1 because lists are 0-indexed)
    print(f"\nFetching files for station: {selected_station}...")

    # --- 5. Filter files for the chosen station and return full URLs ---
    final_urls = []
    for filename in files_for_day:
        if filename.startswith(f"{selected_station}_{date_to_match}"):
            final_urls.append(f"{dir_url}{filename}")
            
    return final_urls, selected_station



def files_to_numpy(station: str, year: str, month: str, day: str, time_offset: str = "000000"):
    """
    Downloads and processes e-CALLISTO files into a single NumPy array with a progress bar.
    """
    # --- Convert string inputs to integers for formatting ---
    year = int(year)
    month = int(month)
    day = int(day)

    # --- 1. Get and Filter File List ---
    base_url = "https://soleil.i4ds.ch/solarradio/data/2002-20yy_Callisto/"
    
    # CORRECTED PATH: The server directory is structured by Year/Month, not Year/Month/Day
    path = f"{year:04d}/{month:02d}/{day:02d}/"
    dir_url = urljoin(base_url, path)
    date_str_match = f"{year:04d}{month:02d}{day:02d}"

    try:
        response = requests.get(dir_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"Error: Could not access the directory at {dir_url}. Details: {e}")
        return None, None

    all_files = [urljoin(dir_url, a['href']) for a in soup.find_all('a', href=True)]
    
    station_files = [
        f for f in all_files 
        if station in f and date_str_match in f and f.endswith(".fit.gz")
    ]

    if not station_files:
        print(f"Error: No files found for station '{station}' on {year}-{month}-{day} at {dir_url}")
        return None, None

    # --- 2. Circularly Sort Files by Time ---
    def hhmmss_to_seconds(hhmmss: str) -> int:
        h, m, s = int(hhmmss[:2]), int(hhmmss[2:4]), int(hhmmss[4:6])
        return h * 3600 + m * 60 + s

    time_re = re.compile(r"_(\d{6})[i_]")
    time_file_pairs = []
    for f_url in station_files:
        match = time_re.search(f_url)
        if match:
            t = hhmmss_to_seconds(match.group(1))
            time_file_pairs.append((t, f_url))
    
    time_file_pairs.sort(key=lambda x: x[0])
    offset_sec = hhmmss_to_seconds(time_offset)
    times = [t for t, _ in time_file_pairs]
    idx = next((i for i, t in enumerate(times) if t >= offset_sec), 0)
    sorted_urls = [f for _, f in time_file_pairs[idx:]] + [f for _, f in time_file_pairs[:idx]]

    # --- 3. Process Files into NumPy arrays ---
    data_chunks = []
    overall_start_time, overall_end_time = None, None

    # The loop is now wrapped in tqdm() to create the progress bar
    for url in tqdm(sorted_urls, desc=f"Processing files for {station}"):
        try:
            r = requests.get(url, stream=True)
            r.raise_for_status()
            with gzip.GzipFile(fileobj=io.BytesIO(r.content)) as gz:
                with fits.open(io.BytesIO(gz.read())) as hdul:
                    data = hdul[0].data
                    if data.ndim == 1:
                        data = np.atleast_2d(data)
                    data_chunks.append(np.array(data, dtype=np.float32))

                    header = hdul[0].header
                    start_str = f"{header['DATE-OBS']} {header['TIME-OBS']}"
                    end_date_str, end_time_str = header['DATE-END'], header['TIME-END']
                    
                    current_start = datetime.fromisoformat(start_str.replace('/', '-'))
                    if end_time_str.startswith("24:00"):
                        current_end = datetime.fromisoformat(end_date_str.replace('/', '-')) + timedelta(days=1)
                    else:
                        current_end = datetime.fromisoformat(f"{end_date_str.replace('/', '-')} {end_time_str}")

                    if overall_start_time is None or current_start < overall_start_time:
                        overall_start_time = current_start
                    if overall_end_time is None or current_end > overall_end_time:
                        overall_end_time = current_end
        except Exception as e:
            # Using tqdm.write is better for printing during a loop
            tqdm.write(f"\nWarning: Skipping file {os.path.basename(url)} due to error: {e}")
            continue

    if not data_chunks:
        print("Error: No valid FITS data could be processed.")
        return None, None

    # --- 4. Standardize Dimensions and Concatenate ---
    max_freq_bins = max(chunk.shape[0] for chunk in data_chunks)
    
    padded_chunks = []
    for chunk in data_chunks:
        if chunk.shape[0] < max_freq_bins:
            padding_height = max_freq_bins - chunk.shape[0]
            pad_block = np.full((padding_height, chunk.shape[1]), np.nan, dtype=np.float32)
            padded_chunk = np.vstack([chunk, pad_block])
            padded_chunks.append(padded_chunk)
        else:
            padded_chunks.append(chunk)

    full_spectrogram = np.concatenate(padded_chunks, axis=1)
    full_spectrogram = np.flipud(full_spectrogram)

    metadata = {
        "station": station,
        "date": f"{year}-{month:02d}-{day:02d}",
        "start_time": overall_start_time,
        "end_time": overall_end_time,
        "files_processed": len(data_chunks),
        "shape": full_spectrogram.shape,
        "frequency_bins": full_spectrogram.shape[0],
        "time_steps": full_spectrogram.shape[1]
    }
    
    return full_spectrogram, metadata

import numpy as np
import os # Make sure os is imported

def save_numpy_array(data_array, metadata):
    """
    Saves a NumPy array to a .npy file with a descriptive name.

    Args:
        data_array (np.ndarray): The final aggregated NumPy array.
        metadata (dict): The summary metadata dictionary.
    """
    # Create an organized folder path, e.g., "data/ALASKA-ANCHORAGE/"
    save_path = os.path.join("data", metadata['station'])
    os.makedirs(save_path, exist_ok=True) # Ensure the directory exists

    # Construct a descriptive filename, e.g., "ALASKA-ANCHORAGE_2024-07-20.npy"
    filename = f"{metadata['station']}_{metadata['date']}.npy"
    full_filepath = os.path.join(save_path, filename)

    try:
        print(f"\nSaving data to {full_filepath}...")
        # Use NumPy's save function for efficient, binary storage
        np.save(full_filepath, data_array)
        print("Save complete.")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == "__main__":
    # Set the date you are interested in
    year = 2024
    month = 7
    day = 20

    # url = get_date_directory_url(year, month, day)
    # print(f"The URL for {year}/{month}/{day} is: {url}")

    file_links, station_name = get_files_for_day(year, month, day)

    # Print the results
    if isinstance(file_links, list):
        # Call the processing function as before
        final_numpy_array, summary_metadata = files_to_numpy(station_name, year, month, day)

        # If processing was successful, print the summary and save the file
        if final_numpy_array is not None:
            print("\n--- Processing Complete ---")
            print(f"Station: {summary_metadata['station']}")
            print(f"Date: {summary_metadata['date']}")
            print(f"Final array shape: {final_numpy_array.shape}")
            
            # --- NEW: Call the save function here ---
            save_numpy_array(final_numpy_array, summary_metadata)
    else:
        # This will print any error messages
        print(file_links)

