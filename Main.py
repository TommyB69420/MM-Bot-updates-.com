import datetime
import random
import time

from selenium.common import StaleElementReferenceException
from selenium.webdriver.common.by import By
import global_vars
from agg_crimes import execute_aggravated_crime_logic, execute_yellow_pages_scan, execute_funeral_parlour_scan
from earn_functions import execute_earns_logic
from occupations import execute_judge_casework_logic, execute_lawyer_casework_logic, execute_medical_casework_logic, \
    execute_community_services_logic, execute_engineering_casework_logic, execute_launder_logic, \
    execute_manufacture_drugs_logic, execute_banker_laundering, execute_banker_add_clients, execute_fire_work_logic, \
    execute_fire_duties_logic
from helper_functions import _get_element_text, _find_and_send_keys, _find_and_click, is_player_in_jail
from database_functions import init_local_db
from timer_functions import get_all_active_game_timers
from comms_journals import send_discord_notification, get_unread_message_count, read_and_send_new_messages, get_unread_journal_count, process_unread_journal_entries
from misc_functions import study_degrees, do_events, check_weapon_shop, check_drug_store, jail_work, \
    clean_money_on_hand_logic, gym_training, check_bionics_shop

# --- Initialize Local Cooldown Database ---
if not init_local_db():
    exit()

# Capture the initial state
global_vars.initial_game_url = global_vars.driver.current_url

# --- Initial Player Data Fetch ---
def fetch_initial_player_data():
    """Fetches and prints initial player data from the game UI."""
    player_data = {}
    data_elements = {
        "Character Name": {"xpath": "//div[@id='nav_right']/div[normalize-space(text())='Name']/following-sibling::div[1]/a", "is_money": False},
        "Rank": {"xpath": "//div[@id='nav_right']/div[normalize-space(text())='Rank']/following-sibling::div[1]", "is_money": False},
        "Occupation": {"xpath": "//div[@id='nav_right']//div[@id='display_top'][normalize-space(text())='Occupation']/following-sibling::div[@id='display_end']", "is_money": False},
        "Clean Money": {"xpath": "//div[@id='nav_right']//form[contains(., '$')]", "is_money": True},
        "Dirty Money": {"xpath": "//div[@id='nav_right']/div[normalize-space(text())='Dirty money']/following-sibling::div[1]", "is_money": True},
        "Location": {"xpath": "//div[@id='nav_right']/div[contains(normalize-space(text()), 'Location')]/following-sibling::div[1]", "is_money": False, "strip_label": "Location:"},
        "Home City": {"xpath": "//div[contains(text(), 'Home City')]/following-sibling::div[1]", "is_money": False, "strip_label": "Home city:"}
    }

    for key, details in data_elements.items():
        text_content = _get_element_text(By.XPATH, details["xpath"])
        if text_content:
            if details.get("strip_label"):
                text_content = text_content.replace(details["strip_label"], "").strip()
            if details["is_money"]:
                player_data[key] = int(''.join(filter(str.isdigit, text_content)))
            else:
                player_data[key] = text_content
        else:
            print(f"Warning: Could not fetch {key}.")
            player_data[key] = None
    return player_data

