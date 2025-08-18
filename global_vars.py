import datetime
import random
import os
import configparser
import subprocess
import time
import socket
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

# --- Load Settings ---
print("Loading settings from settings.ini...")
config = configparser.ConfigParser()
try:
    config.read('settings.ini')
    print("Successfully loaded settings from settings.ini")
except Exception as e:
    print(f"Error loading settings.ini: {e}")
    exit()

# --- Prepare Chrome Profile Directory ---
user_data_dir = r"C:\tmp\chrome-profile"
try:
    os.makedirs(user_data_dir, exist_ok=True)
    print(f"Chrome user profile directory ready: {user_data_dir}")
except Exception as e:
    print(f"Failed to prepare Chrome user profile directory: {e}")
    exit()

# --- Setup Chrome Options ---
print("Configuring undetected Chrome options...")
options = uc.ChromeOptions()
options.add_argument(f"--user-data-dir={user_data_dir}")
options.add_argument("--no-sandbox")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--disable-popup-blocking")
print("Chrome options configured")

# --- Launch Chrome ---
try:
    driver = uc.Chrome(options=options, headless=False)
    print("Successfully launched undetected Chrome")
except Exception as e:
    print(f"Failed to launch undetected Chrome: {e}")
    exit()

# --- Navigate to MafiaMatrix if not already there ---
try:
    current_url = driver.current_url.lower()
    if "mafiamatrix" not in current_url:
        print("Navigating to https://mafiamatrix.com/default.asp...")
        driver.get("https://mafiamatrix.com/default.asp")
        print("Successfully navigated to MafiaMatrix")
    else:
        print(f"Already on MafiaMatrix: {current_url}")
except Exception as e:
    print(f"Failed to navigate to MafiaMatrix: {e}")
    exit()

# --- Global Configurations ---
EXPLICIT_WAIT_SECONDS = random.uniform(4, 5) # This is a wait for specific elements to appear, preventing TimeoutException when elements load dynamically.
ACTION_PAUSE_SECONDS = random.uniform(0.1, 0.4) # This is an unconditional sleep between actions, primarily for pacing and simulating human interaction.
wait = WebDriverWait(driver, EXPLICIT_WAIT_SECONDS)
MIN_POLLING_INTERVAL_LOWER = 40
MIN_POLLING_INTERVAL_UPPER = 80

# Directory for game data and logs
COOLDOWN_DATA_DIR = 'game_data'
COOLDOWN_FILE = os.path.join(COOLDOWN_DATA_DIR, 'aggravated_crime_cooldowns.json')
AGGRAVATED_CRIMES_LOG_FILE = os.path.join(COOLDOWN_DATA_DIR, 'aggravated_crimes_log.txt')
FUNERAL_PARLOUR_LAST_SCAN_FILE = os.path.join(COOLDOWN_DATA_DIR, 'funeral_parlour_last_scan.txt')
YELLOW_PAGES_LAST_SCAN_FILE = os.path.join(COOLDOWN_DATA_DIR, 'yellow_pages_last_scan.txt')
AGGRAVATED_CRIME_LAST_ACTION_FILE = os.path.join(COOLDOWN_DATA_DIR, 'aggravated_crimes_last_action.txt')
ALL_DEGREES_FILE = os.path.join(COOLDOWN_DATA_DIR, 'all_degrees.json')
WEAPON_SHOP_NEXT_CHECK_FILE = os.path.join(COOLDOWN_DATA_DIR, "weapon_shop_next_check.txt")
GYM_TRAINING_FILE = os.path.join("game_data", "gym_timer.txt")
BIONICS_SHOP_NEXT_CHECK_FILE = os.path.join(COOLDOWN_DATA_DIR, "bionics_shop_next_check.txt")
POLICE_911_NEXT_POST_FILE = os.path.join(COOLDOWN_DATA_DIR, "police_911_next_post.txt")
POLICE_911_CACHE_FILE = os.path.join(COOLDOWN_DATA_DIR, "police_911_cache.json")
PENDING_FORENSICS_FILE = os.path.join(COOLDOWN_DATA_DIR, "pending_forensics.json")
FORENSICS_TRAINING_DONE_FILE = os.path.join(COOLDOWN_DATA_DIR, "forensics_training_done.json")
POLICE_TRAINING_DONE_FILE = os.path.join(COOLDOWN_DATA_DIR, "police_training_done.json")
COMBAT_TRAINING_DONE = os.path.join(COOLDOWN_DATA_DIR, "combat_training_completed.json")
CUSTOMS_TRAINING_DONE_FILE = os.path.join(COOLDOWN_DATA_DIR, "customs_training_done.json")
FIRE_TRAINING_DONE_FILE = os.path.join(COOLDOWN_DATA_DIR, "fire_training_done.json")

