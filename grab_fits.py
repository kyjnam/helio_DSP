# good morning!

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

# --- Example ---
year_to_find = 2023
month_to_find = 1
day_to_find = 15

url = get_date_directory_url(year_to_find, month_to_find, day_to_find)
print(f"The URL for {month_to_find}/{year_to_find} is: {url}")

# --------------------
import requests
from bs4 import BeautifulSoup
import re

def get_files_for_day_interactive(year, month, day):
    """
    Finds available stations for a day, prompts the user to choose one,
    and returns all corresponding file URLs for that day.
    """
    # --- 1. Call your function to get the base directory URL ---

    # format the month & day to have a leading zero if needed (5 -> 05)
    month_str = str(month).zfill(2)
    day_str = str(day).zfill(2)

    base_url = "https://soleil.i4ds.ch/solarradio/data/2002-20yy_Callisto" # the base URL for the data archive
    dir_url = f"{base_url}/{year}/{month_str}/{day_str}" # create the full directory URL

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
            
    return final_urls

# --- Example of how to run the functions together ---

# Set the date you are interested in
year = 2024
month = 7
day = 20

# Run the interactive function
file_links = get_files_for_day_interactive(year, month, day)

# Print the results
if isinstance(file_links, list):
    print("\n--- Found Files ---")
    for link in file_links:
        print(link)
    print(f"\nTotal: {len(file_links)} files.")
else:
    # This will print any error messages
    print(file_links)