def check_for_logout_and_login():
    """
    Checks if the bot is logged out (on the default.asp page) and performs login if necessary.
    Returns True if a login was performed, False otherwise.
    """
    if "default.asp" in global_vars.driver.current_url.lower():
        print("Detected logout to default.asp. Attempting to log in...")
        send_discord_notification("Logged out - Attempting to log in.")

        username = global_vars.config['Login Credentials'].get('UserName')
        password = global_vars.config['Login Credentials'].get('Password')

        if not username or not password:
            print("ERROR: Login credentials (UserName or Password) not found in settings.ini.")
            send_discord_notification("Login credentials missing. Cannot log in.")
            return False

        if not _find_and_send_keys(By.XPATH, "//form[@id='loginForm']//input[@id='email']", username):
            print("FAILED: Could not enter username.")
            send_discord_notification("Failed to enter username during login.")
            return False

        if not _find_and_send_keys(By.XPATH, "//input[@id='pass']", password):
            print("FAILED: Could not enter password.")
            send_discord_notification("Failed to enter password during login.")
            return False

        if not _find_and_click(By.XPATH, "//button[normalize-space()='Sign in']", pause=global_vars.ACTION_PAUSE_SECONDS * 3):
            print("FAILED: Could not click Sign In button.")
            send_discord_notification("Failed to click Sign In button during login.")
            return False

        if not _find_and_click(By.XPATH, "//a[@title='Log in with the character!|Get inside the world of MafiaMatrix!']", pause=global_vars.ACTION_PAUSE_SECONDS * 5):
            print("FAILED: Could not click Play Now button.")
            send_discord_notification("Failed to click Play Now button after login.")
            return False

        print("Successfully logged in.")
        send_discord_notification("Logged In Successfully!")
        return True
    return False

def get_enabled_configs(location):
    """
    Reads the settings from settings.ini to determine what functions to turn on
    """
    config = global_vars.config
    return {
    "do_earns_enabled": config.getboolean('Earns Settings', 'DoEarns', fallback=False),
    "do_community_services_enabled": config.getboolean('Actions Settings', 'CommunityService', fallback=False),
    "mins_between_aggs": config.getint('Misc', 'MinsBetweenAggs', fallback=30),
    "do_hack_enabled": config.getboolean('Hack', 'DoHack', fallback=False),
    "do_pickpocket_enabled": config.getboolean('PickPocket', 'DoPickPocket', fallback=False),
    "do_mugging_enabled": config.getboolean('Mugging', 'DoMugging', fallback=False),
    "do_armed_robbery_enabled": config.getboolean('Armed Robbery', 'DoArmedRobbery', fallback=False),
    "do_torch_enabled": config.getboolean('Torch', 'DoTorch', fallback=False),
    "do_judge_cases_enabled": config.getboolean('Judge', 'Do_Cases', fallback=False),
    "do_launders_enabled": config.getboolean('Launder', 'DoLaunders', fallback=False),
    "do_manufacture_drugs_enabled": config.getboolean('Actions Settings', 'ManufactureDrugs', fallback=False),
    "do_university_degrees_enabled": config.getboolean('Actions Settings', 'StudyDegrees', fallback=False),
    "do_event_enabled": config.getboolean('Misc', 'DoEvent', fallback=False),
    "do_weapon_shop_check_enabled": config.getboolean('Weapon Shop', 'CheckWeaponShop', fallback=False) and any("Weapon Shop" in biz_list for city, biz_list in global_vars.private_businesses.items() if city == location),
    "do_drug_store_enabled": config.getboolean('Drug Store', 'CheckDrugStore', fallback=False) and any("Drug Store" in biz_list for city, biz_list in global_vars.private_businesses.items() if city == location),
    "do_firefighter_duties_enabled": config.getboolean('Fire', 'DoFireDuties', fallback=False),
    "do_gym_trains_enabled": config.getboolean('Misc', 'GymTrains', fallback=False) and any("Gym" in biz_list for city, biz_list in global_vars.private_businesses.items() if city == location),
    "do_bionics_shop_check_enabled": config.getboolean('Bionics Shop', 'CheckBionicsShop', fallback=False) and any ("Bionics" in biz_list for city, biz_list in global_vars.private_businesses.items() if city == location)
}

