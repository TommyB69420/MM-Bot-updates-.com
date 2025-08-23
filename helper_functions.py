import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.select import Select
import global_vars
from database_functions import _write_json_file, _read_json_file
from global_vars import driver, wait, EXPLICIT_WAIT_SECONDS, ACTION_PAUSE_SECONDS, driver

# --- Helper Functions for WebDriver Interactions ---
def _find_element(by_type, value, timeout=EXPLICIT_WAIT_SECONDS, suppress_logging=False):
    """Finds an element using WebDriverWait."""
    try:
        element = wait.until(ec.presence_of_element_located((by_type, value)))
        if element.is_displayed():
            return element
        return None
    except TimeoutException:
        if not suppress_logging:
            if value == "/html/body/div[4]/div[4]/div[1]/div[2]/center/font[3]":
                return None
            print(f"Timeout: Element not found or visible after {timeout:.2f} seconds for {by_type}: {value}")
        return None
    except Exception as e:
        print(f"An error occurred while finding element {by_type}: {value} - {e}")
        return None


def _get_current_url():
    """Gets the current URL using WebDriver."""
    try:
        return driver.current_url
    except Exception as e:
        print(f"Error: could not get current URL - {e}")
        return None # Does None work here?

def _find_elements(by_type, value, timeout=EXPLICIT_WAIT_SECONDS):
    """Finds multiple elements using WebDriverWait."""
    try:
        elements = wait.until(ec.presence_of_all_elements_located((by_type, value)))
        # Filter for visible elements
        visible_elements = [elem for elem in elements if elem.is_displayed()]
        return visible_elements
    except TimeoutException:
        print(f"Timeout: No elements found or visible after {timeout:.2f} seconds for {by_type}: {value}")
        return []
    except Exception as e:
        print(f"An error occurred while finding elements {by_type}: {value} - {e}")
        return []

def _find_and_click(by_type, value, timeout=EXPLICIT_WAIT_SECONDS, pause=ACTION_PAUSE_SECONDS):
    """Finds and clicks an element."""
    element = _find_element(by_type, value, timeout)
    if element:
        try:
            wait.until(ec.element_to_be_clickable((by_type, value))).click()
            time.sleep(pause)
            return True
        except TimeoutException:
            print(f"Timeout: Element not clickable after {timeout:.2f} seconds for {by_type}: {value}")
            return False
        except Exception as e:
            print(f"An error occurred while clicking element {by_type}: {value} - {e}")
            return False
    return False

def _find_and_send_keys(by_type, value, keys, timeout=EXPLICIT_WAIT_SECONDS, pause=ACTION_PAUSE_SECONDS):
    """Finds a text box, clears it, and sends new keys."""
    element = _find_element(by_type, value, timeout)
    if element:
        try:
            element.clear()
            element.send_keys(keys)
            time.sleep(pause)
            return True
        except Exception as e:
            print(f"An error occurred while sending keys to element {by_type}: {value} - {e}")
            return False
    return False

def _get_element_text(by_type, value, timeout=EXPLICIT_WAIT_SECONDS):
    """Gets text from an element."""
    element = _find_element(by_type, value, timeout)
    return element.text.strip() if element else None

def _get_element_attribute(by_type, value, attribute, timeout=EXPLICIT_WAIT_SECONDS):
    """Gets an attribute from an element."""
    element = _find_element(by_type, value, timeout)
    return element.get_attribute(attribute) if element else None

def regex_match_between(start_string, end_string, full_string):
    """Extracts text between two specified strings."""
    try:
        start_index = full_string.find(start_string)
        if start_index == -1:
            return None
        start_index += len(start_string)
        end_index = full_string.find(end_string, start_index)
        if end_index == -1:
            return None
        return full_string[start_index:end_index]
    except Exception as e:
        print(f"Error in regex_match_between: {e}")
        return None

