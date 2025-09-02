import datetime
import os
import random
import time
import re
from selenium.common import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
import global_vars
from comms_journals import send_discord_notification, _clean_amount
from helper_functions import _find_and_click, _find_element, _navigate_to_page_via_menu, _get_element_text, _get_dropdown_options, _select_dropdown_option, _find_and_send_keys, _get_current_url
from database_functions import set_all_degrees_status, get_all_degrees_status, _set_last_timestamp, _read_json_file, _write_json_file
from timer_functions import get_all_active_game_timers

def study_degrees():
    """
    Manages the process of studying university degrees.
    Checks a config setting to determine if a degree study should be attempted.
    Navigates to the university page, checks for available degrees, and attempts to study them.
    Updates a local file (game_data/all_degrees.json) when all degrees are completed.
    """
    print("\n--- Beginning Study Degrees Operation ---")

    # Check if all degrees are already completed based on a local file
    if get_all_degrees_status():
        print("All degrees already completed according to local data. Skipping operation.")
        return False

    # Navigate to the University Degree page
    if not _navigate_to_page_via_menu(
            "//*[@id='nav_left']/div[3]/a[2]", # Click the city page
            "//*[@id='city_holder']//a[contains(@class, 'business') and contains(@class, 'university')]", # Click University
            "University"):
        print("FAILED: Failed to navigate to University Degree page.")
        # Set a cooldown before retrying, as navigation failed
        global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    # Check if there are no more university studies to complete
    no_more_studies_element = _find_element(By.XPATH, "//*[@id='content']/div[@id='study_holder']/div[@id='holder_content']/p[@class='center']")
    if no_more_studies_element:
        results_text = _get_element_text(By.XPATH, "//*[@id='content']/div[@id='study_holder']/div[@id='holder_content']/p[@class='center']")
        if 'no more university studies to complete' in results_text:
            print("Detected 'no more university studies to complete'. Updating all_degrees.json to True.")
            set_all_degrees_status(True) # Set status to True
            # Set a long cooldown as there's nothing more to do
            global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(days=365)
            return True # Successfully determined all degrees are done

    # Get available dropdown options for degrees
    dropdown_options = _get_dropdown_options(By.XPATH, ".//*[@id='study_holder']/div[@id='holder_content']/form/select")

    degree_selected = False
    if "Yes, I would like to study" in dropdown_options:
        print(f"Dropdown options: {dropdown_options}")
        if _select_dropdown_option(By.XPATH, ".//*[@id='study_holder']/div[@id='holder_content']/form/select", "Yes, I would like to study"):
            if _find_and_click(By.XPATH, "//form//input[@type='submit']", pause=global_vars.ACTION_PAUSE_SECONDS * 2):
                print("Clicked submit to start studying.")
                degree_selected = True
            else:
                print("FAILED: Could not click submit button for 'Yes, I would like to study'.")
        else:
            print("FAILED: Could not select 'Yes, I would like to study' from dropdown.")
    else:
        # Prioritise specific degrees if 'study' is not an option
        degrees_to_check = ["Business", "Science", "Engineering", "Medicine", "Law"]
        for degree in degrees_to_check:
            if degree in dropdown_options:
                print(f"Starting a new degree ('{degree}') — withdrawing $10,000 first.")
                if not withdraw_money(10000):
                    print("FAILED: Could not withdraw $10,000 for new degree.")
                    return False
                if _select_dropdown_option(By.XPATH, ".//*[@id='study_holder']/div[@id='holder_content']/form/select", degree):
                    print(f"Selected '{degree}' degree.")
                    if _find_and_click(By.XPATH, "//form//input[@type='submit']", pause=global_vars.ACTION_PAUSE_SECONDS * 2):
                        print(f"Clicked submit for '{degree}'.")
                        # Confirm the degree study
                        confirm_text = f"Yes, I would like to study for a {degree.lower()} degree"
                        if _select_dropdown_option(By.XPATH, ".//*[@id='study_holder']/div[@id='holder_content']/form/select", confirm_text):
                            print(f"Confirmed study for '{degree}'.")
                            if _find_and_click(By.XPATH, "//form//input[@type='submit']", pause=global_vars.ACTION_PAUSE_SECONDS * 2):
                                print(f"Successfully started studying '{degree}'.")
                                degree_selected = True
                                break # Exit loop after successfully starting a degree
                            else:
                                print(f"FAILED: Could not click final submit button for '{degree}'.")
                        else:
                            print(f"FAILED: Could not confirm study for '{degree}'.")
                else:
                    print(f"FAILED: Could not select '{degree}' from dropdown.")
            if degree_selected:
                break # Break the outer loop if a degree was successfully selected and initiated

    if degree_selected:
        print("Successfully initiated degree study.")
        return True
    else:
        print("No suitable degree options found or could not initiate study.")
        # If no degree was selected, set a slightly longer cooldown before re-checking
        global_vars._script_action_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(300, 600))
        return False

def clean_money_on_hand_logic(initial_player_data):
    """
    Manages clean money: deposits excess using quick deposit and withdraws desired amount from bank.
    Returns True if an action was performed, False otherwise.
    """
    action_performed = False
    clean_money = initial_player_data.get("Clean Money", 0)

    excess_money_on_hand_limit = global_vars.config.getint('Misc', 'ExcessMoneyOnHand', fallback=100000)
    desired_money_on_hand = global_vars.config.getint('Misc', 'MoneyOnHand', fallback=50000)

    # --- Deposit excess money ---
    if clean_money > excess_money_on_hand_limit:
        print(f"Clean money (${clean_money:,}) is above the excess limit (${excess_money_on_hand_limit:,}). Attempting quick deposit.")
        quick_deposit_xpath = "//form[@name='autodepositM']"

        if _find_and_click(By.XPATH, quick_deposit_xpath):
            print("Successfully initiated quick deposit for excess money.")
            action_performed = True
            time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
        else:
            print("Failed to click the quick deposit element.")

    # Withdraw money if under target
    if clean_money < desired_money_on_hand:
        withdraw_amount = desired_money_on_hand - clean_money
        print(f"Clean money (${clean_money:,}) is below desired amount (${desired_money_on_hand:,}). Will attempt to withdraw ${withdraw_amount:,}.")
        if withdraw_amount > 0 and withdraw_money(withdraw_amount):
            action_performed = True

    return action_performed

def withdraw_money(amount: int):
    """
    Withdraws the specified amount of money from the bank.
    Returns True if the withdrawal was successful, False otherwise.
    """
    print(f"Attempting to withdraw ${amount:,} from the bank.")
    initial_url = _get_current_url()

    try:
        # Navigate to Bank page
        if not _navigate_to_page_via_menu(
            "//span[@class='income']",
            "//a[normalize-space()='Bank']",
            "Bank"
        ):
            print("Failed to navigate to the Bank page.")
            return False

        if not _find_and_click(By.XPATH, "//a[normalize-space()='Withdrawal']"):
            print("Failed to click withdrawal button.")
            return False

        if not _find_and_send_keys(By.XPATH, "//input[@name='withdrawal']", str(amount)):
            print("Failed to enter withdrawal amount.")
            return False

        if not _find_and_click(By.XPATH, "//input[@name='B1']"):
            print("Failed to click withdraw submit button.")
            return False

        print(f"Successfully withdrew ${amount:,}.")
        time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
        return True

    finally:
        # Safely return to the previous page
        try:
            if initial_url:
                global_vars.driver.get(initial_url)
                time.sleep(global_vars.ACTION_PAUSE_SECONDS)
        except Exception:
            print("WARNING: Could not return to previous page after withdrawal.")