def _determine_sleep_duration(action_performed_in_cycle, timers_data):
    """
    Determines the optimal sleep duration based on enabled activities and cooldown timers.
    """
    print("\n--- Calculating Sleep Duration ---")

    # Extract static context
    occupation = timers_data.get('occupation')
    location = timers_data.get('location')

    # Extract timers
    get_timer = lambda key: timers_data.get(key, float('inf'))
    earn = get_timer('earn_time_remaining')
    action = get_timer('action_time_remaining')
    launder = get_timer('launder_time_remaining')
    case = get_timer('case_time_remaining')
    event = get_timer('event_time_remaining')
    bank_add = get_timer('bank_add_clients_time_remaining')
    aggro = get_timer('aggravated_crime_time_remaining')
    rob_recheck = get_timer('armed_robbery_recheck_time_remaining')
    torch_recheck = get_timer('torch_recheck_time_remaining')
    yps = get_timer('yellow_pages_scan_time_remaining')
    fps = get_timer('funeral_parlour_scan_time_remaining')
    weapon = get_timer('check_weapon_shop_time_remaining')
    drug = get_timer('check_drug_store_time_remaining')
    gym = get_timer('gym_trains_time_remaining')
    bionics = get_timer('check_bionics_store_time_remaining')

    cfg = global_vars.config
    businesses = global_vars.private_businesses

    active = []

    # Add timers if enabled
    if cfg.getboolean('Earns Settings', 'DoEarns', fallback=False):
        active.append(('Earn', earn))
    if cfg.getboolean('Actions Settings', 'CommunityService', fallback=False):
        active.append(('Community Service', action))
    if cfg.getboolean('Actions Settings', 'StudyDegrees', fallback=False):
        active.append(('Study Degree', action))
    if cfg.getboolean('Actions Settings', 'ManufactureDrugs', fallback=False):
        active.append(('Manufacture Drugs', action))
    if cfg.getboolean('Misc', 'DoEvent', fallback=False):
        active.append(('Event', event))
    if cfg.getboolean('Fire', 'DoFireDuties', fallback=False):
        active.append(('Firefighter Duties', action))
    if cfg.getboolean('Launder', 'DoLaunders', fallback=False):
        active.append(('Launder', launder))

    # Aggravated Crime logic
    if any(cfg.getboolean(section, f'Do{key}', fallback=False) for section, key in [('Hack', 'Hack'), ('PickPocket', 'PickPocket'), ('Mugging', 'Mugging')]):
        active.append(('Aggravated Crime (General)', aggro))
    elif cfg.getboolean('Armed Robbery', 'DoArmedRobbery', fallback=False):
        if aggro > global_vars.ACTION_PAUSE_SECONDS:
            active.append(('Armed Robbery (General)', aggro))
        else:
            active += [('Armed Robbery (Re-check)', rob_recheck), ('Armed Robbery (General)', aggro)]
    elif cfg.getboolean('Torch', 'DoTorch', fallback=False):
        if aggro > global_vars.ACTION_PAUSE_SECONDS:
            active.append(('Torch (General)', aggro))
        else:
            active += [('Torch (Re-check)', torch_recheck), ('Torch (General)', aggro)]

    # Casework based on occupation
    if cfg.getboolean('Judge', 'Do_Cases', fallback=False):
        active.append(('Judge Casework', case))
    if occupation == "Lawyer":
        active.append(('Lawyer Casework', case))
    if occupation in ("Mechanic", "Technician", "Engineer", "Chief Engineer"):
        active.append(('Engineering Casework', case))
    if occupation in ("Volunteer Fire Fighter", "Fire Fighter", "Fire Chief"):
        active.append(('FireFighter Casework', case))
    if occupation in ("Nurse", "Doctor", "Surgeon", "Hospital Director"):
        active.append(('Medical Casework', case))
    if occupation in ("Bank Teller", "Loan Officer", "Bank Manager"):
        active.append(('Bank Casework', case))
        active.append(('Bank add clients', bank_add))

    if cfg.getboolean('Weapon Shop', 'CheckWeaponShop', fallback=False) and any("Weapon Shop" in b for c, b in businesses.items() if c == location):
        active.append(('Check Weapon Shop', weapon))
    if cfg.getboolean('Drug Store', 'CheckDrugStore', fallback=False) and any("Drug Store" in b for c, b in businesses.items() if c == location):
        active.append(('Check Drug Store', drug))
    if cfg.getboolean('Misc', 'GymTrains', fallback=False) and any("Gym" in b for c, b in businesses.items() if c == location):
        active.append(('Gym Trains', gym))
    if cfg.getboolean('Bionics Shop', 'CheckBionicsShop', fallback=False) and any("Bionics" in b for c, b in businesses.items() if c == location):
        active.append(('Check Bionics Shop', bionics))

    active.append(('Yellow Pages Scan', yps))
    active.append(('Funeral Parlour Scan', fps))

    print("\n--- Timers Under Consideration for Sleep Duration ---")
    for name, timer_val in active:
        print(f"  {name}: {timer_val:.2f} seconds")
    print("----------------------------------------------------")

    # Sleep logic
    valid = [t for _, t in active if t is not None and t != float('inf')]
    sleep_reason = "No active timers found."
    sleep_duration = random.randint(global_vars.MIN_POLLING_INTERVAL_LOWER, global_vars.MIN_POLLING_INTERVAL_UPPER)

    if valid:
        ready = [t for t in valid if t <= global_vars.ACTION_PAUSE_SECONDS]
        if ready:
            min_ready = min(ready)
            sleep_reason = "One or more enabled tasks are immediately ready (timer <= 0)."
            sleep_duration = global_vars.ACTION_PAUSE_SECONDS if min_ready <= 0 else min_ready
        else:
            upcoming = [t for t in valid if t > global_vars.ACTION_PAUSE_SECONDS]
            if upcoming:
                next_time = min(upcoming)
                sleep_reason = f"Waiting for next task in {next_time:.2f}s."
                sleep_duration = max(global_vars.ACTION_PAUSE_SECONDS, next_time)
            else:
                sleep_reason = "All enabled timers are infinite or already processed."

    if not action_performed_in_cycle and sleep_duration > global_vars.MIN_POLLING_INTERVAL_UPPER:
        sleep_duration = random.randint(global_vars.MIN_POLLING_INTERVAL_LOWER, global_vars.MIN_POLLING_INTERVAL_UPPER)
    if action_performed_in_cycle:
        sleep_duration = global_vars.ACTION_PAUSE_SECONDS
        sleep_reason = "An action was just performed in this cycle, re-evaluating soon."

    print(f"Decision: {sleep_reason}")
    return sleep_duration


    # --- SCRIPT CHECK DETECTION & LOGOUT/LOGIN ---
