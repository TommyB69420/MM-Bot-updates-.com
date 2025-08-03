import datetime
import time
import random
from selenium.webdriver.common.by import By
from helper_functions import _get_element_text, _get_element_attribute
from database_functions import _read_text_file, _get_last_timestamp
import global_vars

def parse_game_datetime(time_str):
    """
    Parses a game date/time string into a datetime object.
    '1/1/2000' is treated as 'timer ready'.
    """
    if time_str == '1/1/2000':
        return datetime.datetime.min
    try:
        return datetime.datetime.strptime(time_str, "%m/%d/%Y %I:%M:%S %p")
    except ValueError as ve:
        print(f"Error parsing game time '{time_str}': {ve}. Expected format M/D/YYYY HH:MM:SS AM/PM")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while parsing game time '{time_str}': {e}")
        return None

def get_game_timer_remaining(timer_xpath):
    """
    Retrieves the remaining time for an in-game timer.
    Returns seconds remaining, or float('inf') on error/not found.
    """
    max_time_retries = 3
    for _ in range(max_time_retries):
        current_game_time_str = _get_element_text(By.XPATH, "//*[@id='header_time']/div")
        next_timer_str = _get_element_attribute(By.XPATH, timer_xpath, 'data-date-end')

        current_game_time_parsed = parse_game_datetime(current_game_time_str)
        next_timer_datetime = parse_game_datetime(next_timer_str)

        if current_game_time_parsed and next_timer_datetime:
            time_difference = next_timer_datetime - current_game_time_parsed
            time_to_wait_seconds = time_difference.total_seconds()
            additional_random_wait = random.uniform(2, 5)
            return max(0, time_to_wait_seconds + additional_random_wait)
        else:
            print(f"Warning: Could not parse game time or timer from XPath: {timer_xpath}. Retrying...")
            time.sleep(random.uniform(2, 5))

    print(f"Failed to get game timer from {timer_xpath} after {max_time_retries} retries. Returning infinity.")
    return float('inf')