def transfer_money(amount, recipient):
    """
    Transfers a specified amount of money to another player.

    Args:
        amount (int or float): The amount of money to transfer.
        recipient (str): The exact name of the player receiving the money.

    Returns:
        bool: True if the transfer was successful, False otherwise.
    """
    print(f"\n--- Initiating Money Transfer: ${amount} to {recipient} ---")
    initial_url = _get_current_url()

    try:
        # Navigate to Bank via Income menu
        if not _navigate_to_page_via_menu("//span[@class='income']", "//td[@class='toolitem']//a[normalize-space()='Bank']", "Bank"):
            print("FAILED: Navigation to Bank failed.")
            return False

        # Go to Transfers page
        if not _find_and_click(By.XPATH, "//a[normalize-space()='Transfers']", pause=global_vars.ACTION_PAUSE_SECONDS):
            print("FAILED: Could not click Transfers link.")
            return False

        # Fill out the transfer page
        if not _find_and_send_keys(By.XPATH, "//input[@name='transferamount']", str(amount)):
            print("FAILED: Could not enter transfer amount.")
            return False

        if not _find_and_send_keys(By.XPATH, "//input[@name='transfername']", recipient):
            print("FAILED: Could not enter recipient name.")
            return False

        # Submit the transfer
        if not _find_and_click(By.XPATH, "//input[@id='B1']", pause=global_vars.ACTION_PAUSE_SECONDS):
            print("FAILED: Could not click Submit button.")
            return False

        # Verify transfer success
        success_message = _find_element(By.XPATH, "//div[@id='success']", timeout=3, suppress_logging=True)
        if success_message:
            print(f"SUCCESS: Transferred ${amount} to {recipient} successfully.")
            return True
        else:
            print("WARNING: Transfer may have failed (no success message detected).")
            return False

    except Exception as e:
        print(f"ERROR during money transfer: {e}")
        return False

    finally:
        # Safely return to the previous page
        try:
            if initial_url:
                global_vars.driver.get(initial_url)
                time.sleep(global_vars.ACTION_PAUSE_SECONDS)
        except Exception:
            print("WARNING: Could not return to previous page after transfer.")

def do_events():
    """
    Checks for and attempts the in the game event based on settings.ini.
    Returns True if an action was performed (attacked or cooldown set), False otherwise.
    """

    print("\n--- Beginning Event Operation ---")

    # Click the logo to go to the game home page
    if not _find_and_click(By.XPATH, "//*[@id='logo_hit']"):
        print("Failed to click game logo to navigate to home page.")
        return False
    time.sleep(global_vars.ACTION_PAUSE_SECONDS)

    # Click the button to navigate to the event page
    event_page_button_xpath = "//a[@class='easterboss acceptbutton' and contains(text(), 'help defend your local city')]"
    if not _find_and_click(By.XPATH, event_page_button_xpath):
        print("Event button 'help defend your local city' not found or not clickable.")
        # If the event button is not available, set a cooldown and return. It prevents constant re-checking when no event is active
        print("Setting event re-check cooldown for 5-7 minutes.")
        global_vars._script_event_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(5, 7))
        return False

    time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)

    # Check for the 'ATTACK' button
    attack_button_xpath = "//a[@class='declinebutton' and contains(text(), 'ATTACK')]"
    if _find_and_click(By.XPATH, attack_button_xpath):
        print("Successfully clicked 'ATTACK' button for the event!")
        # If attacked, read the event_time_remaining from timer_functions.py
        all_timers = get_all_active_game_timers()
        event_time_remaining = all_timers.get('event_time_remaining', float('inf'))

        time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)

        if event_time_remaining > 0 and event_time_remaining != float('inf'):
            print(f"Event attack successful. Next event action available in {event_time_remaining:.2f} seconds.")
        else:
            print("Event attack successful, but could not determine event cooldown from game timers. Will re-evaluate soon.")
            # Set a fallback cooldown if the game timer is not immediately available
            global_vars._script_event_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(60, 120))
        return True
    else:
        print("ATTACK button not available on the event page. Event might be on cooldown or completed.")
        # If attack button not available, set a cooldown of 5-7 minutes
        print("Setting event re-check cooldown for 5-7 minutes.")
        global_vars._script_event_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(5, 7))
        return False

def check_weapon_shop(initial_player_data):
    """
    Checks the weapons shop for stock, message discord with results,
    Withdraws money if required and automatically buy top weapons if enabled in settings.ini.
    """
    print("\n--- Beginning Weapon Shop Operation ---")

    # The main loop has already determined this timer is ready, so no need to check again
    print("Timer was marked ready by main loop. Proceeding with Weapon Shop check.")

    # Read settings
    min_check = global_vars.config['Weapon Shop'].getint('MinWSCheck', 13)
    max_check = global_vars.config['Weapon Shop'].getint('MaxWSCheck', 18)
    notify_stock = global_vars.config['Weapon Shop'].getboolean('NotifyWSStock', fallback=True)
    auto_buy_enabled = global_vars.config['Weapon Shop'].getboolean('AutoBuyWS', fallback=False)
    priority_weapons = [w.strip() for w in global_vars.config['Weapon Shop'].get('AutoBuyWeapons', fallback='').split(',')]

    # Navigate to Weapon Shop
    if not _navigate_to_page_via_menu(
        "//span[@class='city']",
        "//p[@class='weapon_shop']",
        "Weapon Shop"
    ):
        print("FAILED: Failed to navigate to Weapon Shop page.")
        global_vars._script_weapon_shop_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    print("Checking weapon shop for available stock...")
    time.sleep(global_vars.ACTION_PAUSE_SECONDS)

    found_weapons_in_stock = False
    weapon_data = {}

    # Check for stock
    try:
        table = global_vars.driver.find_element(By.TAG_NAME, "table")
        rows = table.find_elements(By.TAG_NAME, "tr")

        for row in rows:
            try:
                # Skip header and description rows
                if row.find_elements(By.CLASS_NAME, "column_title"):
                    continue
                if "display_description" in row.get_attribute("class"):
                    continue

                td_elements = row.find_elements(By.TAG_NAME, "td")
                if len(td_elements) < 4:
                    continue  # Not a valid row

                try:
                    item_name_element = td_elements[1].find_element(By.TAG_NAME, "label")
                    item_name = item_name_element.text.strip().split("\n")[0]
                except NoSuchElementException:
                    print("Warning: Couldn't find label element in second column. Skipping row.")
                    continue

                stock_str = td_elements[3].text.strip()
                try:
                    price_str = td_elements[2].text.strip().replace("$", "").replace(",", "")
                    price = int(price_str)
                    stock = int(stock_str)
                except ValueError:
                    print(f"Warning: Could not parse stock value '{stock_str}' for item '{item_name}'. Skipping.")
                    continue

                # Confirm stock level
                if stock >= 1:
                    found_weapons_in_stock = True
                    print(f"{item_name} is in stock! Stock: {stock}")
                    if notify_stock and item_name in priority_weapons:
                        send_discord_notification("@here " f"{item_name} is in stock! Stock: {stock}")
                    weapon_data[item_name] = {"stock": stock, "price": price}
                else:
                    print(f"Item: {item_name}, Stock: {stock} (out of stock)")

            except (StaleElementReferenceException, Exception) as e:
                print(f"Skipping row due to DOM or unknown error: {e}")
                continue

        # Attempt auto-buy if a priortised weapon is in stock
        if found_weapons_in_stock and auto_buy_enabled and priority_weapons:
            for weapon in priority_weapons:
                data = weapon_data.get(weapon)
                if not data or data["stock"] <= 0:
                    continue

                price = data["price"]
                clean_money_text = _get_element_text(By.XPATH, "//div[@id='nav_right']//form[contains(., '$')]")
                clean_money = int(''.join(filter(lambda c: c.isdigit(), clean_money_text))) if clean_money_text else 0

                if clean_money < price:
                    amount_needed = price - clean_money
                    print(f"Not enough clean money to buy {weapon}. Withdrawing ${amount_needed:,}.")
                    withdraw_money(amount_needed)

                auto_buy_weapon(weapon)
                break # Remove this break to buy all weapons in the priority list if multiple is in stock.

        if not found_weapons_in_stock:
            print("No weapons found in stock at the shop currently.")

    # Unable to find the weapon shop table, meaning at max views or page structure has changed.
    except NoSuchElementException:
        print("Error: Could not find the weapon shop table on the page. Page structure might have changed.")
        send_discord_notification("Error: Failed to locate weapon shop table. At max views.")
        global_vars._script_weapon_shop_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(15, 17))
        return False
    except Exception as e:
        print(f"An unexpected error occurred during weapon shop check: {e}")
        send_discord_notification(f"Error during weapon shop check: {e}")
        global_vars._script_weapon_shop_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    # Set the next cooldown timestamp (randomized range from settings.ini)
    next_check_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(min_check, max_check))
    _set_last_timestamp(global_vars.WEAPON_SHOP_NEXT_CHECK_FILE, next_check_time)
    global_vars._script_weapon_shop_cooldown_end_time = next_check_time
    print(f"Weapon Shop check completed. Next check scheduled for {global_vars._script_weapon_shop_cooldown_end_time.strftime('%Y-%m-%d %H:%M:%S')}.")
    return True