def perform_critical_checks(character_name):
    """
    Fast, non-blocking check for logout and script check pages.
    Uses instant checks with no WebDriverWait.
    """
    # Check for logout
    if "default.asp" in global_vars.driver.current_url.lower():
        print("Logged out. Attempting login...")
        if check_for_logout_and_login():
            global_vars.initial_game_url = global_vars.driver.current_url
            return True  # Restart main loop after re-login

    # --- Script Check Detection ---
    current_url = global_vars.driver.current_url.lower()
    script_check_found = False

    # Fastest check: by URL
    if "test.asp" in current_url or "activity" in current_url or "test" in current_url:
        script_check_found = True
    else:
        # Fast DOM probe (no wait), safely handle stale elements
        try:
            elements = global_vars.driver.find_elements(By.XPATH, "//font")
            for e in elements:
                try:
                    text = e.text.lower()
                    if "first" in text and "characters" in text:
                        script_check_found = True
                        break
                except StaleElementReferenceException:
                    print("Stale element during fast script check DOM probe.")
                except Exception as inner_e:
                    print(f"Unexpected error while probing for script check: {inner_e}")
        except Exception as e:
            print(f"Error during fast script check DOM probe: {e}")

    # If a script is check found — alert and terminate
    if script_check_found:
        discord_message_content = f"{character_name}@here ADMIN SCRIPT CHECK AARRHHH FUUCCCKK"
        send_discord_notification(discord_message_content)
        exit()

    return False  # No critical issues

