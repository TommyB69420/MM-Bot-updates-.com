import datetime
import random
import time
import sys
from selenium.common import StaleElementReferenceException
from selenium.webdriver.common.by import By
import global_vars
from agg_crimes import execute_aggravated_crime_logic, execute_yellow_pages_scan, execute_funeral_parlour_scan
from earn_functions import execute_earns_logic
from occupations import judge_casework, lawyer_casework, medical_casework, community_services, laundering, \
    manufacture_drugs, banker_laundering, banker_add_clients, fire_casework, fire_duties, engineering_casework, \
    customs_blind_eyes
from helper_functions import _get_element_text, _find_and_send_keys, _find_and_click, is_player_in_jail, \
    blind_eye_queue_count, community_service_queue_count, dequeue_community_service
from database_functions import init_local_db
from police import police_911, prepare_police_cases, train_forensics
from timer_functions import get_all_active_game_timers
from comms_journals import send_discord_notification, get_unread_message_count, read_and_send_new_messages, get_unread_journal_count, process_unread_journal_entries
from misc_functions import study_degrees, do_events, check_weapon_shop, check_drug_store, jail_work, \
    clean_money_on_hand_logic, gym_training, check_bionics_shop, police_training, combat_training, fire_training, \
    customs_training, take_promotion

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
        "Home City": {"xpath": "//div[contains(text(), 'Home City')]/following-sibling::div[1]", "is_money": False, "strip_label": "Home city:"},
        "Next Rank": {"xpath": "//div[@id='nav_right']//div[@role='progressbar' and contains(@class,'bg-rankprogress')]", "attr": "aria-valuenow", "is_percent": True}
    }

    for key, details in data_elements.items():
        raw = None

        # Use attribute if specified
        if "attr" in details:
            from helper_functions import _get_element_attribute
            raw = _get_element_attribute(By.XPATH, details["xpath"], details["attr"])
        else:
            raw = _get_element_text(By.XPATH, details["xpath"])

        if raw:
            text_content = raw.strip()
            if details.get("strip_label"):
                text_content = text_content.replace(details["strip_label"], "").strip()

            if details.get("is_money"):
                player_data[key] = int(''.join(filter(str.isdigit, text_content)))
            elif details.get("is_percent"):
                # Handle values like "38" or "38%"
                digits = ''.join(ch for ch in text_content if ch.isdigit())
                player_data[key] = int(digits) if digits else None
            else:
                player_data[key] = text_content
        else:
            print(f"Warning: Could not fetch {key}.")
            player_data[key] = None

    return player_data

def check_for_logout_and_login():
    """
    Handles bounce-back after logging in:
    - If on login screen (default.asp), enter username/password and click Sign in.
    - If redirected back to login, try again until logged in.
    - Once logged in, click Play Now.
    Returns True if a login attempt was made, False otherwise.
    """
    import time

    if "default.asp" not in (global_vars.driver.current_url or "").lower():
        return False  # Not on login screen

    username = global_vars.config['Login Credentials'].get('UserName')
    password = global_vars.config['Login Credentials'].get('Password')
    if not username or not password:
        print("ERROR: Missing UserName/Password in settings.ini.")
        send_discord_notification("Login credentials missing. Cannot log in.")
        return False

    send_discord_notification("Logged out — attempting to log in.")
    login_attempted = False

    while True:
        login_attempted = True
        print("Attempting login…")

        if not _find_and_send_keys(By.XPATH, "//form[@id='loginForm']//input[@id='email']", username):
            print("FAILED: Could not enter username.")
            return True
        if not _find_and_send_keys(By.XPATH, "//input[@id='pass']", password):
            print("FAILED: Could not enter password.")
            return True
        if not _find_and_click(By.XPATH, "//button[normalize-space()='Sign in']", pause=global_vars.ACTION_PAUSE_SECONDS * 2):
            print("FAILED: Could not click Sign In button.")
            return True

        # Wait briefly then check URL
        time.sleep(2)
        if "default.asp" not in (global_vars.driver.current_url or "").lower():
            if _find_and_click(By.XPATH, "//a[@title='Log in with the character!|Get inside the world of MafiaMatrix!']",
                               pause=global_vars.ACTION_PAUSE_SECONDS * 3):
                print("Successfully logged in.")
                send_discord_notification("Logged in successfully!")
            else:
                print("Logged in, but Play Now click failed.")
                send_discord_notification("Logged in, but Play Now click failed.")
            return True

        print("Bounce back to login detected. Retrying…")
        time.sleep(1)  # small pause before retry