def auto_buy_weapon(item_name: str):
    """
    Attempts to auto-buy the specified weapon if auto-buy is enabled and the weapon is whitelisted.
    """
    config = global_vars.config['Weapon Shop']
    auto_buy_enabled = config.getboolean('AutoBuyWS', fallback=False)
    allowed_weapons = [w.strip() for w in config.get('AutoBuyWeapons', fallback='').split(',')]

    if not auto_buy_enabled:
        print(f"[AutoBuy] Skipping {item_name} - AutoBuy is disabled.")
        return

    if item_name not in allowed_weapons:
        print(f"[AutoBuy] Skipping {item_name} - Not in allowed weapons list.")
        return

    print(f"[AutoBuy] Attempting to buy: {item_name}")
    weapon_radio_xpath = f"//input[@id='{item_name}']"
    purchase_button_xpath = "//input[@name='B1']"

    # Try to select the weapon radio button
    selected = _find_and_click(By.XPATH, weapon_radio_xpath)
    if not selected:
        print(f"[AutoBuy] Failed to select radio button for {item_name}")
        return

    # Try to click the purchase button
    purchased = _find_and_click(By.XPATH, purchase_button_xpath)
    if purchased:
        print(f"[AutoBuy] Purchase attempt submitted for {item_name}")
        send_discord_notification(f"Attempting to buy {item_name} from Weapon Shop!")
        time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)

        # Check for success message in div#success
        success_xpath = "//div[@id='success']"
        success_element = _find_element(By.XPATH, success_xpath)

        if success_element:
            print(f"[AutoBuy] SUCCESS: {item_name} purchase confirmed.")
            send_discord_notification(f"Successfully purchased {item_name} from Weapon Shop!")
        else:
            print(f"[AutoBuy] FAILED: No confirmation message found for {item_name}.")
            send_discord_notification(f"Attempted to purchase {item_name}, but failed. The item is gone, no available hands, or insufficient funds.")

def check_drug_store(initial_player_data):
    """
    Checks the Drug Store for stock of Pseudoephedrine and Medipack.
    Withdraws money and purchases if AutoBuy is enabled.
    Sends a Discord alert if stock is found and sets a cooldown if not.
    """
    print("\n--- Beginning Drug Store Operation ---")

    notify_stock = global_vars.config.getboolean('Drug Store', 'NotifyDSStock', fallback=True)

    # Cooldown Check
    if not hasattr(global_vars, '_script_drug_store_cooldown_end_time'):
        global_vars._script_drug_store_cooldown_end_time = datetime.datetime.min

    now = datetime.datetime.now()
    if now < global_vars._script_drug_store_cooldown_end_time:
        minutes_left = (global_vars._script_drug_store_cooldown_end_time - now).total_seconds() / 60
        print(f"Drug Store check on cooldown. Next check in {minutes_left:.2f} minutes.")
        return False

    # Navigation
    if not _navigate_to_page_via_menu(
        "//span[@class='city']",
        "//a[@class='business drug_store']",
        "Drug Store"
    ):
        print("FAILED: Could not navigate to Drug Store.")
        global_vars._script_drug_store_cooldown_end_time = now + datetime.timedelta(seconds=random.uniform(30, 90))
        return False

    print("Checking Drug Store for Pseudoephedrine and Medipack stock...")
    time.sleep(global_vars.ACTION_PAUSE_SECONDS)

    # Extract stock and price for both items
    items_to_check = {
        "Pseudoephedrine": "//label[normalize-space()='Pseudoephedrine']/ancestor::tr",
        "Medipack": "//td[normalize-space()='Medipack']/parent::tr"
    }

    item_data = {}
    found_stock = False

    for name, row_xpath in items_to_check.items():
        row_element = _find_element(By.XPATH, row_xpath)
        if not row_element:
            print(f"{name} row not found on the page.")
            continue

        td_elements = row_element.find_elements(By.TAG_NAME, "td")
        if len(td_elements) < 4:
            print(f"Not enough columns in row for {name}.")
            continue

        price_str = td_elements[2].text.strip().replace("$", "").replace(",", "")
        stock_str = td_elements[3].text.strip()

        try:
            price = int(price_str)
            stock = int(stock_str)
            item_data[name] = {"price": price, "stock": stock}

            if stock > 0:
                print(f"DRUG STORE ALERT: {name} is in stock! Stock: {stock}")
                if notify_stock:
                    send_discord_notification(f"{name} is in stock! Stock: {stock}")
                found_stock = True
            else:
                print(f"{name} is out of stock.")
        except ValueError:
            print(f"Warning: Could not parse price or stock for {name}. Raw values: price='{price_str}', stock='{stock_str}'")

    # Attempt to buy, priortising Medipack over Pseudoephedrine
    for name in ["Medipack", "Pseudoephedrine"]:
        data = item_data.get(name)
        if not data or data["stock"] <= 0:
            continue

        clean_money_text = _get_element_text(By.XPATH, "//div[@id='nav_right']//form[contains(., '$')]")
        clean_money = int(''.join(filter(lambda c: c.isdigit(), clean_money_text))) if clean_money_text else 0
        price = data["price"]

        if clean_money < price:
            amount_needed = price - clean_money
            print(f"Not enough clean money to buy {name}. Withdrawing ${amount_needed:,}.")
            withdraw_money(amount_needed)

        auto_buy_drug_store_item(name)

    if not found_stock:
        print("No stock found for Pseudoephedrine or Medipack.")
        global_vars._script_drug_store_cooldown_end_time = now + datetime.timedelta(minutes=random.uniform(5, 8))
    else:
        print("Stock was found, no cooldown set for Drug Store check.")

    print(f"Drug Store check complete.")
    return True