while True:
    if perform_critical_checks("UNKNOWN"):
        continue

    # Re-read settings.ini in case they've changed
    global_vars.config.read('settings.ini') # Re-read config in case it's changed
    current_time = datetime.datetime.now()
    action_performed_in_cycle = False

    # --- Fetch all timers first ---
    all_timers = get_all_active_game_timers()
    global_vars.jail_timers = all_timers  # Store for jail logic access

    # --- Jail Check ---
    if is_player_in_jail():
        print("Player is in jail. Entering jail work loop...")

        while is_player_in_jail():
            global_vars.jail_timers = get_all_active_game_timers()
            jail_work()
            time.sleep(2)  # Tighter loop for responsiveness

        print("Player released from jail. Resuming normal script.")
        continue  # Skip the rest of the main loop for this cycle

    global_vars.driver.refresh()
    time.sleep(2)

    # Now fetch the player data
    initial_player_data = fetch_initial_player_data()
    character_name = initial_player_data.get("Character Name", "UNKNOWN")

    # Critical checks are performed throughout the loop to ensure script checks and log-outs are captured quickly
    if perform_critical_checks(character_name):
        continue

    # Re-fetch player data after potential navigation or actions
    initial_player_data = fetch_initial_player_data()
    character_name = initial_player_data.get("Character Name", character_name)
    rank = initial_player_data.get("Rank")
    occupation = initial_player_data.get("Occupation")
    clean_money = initial_player_data.get("Clean Money")
    dirty_money = initial_player_data.get("Dirty Money")
    location = initial_player_data.get("Location")
    home_city = initial_player_data.get("Home City")
    print(f"Current Character: {character_name}, Rank: {rank}, Occupation: {occupation}, Clean Money: {clean_money}, Dirty Money: {dirty_money}, Location: {location}. Home City: {home_city}")

    # Read enabled configs.
    enabled_configs = get_enabled_configs(location)

    if perform_critical_checks(character_name):
        continue

    # --- Fetch all game timers AFTER player data and BEFORE action logic ---
    all_timers = get_all_active_game_timers()

    if perform_critical_checks(character_name):
        continue

    # Extract timers for easier use in conditions (from the freshly fetched all_timers)
    earn_time_remaining = all_timers.get('earn_time_remaining', float('inf'))
    action_time_remaining = all_timers.get('action_time_remaining', float('inf'))
    case_time_remaining = all_timers.get('case_time_remaining', float('inf'))
    launder_time_remaining = all_timers.get('launder_time_remaining', float('inf'))
    event_time_remaining = all_timers.get('event_time_remaining', float('inf'))

    aggravated_crime_time_remaining = all_timers.get('aggravated_crime_time_remaining', float('inf'))
    armed_robbery_recheck_time_remaining = (getattr(global_vars, "_script_armed_robbery_recheck_cooldown_end_time", datetime.datetime.min) - datetime.datetime.now()).total_seconds()
    torch_recheck_time_remaining = (getattr(global_vars, "_script_torch_recheck_cooldown_end_time", datetime.datetime.min) - datetime.datetime.now()).total_seconds()

    yellow_pages_scan_time_remaining = all_timers.get('yellow_pages_scan_time_remaining', float('inf'))
    funeral_parlour_scan_time_remaining = all_timers.get('funeral_parlour_scan_time_remaining', float('inf'))

    check_weapon_shop_time_remaining = all_timers.get('check_weapon_shop_time_remaining', float('inf'))
    check_drug_store_time_remaining = all_timers.get('check_drug_store_time_remaining', float('inf'))
    gym_trains_time_remaining = all_timers.get('gym_trains_time_remaining', float('inf'))
    check_bionics_store_time_remaining = all_timers.get('check_bionics_store_time_remaining', float('inf'))

    if perform_critical_checks(character_name):
        continue

    # Earn logic
    if enabled_configs['do_earns_enabled'] and earn_time_remaining <= 0:
        print(f"Earn timer ({earn_time_remaining:.2f}s) is ready. Attempting earn.")
        if execute_earns_logic():
            action_performed_in_cycle = True
        else:
            print("Earns logic did not perform an action or failed. Setting fallback cooldown.")

    if perform_critical_checks(character_name):
        continue

    # Yellow pages scan logic
    if yellow_pages_scan_time_remaining <= 0:
        print(f"Yellow Pages Scan timer ({yellow_pages_scan_time_remaining:.2f}s) is ready. Attempting scan.")
        if execute_yellow_pages_scan():
            action_performed_in_cycle = True
        else:
            print("Yellow Pages Scan logic did not perform an action or failed. No immediate cooldown from here.")

    if perform_critical_checks(character_name):
        continue

    # Funeral Parlour scan logic
    if funeral_parlour_scan_time_remaining <= 0:
        print(f"Funeral Parlour Scan timer ({funeral_parlour_scan_time_remaining:.2f}s) is ready. Attempting scan.")
        if execute_funeral_parlour_scan():
            action_performed_in_cycle = True
        else:
            print("Funeral Parlour Scan logic did not perform an action or failed. No immediate cooldown from here.")

    if perform_critical_checks(character_name):
        continue

    # Community Service Logic
    if enabled_configs['do_community_services_enabled'] and action_time_remaining <= 0:
        print(f"Community Service timer ({action_time_remaining:.2f}s) is ready. Attempting CS.")
        if execute_community_services_logic(initial_player_data):
            action_performed_in_cycle = True
        else:
            print("Community Service logic did not perform an action or failed. Setting fallback cooldown.")

    if perform_critical_checks(character_name):
        continue

    # Firefighter duties Logic
    if enabled_configs['do_firefighter_duties_enabled'] and action_time_remaining <= 0:
        print(f"Firefighter duties timer ({action_time_remaining:.2f}s) is ready. Attempting to do duties   .")
        if execute_fire_duties_logic():
            action_performed_in_cycle = True
        else:
            print("Firefighter duties logic did not perform an action or failed. Setting fallback cooldown.")

    if perform_critical_checks(character_name):
        continue

    # Study Degrees Logic
    if enabled_configs['do_university_degrees_enabled'] and location == home_city and action_time_remaining <= 0:
        print(f"Study Degree timer ({action_time_remaining:.2f}s) is ready. Attempting Study Degree.")
        if study_degrees():
            action_performed_in_cycle = True
        else:
            print("Study Degree logic did not perform an action or failed. Setting fallback cooldown.")

    if perform_critical_checks(character_name):
        continue

    # Drug manufacturing logic
    if enabled_configs['do_manufacture_drugs_enabled'] and occupation == "Gangster":
        if action_time_remaining <= 0:
            print(f"Manufacture Drugs timer ({action_time_remaining:.2f}s) is ready. Attempting manufacture.")
            if execute_manufacture_drugs_logic(initial_player_data):
                action_performed_in_cycle = True
            else:
                print("Manufacture Drugs logic did not perform an action or failed. Setting fallback cooldown.")

    if perform_critical_checks(character_name):
        continue

    # Do Aggravated Crime Logic
    should_attempt_aggravated_crime = False

    # Check if any aggravated crime setting is enabled
    if any([
        enabled_configs['do_hack_enabled'],
        enabled_configs['do_pickpocket_enabled'],
        enabled_configs['do_mugging_enabled'],
        enabled_configs['do_armed_robbery_enabled'],
        enabled_configs['do_torch_enabled']
    ]):
        # Hack / Pickpocket / Mugging — check general timer only
        if any([
            enabled_configs['do_hack_enabled'],
            enabled_configs['do_pickpocket_enabled'],
            enabled_configs['do_mugging_enabled']
        ]) and aggravated_crime_time_remaining <= 0:
            should_attempt_aggravated_crime = True
            print(f"Aggravated Crime (Hack/Pickpocket/Mugging) timer ({aggravated_crime_time_remaining:.2f}s) is ready. Attempting crime.")

        # Armed Robbery — needs general + recheck timer
        if enabled_configs['do_armed_robbery_enabled']:
            if aggravated_crime_time_remaining <= 0 and armed_robbery_recheck_time_remaining <= 0:
                should_attempt_aggravated_crime = True
                print("Armed Robbery timers are ready. Attempting crime.")

        # Torch — needs general + recheck timer
        if enabled_configs['do_torch_enabled']:
            if aggravated_crime_time_remaining <= 0 and torch_recheck_time_remaining <= 0:
                should_attempt_aggravated_crime = True
                print("Torch timers are ready. Attempting crime.")

        # Execute if any path above marked it ready
        if should_attempt_aggravated_crime:
            if execute_aggravated_crime_logic(initial_player_data):
                action_performed_in_cycle = True
            else:
                print("Aggravated Crime logic did not perform an action or failed. No immediate cooldown from here.")

    if perform_critical_checks(character_name):
        continue

    # Deposit and withdraw excess money logic
    if clean_money_on_hand_logic(initial_player_data):
        action_performed_in_cycle = True
    else:
        print("Checking clean money on hand - Amount is within limits.")

    if perform_critical_checks(character_name):
        continue

    # Do event logic
    if enabled_configs['do_event_enabled'] and event_time_remaining <= 0:
        print(f"Event timer ({event_time_remaining:.2f}s) is ready. Attempting the event.")
        if do_events():
            action_performed_in_cycle = True
        else:
            print("Event logic did not perform an action or failed.")

    if perform_critical_checks(character_name):
        continue

    # Do Weapon Shop Logic
    if enabled_configs['do_weapon_shop_check_enabled'] and check_weapon_shop_time_remaining <= 0:
        print(f"Weapon Shop timer ({check_weapon_shop_time_remaining:.2f}s) is ready. Attempting check now.")
        if check_weapon_shop(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Do Bionics Shop Logic
    if enabled_configs['do_bionics_shop_check_enabled'] and check_bionics_store_time_remaining <= 0:
        print(f"Bionics Shop timer ({check_bionics_store_time_remaining:.2f}s) is ready. Attempting check now.")
        if check_bionics_shop(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Do Drug Store Check Logic
    if enabled_configs['do_drug_store_enabled'] and check_drug_store_time_remaining <= 0:
        print(f"Drug Store timer ({check_drug_store_time_remaining:.2f}s) is ready. Attempting to check Drug Store.")
        if check_drug_store(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Do Gym Train Logic
    if enabled_configs['do_gym_trains_enabled'] and gym_trains_time_remaining <= 0:
        print(f"Gym trains timer ({gym_trains_time_remaining:.2f}s) is ready. Attempting Gym trains.")
        if gym_training():
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Judge Casework Logic
    if enabled_configs['do_judge_cases_enabled'] and occupation in ["Judge", "Supreme Court Judge"] and location == home_city and case_time_remaining <= 0:
        print(f"Judge Casework timer ({case_time_remaining:.2f}s) is ready. Attempting judge cases.")
        if execute_judge_casework_logic(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Do Lawyer case work logic
    if occupation in "Lawyer" and case_time_remaining <= 0:
        print(f"Lawyer Casework timer ({case_time_remaining:.2f}s) is ready. Attempting lawyer cases.")
        if execute_lawyer_casework_logic():
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Medical Casework Logic
    if occupation in ("Nurse", "Doctor", "Surgeon", "Hospital Director") and case_time_remaining <= 0:
        print(f"Medical Casework timer ({case_time_remaining:.2f}s) is ready. Attempting medical cases.")
        if execute_medical_casework_logic(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Firefighter Casework Logic
    if occupation in ("Volunteer Fire Fighter", "Fire Fighter", "Fire Chief") and case_time_remaining <= 0:
        print(f"Fire Fighter Casework timer ({case_time_remaining:.2f}s) is ready. Attempting Fire Fighter cases.")
        if execute_fire_work_logic(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Bank Laundering Casework Logic
    if occupation in ("Bank Teller", "Loan Officer", "Bank Manager") and case_time_remaining <= 0:
        if location == home_city:
            print(f"Bank Casework timer ({case_time_remaining:.2f}s) is ready. Attempting bank cases.")
            if execute_banker_laundering():
                action_performed_in_cycle = True
        else:
            print(f"Skipping Bank Casework: Not in home city. Location: {location}, Home City: {home_city}.")

    if perform_critical_checks(character_name):
        continue

    # Bank Add Clients Logic
    if occupation in ("Bank Teller", "Loan Officer", "Bank Manager"):
        if location == home_city:
            bank_add_clients_time_remaining = all_timers.get('bank_add_clients_time_remaining', float('inf'))
            if bank_add_clients_time_remaining <= 0:
                print(f"Bank Add Clients timer ({bank_add_clients_time_remaining:.2f}s) is ready. Attempting to add new clients.")
                if execute_banker_add_clients(initial_player_data):
                    action_performed_in_cycle = True
        else:
            print(f"Skipping Bank Casework: Not in home city. Location: {location}, Home City: {home_city}.")
    # No else clause — just skip silently if not a banker

    if perform_critical_checks(character_name):
        continue

    # Engineering Casework Logic
    if occupation in ("Mechanic", "Technician", "Engineer", "Chief Engineer") and case_time_remaining <= 0:
        print(f"Engineering Casework timer ({case_time_remaining:.2f}s) is ready. Attempting engineering cases.")
        if execute_engineering_casework_logic(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Check messages logic
    current_unread_messages = get_unread_message_count()

    if current_unread_messages > 0:
        read_and_send_new_messages()
        global_vars._last_unread_message_count = get_unread_message_count()
        action_performed_in_cycle = True

    elif global_vars._last_unread_message_count > 0:
        global_vars._last_unread_message_count = 0

    # Check Journals logic
    current_unread_journals = get_unread_journal_count()

    if current_unread_journals > 0:
        if process_unread_journal_entries(initial_player_data):
            action_performed_in_cycle = True
        global_vars._last_unread_journal_count = get_unread_journal_count()

    elif global_vars._last_unread_journal_count > 0:
        global_vars._last_unread_journal_count = 0

    if perform_critical_checks(character_name):
        continue

    # Do Laundering logic (as a gangster, not a banker)
    if enabled_configs['do_launders_enabled']:
        if location == home_city:
            print(f"Skipping Launder: In home city ({location}).")
            global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(100, 200))
        elif launder_time_remaining <= 0:
            print(f"Launder timer ({launder_time_remaining:.2f}s) is ready. Attempting launder.")
            if execute_launder_logic(initial_player_data):
                action_performed_in_cycle = True
            else:
                print("Launder logic did not perform an action or failed. Setting fallback cooldown.")

    if perform_critical_checks(character_name):
        continue

    # --- Re-fetch all game timers just before determining sleep duration ---
    all_timers = get_all_active_game_timers()

    # --- Return to the resting page if drifted ---
    resting_page_url = global_vars.config.get('Auth', 'RestingPage', fallback='').strip()

    if resting_page_url:
        if resting_page_url not in global_vars.driver.current_url:
            print(f"Current URL is '{global_vars.driver.current_url}', expected to include '{resting_page_url}'. Navigating back...")
            try:
                global_vars.driver.get(resting_page_url)
                time.sleep(global_vars.ACTION_PAUSE_SECONDS)
            except Exception as e:
                print(f"FAILED: Could not navigate to the resting page URL '{resting_page_url}'. Error: {e}")
                continue  # Restart loop to try again

            if resting_page_url not in global_vars.driver.current_url:
                print(f"Still not back on resting page. Current URL: {global_vars.driver.current_url}")
                continue  # Restart loop to reset state
    else:
        print("WARNING: No 'RestingPage' URL set in settings.ini under [Auth].")

    # --- Determine the total sleep duration ---
    total_sleep_duration = _determine_sleep_duration(action_performed_in_cycle, {**all_timers, 'occupation': occupation, 'location': location})

    print(f"Sleeping for {total_sleep_duration:.2f} seconds...")
    time.sleep(total_sleep_duration)