def check_for_gbh(character_name: str):
    """
    If current URL contains gbh.asp, alert Discord and terminate.
    Returns True if GBH was detected (process will exit).
    """
    try:
        url = (global_vars.driver.current_url or "").lower()
    except Exception:
        url = ""

    if "gbh.asp" in url:
        try:
            discord_id = global_vars.config['Discord Webhooks'].get('DiscordID', '').strip()
        except Exception:
            discord_id = '@discordID'

        # message discord
        msg = f"{discord_id} @here, {character_name} has been GBHd. OMGGG FUCCCKK"
        print("GBH DETECTED — sending Discord alert and stopping the bot.")
        send_discord_notification(msg)
        sys.exit(0)

    return False

def get_enabled_configs(location):
    """
    Reads the settings from settings.ini to determine what functions to turn on
    """
    config = global_vars.config
    return {
    "do_earns_enabled": config.getboolean('Earns Settings', 'DoEarns', fallback=True),
    "do_community_services_enabled": config.getboolean('Actions Settings', 'CommunityService', fallback=False),
    "mins_between_aggs": config.getint('Misc', 'MinsBetweenAggs', fallback=30),
    "do_hack_enabled": config.getboolean('Hack', 'DoHack', fallback=False),
    "do_pickpocket_enabled": config.getboolean('PickPocket', 'DoPickPocket', fallback=False),
    "do_mugging_enabled": config.getboolean('Mugging', 'DoMugging', fallback=False),
    "do_armed_robbery_enabled": config.getboolean('Armed Robbery', 'DoArmedRobbery', fallback=False),
    "do_torch_enabled": config.getboolean('Torch', 'DoTorch', fallback=False),
    "do_judge_cases_enabled": config.getboolean('Judge', 'Do_Cases', fallback=False) and occupation in ["Judge", "Supreme Court Judge"] and location == home_city,
    "do_launders_enabled": config.getboolean('Launder', 'DoLaunders', fallback=False),
    "do_manufacture_drugs_enabled": config.getboolean('Actions Settings', 'ManufactureDrugs', fallback=False),
    "do_university_degrees_enabled": config.getboolean('Actions Settings', 'StudyDegrees', fallback=False),
    "do_event_enabled": config.getboolean('Misc', 'DoEvent', fallback=False),
    "do_weapon_shop_check_enabled": config.getboolean('Weapon Shop', 'CheckWeaponShop', fallback=False) and any("Weapon Shop" in biz_list for city, biz_list in global_vars.private_businesses.items() if city == location),
    "do_drug_store_enabled": config.getboolean('Drug Store', 'CheckDrugStore', fallback=False) and any("Drug Store" in biz_list for city, biz_list in global_vars.private_businesses.items() if city == location),
    "do_firefighter_duties_enabled": config.getboolean('Fire', 'DoFireDuties', fallback=False),
    "do_gym_trains_enabled": config.getboolean('Misc', 'GymTrains', fallback=False) and any("Gym" in biz_list for city, biz_list in global_vars.private_businesses.items() if city == location),
    "do_bionics_shop_check_enabled": config.getboolean('Bionics Shop', 'CheckBionicsShop', fallback=False) and any ("Bionics" in biz_list for city, biz_list in global_vars.private_businesses.items() if city == location),
    "do_training_enabled": config.get('Actions Settings', 'Training', fallback='').strip().lower(),
    "do_post_911_enabled": config.getboolean('Police', 'Post911', fallback=False),
    "do_police_cases_enabled": config.getboolean('Police', 'DoCases', fallback=False),
    "do_bank_add_clients_enabled": config.getboolean('Bank', 'AddClients', fallback=False) and location == home_city and occupation in ["Bank Teller", "Loan Officer", "Bank Manager"],
    "do_auto_promo_enabled": config.getboolean('Misc', 'TakePromo', fallback=True) and (next_rank_pct >= 95),
}