def auto_buy_drug_store_item(item_name: str):
    """
    Attempts to auto-buy the specified drug store item if AutoBuyDS is enabled in settings.ini.
    Sends Discord notification only if a success message is detected.
    """
    config = global_vars.config['Drug Store']
    auto_buy_enabled = config.getboolean('AutoBuyDS', fallback=False)

    if not auto_buy_enabled:
        print(f"[AutoBuy] Skipping {item_name} - AutoBuyDS is disabled in settings.ini.")
        return

    print(f"[AutoBuy] Attempting to buy: {item_name}")
    item_radio_xpath = f"//input[@id='{item_name}']"
    purchase_button_xpath = "//input[@name='B1']"
    success_message_xpath = "//div[@id='success' and (contains(text(), 'You keep') or contains(text(), 'something special'))]"

    # Try to select the radio button
    selected = _find_and_click(By.XPATH, item_radio_xpath)
    if not selected:
        print(f"[AutoBuy] Failed to select radio button for {item_name}")
        return

    # Try to click the purchase button
    purchased = _find_and_click(By.XPATH, purchase_button_xpath)
    send_discord_notification(f"Attempting to buy {item_name} from Drug Store.")
    if not purchased:
        print(f"[AutoBuy] Failed to click purchase button for {item_name}")
        return

    print(f"[AutoBuy] Clicked purchase button for {item_name}, waiting for success message...")
    time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)

    # Look for the success message
    success_element = _find_element(By.XPATH, success_message_xpath)
    if success_element:
        success_text = success_element.text.strip()
        print(f"[AutoBuy] SUCCESS: {success_text}")
        send_discord_notification(f"Purchased {item_name} from Drug Store.")

        # Set a cooldown after a successful purchase.
        global_vars._script_drug_store_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
        print(f"[AutoBuy] Drug Store cooldown set until {global_vars._script_drug_store_cooldown_end_time}")
    else:
        print(f"[AutoBuy] WARNING: No success message found after purchasing {item_name}.")
        global_vars._script_drug_store_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
        send_discord_notification(f"Failed to purchase {item_name} from Drug Store. The item is gone, or insufficient funds.")

def check_bionics_shop(initial_player_data):
    """
    Checks the Bionics Shop for stock, notifies Discord if enabled,
    and attempts auto-buy if enabled and affordable.
    """
    print("\n--- Beginning Bionics Shop Operation ---")

    # Settings
    config = global_vars.config['Bionics Shop']
    min_check = config.getint('MinBiosCheck', 11)
    max_check = config.getint('MaxBiosCheck', 13)
    notify_stock = config.getboolean('NotifyBSStock', fallback=True)
    auto_buy_enabled = config.getboolean('DoAutoBuyBios', fallback=False)
    priority_bionics = [b.strip() for b in config.get('AutoBuyBios', fallback='').split(',')]

    # Navigation
    if not _navigate_to_page_via_menu("//span[@class='city']",
                                      "//a[@class='business bionics']",
                                      "Bionics Shop"):
        print("FAILED: Could not navigate to Bionics Shop.")
        next_check = datetime.datetime.now() + datetime.timedelta(seconds=random.uniform(30, 90))
        _set_last_timestamp(global_vars.BIONICS_SHOP_NEXT_CHECK_FILE, next_check)
        return False

    print("Checking Bionics Shop for available stock...")
    time.sleep(global_vars.ACTION_PAUSE_SECONDS)

    found_bionics_in_stock = False
    bionic_data = {}

    try:
        rows = global_vars.driver.find_elements(By.XPATH, "//table//tr[td/input[@type='radio']]")
        for row in rows:
            try:
                radio = row.find_element(By.XPATH, ".//input[@type='radio']")
                radio_id = radio.get_attribute("value")
                name = row.find_element(By.TAG_NAME, "label").text.strip().split("\n")[0]
                print(f"[DEBUG] Parsed: {name} | Value: {radio.get_attribute('value')} | ID: {radio.get_attribute('id')}")
                price = int(row.find_elements(By.TAG_NAME, "td")[2].text.strip().replace("$", "").replace(",", ""))
                stock = int(row.find_elements(By.TAG_NAME, "td")[3].text.strip())
            except Exception as e:
                print(f"Skipping row due to parse error: {e}")
                continue

            if stock > 0:
                found_bionics_in_stock = True
                print(f"{name} is in stock! Stock: {stock}")
                if notify_stock and name in priority_bionics:
                    send_discord_notification(f"@here {name} is in stock! Stock: {stock}")
                bionic_data[name] = {"stock": stock, "price": price, "id": radio_id}
            else:
                print(f"{name} is out of stock.")

        if found_bionics_in_stock and auto_buy_enabled:
            for bionic in priority_bionics:
                data = bionic_data.get(bionic)
                if not data or data["stock"] <= 0:
                    continue

                price = data["price"]
                clean_money_text = _get_element_text(By.XPATH, "//div[@id='nav_right']//form[contains(., '$')]")
                clean_money = int(''.join(filter(str.isdigit, clean_money_text))) if clean_money_text else 0

                if clean_money < price:
                    amount_needed = price - clean_money
                    print(f"Not enough clean money to buy {bionic}. Withdrawing ${amount_needed:,}.")
                    withdraw_money(amount_needed)

                auto_buy_bionic(bionic, data["id"])
                break

        if not found_bionics_in_stock:
            print("No bionics found in stock.")

    except Exception as e:
        print(f"Error during Bionics Shop check: {e}")
        send_discord_notification(f"Error: Failed during Bionics Shop check. At max views {e}")
        next_check = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(10, 13))
        _set_last_timestamp(global_vars.BIONICS_SHOP_NEXT_CHECK_FILE, next_check)
        return False

    next_check = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(min_check, max_check))
    _set_last_timestamp(global_vars.BIONICS_SHOP_NEXT_CHECK_FILE, next_check)
    print(f"Bionics Shop check complete. Next check at {next_check.strftime('%Y-%m-%d %H:%M:%S')}.")
    return True

def auto_buy_bionic(item_name: str, item_id: str):
    """
    Attempts to buy a bionic if it's allowed by settings.
    """
    config = global_vars.config['Bionics Shop']
    if not config.getboolean('DoAutoBuyBios', fallback=False):
        print(f"[AutoBuy] Skipping {item_name} - AutoBuy disabled.")
        return

    allowed_items = [b.strip() for b in config.get('AutoBuyBios', fallback='').split(',')]
    if item_name not in allowed_items:
        print(f"[AutoBuy] Skipping {item_name} - Not in allowed list.")
        return

    print(f"[AutoBuy] Attempting to buy: {item_name}")
    radio_xpath = f"//input[@type='radio' and @value='{item_id}']"
    purchase_xpath = "//input[@name='B1']"

    if not _find_and_click(By.XPATH, radio_xpath):
        print(f"[AutoBuy] Failed to select {item_name}. XPath attempted: {radio_xpath}")
        return

    if not _find_and_click(By.XPATH, purchase_xpath):
        print(f"[AutoBuy] Failed to click purchase for {item_name}.")
        return

    send_discord_notification(f"Attempting to buy {item_name} from Bionics Shop...")
    time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)

    success = _find_element(By.XPATH, "//div[@id='success']")
    if success:
        print(f"[AutoBuy] SUCCESS: Purchased {item_name}.")
        send_discord_notification(f"Successfully bought {item_name} from Bionics Shop!")
    else:
        print(f"[AutoBuy] FAILED: No confirmation for {item_name}.")
        send_discord_notification(f"Failed to purchase {item_name}. It might be gone, you may not have free hands, or funds were insufficient.")