def get_all_active_game_timers():
    """
    Reads all active in-game timers from the current page, calculates file-based timers,
    and incorporates script-managed cooldowns, returning the longest remaining time for each.
    Returns a dictionary with timer names as keys and remaining seconds as values.
    """
    # Initialize all known timers to 0, meaning "ready to act" by default
    timers = {
        'earn_time_remaining': 0,
        'action_time_remaining': 0,
        'case_time_remaining': 0,
        'launder_time_remaining': 0,
        'event_time_remaining': 0,

        'bank_add_clients_time_remaining': 0,

        'yellow_pages_scan_time_remaining': 0,
        'funeral_parlour_scan_time_remaining': 0,
        'aggravated_crime_time_remaining': 0,
        'armed_robbery_recheck_time_remaining': 0,
        'torch_recheck_time_remaining': 0,

        'check_weapon_shop_time_remaining': 0,
        'check_drug_store_time_remaining': 0,
        'check_bionics_store_time_remaining': 0,
        'gym_trains_time_remaining': 0

    }
    current_time = datetime.datetime.now()

    # --- Phase 1: Scrape In-Game UI Timers ---
    # XPath mappings for main game page timers
    timer_xpaths = {
        'earn_time_remaining': "//div[@id='user_timers_holder']/div[contains(@title, 'Next Earn')]/form/span[@class='donation_timer']",
        'action_time_remaining': "//div[@id='user_timers_holder']/div[contains(@title, 'Next Action')]/form/span[@class='donation_timer']",
        'case_time_remaining': "//div[@id='user_timers_holder']/div[contains(@title, 'Next Case')]/form/span[@class='donation_timer']",
        'launder_time_remaining': "//div[@id='user_timers_holder']/div[contains(@title, 'Next Launder')]/form/span[@class='donation_timer']",
        'event_time_remaining': "//div[@id='user_timers_holder']/div[contains(@title, 'Next Event action')]/form/span[@class='donation_timer']",
    }

    for timer_name, xpath in timer_xpaths.items():
        # get_game_timer_remaining returns 0 if not found/expired
        remaining_time = get_game_timer_remaining(xpath)
        timers[timer_name] = remaining_time # Directly assign scraped time

    # --- Phase 2: Calculate File-Based Timers & Aggravated Crime Cooldowns ---

    # Yellow Pages Scan Timer (Always enabled, 7-hour interval)
    yellow_pages_scan_interval_hours = 7
    last_yp_scan_time = _get_last_timestamp(global_vars.YELLOW_PAGES_LAST_SCAN_FILE)
    if last_yp_scan_time:
        remaining = int(yellow_pages_scan_interval_hours * 3600 - (current_time - last_yp_scan_time).total_seconds())
        timers['yellow_pages_scan_time_remaining'] = max(0, remaining)
    else:
        timers['yellow_pages_scan_time_remaining'] = 0  # If never scanned, scan immediately

    # Funeral Parlour Scan Timer (Always enabled, 8-hour interval)
    funeral_parlour_scan_interval_hours = 8
    last_fp_scan_time = _get_last_timestamp(global_vars.FUNERAL_PARLOUR_LAST_SCAN_FILE)
    if last_fp_scan_time:
        remaining = int(funeral_parlour_scan_interval_hours * 3600 - (current_time - last_fp_scan_time).total_seconds())
        timers['funeral_parlour_scan_time_remaining'] = max(0, remaining)
    else:
        timers['funeral_parlour_scan_time_remaining'] = 0  # If never scanned, scan immediately

    # Weapon Shop Check Timer
    next_ws_check = _get_last_timestamp(global_vars.WEAPON_SHOP_NEXT_CHECK_FILE)

    if next_ws_check:
        ws_time_remaining = (next_ws_check - current_time).total_seconds()
        timers['check_weapon_shop_time_remaining'] = max(0, ws_time_remaining)
    else:
        timers['check_weapon_shop_time_remaining'] = 0.0  # If never checked, check immediately

    # Gym Trains Timer
    next_gym_train = _get_last_timestamp(global_vars.GYM_TRAINING_FILE)
    if next_gym_train:
        gym_time_remaining = (next_gym_train - current_time).total_seconds()
        timers['gym_trains_time_remaining'] = max(0, gym_time_remaining)
    else:
        timers['gym_trains_time_remaining'] = 0.0 # If never checked, check immediately

    # Bionics Shop Check Timer
    next_bios_check = _get_last_timestamp(global_vars.BIONICS_SHOP_NEXT_CHECK_FILE)
    if next_bios_check:
        bios_time_remaining = (next_bios_check - current_time).total_seconds()
        timers['check_bionics_store_time_remaining'] = max(0, bios_time_remaining)
    else:
        timers['check_bionics_store_time_remaining'] = 0.0 # If never checked, check immediately

    # Aggravated Crime Cooldowns (Base + Rechecks)
    mins_between_aggs = global_vars.config.getint('Misc', 'MinsBetweenAggs', fallback=30)
    last_agg_crime_time_str = _read_text_file(global_vars.AGGRAVATED_CRIME_LAST_ACTION_FILE)
    # Ensure last_agg_crime_time is a datetime object, default to far past if file empty
    last_agg_crime_time = datetime.datetime.strptime(last_agg_crime_time_str, "%Y-%m-%d %H:%M:%S.%f") if last_agg_crime_time_str else (current_time - datetime.timedelta(days=365))

    base_agg_time_remaining = max(0, mins_between_aggs * 60 - (current_time - last_agg_crime_time).total_seconds())

    # Calculate recheck cooldowns (these are purely script-managed)
    torch_recheck_remaining = max(0, (global_vars._script_torch_recheck_cooldown_end_time - current_time).total_seconds())
    armed_robbery_recheck_remaining = max(0, (global_vars._script_armed_robbery_recheck_cooldown_end_time - current_time).total_seconds())

    # The crime isn't truly ready unless ALL relevant timers are zero. This combines the base cooldown with any specific recheck cooldowns
    effective_agg_ready_time = max(base_agg_time_remaining, torch_recheck_remaining, armed_robbery_recheck_remaining)
    timers['aggravated_crime_time_remaining'] = effective_agg_ready_time
    if global_vars._script_aggravated_crime_recheck_cooldown_end_time:
        short_retry_remaining = (global_vars._script_aggravated_crime_recheck_cooldown_end_time - current_time).total_seconds()
        if short_retry_remaining > 0:
            timers['aggravated_crime_time_remaining'] = max(timers['aggravated_crime_time_remaining'], short_retry_remaining)

    # Assign recheck timers directly, as they are derived from script-managed end times
    timers['torch_recheck_time_remaining'] = torch_recheck_remaining
    timers['armed_robbery_recheck_time_remaining'] = armed_robbery_recheck_remaining


    # --- Phase 3: Integrate ALL Script-Managed Internal Cooldowns (using max()) ---
    # This ensures that if the script sets a cooldown (e.g., because an action failed,
    # or you're in the wrong city), that cooldown is respected, overriding any shorter or non-existent in-game timers.

    # Medical Cooldown
    script_medical_remaining = (global_vars._script_case_cooldown_end_time - current_time).total_seconds()
    if script_medical_remaining > 0:
        timers['case_time_remaining'] = max(timers.get('case_time_remaining', 0), script_medical_remaining)

    # Bank Cooldown
    script_bank_remaining = (global_vars._script_case_cooldown_end_time - current_time).total_seconds()
    if script_bank_remaining > 0:
        timers['case_time_remaining'] = max(timers.get('case_time_remaining', 0), script_bank_remaining)

    # Bank Add Clients Cooldown
    script_bank_add_clients_remaining = (global_vars._script_bank_add_clients_cooldown_end_time - current_time).total_seconds()
    if script_bank_add_clients_remaining > 0:
        timers['bank_add_clients_time_remaining'] = max(timers.get('bank_add_clients_time_remaining', 0), script_bank_add_clients_remaining)

    # Judge Cooldown
    script_judge_remaining = (global_vars._script_case_cooldown_end_time - current_time).total_seconds()
    if script_judge_remaining > 0:
        timers['case_time_remaining'] = max(timers.get('case_time_remaining', 0), script_judge_remaining)

    # Fire Fighter Cooldown
    script_firefighter_remaining = (global_vars._script_case_cooldown_end_time - current_time).total_seconds()
    if script_firefighter_remaining > 0:
        timers['case_time_remaining'] = max(timers.get('case_time_remaining', 0), script_firefighter_remaining)

    # Lawyer Cooldown
    script_lawyer_remaining = (global_vars._script_case_cooldown_end_time - current_time).total_seconds()
    if script_lawyer_remaining > 0:
        timers['case_time_remaining'] = max(timers.get('case_time_remaining', 0), script_lawyer_remaining)

    # Engineering Cooldown
    script_engineering_remaining = (global_vars._script_case_cooldown_end_time - current_time).total_seconds()
    if script_engineering_remaining > 0:
        timers['case_time_remaining'] = max(timers.get('case_time_remaining', 0), script_engineering_remaining)

    # Earn Cooldown
    script_earn_remaining = (global_vars._script_earn_cooldown_end_time - current_time).total_seconds()
    if script_earn_remaining > 0:
        timers['earn_time_remaining'] = max(timers.get('earn_time_remaining', 0), script_earn_remaining)

    # Community Service Cooldown
    script_community_service_remaining = (global_vars._script_action_cooldown_end_time - current_time).total_seconds()
    if script_community_service_remaining > 0:
        timers['action_time_remaining'] = max(timers.get('action_time_remaining', 0), script_community_service_remaining)

    # FireFighter Duties Cooldown
    script_firefighter_remaining = (global_vars._script_action_cooldown_end_time - current_time).total_seconds()
    if script_firefighter_remaining > 0:
        timers['action_time_remaining'] = max(timers.get('action_time_remaining', 0), script_firefighter_remaining)

    # Launder Cooldown
    script_launder_remaining = (global_vars._script_launder_cooldown_end_time - current_time).total_seconds()
    if script_launder_remaining > 0:
        timers['launder_time_remaining'] = max(timers.get('launder_time_remaining', 0), script_launder_remaining)

    # Manufacture Drugs Cooldown
    script_manufacture_drugs_remaining = (global_vars._script_action_cooldown_end_time - current_time).total_seconds()
    if script_manufacture_drugs_remaining > 0:
        timers['action_time_remaining'] = max(timers.get('action_time_remaining', 0), script_manufacture_drugs_remaining)

    # Study Degree Cooldown
    script_university_degree_remaining = (global_vars._script_action_cooldown_end_time - current_time).total_seconds()
    if script_university_degree_remaining > 0:
        timers['action_time_remaining'] = max(timers.get('action_time_remaining', 0), script_university_degree_remaining)

    # Event Cooldown
    script_event_remaining = (global_vars._script_event_cooldown_end_time - current_time).total_seconds()
    if script_event_remaining > 0:
        timers['event_time_remaining'] = max(timers.get('event_time_remaining', 0), script_event_remaining)

    # Weapon Shop Cooldown
    script_weapon_shop_remaining = (global_vars._script_weapon_shop_cooldown_end_time - current_time).total_seconds()
    if script_weapon_shop_remaining > 0:
        timers['check_weapon_shop_time_remaining'] = max(timers.get('check_weapon_shop_time_remaining', 0), script_weapon_shop_remaining)

    # Drug Store Cooldown
    script_drug_store_remaining = (global_vars._script_drug_store_cooldown_end_time - current_time).total_seconds()
    if script_drug_store_remaining > 0:
        timers['check_drug_store_time_remaining'] = max(timers.get('check_drug_store_time_remaining', 0), script_drug_store_remaining)

    # Gym Trains Cooldown
    script_gym_trains_remaining = (global_vars._script_gym_train_cooldown_end_time - current_time).total_seconds()
    if script_gym_trains_remaining > 0:
        timers['gym_trains_time_remaining'] = max(timers.get('gym_trains_time_remaining', 0), script_gym_trains_remaining)

    # Bionics Shop Cooldown
    script_bionics_shop_remaining = (global_vars._script_bionics_shop_cooldown_end_time - current_time).total_seconds()
    if script_bionics_shop_remaining > 0:
        timers['check_bionics_store_time_remaining'] = max(timers.get('check_bionics_store_time_remaining', 0), script_bionics_shop_remaining)

    return timers