def _determine_sleep_duration(action_performed_in_cycle, timers_data, enabled_configs, next_rank_pc):
    """
    Determines the optimal sleep duration based on enabled activities and cooldown timers.
    """
    print("\n--- Calculating Sleep Duration ---")

    # Extract static context
    occupation = timers_data.get('occupation')
    location = timers_data.get('location')
    home_city = timers_data.get('home_city')
    queue_count = blind_eye_queue_count()

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
    post_911 = get_timer('post_911_time_remaining')
    trafficking = get_timer('trafficking_time_remaining')
    auto_promo = get_timer('promo_check_time_remaining')

    cfg = global_vars.config
    businesses = global_vars.private_businesses

    active = []

    # Add timers if enabled
    if cfg.getboolean('Earns Settings', 'DoEarns', fallback=False):
        active.append(('Earn', earn))
    if cfg.getboolean('Actions Settings', 'CommunityService', fallback=False):
        active.append(('Community Service', action))
    if cfg.getboolean('Actions Settings', 'StudyDegrees', fallback=False) and location == home_city:
        active.append(('Study Degree', action))
    if cfg.getboolean('Actions Settings', 'ManufactureDrugs', fallback=False):
        active.append(('Manufacture Drugs', action))
    if cfg.getboolean('Misc', 'DoEvent', fallback=False):
        active.append(('Event', event))
    if cfg.getboolean('Launder', 'DoLaunders', fallback=False) and location != home_city:
        active.append(('Launder', launder))
    if cfg.get('Actions Settings', 'Training', fallback='').strip() and location == home_city:
        active.append(('Training', action))
    if enabled_configs.get('do_auto_promo_enabled'):
        active.append(('Auto Promo', auto_promo))
    active.append(('Yellow Pages Scan', yps))
    active.append(('Funeral Parlour Scan', fps))

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

    # Career specific based on occupation
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
    if occupation in ("Bank Teller", "Loan Officer", "Bank Manager") and location == home_city:
        active.append(('Bank Casework', case))
    if ('customs' in (occupation or '').lower()) and location == home_city and queue_count > 0:
        active.append(('Blind Eye', trafficking))
    if enabled_configs['do_bank_add_clients_enabled']:
        active.append(('Bank add clients', bank_add))
    if cfg.getboolean('Fire', 'DoFireDuties', fallback=False):
        active.append(('Firefighter Duties', action))
    if cfg.getboolean('Police', 'Post911', fallback=False) and occupation in ["Police Officer"] and location == home_city:
        active.append(('Post 911', post_911))
    if cfg.getboolean('Police', 'DoCases', fallback=False) and occupation in ["Police Officer"] and location == home_city:
        active.append(('Do Cases', case))
    if cfg.getboolean('Police', 'DoForensics', fallback=False) and occupation in ["Police Officer"] and location == home_city:
        effective_forensics = max(action, case)
        active.append(('Forensics', effective_forensics))

    # City actions
    if cfg.getboolean('Weapon Shop', 'CheckWeaponShop', fallback=False) and any("Weapon Shop" in b for c, b in businesses.items() if c == location):
        active.append(('Check Weapon Shop', weapon))
    if cfg.getboolean('Drug Store', 'CheckDrugStore', fallback=False) and any("Drug Store" in b for c, b in businesses.items() if c == location):
        active.append(('Check Drug Store', drug))
    if cfg.getboolean('Misc', 'GymTrains', fallback=False) and any("Gym" in b for c, b in businesses.items() if c == location):
        active.append(('Gym Trains', gym))
    if cfg.getboolean('Bionics Shop', 'CheckBionicsShop', fallback=False) and any("Bionics" in b for c, b in businesses.items() if c == location):
        active.append(('Check Bionics Shop', bionics))

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
            return True  # Restart the main loop after re-login

        # GBH page detection
    if check_for_gbh(character_name):
        return True

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

    # Fetch the player data
    initial_player_data = fetch_initial_player_data()
    character_name = initial_player_data.get("Character Name", "UNKNOWN")

    # --- Jail Check ---
    if is_player_in_jail():
        print("Player is in jail. Entering jail work loop...")

        while is_player_in_jail():
            # check for script checks and logouts in jail
            if perform_critical_checks(character_name):
                continue

            global_vars.jail_timers = get_all_active_game_timers()
            jail_work()
            time.sleep(2)  # Tighter loop for responsiveness

        print("Player released from jail. Resuming normal script.")
        continue  # Skip the rest of the main loop for this cycle

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
    next_rank_pct = initial_player_data.get("Next Rank")
    print(f"Current Character: {character_name}, Rank: {rank}, Occupation: {occupation}, Clean Money: {clean_money}, Dirty Money: {dirty_money}, Location: {location}. Home City: {home_city}. Next Rank {next_rank_pct}.")

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
    trafficking_time_remaining = all_timers.get('trafficking_time_remaining', float('inf'))

    # Aggravated crime timers
    aggravated_crime_time_remaining = all_timers.get('aggravated_crime_time_remaining', float('inf'))
    armed_robbery_recheck_time_remaining = (getattr(global_vars, "_script_armed_robbery_recheck_cooldown_end_time", datetime.datetime.min) - datetime.datetime.now()).total_seconds()
    torch_recheck_time_remaining = (getattr(global_vars, "_script_torch_recheck_cooldown_end_time", datetime.datetime.min) - datetime.datetime.now()).total_seconds()
    yellow_pages_scan_time_remaining = all_timers.get('yellow_pages_scan_time_remaining', float('inf'))
    funeral_parlour_scan_time_remaining = all_timers.get('funeral_parlour_scan_time_remaining', float('inf'))

    # Misc city timers
    check_weapon_shop_time_remaining = all_timers.get('check_weapon_shop_time_remaining', float('inf'))
    check_drug_store_time_remaining = all_timers.get('check_drug_store_time_remaining', float('inf'))
    gym_trains_time_remaining = all_timers.get('gym_trains_time_remaining', float('inf'))
    check_bionics_store_time_remaining = all_timers.get('check_bionics_store_time_remaining', float('inf'))
    promo_check_time_remaining = all_timers.get('promo_check_time_remaining', float('inf'))

    # Career specific timers
    bank_add_clients_time_remaining = all_timers.get('bank_add_clients_time_remaining', float('inf'))
    post_911_time_remaining = all_timers.get('post_911_time_remaining', float('inf'))

    if perform_critical_checks(character_name):
        continue

    # Auto Promo logic
    if enabled_configs['do_auto_promo_enabled'] and promo_check_time_remaining <= 0:
        print(f"Auto Promo timer ({promo_check_time_remaining:.2f}s) is ready. Attempting auto-promotion...")
        if take_promotion():
            action_performed_in_cycle = True

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

    # Mandatory Community Services (queued by AgCrime gate)
    queued_cs = community_service_queue_count()
    if queued_cs > 0 and action_time_remaining <= 0:
        print(f"Mandatory Community Service queued ({queued_cs}). Attempting 1 now.")
        if community_services(initial_player_data):
            if dequeue_community_service():
                print(f"Completed 1 queued Community Service. Remaining: {community_service_queue_count()}")
            action_performed_in_cycle = True
        else:
            print("Queued Community Service attempt failed or could not start. Will retry next cycle.")

    # Community Service Logic
    if enabled_configs['do_community_services_enabled'] and action_time_remaining <= 0:
        print(f"Community Service timer ({action_time_remaining:.2f}s) is ready. Attempting CS.")
        if community_services(initial_player_data):
            action_performed_in_cycle = True
        else:
            print("Community Service logic did not perform an action or failed. Setting fallback cooldown.")

    if perform_critical_checks(character_name):
        continue

    # Firefighter duties Logic
    if enabled_configs['do_firefighter_duties_enabled'] and action_time_remaining <= 0:
        print(f"Firefighter duties timer ({action_time_remaining:.2f}s) is ready. Attempting to do duties   .")
        if fire_duties():
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

    # Training logic
    if enabled_configs.get('do_training_enabled') and action_time_remaining <= 0:
        training_type = enabled_configs['do_training_enabled'].lower()

        training_map = {
            "police": police_training,
            "forensics": train_forensics,
            "fire": fire_training,
            "customs": customs_training,
            "jui jitsu": combat_training,
            "muay thai": combat_training,
            "karate": combat_training,
            "mma": combat_training,
        }

        func = training_map.get(training_type)
        if func:
            func()
            action_performed_in_cycle = True
        else:
            print(f"WARNING: Unknown training type '{training_type}' specified in settings.ini.")

    if perform_critical_checks(character_name):
        continue

    # Drug manufacturing logic
    if enabled_configs['do_manufacture_drugs_enabled'] and occupation == "Gangster":
        if action_time_remaining <= 0:
            print(f"Manufacture Drugs timer ({action_time_remaining:.2f}s) is ready. Attempting manufacture.")
            if manufacture_drugs(initial_player_data):
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
        enabled_configs['do_torch_enabled'],
    ]):
        # Hack / Pickpocket / Mugging — only if no mandatory CS queued
        if any([
            enabled_configs['do_hack_enabled'],
            enabled_configs['do_pickpocket_enabled'],
            enabled_configs['do_mugging_enabled'],
        ]) and aggravated_crime_time_remaining <= 0 and community_service_queue_count() == 0:
            should_attempt_aggravated_crime = True
            print(f"Aggravated Crime (Hack/Pickpocket/Mugging) timer ({aggravated_crime_time_remaining:.2f}s) is ready. Attempting crime.")

        # Armed Robbery — only if no mandatory CS queued
        if enabled_configs['do_armed_robbery_enabled']:
            if (aggravated_crime_time_remaining <= 0
                    and armed_robbery_recheck_time_remaining <= 0
                    and community_service_queue_count() == 0):
                should_attempt_aggravated_crime = True
                print("Armed Robbery timers are ready. Attempting crime.")

        # Torch — only if no mandatory CS queued
        if enabled_configs['do_torch_enabled']:
            if (aggravated_crime_time_remaining <= 0
                    and torch_recheck_time_remaining <= 0
                    and community_service_queue_count() == 0):
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
    if enabled_configs['do_judge_cases_enabled'] and case_time_remaining <= 0:
        print(f"Judge Casework timer ({case_time_remaining:.2f}s) is ready. Attempting judge cases.")
        if judge_casework(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Do Lawyer case work logic
    if occupation == "Lawyer" and case_time_remaining <= 0:
        print(f"Lawyer Casework timer ({case_time_remaining:.2f}s) is ready. Attempting lawyer cases.")
        if lawyer_casework():
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Medical Casework Logic
    if occupation in ("Nurse", "Doctor", "Surgeon", "Hospital Director") and case_time_remaining <= 0:
        print(f"Medical Casework timer ({case_time_remaining:.2f}s) is ready. Attempting medical cases.")
        if medical_casework(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Police Casework Logic
    if enabled_configs['do_police_cases_enabled'] and occupation in ["Police Officer"] and location == home_city and case_time_remaining <= 0:
        print(f"Police case timer ({case_time_remaining:.2f}s) is ready. Attempting to do Police Cases")
        if prepare_police_cases(character_name):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Post 911 Logic
    if enabled_configs['do_post_911_enabled'] and occupation in ["Police Officer"] and location == home_city and post_911_time_remaining <= 0:
        print(f"Post 911 timer ({post_911_time_remaining:.2f}s) is ready. Attempting to post 911")
        if police_911():
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Firefighter Casework Logic
    if occupation in ("Volunteer Fire Fighter", "Fire Fighter", "Fire Chief") and case_time_remaining <= 0:
        print(f"Fire Fighter Casework timer ({case_time_remaining:.2f}s) is ready. Attempting Fire Fighter cases.")
        if fire_casework(initial_player_data):
            action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Bank Laundering Casework Logic
    if occupation in ("Bank Teller", "Loan Officer", "Bank Manager") and case_time_remaining <= 0:
        if location == home_city:
            print(f"Bank Casework timer ({case_time_remaining:.2f}s) is ready. Attempting bank cases.")
            if banker_laundering():
                action_performed_in_cycle = True
        else:
            print(f"Skipping Bank Casework: Not in home city. Location: {location}, Home City: {home_city}.")

    if perform_critical_checks(character_name):
        continue

    # Customs Blind Eye Logic
    queue_count = blind_eye_queue_count()
    if ('customs' in (occupation or '').lower()) and location == home_city and queue_count > 0:
        if trafficking_time_remaining <= 0:
            print(f"Blind Eye queued ({queue_count}) and Trafficking timer ({trafficking_time_remaining:.2f}s) is ready. Attempting Blind Eye.")
            if customs_blind_eyes():
                action_performed_in_cycle = True
        else:
            print(f"Blind Eye queued ({queue_count}), but Trafficking timer not ready ({trafficking_time_remaining:.2f}s).")

    # Bank Add Clients Logic
    if enabled_configs['do_bank_add_clients_enabled']:
        if bank_add_clients_time_remaining <= 0:
            print(f"Add Clients timer ({bank_add_clients_time_remaining:.2f}s) is ready. Attempting to add new clients.")
            if banker_add_clients(initial_player_data):
                action_performed_in_cycle = True

    if perform_critical_checks(character_name):
        continue

    # Engineering Casework Logic
    if occupation in ("Mechanic", "Technician", "Engineer", "Chief Engineer") and case_time_remaining <= 0:
        print(f"Engineering Casework timer ({case_time_remaining:.2f}s) is ready. Attempting engineering cases.")
        if engineering_casework(initial_player_data):
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
            if laundering(initial_player_data):
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
    total_sleep_duration = _determine_sleep_duration(action_performed_in_cycle, {**all_timers, 'occupation': occupation, 'location': location, 'home_city': home_city}, enabled_configs, next_rank_pct)

    print(f"Sleeping for {total_sleep_duration:.2f} seconds...")
    time.sleep(total_sleep_duration)


