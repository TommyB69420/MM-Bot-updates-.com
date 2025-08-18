import datetime
import random
import re
import time
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

import global_vars
from database_functions import _read_json_file, remove_player_cooldown, set_player_data
from helper_functions import _find_and_send_keys, _find_and_click, _find_element, _navigate_to_page_via_menu, _get_element_text, _get_element_attribute, _find_elements
from timer_functions import get_game_timer_remaining, get_all_active_game_timers


def community_services(player_data):
    """Manages and performs community service operations based on the player's location."""
    print("\n--- Beginning Community Service Operation ---")

    current_location = player_data.get("Location")
    home_city = player_data.get("Home City")

    if not _navigate_to_page_via_menu(
            "//span[@class='income']",
            "//a[normalize-space()='Community Service']",
            "Community Services Page"
    ):
        print("FAILED: Failed to open Community Services menu.")
        global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    service_clicked = False

    if current_location == home_city:
        print(f"In home city ({home_city}). Attempting regular community services.")
        community_service_options = [
            "reading", "suspect", "football", "delivery", "pamphlets",
            "kids", "weeding", "tags", "gum"
        ]
        try:
            # Get all matching visible elements in one go
            service_elements = global_vars.driver.find_elements(By.XPATH, "//input[@type='radio' and @id]")

            # Filter by only the known IDs in order
            filtered_services = [elem for elem in service_elements if elem.get_attribute("id") in community_service_options and elem.is_displayed()]

            if filtered_services:
                # Click the last one available (bottom-most)
                filtered_services[-1].click()
                selected_id = filtered_services[-1].get_attribute("id")
                print(f"Clicked community service: {selected_id}")
                service_clicked = True
            else:
                print("No regular community service option could be selected.")
        except Exception as e:
            print(f"ERROR while trying to find community services: {e}")
        if not service_clicked:
            print("No regular community service option could be selected.")
    else:
        print(f"Not in home city ({current_location} vs {home_city}). Only attempting 'CS in other cities'.")
        if _find_and_click(By.NAME, "csinothercities"):
            print("Clicked 'CS in other cities'.")
            service_clicked = True
        else:
            print("FAILED: Could not find or click 'CS in other cities' option.")

    if service_clicked:
        if _find_and_click(By.XPATH, "//input[@name='B1']"):
            print("Community Service commenced successfully.")
            return True
        else:
            print("FAILED: Failed to click 'Commence Service' button.")
    else:
        print("No community service option could be selected or commenced.")
    global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
    return False

def manufacture_drugs(player_data):
    """
    Manages and performs drug manufacturing operations.
    Only works if occupation is 'Gangster'.
    """
    print("\n--- Beginning Drug Manufacturing Operation ---")

    if not _navigate_to_page_via_menu(
            "//span[@class='income']",
            "//a[normalize-space()='Drugs']",
            "Drugs Page"
    ):
        print("FAILED: Navigation to Drugs Page failed.")
        global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    if not _find_and_click(By.XPATH, "//strong[normalize-space()='Manufacture Drugs at the local Drug House']"):
        print("FAILED: Could not click 'Manufacture Drugs' link.")
        global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    select_dropdown_xpath = "//select[@name='action']"
    yes_option_xpath = "/html/body/div[4]/div[4]/div[1]/div[2]/form/select/option[2]"

    if not _find_and_click(By.XPATH, select_dropdown_xpath):
        print("FAILED: Could not click on the drug manufacturing dropdown.")
        global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    if not _find_and_click(By.XPATH, yes_option_xpath, pause=global_vars.ACTION_PAUSE_SECONDS * 2):
        print("FAILED: Could not select 'Yes, I want to work at the drug house'.")
        global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    submit_button_xpath = "//input[@name='B1']"
    if not _find_and_click(By.XPATH, submit_button_xpath):
        print("FAILED: Could not click 'Submit' for drug manufacturing.")
        global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    try:
        fail_element = global_vars.driver.find_element(By.XPATH, "//div[@id='fail']")
        fail_text = fail_element.text.strip()
        print(f"Manufacture Result: {fail_text}")

        if "can't manufacture at this" in fail_text:
            print("Drug house is overstocked. Setting 10-minute cooldown.")
            global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=10)
            return False

    except Exception:
        # No fail message found
        pass

    print("Successfully initiated drug manufacturing.")
    return True