# Define keys for database (aggravated_crime_cooldowns.json) entries
MINOR_CRIME_COOLDOWN_KEY = 'minor_crime_cooldown'
MAJOR_CRIME_COOLDOWN_KEY = 'major_crime_cooldown'
PLAYER_HOME_CITY_KEY = 'home_city'

# Global variables for script's internal cooldowns
# Game timers
_script_earn_cooldown_end_time = datetime.datetime.now()
_script_action_cooldown_end_time = datetime.datetime.now()
_script_launder_cooldown_end_time = datetime.datetime.now()
_script_case_cooldown_end_time = datetime.datetime.now()
_script_event_cooldown_end_time = datetime.datetime.now()
# Career-specific timers
_script_bank_add_clients_cooldown_end_time = datetime.datetime.now()
_script_post_911_cooldown_end_time = datetime.datetime.min
_cases_pending_forensics = set()
# Aggravated crime timers
_script_armed_robbery_recheck_cooldown_end_time = datetime.datetime.now()
_script_torch_recheck_cooldown_end_time = datetime.datetime.now()
_script_aggravated_crime_recheck_cooldown_end_time = None
# Misc timers
_script_gym_train_cooldown_end_time = datetime.datetime.now()
_script_bionics_shop_cooldown_end_time = datetime.datetime.now()
_script_weapon_shop_cooldown_end_time = datetime.datetime.now()
_script_drug_store_cooldown_end_time = datetime.datetime.now()
jail_timers = {}

# Global variable to store the last known unread message and journal count
_last_unread_message_count = 0
_last_unread_journal_count = 0

# Global variable to store the initial URL. This will be replaced once the driver is established in Main.py
initial_game_url = None

# Global variables to store hacked player and amount for repayment
hacked_player_for_repay = None
hacked_amount_for_repay = None
hacked_successful = False

# Global variables to store pickpocketed player and amount for repayment
pickpocketed_player_for_repay = None
pickpocketed_amount_for_repay = None
pickpocket_successful = False

# Global variables to store mugging player and amount for repayment
mugging_player_for_repay = None
mugging_amount_for_repay = None
mugging_successful = False

# Global variables for Armed Robbery repayment
armed_robbery_amount_for_repay = None
armed_robbery_business_name_for_repay = None
armed_robbery_successful = False

# Global variables for Torch repayment
torch_amount_for_repay = None
torch_business_name_for_repay = None
torch_successful = False

# Global lists for businesses for repayment logic
public_businesses = [
    "Bank Tills", "Hospital", "Fire Station", "Town Hall", "Airport", "Construction Company",
]

private_businesses = {
    "Auckland": ["Bar", "Underground Auction", "Weapon Shop", "Dog Fights", "Eden Park", "Drug Store", "Tattoo Parlour"],
    "Beirut": ["Bar", "Clothing Shop", "Hotel", "Horse Racing", "Casino", "Dog Pound", "Vehicle Yard"],
    "Chicago": ["Bar", "Brothel", "Boxing", "Bionics", "Dog Pound", "Gym", "Parking Lot", "Funeral Parlour"]
}

PUBLIC_BUSINESS_OCCUPATION_MAP = {
    "funeral parlour": "Funeral Director",
    "banks tills": "Bank Manager",
    "hospital": "Hospital Director",
    "fire station": "Fire Chief",
    "town hall": "Mayor",
    "airport": "Commissioner-General",
    "construction company": "Chief Engineer"
}

# Global variables for viewing/notifying/buying stock from city shops.
ALL_WEAPON_NAMES = [
    "Baseball Bat", "Pistol", "Hand Grenade", "Assault Rifle", "Katana", "Shotgun",
    "Lightsaber", "Sniper Rifle", "Flamethrower", "Omega Death Laser", "Plasma Rifle",
    "Protection Vest", "Kevlar Bullet Proof Vest", "Riot Shield"
]
ALL_WEAPON_NAMES_LOWER = [weapon.lower() for weapon in ALL_WEAPON_NAMES]