def jail_work():
    """
    Executes jail earn jobs and gym workout, obeying earn/action timers.
    Picks the last available job (except 'makeshank', unless enabled in settings.ini).
    """
    print("\n--- Jail Detected: Executing Jail Work ---")

    # --- EARN JOB SELECTION ---
    if global_vars.jail_timers.get("earn_time_remaining", 999) <= 0:
        print("Earn timer ready. Attempting jail earn job.")

        if _find_and_click(By.XPATH, "//span[@class='income']"):
            try:
                # Check Settings.ini to determine if making a shank is enabled
                make_shank = global_vars.config.getboolean("Earns Settings", "MakeShank", fallback=False)
                dig_tunnel = global_vars.config.getboolean("Earns Settings", "DigTunnel", fallback=False)

                # Find all duties radio buttons
                all_jobs = global_vars.driver.find_elements(By.XPATH, "//input[@type='radio' and @name='job']")

                # Filter the duties into a list, excluding makeshank and dig tunnel unless enabled. Jailappeal will always be off
                valid_jobs = [
                    job for job in all_jobs
                    if job.get_attribute("id") not in {"makeshank", "digtunnel", "jailappeal"}
                       or (job.get_attribute("id") == "makeshank" and make_shank)
                       or (job.get_attribute("id") == "digtunnel" and dig_tunnel)
                ]

                if valid_jobs:
                    # Select the last valid duty
                    last_job = valid_jobs[-1]
                    job_id = last_job.get_attribute("id")
                    print(f"Selecting job: {job_id}")
                    last_job.click()

                    # Click submit
                    if _find_and_click(By.XPATH, "//input[@name='B1']"):
                        print(f"Successfully completed jail job: {job_id}")
                    else:
                        print("FAILED: Couldn't click 'Work' button.")
                else:
                    print("No valid jobs found (MakeShank disabled?).")
            except Exception as e:
                print(f"ERROR: Exception while processing earn jobs: {e}")
        else:
            print("FAILED: Couldn't open Earn (income) tab.")
    else:
        print(f"Earn timer not ready ({global_vars.jail_timers['earn_time_remaining']:.1f} sec left)")

    # --- GYM WORKOUT (action timer) ---
    if global_vars.jail_timers.get("action_time_remaining", 999) <= 0:
        print("Action timer ready. Attempting Gym Workout.")
        if _find_and_click(By.XPATH, "//span[@class='family']"):
            if _find_and_click(By.XPATH, "//input[@id='gym']"):
                if _find_and_click(By.XPATH, "//input[@name='B1']"):
                    print("Successfully completed Gym Workout.")
                else:
                    print("FAILED: Couldn't click 'Submit' button.")
            else:
                print("FAILED: Couldn't click 'Gym' radio.")
    else:
        print(f"Action timer not ready ({global_vars.jail_timers['action_time_remaining']:.1f} sec left)")

def gym_training():
    """
    Attempts to perform gym training if 12h cooldown has passed.
    Buys membership card if required, withdraws funds if necessary.
    Updates cooldown file on success.
    """
    print("\n--- Beginning Gym Training Operation ---")

    now = datetime.datetime.now()

    # Navigate to Gym
    if not _navigate_to_page_via_menu(
        "//span[@class='city']",
        "//a[@class='business gym']",
        "Gym"
    ):
        print("FAILED: Could not navigate to Gym.")
        return False

    dropdown_xpath = ".//*[@class='input']"
    dropdown_options = _get_dropdown_options(By.XPATH, dropdown_xpath)

    if not dropdown_options:
        print("FAILED: Could not find gym dropdown options.")
        return False

    if any("membership card" in option.lower() for option in dropdown_options):
        print("Membership required. Attempting to withdraw $10,000...")

        # Withdraw money for membership
        if not withdraw_money(10000):
            print("FAILED: Could not withdraw money for membership.")
            return False

        dropdown_options = _get_dropdown_options(By.XPATH, dropdown_xpath)
        if not dropdown_options or not any("membership card" in option.lower() for option in dropdown_options):
            print("FAILED: Gym membership option not present after returning.")
            return False

        if not _select_dropdown_option(By.XPATH, dropdown_xpath, "Purchase 1 week membership card"):
            print("FAILED: Could not select membership option.")
            return False
        if not _find_and_click(By.XPATH, "//form//input[@type='submit']"):
            print("FAILED: Could not submit membership purchase.")
            return False

        print("Successfully purchased gym membership.")
        return True  # Stop here, training will be available next cycle

    # Proceed with training
    print("Proceeding with gym training...")
    if not _select_dropdown_option(By.XPATH, dropdown_xpath, "Have a spa/sauna"):
        print("FAILED: Could not select training option.")
        return False
    if not _find_and_click(By.XPATH, "//form//input[@type='submit']"):
        print("FAILED: Could not submit gym training.")
        return False

    print("Gym training completed successfully.")
    cooldown = now + datetime.timedelta(hours=12, seconds=random.randint(60, 360))
    _set_last_timestamp(global_vars.GYM_TRAINING_FILE, cooldown)
    print(f"Next gym training available at {cooldown.strftime('%Y-%m-%d %H:%M:%S')}")
    return True

def police_training():
    """
    Handles police training sign-up and progression.
    Dynamically stops after completing the required number of training sessions (e.g. 15, 30, etc.).
    """

    # Skip if already marked complete in game_data
    try:
        if _read_json_file(global_vars.POLICE_TRAINING_DONE_FILE) is True:
            print("Police training already marked complete — skipping.")
            return False
    except Exception as e:
        print(f"WARNING: Could not read police training flag: {e}")

    print("\n--- Starting Police Training Operation ---")

    # Navigate to the Police Recruitment page
    if not _navigate_to_page_via_menu(
        "//span[@class='city']",
        "//a[@class='business police']",
        "Police Training"):
        return False

    success_box_xpath = "//div[@id='success']"

    # If the first-time option exists, click it; otherwise select "Yes" (continue)
    accept_opt = _find_element(By.XPATH, "//option[@value='acceptpolice']", timeout=1, suppress_logging=True)

    if accept_opt:
        print("Step: Signing up for Police Training.")
        if not _find_and_click(By.XPATH, "//option[@value='acceptpolice']"):
            print("FAILED: Could not click 'Yes, I would like to join' option.")
            return False
    else:
        print("Step: Continuing Police Training (subsequent training).")
        yes_option_xpath = "//select[@name='action']/option[@value='Yes']"

        # Try to click "Yes", with one retry after focusing the dropdown
        if not _find_and_click(By.XPATH, yes_option_xpath):
            _find_and_click(By.XPATH, "//select[@name='action']")
            if not _find_and_click(By.XPATH, yes_option_xpath):
                print("FAILED: Could not select 'Yes' from dropdown.")
                return False

    # Submit the form
    if not _find_and_click(By.XPATH, "//input[@name='B1']"):
        print("FAILED: Could not click Submit.")
        return False

    # Check training progress to determine how many trains left to do
    success_text = _get_element_text(By.XPATH, success_box_xpath)
    if success_text:
        print(f"Success Message: '{success_text}'")
        match = re.search(r"\((\d+)\s+of\s+(\d+)\s+studies\)", success_text)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            print(f"Training Progress: {current}/{total}")
        else:
            print("WARNING: Could not parse training progress.")
    else:
        print("No success box found — likely finished training.")
        #Check for completion paragraph
        final_text = _get_element_text(By.XPATH, "//div[@id='content']//p[1]") or ""
        if "your hard work" in final_text.lower():
            _write_json_file(global_vars.POLICE_TRAINING_DONE_FILE, True)
            print("FINAL SUCCESS: Police training is now fully complete.")
            return False

    print("Police training step completed successfully.")
    return True

