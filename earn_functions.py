import datetime
import random
import time
from selenium.webdriver.common.by import By
from global_vars import ACTION_PAUSE_SECONDS, config
from helper_functions import _find_and_click, _find_element, _navigate_to_page_via_menu

def _perform_earn_action(earn_name):
    """Clicks a specific earn option and then the 'Work' button."""
    if not _find_and_click(By.XPATH, f"//*[@id='earns_list']//span[normalize-space(text())='{earn_name}']"):
        print(f"FAILED: Could not click earn option '{earn_name}'.")
        return False

    work_button_xpaths = [
        "//*[@id='holder_content']/form/p/input",
        "//*[@id='holder_content']/form/p/button"
    ]

    for xpath in work_button_xpaths:
        if _find_and_click(By.XPATH, xpath):
            print(f"Earn '{earn_name}' completed successfully.")
            return True

    print(f"FAILED: Could not click 'Work' button for '{earn_name}'.")
    return False

def execute_earns_logic():
    """Manages the earn operation, trying quick earn first (via dropdown), then regular menu earn."""
    global _script_earn_cooldown_end_time
    print("\n--- Beginning Earn Operation ---")

    try:
        quick_earn_arrow_xpath = ".//*[@id='nav_left']/p[5]/a[2]/img"
        if _find_element(By.XPATH, quick_earn_arrow_xpath, timeout=1):
            if _find_and_click(By.XPATH, quick_earn_arrow_xpath):
                time.sleep(ACTION_PAUSE_SECONDS)
                if _find_and_click(By.NAME, "lastearn"):
                    print("Quick earn successful via dropdown.")
                    return True
                else:
                    print("Quick earn dropdown clicked but 'lastearn' still not found. Proceeding to regular menu.")
            else:
                print("Failed to click quick earn arrow. Proceeding to regular menu.")
        else:
            print("Quick earn arrow element not found. Proceeding to regular menu.")
    except Exception as e:
        print(f"Error during quick earn attempt: {e}. Proceeding to regular menu.")

    if not _navigate_to_page_via_menu(
            "//*[@id='nav_left']/p[5]/a[1]/span",
            "//*[@id='admintoolstable']/tbody/tr[1]/td/a",
            "Earns Page"
    ):
        print("FAILED: Failed to open Earns menu.")
        _script_earn_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    which_earn = config['Earns Settings'].get('WhichEarn')
    if not which_earn:
        print("ERROR: 'WhichEarn' setting not found in settings.ini under [Earns Settings].")
        _script_earn_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    earns_holder_element = _find_element(By.XPATH, "//*[@id='content']/div[@id='earns_holder']/div[@id='holder_content']")
    earns_table_outer_html = earns_holder_element.get_attribute('outerHTML') if earns_holder_element else ""

    # Dictionary of earns by category
    earn_priority = {
        "Law": ['Parole sitting', 'Judge', 'Lawyer', 'Legal Secretary'],
        "Secrets": ['Whore', 'Joyride', 'Streetfight', 'Pimp', 'Newspaper Editor'],
        "Fire": ['Fire Chief', 'Fire Fighter', 'Volunteer Firefighter'],
        "Gangster": ['Scamming', 'Hack bank account', 'Compete at illegal drags', 'Steal cheques', 'Shoplift'],
        "Engineering": ['Chief Engineer at local Construction Company', 'Engineer at local Construction Site', 'Technician at local vehicle yard', 'Mechanic at local vehicle yard'],
        "Medical": ['Hospital Director', 'Surgeon at local hospital', 'Doctor at local hospital', 'Nurse at local hospital'],
        "Bank": ['Bank Manager', 'Review loan requests', 'Work at local bank']
    }

    final_earn_to_click = which_earn
    if which_earn in earn_priority:
        for option in earn_priority[which_earn]:
            if option in earns_table_outer_html:
                final_earn_to_click = option
                break

    # Perform the selected earn
    if not _perform_earn_action(final_earn_to_click):
        print(f"FAILED: Could not perform earn '{final_earn_to_click}'.")
        _script_earn_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    print(f"Earn action'{final_earn_to_click}' completed completed.")
    return True