def _navigate_to_page_via_menu(main_menu_xpath, sub_menu_xpath_or_text, page_name):
    """
    Navigates to a specific page via a two-step menu click.
    Sub_menu_xpath_or_text can be an XPath or the exact text of the submenu link.
    """
    print(f"Navigating to {page_name}...")
    if not _find_and_click(By.XPATH, main_menu_xpath):
        print(f"FAILED: Failed to click main menu for {page_name}.")
        return False

    if sub_menu_xpath_or_text.startswith("/"):
        if not _find_and_click(By.XPATH, sub_menu_xpath_or_text, pause=ACTION_PAUSE_SECONDS * 2):
            print(f"FAILED: Failed to click sub-menu for {page_name} using XPath: {sub_menu_xpath_or_text}.")
            return False
    else:
        # Construct a flexible XPath to find the link by its text
        dynamic_sub_menu_xpath = f"//a[normalize-space(text())='{sub_menu_xpath_or_text}']"
        if not _find_and_click(By.XPATH, dynamic_sub_menu_xpath, pause=ACTION_PAUSE_SECONDS * 2):
            print(f"FAILED: Failed to click sub-menu for {page_name} using text: '{sub_menu_xpath_or_text}'.")
            return False

    print(f"Successfully navigated to {page_name}.")
    return True


def _get_dropdown_options(by_type, value, timeout=EXPLICIT_WAIT_SECONDS):
    """
    Retrieves all visible text options from a dropdown element.
    Returns a list of option texts or an empty list if the element is not found or has no options.
    """
    try:
        dropdown_element = wait.until(ec.presence_of_element_located((by_type, value)))
        if not dropdown_element.is_displayed():
            print(f"Dropdown element not visible for {by_type}: {value}")
            return []

        select = Select(dropdown_element)
        options = [option.text for option in select.options if option.text.strip()] # Get text of all options, filter out empty strings
        return options
    except TimeoutException:
        print(f"Timeout: Dropdown element not found after {timeout:.2f} seconds for {by_type}: {value}")
        return []
    except NoSuchElementException:
        print(f"Dropdown element not found for {by_type}: {value}")
        return []
    except Exception as e:
        print(f"An error occurred while getting dropdown options for {by_type}: {value} - {e}")
        return []

def _select_dropdown_option(by_type, value, option_text, timeout=EXPLICIT_WAIT_SECONDS, *, use_value=False):
    """
    Selects an option from a dropdown by its visible text.
    Returns True on success, False otherwise.
    """
    try:
        dropdown_element = wait.until(ec.presence_of_element_located((by_type, value)))
        if not dropdown_element.is_displayed():
            print(f"Dropdown element not visible for {by_type}: {value}")
            return False

        select = Select(dropdown_element)
        if use_value:
            select.select_by_value(option_text)
        else:
            select.select_by_visible_text(option_text)

        time.sleep(ACTION_PAUSE_SECONDS) # Pause after selection
        print(f"Selected '{option_text}'")
        return True
    except TimeoutException:
        print(f"Timeout: Dropdown element not found after {timeout:.2f} seconds for {by_type}: {value}")
        return False
    except NoSuchElementException:
        print(f"Dropdown element not found for {by_type}: {value}")
        return False
    except Exception as e:
        print(f"An error occurred while selecting option '{option_text}' from dropdown {by_type}: {value} - {e}")
        return False

def is_player_in_jail():
    """Returns True if the current URL suggests the player is in jail."""
    current_url = global_vars.driver.current_url
    return "jail" in current_url.lower()

def enqueue_blind_eyes(n: int = 1):
    """Append n units to the Blind Eye queue."""
    os.makedirs(os.path.dirname(global_vars.BLIND_EYE_QUEUE_FILE), exist_ok=True)
    q = _read_json_file(global_vars.BLIND_EYE_QUEUE_FILE) or []
    if not isinstance(q, list):
        q = []
    q.extend(["accepted"] * max(0, int(n)))
    _write_json_file(global_vars.BLIND_EYE_QUEUE_FILE, q)

def dequeue_blind_eye():
    """Consume a single unit from the Blind Eye queue. Return True if dequeued."""
    q = _read_json_file(global_vars.BLIND_EYE_QUEUE_FILE) or []
    if not isinstance(q, list) or not q:
        return False
    q.pop(0)
    _write_json_file(global_vars.BLIND_EYE_QUEUE_FILE, q)
    return True

def blind_eye_queue_count():
    """Current queue count."""
    q = _read_json_file(global_vars.BLIND_EYE_QUEUE_FILE) or []
    return len(q) if isinstance(q, list) else 0