def combat_training():
    """
    Combat Training driver:
      - If already marked complete, skip.
      - Navigate: City -> Training Centre.
      - If dropdown shows a course (Karate/Muay Thai/Jui Jitsu/MMA):
          * Select configured course ([Actions Settings] Training)
          * Submit to show info paragraph; parse one-off $fee
          * Withdraw shortfall; reselect course; submit
          * On confirmation, select 'Yes...' and submit
          * Stop script for manual review (first run only)
      - Else if dropdown shows 'Yes, I would like to train':
          * Select 'Yes'; submit
          * Read progress from //p[@class='center'] e.g. "(3 of 15 studies)"
          * If complete, write game_data/combat_training_completed.json = true
    """

    # file to mark completion
    COMBAT_DONE_FILE = os.path.join(global_vars.COOLDOWN_DATA_DIR, "combat_training_completed.json")

    # Skip if already marked complete
    try:
        if _read_json_file(COMBAT_DONE_FILE) is True:
            print("Combat training already marked complete — skipping.")
            return False
    except Exception:
        pass

    print("\n--- Beginning Combat Training Operation ---")

    # Desired course from settings
    course_name = global_vars.config.get('Actions Settings', 'Training', fallback='').strip()
    if not course_name:
        print("FAILED: Set [Actions Settings] Training = (Jui Jitsu | Muay Thai | Karate | MMA)")
        return False

    # Navigate to Training Centre
    if not _navigate_to_page_via_menu("//span[@class='city']",
                                      "//a[@class='business training']",
                                      "Training Centre"):
        print("FAILED: Could not navigate to Training Centre.")
        return False

    time.sleep(global_vars.ACTION_PAUSE_SECONDS)

    dropdown_xpath = "//select[@name='action']"
    submit_xpath   = "//input[@name='B1']"

    # What options are currently shown?
    opts = _get_dropdown_options(By.XPATH, dropdown_xpath) or []
    opts_lower = [o.lower() for o in opts]

    # Subsequent trains (Yes/No)
    if any("yes" in o for o in opts_lower):
        # Select the "Yes" option and submit
        yes_text = next((o for o in opts if "yes" in o.lower()), "Yes")
        if not _select_dropdown_option(By.XPATH, dropdown_xpath, yes_text):
            print("FAILED: Could not select 'Yes' to continue training.")
            return False
        if not _find_and_click(By.XPATH, submit_xpath):
            print("FAILED: Could not click Submit to continue training.")
            return False

        # Check for final completion phrase in first paragraph
        final_p_xpath = "//div[@id='content']//p[1]"
        final_p_text = (_get_element_text(By.XPATH, final_p_xpath) or "").strip()
        print(f"Post-train message: {final_p_text!r}")

        if "proud to award you with bonus stats for your" in final_p_text.lower():
            print("Combat training complete (bonus stats message detected). Writing completion flag.")
            _write_json_file(COMBAT_DONE_FILE, True)
            return True

        print("Submitted subsequent combat training step.")
        return True

    # FIRST SIGN-UP - Validate configured course is present
    if course_name not in opts:
        print(f"FAILED: Desired course '{course_name}' not found. Options: {opts}")
        return False

    # Select course & submit
    if not _select_dropdown_option(By.XPATH, dropdown_xpath, course_name):
        print(f"FAILED: Could not select '{course_name}'.")
        return False
    if not _find_and_click(By.XPATH, submit_xpath):
        print("FAILED: Could not click initial Submit for course selection.")
        return False

    # Parse one-off price from info paragraph
    blurb = _get_element_text(By.XPATH, "//p[contains(text(),'The Training Centre in') and contains(text(),'offers')]")
    if not blurb:
        print("FAILED: Could not find the training info paragraph to parse price.")
        return False

    m = re.search(r"\$\s*([\d,]+)", blurb)
    if not m:
        print(f"FAILED: Could not parse price from paragraph: {blurb}")
        return False
    price = int(m.group(1).replace(",", ""))
    print(f"Parsed course fee: ${price:,}")

    # Determine clean cash (best effort) and withdraw shortfall
    current_clean = 0
    try:
        clean_text = _get_element_text(By.XPATH, "//div[@id='nav_right']//form")
        if clean_text:
            digits = "".join(ch for ch in clean_text if ch.isdigit())
            if digits:
                current_clean = int(digits)
    except Exception:
        pass

    need = max(0, price - current_clean)
    if need > 0:
        print(f"Withdrawing ${need:,} to cover fee.")
        if not withdraw_money(need):
            print("FAILED: Withdrawal failed.")
            return False
        # Back the Training Centre after withdraw_money()

    # Reselect course & submit again
    if not _select_dropdown_option(By.XPATH, dropdown_xpath, course_name):
        print(f"FAILED: Could not reselect '{course_name}' after withdrawal.")
        return False
    if not _find_and_click(By.XPATH, submit_xpath):
        print("FAILED: Could not click Submit after reselecting the course.")
        return False

    # Pick the 'Yes' option and submit
    confirm_opts = _get_dropdown_options(By.XPATH, dropdown_xpath) or []
    yes_text = next((o for o in confirm_opts if "yes" in o.lower()), None)
    picked = False
    if yes_text:
        picked = _select_dropdown_option(By.XPATH, dropdown_xpath, yes_text)
    if not picked:
        picked = _select_dropdown_option(By.CSS_SELECTOR, "select[name='action']", "accept", use_value=True)
    if not picked:
        print(f"FAILED: Could not select the 'Yes' confirmation option. Options: {confirm_opts}")
        return False

    if not _find_and_click(By.XPATH, submit_xpath):
        print("FAILED: Could not click final Submit on confirmation.")
        return False

    print("Combat training submitted successfully — stopping now for manual review.")
    raise SystemExit("Combat training submitted — manual review requested.")

def fire_training():
    """
    Handles fire training sign-up and progression.
    Dynamically stops after completing the required number of training sessions (e.g. 15, 30, etc.).
    """

    # Skip if already marked complete in game_data
    try:
        if _read_json_file(global_vars.FIRE_TRAINING_DONE_FILE) is True:
            print("Fire training already marked complete — skipping.")
            return False
    except Exception as e:
        print(f"WARNING: Could not read fire training flag: {e}")

    print("\n--- Starting Fire Training Operation ---")

    # Navigate to Fire Recruitment page
    if not _navigate_to_page_via_menu(
        "//span[@class='city']",
        "//a[@class='business fire_station']",
        "Fire Training"):
        return False

    success_box_xpath = "//div[@id='success']"

    # If the first-time option exists, click it; otherwise select "Yes" (continue)
    accept_opt = _find_element(By.XPATH, "//option[@value='acceptfire']", timeout=1, suppress_logging=True)

    if accept_opt:
        print("Step: Signing up for Fire Training.")
        if not _find_and_click(By.XPATH, "//option[@value='acceptfire']"):
            print("FAILED: Could not click 'Yes, I would like to join' option.")
            return False
    else:
        print("Step: Continuing Fire Training (subsequent training).")
        yes_option_xpath = "//select[@name='action']/option[@value='Yes']"

        # Try to click "Yes", with one retry after focusing the dropdown
        if not _find_and_click(By.XPATH, yes_option_xpath):
            _find_and_click(By.XPATH, "//select[@name='action']")
            if not _find_and_click(By.XPATH, yes_option_xpath):
                print("FAILED: Could not select 'Yes' from dropdown.")
                return False

    # Submit the form
    if not _find_and_click(By.XPATH, "//input[@name='B1']"):
        print("FAILED: Could not click Submit.")
        return False

    # Check training progress to determine how many trains left to do
    success_text = _get_element_text(By.XPATH, success_box_xpath)
    if success_text:
        print(f"Success Message: '{success_text}'")
        match = re.search(r"\((\d+)\s+of\s+(\d+)\s+studies\)", success_text)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            print(f"Training Progress: {current}/{total}")
        else:
            print("WARNING: Could not parse training progress.")
    else:
        print("No success box found — likely finished training.")
        # Final fallback: Check for completion paragraph
        final_text = _get_element_text(By.XPATH, "//div[@id='content']//p[1]") or ""
        if "your hard work" in final_text.lower():
            _write_json_file(global_vars.FIRE_TRAINING_DONE_FILE, True)
            print("FINAL SUCCESS: Fire training is now fully complete.")
            return False

    print("Fire training step completed successfully.")
    return True