def laundering(player_data):
    """Launder dirty money via Income menu. Can set preferred launder contacts in settings.ini"""

    print("\n--- Money Laundering ---")

    # Load player money + launder config
    dirty = int(player_data.get("Dirty Money", 0))
    reserve = global_vars.config.getint("Launder", "Reserve", fallback=0)
    preferred_raw = global_vars.config.get("Launder", "Preferred", fallback="").strip()
    preferred = {n.strip().lower() for n in preferred_raw.split(",") if n.strip()}

    # Skip if dirty money is not above reserve
    if dirty <= reserve:
        print(f"Skip: dirty ${dirty} ≤ reserve ${reserve}.")
        global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(300, 600))  # 5–10 min backoff
        return False

    # Navigate via Income → Money Laundering
    if not _navigate_to_page_via_menu(
        "//span[@class='income']",
        "//a[normalize-space()='Money Laundering']",
        "Money Laundering Page"):
        print("FAILED: open Money Laundering via menu.")
        global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    # Find laundering contacts table
    table = _find_element(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div[2]/table")
    if not table:
        print("No laundering contacts. Backing off 30m.")
        global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
        return False

    # Gather all rows (excluding header)
    rows = table.find_elements(By.TAG_NAME, "tr")[1:]
    target_link = None
    fallback_link = None

    # Scan rows for preferred/fallback launderer
    for row in rows:
        try:
            link = row.find_element(By.XPATH, ".//td[1]/a")
            name = (link.text or "").strip()
            if not name:
                continue
            lname = name.lower()

            # If preferred launderer is found; stop here
            if lname in preferred:
                target_link = link
                print(f"Preferred launderer: {name}")
                break

            # If no preferred found yet, keep track of the first available one
            if fallback_link is None:
                fallback_link = link
                print(f"Set first available launderer as fallback: {name}")

        except Exception:
            continue

    # Use fallback if no preferred launderer was found
    if not target_link:
        if not fallback_link:
            print("No suitable launderers. Backing off 30m.")
            global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
            return False
        target_link = fallback_link
        print("No preferred launderer found, using first available.")

    # Click into chosen launderer
    try:
        target_link.click()
        time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
    except Exception as e:
        print(f"FAILED: click launderer: {e}")
        global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    # Read max launderable amount from contact page
    max_text = _get_element_text(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div[2]/form[1]/p[1]/font")
    if not max_text:
        print("No 'max' text on contact page.")
        global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    m = re.search(r"\$(\d[\d,]*)\s*max", max_text)
    if not m:
        print("Couldn't parse max amount.")
        global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    max_amt = int(m.group(1).replace(",", ""))

    # Launder only what fits under (dirty – reserve) and contact’s max
    amt = min(max_amt, dirty - reserve)
    if amt <= 0:
        print(f"Nothing to launder (dirty ${dirty}, reserve ${reserve}, max ${max_amt}).")
        global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(300, 600))
        return False

    # Enter amount to launder
    if not _find_and_send_keys(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div[2]/form[1]/p[1]/input", str(amt)):
        print("FAILED: enter amount.")
        global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    # Click submit
    if not _find_and_click(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div[2]/form[1]/p[2]/input"):
        print("FAILED: click 'Launder'.")
        global_vars._script_launder_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    print(f"Successfully initiated laundering of ${amt}.")
    return True


def medical_casework(player_data):
    """
    Manages and processes hospital casework.
    Only works if occupation is 'Nurse', 'Doctor', 'Surgeon' or 'Hospital Director'.
    Navigates to the hospital if needed and performs available casework tasks.
    """
    print("\n--- Beginning Medical Casework Operation ---")

    occupation = player_data.get("Occupation")
    your_character_name = player_data.get("Character Name")
    medical_eligible_occupations = ["Nurse", "Doctor", "Surgeon", "Hospital Director"]

    if occupation not in medical_eligible_occupations:
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(60, 180))
        return False

    # Navigate to Hospital if not already there
    if 'hospital.asp' not in global_vars.driver.current_url:
        city_menu_xpath = "//div[@id='nav_left']//a[@href='/localcity/local.asp']"
        hospital_xpath = "//a[@href='hospital.asp' and contains(@class, 'business') and contains(@class, 'hospital')]"

        if not _find_and_click(By.XPATH, city_menu_xpath):
            print("FAILED: Navigation to City Menu failed. Setting cooldown.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(60, 180))
            return False

        if not _find_and_click(By.XPATH, hospital_xpath):
            print("FAILED: Hospital not found. Possibly torched. Setting cooldown.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(5, 7))
            return False

        if _find_element(By.ID, "fail"):
            fail_text = _get_element_attribute(By.ID, "fail", "innerHTML")
            if fail_text and "under going repairs" in fail_text:
                print("Hospital is torched. Backing off.")
                global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(5, 7))
                return False

    else:
        # If already on hospital.asp, click the "PATIENTS" link to refresh
        print("Already on Hospital page. Clicking 'PATIENTS' to refresh.")
        patients_xpath = "//div[@class='links']//a[@href='hospital.asp?display=patients' and contains(text(), 'PATIENTS')]"
        if not _find_and_click(By.XPATH, patients_xpath):
            print("ERROR: Could not click 'PATIENTS' link for refresh.")

    print("SUCCESS: On Hospital page. Checking for casework...")

    # Ensure the table with casework options is visible
    table_xpath = "//*[@id='holder_table']/form/div[@id='holder_content']/center/table"
    if not _find_element(By.XPATH, table_xpath):
        pass

    table_html = _get_element_attribute(By.XPATH, table_xpath, "innerHTML")
    if not table_html:
        print("No hospital casework table found.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(22, 43))
        return False

    task_clicked = False

    for row in table_html.split("<tr>"):
        if "PROCESS SAMPLE" in row:
            task_clicked = _find_and_click(By.LINK_TEXT, "PROCESS SAMPLE")
            break
        elif "COMMENCE SURGERY" in row:
            if your_character_name not in row:
                task_clicked = _find_and_click(By.LINK_TEXT, "COMMENCE SURGERY", timeout=5)
                break
        elif "START TREATMENT" in row:
            if your_character_name not in row:
                task_clicked = _find_and_click(By.LINK_TEXT, "START TREATMENT", timeout=5)
                break
        elif "PROVIDE ASSISTANCE" in row:
            task_clicked = _find_and_click(By.LINK_TEXT, "PROVIDE ASSISTANCE")
            break

    if task_clicked:
        print("SUCCESS: Casework task initiated.")
        all_timers = get_all_active_game_timers()
        medical_case_time_remaining = all_timers.get('medical_case_time_remaining', 0)
        if medical_case_time_remaining > 0:
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=medical_case_time_remaining)
        else:
            print("No casework tasks found. Setting fallback cooldown.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(8, 14))
        return task_clicked
    else:
        print("No casework tasks found. Setting fallback cooldown.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(8, 14))
        return False

def engineering_casework(player_data):
    """
    Super-simple engineering: open Maintenance & Construction via Income menu,
    pick the first available job, submit. No prioritization.
    """
    import datetime, random, time
    from selenium.webdriver.common.by import By
    import global_vars
    from helper_functions import _navigate_to_page_via_menu, _find_elements

    print("\n--- Beginning Engineering Casework ---")

    # Navigate via menus
    if not _navigate_to_page_via_menu(
        "//span[@class='income']",
        "//a[normalize-space()='Maintenance and Construction']",
        "Maintenance and Construction Page"
    ):
        print("FAILED: Navigation to Maintenance and Construction page failed.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    print("On Maintenance & Construction. Looking for the first available task…")

    # Grab the first visible radio input anywhere under holder_content
    radios = _find_elements(By.XPATH, ".//*[@id='holder_content']//input[@type='radio']")
    if not radios:
        print("No selectable tasks (no radio inputs found). Short cooldown.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(33, 45))
        return False

    # If id prefer the last available radio button instead of first available, change radios[0] to radios[-1]; Should we wish to prioritise cars.
    radio = radios[-1]
    try:
        radio.click()
        time.sleep(global_vars.ACTION_PAUSE_SECONDS)
    except Exception as e:
        print(f"FAILED: Could not click the first radio: {e}")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(33, 45))
        return False

    # Submit the nearest form for that radio (its ancestor form)
    try:
        form = radio.find_element(By.XPATH, "./ancestor::form[1]")
        submit = form.find_element(By.XPATH, ".//input[@type='submit' or @class='submit']")
        submit.click()
        time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
        print("Successfully started the first available engineering task.")
        return True
    except Exception as e:
        print(f"FAILED: Could not submit the selected task: {e}")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(33, 45))
        return False

def judge_casework(player_data):
    """Manages and processes judge cases."""
    print("\n--- Beginning Judge Casework Operation ---")

    if not _navigate_to_page_via_menu(
            "/html/body/div[4]/div[3]/div[6]/a[1]/span",
            "/html/body/div[4]/div[4]/div[1]/div[2]/div/a[1]/strong",
            "Judge Page"
    ):
        print("FAILED: Navigation to Judge Cases Page failed.")
        return False

    print("Successfully navigated to Judge Cases Page. Checking for cases...")

    cases_table = _find_element(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div[2]/form/table")
    if not cases_table:
        print("FAILED: No cases table found.")
        return False

    case_rows = cases_table.find_elements(By.TAG_NAME, "tr")[1:]
    processed_any_case = False

    skip_players = {
        name.strip().lower()
        for name in global_vars.config.get('Judge', 'Skip_Cases_On_Player', fallback='').split(',')
        if name.strip()
    }

    for row in case_rows:
        try:
            suspect_name = row.find_element(By.XPATH, ".//td[3]//a").text.strip()
            victim_name = row.find_element(By.XPATH, ".//td[4]//a").text.strip()

            if player_data['Character Name'] in [suspect_name, victim_name]:
                print(f"Skipping case for self (Suspect: {suspect_name}, Victim: {victim_name}).")
                continue

            if suspect_name.lower() in skip_players or victim_name.lower() in skip_players:
                print(f"Skipping case due to player in skip list (Suspect: {suspect_name}, Victim: {victim_name}).")
                continue

            row.find_element(By.XPATH, ".//td[5]/input[@type='radio']").click()
            time.sleep(global_vars.ACTION_PAUSE_SECONDS)

            if not _find_and_click(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div[2]/form/p/input",
                                   pause=global_vars.ACTION_PAUSE_SECONDS * 2):
                continue

            crime_committed = _get_element_text(
                By.XPATH, "/html/body/div[4]/div[4]/div[3]/div/table/tbody/tr[1]/td[4]"
            )
            if not crime_committed:
                global_vars.driver.get("javascript:history.go(-2)")
                time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
                continue

            if not _find_and_click(
                By.XPATH, "/html/body/div[4]/div[4]/div[3]/div/center/form[1]/p[2]/input",
                pause=global_vars.ACTION_PAUSE_SECONDS * 2
            ):
                continue

            if process_judge_case_verdict(crime_committed, player_data['Character Name']):
                print(f"Successfully processed a case for {suspect_name}.")
                processed_any_case = True
                return True
            else:
                global_vars.driver.get("javascript:history.go(-2)")
                time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
                continue

        except Exception as e:
            print(f"Exception during case processing: {e}")
            continue

    if not processed_any_case:
        cooldown = random.uniform(60, 120)
        print(f"No valid judge cases processed. Waiting {cooldown:.2f} seconds before retry.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=cooldown)

    return False


def process_judge_case_verdict(crime_committed, character_name):
    """Applies fine, sets no community service/jail time, and submits verdict."""
    fine_amount = global_vars.config.getint('Judge', crime_committed, fallback=1000)
    if fine_amount == 1000:
        print(f"Warning: Fine amount for crime '{crime_committed}' not found or invalid in settings.ini. Defaulting to 1000.")

    if not _find_and_send_keys(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div/center/form/p[3]/input", str(fine_amount)):
        return False
    if not _find_and_click(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div/center/form/p[4]/select/option[2]"):
        return False

    jail_time_dropdown = _find_element(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div/center/form/p[5]/select")
    if jail_time_dropdown:
        try:
            no_jail_time_option = jail_time_dropdown.find_element(By.XPATH, "./option[2]")
            no_jail_time_option.click()
        except NoSuchElementException:
            options = jail_time_dropdown.find_elements(By.TAG_NAME, "option")
            min_jail_time_value = float('inf')
            min_jail_time_option = None
            for option in options:
                try:
                    value = int(option.get_attribute('value'))
                    if value > 0 and value < min_jail_time_value:
                        min_jail_time_value = value
                        min_jail_time_option = option
                except ValueError:
                    pass
            if min_jail_time_option:
                min_jail_time_option.click()
            else:
                return False
    else:
        return False

    if not _find_and_click(By.XPATH, "/html/body/div[4]/div[4]/div[2]/div/center/form/p[6]/input", pause=global_vars.ACTION_PAUSE_SECONDS * 2):
        return False
    return True

def lawyer_casework():
    """
    Manages and processes lawyer cases.
    Only works if occupation is 'Lawyer'.
    """
    print("\n--- Beginning Lawyer Casework Operation ---")

    court_menu_xpath = "/html/body/div[4]/div[3]/div[6]/a[1]/span"
    if not _find_and_click(By.XPATH, court_menu_xpath):
        print("FAILED: Navigation to Court menu for Lawyer Cases failed. Setting short cooldown.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(60, 180))
        return False

    print("Successfully navigated to Lawyer Cases Page. Checking for cases...")

    cases_table_xpath = "/html/body/div[4]/div[4]/div[1]/div[2]/center/form/table"
    cases_table = _find_element(By.XPATH, cases_table_xpath)

    processed_any_case = False

    if cases_table:
        case_rows = cases_table.find_elements(By.TAG_NAME, "tr")[1:]

        for i, row in enumerate(case_rows):
            try:
                defend_button_xpath = f".//td[6]/a[@class='box green' and text()='DEFEND']"
                defend_button = _find_element(By.XPATH, defend_button_xpath, timeout=1)

                if defend_button:
                    print(f"Found a defendable case. Clicking DEFEND button.")
                    if _find_and_click(By.XPATH, defend_button_xpath):
                        print(f"Successfully clicked DEFEND for a lawyer case.")
                        processed_any_case = True

                        result_text = _get_element_text(By.XPATH, "/html/body/div[4]/div[4]/div[1]")
                        if result_text:
                            if "managed to defend" in result_text and "successfully" in result_text:
                                print(f"Lawyer case successfully defended: {result_text}")
                                # After successful action, re-read the specific game timer if available
                                new_game_lawyer_time = get_game_timer_remaining("/html/body/div[4]/div[1]/div/div[6]/form/span[2]")
                                if new_game_lawyer_time != float('inf') and new_game_lawyer_time > 0:
                                    global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=new_game_lawyer_time)
                                else:
                                    global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(300, 600))
                            elif "client cannot afford your services" in result_text or "the victim is already dead" in result_text:
                                print(f"Lawyer case failed (client cannot afford/victim dead): {result_text}")
                                global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(180, 300))
                            else:
                                print(f"Lawyer case defended, but unexpected result: {result_text}")
                                global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta( seconds=random.uniform(180, 300))
                        else:
                            print("No result message after defending lawyer case. Setting default cooldown.")
                            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(180, 300))

                        global_vars.driver.get(global_vars.initial_game_url)
                        time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
                        return True

            except NoSuchElementException:
                pass
            except Exception as e:
                print(f"ERROR: Error processing a lawyer case row: {e}. Attempting to return to court page.")
                try:
                    global_vars.driver.get("https://mafiamatrix.net/court/court.asp")
                    time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
                except Exception as back_e:
                    print(f"ERROR: Failed to navigate back to court page after error: {back_e}")
                cases_table = _find_element(By.XPATH, cases_table_xpath)
                if cases_table:
                    case_rows = cases_table.find_elements(By.TAG_NAME, "tr")[1:]
                else:
                    print("CRITICAL: Lawyer cases table not found even after attempting to navigate back. Exiting lawyer casework for this cycle.")
                    return False

    if not processed_any_case:
        wait_time = random.uniform(180, 300)
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
        print(f"No suitable lawyer cases found. Next Lawyer Casework check in {wait_time:.2f} seconds.")

    return processed_any_case

def banker_laundering():
    """
    Manages and performs money laundering services as a banker for other players.
    This function assumes the bot is playing as a Banker and is accepting
    laundering requests from other players.
    """
    print("\n--- Beginning Banker Laundering Service Operation ---")

    # Check if the function is still on cooldown
    if datetime.datetime.now() < getattr(global_vars, '_script_case_cooldown_end_time', datetime.datetime.min):
        remaining_time = (getattr(global_vars, '_script_case_cooldown_end_time') - datetime.datetime.now()).total_seconds()
        print(f"Banker Laundering Service is on cooldown. Remaining: {int(remaining_time)} seconds.")
        return False

    # Navigate to the Banker Laundering page in the bank menu
    try:
        laundering_url = "https://mafiamatrix.net/income/banklaunder.asp"
        global_vars.driver.get(laundering_url)
        time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
        print(f"Successfully navigated directly to: {laundering_url}")
    except Exception as e:
        print(f"FAILED: Could not load banker laundering page: {e}")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    print("Successfully navigated to Banker Laundering Service page. Checking for requests...")

    # Locate the laundering requests table on the page
    requests_table_xpath = "//div[@id='holder_content']/table"
    requests_table = _find_element(By.XPATH, requests_table_xpath)

    if not requests_table:
        print("No banker laundering requests table found.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(180, 300))
        return False

    # Extract all request rows from the table (excluding the header)
    request_rows = requests_table.find_elements(By.TAG_NAME, "tr")[1:]
    if not request_rows:
        print("No pending laundering requests from other players.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(180, 300))
        return False

    # Filter requests to only include those with a balance of $5 or more
    eligible_requests = []
    for row in request_rows:
        try:
            client_name_element = row.find_element(By.XPATH, ".//td[1]")
            client_name = client_name_element.text.strip()

            # XPath to target the correct column for the amount (td[3])
            amount_text_element = row.find_element(By.XPATH, ".//td[3]")
            amount_text = amount_text_element.text.strip()

            # Remove dollar sign, commas, and convert to int
            cleaned_amount_string = amount_text.replace('$', '').replace(',', '').strip()
            amount = 0
            try:
                amount = int(cleaned_amount_string)
            except ValueError:
                # Log a specific warning if the cleaned string still can't be converted to int
                print(f"WARNING: Could not parse amount '{amount_text}' for request from {client_name}. Skipping this request.")
                continue  # Skip to the next row if amount is unparseable

            if amount >= 5:  # Check if amount is $5 or more
                eligible_requests.append(row)
            else:
                print(f"Skipping request from {client_name} with amount ${amount} (less than $5).") # Super spammy, do I want this?

        except NoSuchElementException:
            print("ERROR: Could not find client name or amount element in a laundering request row. Skipping row.")
            continue
        except Exception as e:
            print(f"An unexpected error occurred while parsing a laundering request row: {e}. Skipping row.")
            continue

    if not eligible_requests:
        print("No eligible laundering requests found (all less than $5 or unparseable).")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(180, 300))
        return False

    # Select the first eligible laundering request to process
    selected_request_row = eligible_requests[0] # Changed from random.choice(eligible_requests)

    try:
        # Get the player's name element and its link *from the selected row*
        client_name_link_element = selected_request_row.find_element(By.XPATH, ".//td[1]/a")
        client_name = client_name_link_element.text.strip()

        # Get the amount text from the correct column (td[3]) *from the selected row*
        amount_text_element = selected_request_row.find_element(By.XPATH, ".//td[3]")
        amount_text = amount_text_element.text.strip()

        # Re-parse the amount for the selected launder
        cleaned_amount_string = amount_text.replace('$', '').replace(',', '').strip()
        amount_to_process = 0
        try:
            amount_to_process = int(cleaned_amount_string)
            print(f"Selected request from {client_name} for ${amount_to_process}.")
        except ValueError:
            print(f"WARNING: Could not parse amount '{amount_text}' for selected request from {client_name}. Skipping this request.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(60, 120))
            return False

        # --- STEP 1: Click on the player's name link ---
        # Directly click the element found within the selected row
        try:
            client_name_link_element.click()
            time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2) # Wait for navigation
        except Exception as e:
            print(f"FAILED: Could not click player name link for request from {client_name}: {e}.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
            return False

        print(f"Successfully clicked player name '{client_name}'. Now on the transaction page.")

        # --- STEP 2: Select "Launder Money" from the dropdown ---
        # XPath for the dropdown
        dropdown_xpath = "//select[@name='display']"
        dropdown_element = _find_element(By.XPATH, dropdown_xpath)

        if not dropdown_element:
            print("FAILED: Could not find 'What do you wish to do?' dropdown.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
            return False

        try:
            select = Select(dropdown_element)
            select.select_by_value("result")
            time.sleep(global_vars.ACTION_PAUSE_SECONDS)  # Short pause after selection
            print("Selected 'Launder Money' from the dropdown.")
        except NoSuchElementException:
            print("FAILED: 'Launder Money' option not found in dropdown.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
            return False
        except Exception as select_e:
            print(f"FAILED: Error selecting 'Launder Money' from dropdown: {select_e}.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
            return False

        # --- STEP 3: Click the "Submit" button on the transaction page ---
        submit_button_xpath = "//input[@type='submit' and @value='Submit' and @name='B1']"
        if not _find_and_click(By.XPATH, submit_button_xpath, timeout=global_vars.EXPLICIT_WAIT_SECONDS, pause=global_vars.ACTION_PAUSE_SECONDS * 2):
            print("FAILED: Could not click 'Submit' button after selecting 'Launder Money'.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
            return False

        print("Successfully clicked 'Submit'. Now on the Auto Funds Transfer page.")

        # --- STEP 4: Click "Auto Funds Transfer" button on the next page ---
        auto_funds_transfer_button_xpath = "//input[@type='submit' and @value='Auto Funds Transfer' and @name='B1']"
        if not _find_and_click(By.XPATH, auto_funds_transfer_button_xpath, timeout=global_vars.EXPLICIT_WAIT_SECONDS, pause=global_vars.ACTION_PAUSE_SECONDS * 2):
            print("FAILED: Could not click 'Auto Funds Transfer' button.")
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
            return False

        print(f"Successfully completed laundering and auto-transferred funds for {client_name} (${amount_to_process}).")

        # --- Read the actual game timer for case_time_remaining ---
        all_timers = get_all_active_game_timers()
        case_time_remaining = all_timers.get('case_time_remaining', 0)

        if case_time_remaining > 0:
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=case_time_remaining)
            print(f"Next Banker Laundering check based on game timer: {global_vars._script_case_cooldown_end_time.strftime('%H:%M:%S')}.")
        else:
            # Fallback to 5-10 minutes if game timer cannot be read or is 0
            fallback_cooldown = random.uniform(300, 600)  # 5 to 10 minutes
            global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=fallback_cooldown)
            print(f"Could not read case_time_remaining. Setting fallback cooldown of {int(fallback_cooldown)} seconds.")
        return True

    # Handle expected and unexpected errors during request processing
    except NoSuchElementException:
        print("ERROR: Could not find elements in the selected laundering request row or subsequent pages. Skipping.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False
    except Exception as e:
        print(f"An unexpected error occurred while processing a laundering request: {e}. Setting short cooldown.")
        global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

def banker_add_clients(initial_player_data):
    """
    Manages the process of adding new clients as a Banker.
    Reads aggravated_crime_cooldowns.json to find potential clients
    (players with a home city different from the bot's home city).
    """
    print("\n--- Beginning Banker Add Clients Operation ---")

    # Cooldown check for this specific add clients service
    if datetime.datetime.now() < getattr(global_vars, '_script_bank_add_clients_cooldown_end_time', datetime.datetime.min):
        remaining_time = (getattr(global_vars, '_script_bank_add_clients_cooldown_end_time') - datetime.datetime.now()).total_seconds()
        print(f"Banker Add Clients is on cooldown. Remaining: {int(remaining_time)} seconds.")
        return False

    current_player_home_city = initial_player_data.get("Home City")
    if not current_player_home_city:
        print("ERROR: Could not determine current player's home city. Cannot filter clients.")
        global_vars._script_bank_add_clients_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    print(f"Current player's home city: {current_player_home_city}")

    # Read the aggravated_crime_cooldowns.json file
    cooldowns_data = _read_json_file(global_vars.COOLDOWN_FILE)
    potential_clients = []

    # Identify players with a home city that is NOT the bot's home city
    for player_id, player_data_from_db in cooldowns_data.items():
        db_player_home_city = player_data_from_db.get(global_vars.PLAYER_HOME_CITY_KEY)
        if not db_player_home_city:
            continue

        # Exclude players from the same home city or from 'Hell'
        if db_player_home_city.lower() == current_player_home_city.lower():
            continue
        if db_player_home_city.lower() in ["hell", "heaven"]:
            continue

        # Passed all filters — add to potential clients
        potential_clients.append(player_id)

    if not potential_clients:
        print("No potential clients found with a different home city.")
        global_vars._script_bank_add_clients_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(300, 600))
        return False

    print(f"Found {len(potential_clients)} potential clients to add: {potential_clients}")

    existing_clients = get_existing_banker_clients()

    # Case-insensitive filtering, just in case
    potential_clients = [
        client for client in potential_clients
        if client.lower() not in [ec.lower() for ec in existing_clients]
    ]

    print(f"Filtered potential clients (excluding existing): {potential_clients}")

    if not potential_clients:
        print("All potential clients are already established. Nothing to do.")
        global_vars._script_bank_add_clients_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(hours=random.uniform(7, 9))
        return False

    added_any_client = False

    # Navigate to the Banker page
    try:
        global_vars.driver.get("https://mafiamatrix.net/income/banklaunder.asp")
        time.sleep(global_vars.ACTION_PAUSE_SECONDS)  # Let the page load
    except Exception as e:
        print(f"ERROR: Could not load Banker page: {e}")
        global_vars._script_bank_add_clients_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    # Navigate to the 'Establish New Deal' tab
    add_client_tab_xpath = "//a[text()='Establish New Deal']"
    add_client_link = _find_element(By.XPATH, add_client_tab_xpath)
    if not add_client_link:
        print("FAILED: Could not find 'Establish New Deal' link.")
        global_vars._script_bank_add_clients_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    try:
        add_client_link.click()
        time.sleep(global_vars.ACTION_PAUSE_SECONDS)
    except Exception as e:
        print(f"ERROR: Failed to click 'Establish New Deal' link: {e}")
        global_vars._script_bank_add_clients_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    for client_to_add in potential_clients:
        print(f"\n--- Attempting to add client: {client_to_add} ---")

        # Always navigate to 'Establish New Deal' tab before each client attempt
        add_client_tab_xpath = "//a[text()='Establish New Deal']"
        add_client_link = _find_element(By.XPATH, add_client_tab_xpath)
        if not add_client_link:
            print("FAILED: Could not find 'Establish New Deal' link before adding next client.")
            break

        try:
            add_client_link.click()
            time.sleep(global_vars.ACTION_PAUSE_SECONDS)
        except Exception as e:
            print(f"ERROR: Failed to click 'Establish New Deal' link before adding next client: {e}")
            break

        try:
            gangster_name_input_xpath = "//input[@name='gangster']"
            if not _find_and_send_keys(By.XPATH, gangster_name_input_xpath, client_to_add):
                print(f"FAILED: Could not enter client name '{client_to_add}'. Skipping.")
                continue

            submit_button_xpath = "//input[@type='submit' and @value='Establish Deal']"
            if not _find_and_click(By.XPATH, submit_button_xpath, pause=global_vars.ACTION_PAUSE_SECONDS * 2):
                print(f"FAILED: Could not click submit button for client '{client_to_add}'. Skipping.")
                continue

            fail_element = _find_element(By.ID, "fail", timeout=2, suppress_logging=True)
            if fail_element:
                fail_results = _get_element_attribute(By.ID, "fail", "innerHTML")
                if 'appear to exist' in fail_results:
                    print(f"INFO: Client '{client_to_add}' does not appear to exist (dead/removed). Removing from database.")
                    remove_player_cooldown(client_to_add)
                elif 'from your home city' in fail_results:
                    print(f"INFO: Client '{client_to_add}' is from your home city.")
                    set_player_data(client_to_add, home_city=current_player_home_city)
                elif 'already do business' in fail_results:
                    print(f"INFO: You already do business with '{client_to_add}'. Skipping.")
                else:
                    print(f"WARNING: Unknown failure when adding client '{client_to_add}': {fail_results}")
            else:
                print(f"Successfully added client: {client_to_add}.")
                added_any_client = True

        except Exception as e:
            print(f"An unexpected error occurred while adding client '{client_to_add}': {e}. Skipping.")

    if added_any_client:
        print("Completed Banker Add Clients operation. Some clients were added.")
        # Set a short cooldown as the action was performed
        global_vars._script_bank_add_clients_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(hours=random.uniform(7, 9))
        return True
    else:
        print("No new clients were successfully added in this cycle.")
        # Set a longer cooldown if no clients were added or errors occurred
        global_vars._script_bank_add_clients_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(hours=random.uniform(7, 9))
        return False

def get_existing_banker_clients():
    """
    Scrapes the gangster names the banker already does business with
    from the Laundering Deals table under the 'Gangster' column.
    Ensures it is on the 'Deals' tab first before scraping.
    """
    try:
        # Navigate to the "Deals" tab to ensure the client list is loaded
        deals_tab_xpath = ".//*[@id='content']/div[@id='account_holder']/div[@id='account_nav']/ul/li[1]/a"
        _find_and_click(By.XPATH, deals_tab_xpath, pause=global_vars.ACTION_PAUSE_SECONDS)
        time.sleep(global_vars.ACTION_PAUSE_SECONDS)

        # Grab the HTML content of the clients list
        clients_list_html = global_vars.driver.find_element(
            By.XPATH, ".//*[@id='account_profile']/div[@id='holder_content']").get_attribute("innerHTML")

        existing_clients = []
        if 'no deals' in clients_list_html.lower():
            print("No existing banker clients found.")
            return []

        # Parse HTML rows for client names
        for row in clients_list_html.split("<tr>"):
            if 'display=gangster' in row:
                match = re.search(r'\d+">(.+?)<', row)
                if match:
                    client_name = match.group(1).strip()
                    if client_name:
                        existing_clients.append(client_name)

        print(f"Existing banker clients found: {existing_clients}")
        return existing_clients

    except Exception as e:
        print(f"ERROR: Could not fetch existing banker clients: {e}")
        return []

def fire_casework(initial_player_data):
    """
    Executes firefighting logic (Attend Fires and Fire Safety Inspections)
    Uses case_time_remaining to throttle operations
    """
    print("\n--- Beginning Fire Station Logic ---")

    # Navigate to Fire Station via city menu
    if not _navigate_to_page_via_menu(
        "//span[@class='city']",
        "//a[@class='business fire_station']",
        "Fire Station"
    ):
        print("FAILED: Could not navigate to Fire Station via menu.")
        return False

    print("SUCCESS: Navigated to Fire Station. Checking for active fires...")

    # Attempt to find "Attend Fire" option
    attend_fire_elements = _find_elements(By.XPATH, "//tbody/tr[2]/td[4]/a[1]")
    if attend_fire_elements:
        print("Found active fire. Attending...")
        attend_fire_elements[0].click()
        time.sleep(global_vars.ACTION_PAUSE_SECONDS)
        return True

    # Attempt to find "Investigate" option
    print("No active fires found. Checking for Fire Investigations...")
    investigate_links = _find_elements(By.XPATH, "//a[normalize-space()='Investigate']")
    if investigate_links:
        print("Found Fire Investigation. Investigating...")
        investigate_links[0].click()
        time.sleep(global_vars.ACTION_PAUSE_SECONDS)
        return True

    # No investigations found. Try inspections.
    print("No Fire Investigations found. Checking for Fire Safety Inspections...")
    inspection_tab_xpath = "//a[normalize-space()='Fire safety inspections']"
    if not _find_and_click(By.XPATH, inspection_tab_xpath):
        print("FAILED: Could not navigate to Fire Safety Inspections tab.")
        return False

    # Refresh the inspect link after navigating (avoid stale reference)
    inspect_links = _find_elements(By.XPATH, "//a[normalize-space()='Inspect']")
    for link in inspect_links:
        parent_row = link.find_element(By.XPATH, "./ancestor::tr")
        if initial_player_data.get("Character Name", "") not in parent_row.text:
            print("Found eligible Fire Inspection task. Inspecting...")
            link.click()
            time.sleep(global_vars.ACTION_PAUSE_SECONDS)
            return True

    print("No valid fire inspections available. Setting fallback cooldown.")
    global_vars._script_case_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(180, 300))
    return False

def fire_duties():
    """
    Navigates to firefighter Duties, selects the last available duty, and trains.
    """
    print("\n--- Beginning Fire Fighter Duties ---")

    # Navigate to the Fire Duties page
    if not _navigate_to_page_via_menu(
        "//span[@class='income']",
        "//a[normalize-space()='Fire Fighter Duties']",
        "Fire Fighter Duties"
    ):
        print("FAILED: Could not navigate to Fire Fighter Duties page.")
        return False

    # Find all available radio buttons
    radio_buttons = _find_elements(By.XPATH, "//input[@type='radio' and @name='comservice']")
    if not radio_buttons:
        print("No Fire Duty options found.")
        return False

    # Select the last available option
    last_radio = radio_buttons[-1]
    try:
        last_radio.click()
        print(f"Selected last available duty: {last_radio.get_attribute('value')}")
    except Exception as e:
        print(f"ERROR: Could not click last radio button. {e}")
        return False

    time.sleep(global_vars.ACTION_PAUSE_SECONDS)

    # Click the Train button
    train_buttons = _find_elements(By.XPATH, "//input[@name='B2']")
    if train_buttons:
        train_buttons[0].click()
        print("Clicked Train button.")
        time.sleep(global_vars.ACTION_PAUSE_SECONDS)
        return True
    else:
        print("Train button not found.")
        return False