def customs_training():
    """
    Handles customs training sign-up and progression.
    Dynamically stops after completing the required number of training sessions (e.g. 15, 30, etc.).
    """

    # Skip if already marked complete in game_data
    try:
        if _read_json_file(global_vars.CUSTOMS_TRAINING_DONE_FILE) is True:
            print("Customs training already marked complete — skipping.")
            return False
    except Exception as e:
        print(f"WARNING: Could not read customs training flag: {e}")

    print("\n--- Starting Customs Training Operation ---")

    # Navigate to Customs Recruitment page
    if not _navigate_to_page_via_menu(
        "//span[@class='city']",
        "//a[@class='business customs']",
        "Customs Training"):
        return False

    success_box_xpath = "//div[@id='success']"

    # If the first-time option exists, click it; otherwise select "Yes" (continue)
    accept_opt = _find_element(By.XPATH, "//option[@value='acceptcustoms']", timeout=1, suppress_logging=True)

    if accept_opt:
        print("Step: Signing up for Customs Training.")
        if not _find_and_click(By.XPATH, "//option[@value='acceptcustoms']"):
            print("FAILED: Could not click 'Yes, I would like to join' option.")
            return False
    else:
        print("Step: Continuing Customs Training (subsequent training).")
        yes_option_xpath = "//select[@name='action']/option[@value='Yes']"

        # Try to click "Yes", with one retry after focusing the dropdown
        if not _find_and_click(By.XPATH, yes_option_xpath):
            _find_and_click(By.XPATH, "//select[@name='action']")
            if not _find_and_click(By.XPATH, yes_option_xpath):
                print("FAILED: Could not select 'Yes' from dropdown.")
                return False

    # Submit the form
    if not _find_and_click(By.XPATH, "//input[@name='B1']"):
        print("FAILED: Could not click Submit.")
        return False

    # Check training progress to determine how many trains left to do
    success_text = _get_element_text(By.XPATH, success_box_xpath)
    if success_text:
        print(f"Success Message: '{success_text}'")
        match = re.search(r"\((\d+)\s+of\s+(\d+)\s+studies\)", success_text)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            print(f"Training Progress: {current}/{total}")
        else:
            print("WARNING: Could not parse training progress.")
    else:
        print("No success box found — likely the initial join step or a layout change.")
        # Final fallback: Check for completion paragraph
        final_text = _get_element_text(By.XPATH, "//div[@id='content']//p[1]") or ""
        if "your hard work" in final_text.lower():
            _write_json_file(global_vars.CUSTOMS_TRAINING_DONE_FILE, True)
            print("FINAL SUCCESS: Customs training is now fully complete.")
            return False

    print("Customs training step completed successfully.")
    return True

def map_promo_choice(promo_name: str):
    """
    Lookup-based promo choice against global_vars.PROMO_MAP.
    Returns 'one' or 'two' if a keyword matches, else None for manual.
    """
    key = (promo_name or "").lower().strip()
    for keyword, choice in global_vars.PROMO_MAP.items():
        if keyword in key:
            return choice
    return None


def take_promotion():
    """
    Automatically checks and takes promotions:
      - Reads [Misc] TakePromo in settings.ini
      - Clicks the MMM logo to trigger promo
      - If on Promotion page, picks mapped option and continues
      - Notifies Discord
    Returns True if a promotion was taken; False otherwise.
    """

    print("\n--- Promotion Check ---")

    # Click the MM logo which triggers promo if one exists
    if not _find_and_click(By.XPATH, "//*[@id='logo_hit']", pause=global_vars.ACTION_PAUSE_SECONDS):
        print("Promo: Could not click logo.")
        return False

    time.sleep(global_vars.ACTION_PAUSE_SECONDS)

    curr_url = (_get_current_url() or "").lower()
    if "promotion" not in curr_url:
        print("Promo: No promotion detected.")
        global_vars._script_promo_check_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(2, 4))
        return False

    print("Promo page detected — parsing details...")

    # Read promo header
    header_el = _find_element(By.XPATH, "//*[@id='holder_top']/h1")
    promo_name = (header_el.text if header_el else "").strip()
    if not promo_name:
        print("Promo: Could not read promotion header.")
        return False

    print(f"Detected Promotion: {promo_name}")

    choice = map_promo_choice(promo_name)
    if choice not in {"one", "two"}:
        msg = f"Unable to auto-take promotion — manual action required: {promo_name}"
        print("Promo:", msg)
        global_vars._script_promo_check_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(2, 4))
        try:
            send_discord_notification(msg)
        except Exception:
            pass
        return False

    # Click the mapped option
    if not _find_and_click(By.ID, choice, pause=global_vars.ACTION_PAUSE_SECONDS):
        print(f"Promo: Could not click option '{choice}'.")
        global_vars._script_promo_check_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(2, 4))
        return False

    # Continue
    if not _find_and_click(By.XPATH, "//*[@id='holder_content']/form/center/input", pause=global_vars.ACTION_PAUSE_SECONDS):
        print("Promo: Could not click Continue.")
        global_vars._script_promo_check_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(minutes=random.uniform(2, 4))
        return False

    print("Promo: Continue clicked — promotion accepted.")
    try:
        send_discord_notification(f"Taking promotion: {promo_name}")
    except Exception:
        pass

    setattr(global_vars, "force_reselect_earn", True)
    print("Promo: Flag set to force reselecting earn on next cycle.")

    return True

def consume_drugs():
    """
    Consumes Cocaine up to the [Drugs] ConsumeLimit (per 24h counter).
    After each consumption, runs the last earn to use the reset earn timer.
    Assumes it's only called when consume_drugs_time_remaining == 0.
    Returns True if at least one consumption/earn happened; otherwise False.
    """
    print("\n--- Beginning Consume Drugs Operation ---")

    # Local constant for file path (text file)
    DRUGS_LAST_CONSUMED_FILE = os.path.join(global_vars.COOLDOWN_DATA_DIR, "drugs_last_consumed.txt")

    # Config
    try:
        limit = global_vars.config.getint('Drugs', 'ConsumeLimit', fallback=0)
    except Exception:
        limit = 0

    if limit <= 0:
        print("Consume Drugs disabled or limit <= 0. Skipping.")
        return False

    # Navigate to profile page, then Consumables page
    if not _navigate_to_page_via_menu(
            "//a[normalize-space()='PROFILE']",
            "//a[normalize-space()='Consumables']",
            "Consumables"):
        print("FAILED: Could not open Consumables page (likely no apartment). Setting 12h cooldown.")

        # Set 12 hour cooldown to avoid spamming the page if you dont have an apartment.
        try:
            os.makedirs(global_vars.COOLDOWN_DATA_DIR, exist_ok=True)
            next_eligible = datetime.datetime.now() + datetime.timedelta(hours=12)
            with open(DRUGS_LAST_CONSUMED_FILE, "w") as f:
                f.write(next_eligible.strftime("%Y-%m-%d %H:%M:%S.%f"))
            global_vars._script_consume_drugs_cooldown_end_time = next_eligible
            print(f"Wrote next eligible time (+12h) to {DRUGS_LAST_CONSUMED_FILE}.")
        except Exception as e:
            print(f"WARNING: Could not write 12h cooldown timestamp: {e}")
            # Fall back to in-memory cooldown so we still back off this run
            global_vars._script_consume_drugs_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(hours=12)

        return False

    # Read Consumables 24h counter
    xpath_consumables = "//div[@id='nav_right']/div[normalize-space(text())='Consumables / 24h']/following-sibling::div[1]"
    txt = _get_element_text(By.XPATH, xpath_consumables) or ""
    m = re.fullmatch(r"\s*(\d+)\s*", txt)
    if not m:
        print(f"FAILED: Could not parse Consumables / 24h value from text: '{txt}'")
        return False
    count = int(m.group(1))

    print(f"Consumables / 24h currently at: {count}. Target limit: {limit}.")

    # If we are already at/over limit, set a short cooldown and stop
    if count >= limit:
        try:
            os.makedirs(global_vars.COOLDOWN_DATA_DIR, exist_ok=True)
            with open(DRUGS_LAST_CONSUMED_FILE, "w") as f:
                next_eligible = datetime.datetime.now() + datetime.timedelta(hours=3)
                f.write(next_eligible.strftime("%Y-%m-%d %H:%M:%S.%f"))
            print(f"Already at or above limit ({limit}); recorded next eligible time (+3h) in text file.")
            global_vars._script_consume_drugs_cooldown_end_time = next_eligible
        except Exception as e:
            print(f"WARNING: Could not write timestamp file for +3h cooldown: {e}")
        return False

    actions = 0
    max_cycles = max(0, limit - count)  # don't do more than necessary
    while count < limit and actions < max_cycles:
        # Click Cocaine
        if not _find_and_click(By.XPATH, "//div[@id='consumables']//div[contains(@onclick, 'type=Cocaine')]"):
            print("FAILED: Cocaine button not found/clickable. Stopping.")
            global_vars._script_consume_drugs_cooldown_end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
            break

        time.sleep(global_vars.ACTION_PAUSE_SECONDS * 1.5)

        # Click the Income drop-down
        if not _find_and_click(By.XPATH, "//div[@id='nav_left']//a[contains(text(),'Income')]"):
            print("FAILED: Could not open Income menu after consuming. Stopping.")
            break

        # Only try the 'lastearn' quick button (retry once if needed)
        if not _find_and_click(By.XPATH, "//input[@name='lastearn']"):
            time.sleep(0.5)
            if not _find_and_click(By.XPATH, "//input[@name='lastearn']"):
                print("FAILED: 'lastearn' button not found. Stopping.")
                break

        actions += 1

        # Re-read consumables counter
        txt = _get_element_text(By.XPATH, xpath_consumables) or ""
        m = re.fullmatch(r"\s*(\d+)\s*", txt)
        if not m:
            print(f"FAILED: Could not parse Consumables / 24h value on recheck: '{txt}'")
            break
        new_count = int(m.group(1))
        print(f"Post-consume recheck — Consumables / 24h: {new_count}")

        if new_count <= count:
            # quick second read in case of UI lag, then bail
            time.sleep(0.4)
            txt2 = _get_element_text(By.XPATH, xpath_consumables) or ""
            m2 = re.fullmatch(r"\s*(\d+)\s*", txt2)
            fresh = int(m2.group(1)) if m2 else new_count
            if fresh <= count:
                print("Counter did not increase after consuming; stopping to avoid a loop.")
                break
            new_count = fresh

        count = new_count
        time.sleep(random.uniform(0.6, 1.2))

    # Only record the timestamp if we successfully hit the configured limit
    if count >= limit and actions > 0:
        try:
            os.makedirs(global_vars.COOLDOWN_DATA_DIR, exist_ok=True)
            with open(DRUGS_LAST_CONSUMED_FILE, "w") as f:
                # write NEXT eligible time (now + 25h), to match timer math style used by shop checks
                next_eligible = datetime.datetime.now() + datetime.timedelta(hours=25)
                f.write(next_eligible.strftime("%Y-%m-%d %H:%M:%S.%f"))
            print(f"Reached limit ({limit}); recorded next eligible time (+25h) in text file.")
        except Exception as e:
            print(f"WARNING: Could not write timestamp file: {e}")
        return True

    print("Did not reach configured ConsumeLimit; no timestamp written.")
    return False

def execute_sendmoney_to_player(target_player: str, amount_str: str) -> bool:
    try:
        target_player = (target_player or "").strip()
        amt = _clean_amount(amount_str)

        if not target_player:
            print("Incorrect player name for transfer")
            return False
        if amt is None:
            print("You have insufficient funds")  # or "Invalid amount"; using provided phrasing constraints
            return False

        # 1) Navigate to Bank
        if not _navigate_to_page_via_menu(
                "//span[@class='income']",
                "//a[normalize-space()='Bank']",
                "Bank"):
            print("FAILED: Could not open Bank.")
            return False

        time.sleep(global_vars.ACTION_PAUSE_SECONDS)

        # Click Transfers tab
        if not _find_and_click(By.XPATH, "//a[normalize-space()='Transfers']", pause=global_vars.ACTION_PAUSE_SECONDS):
            print("FAILED: Could not open Bank Transfers.")
            return False

        time.sleep(global_vars.ACTION_PAUSE_SECONDS / 2)

        # Fill amount & player
        amount_xpath = "//input[@name='transferamount']"
        name_xpath = "//input[@name='transfername']"
        transfer_btn_xpath = "//input[@id='B1']"

        amount_el = _find_element(By.XPATH, amount_xpath, timeout=5)
        name_el = _find_element(By.XPATH, name_xpath, timeout=5)
        if not amount_el or not name_el:
            print("FAILED: Transfer inputs not found.")
            return False

        # Clear and type
        if not _find_and_send_keys(By.XPATH, amount_xpath, str(amt)):
            print("FAILED: Could not enter transfer amount.")
            return False

        if not _find_and_send_keys(By.XPATH, name_xpath, target_player):
            print("FAILED: Could not enter recipient name.")
            return False

        # Click Transfer
        if not _find_and_click(By.XPATH, transfer_btn_xpath):
            print("FAILED: Could not click Transfer.")
            return False

        time.sleep(global_vars.ACTION_PAUSE_SECONDS)

        # Fail checks on the result page
        src = (global_vars.driver.page_source or "")

        if "You have entered an incorrect name!" in src:
            print("Incorrect player name for transfer")
            return False

        if "You have insufficient funds to complete this transfer!" in src:
            print("You have insufficient funds")
            return False

        # If we reach here, assume success (no explicit success text provided)
        print(f"Transfer completed: ${amt:,} to '{target_player}'.")
        return True

    except Exception as e:
        print(f"ERROR during sendmoney flow: {e}")
        return False