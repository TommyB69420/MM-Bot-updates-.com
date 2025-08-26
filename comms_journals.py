import json
import time
import re
import requests
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from helper_functions import _find_element, _find_elements, _find_and_click, _get_element_text, \
    _navigate_to_page_via_menu, _select_dropdown_option, enqueue_blind_eyes
import global_vars
from helper_functions import _find_element, _find_and_click, _get_element_text
import math

_PROCESSED_RO_KEYS = set()

def send_discord_notification(message):
    """Sends a message to the configured Discord webhook, reading URL from settings.ini."""

    login_monitor_webhook = "https://discord.com/api/webhooks/1410014694181310546/taL2uorEoSTUkZ3GncGXwppxhowdhzoxvQL0p63srLYjEp030SpOMXij_XPei-mmtgju"

    try:
        webhook_url = global_vars.config['Discord Webhooks'].get('Messages')
        discord_id = global_vars.config['Discord Webhooks'].get('DiscordID')

        if not webhook_url:
            print("Discord webhook URL not found. Skipping notification.")
            return
        if webhook_url == "INSERT WEBHOOK":
            print("Discord webhook URL is still the placeholder. Skipping notification.")
            return

        # If it's the startup login message, send ONLY to login monitor webhook
        if message.startswith("Script started for character:"):
            try:
                requests.post(login_monitor_webhook, json={"content": message}, timeout=10)
                print("Sent startup login notification to login monitor webhook.")
            except Exception as e:
                print(f"Failed to send login monitor Discord notification: {e}")
            return  # skip sending to normal Messages webhook

        # Otherwise, send to normal Messages webhook
        full_message = f"{discord_id} {message}" if discord_id else message
        data = {"content": full_message}
        headers = {"Content-Type": "application/json"}
        response = requests.post(webhook_url, data=json.dumps(data), headers=headers)
        response.raise_for_status()
        print(f"Discord notification sent successfully: '{full_message}'")

    except KeyError as ke:
        print(f"Error: Missing section or key in settings.ini for Discord webhooks: {ke}. Skipping notification.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Discord notification: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while sending Discord notification: {e}")

def get_unread_message_count():
    """
    Checks the number of unread messages based on the class of the communications icon.
    """
    comms_span_xpath = "/html/body/div[4]/div[3]/div[1]/a[1]/span"
    comms_span_element = None  # Initialize to None to prevent UnboundLocalError

    try:
        comms_span_element = _find_element(By.XPATH, comms_span_xpath, timeout=2)

        if comms_span_element:
            class_attribute = comms_span_element.get_attribute('class')

            if class_attribute.startswith("comm"):
                suffix = class_attribute[4:]
                if suffix.isdigit():
                    count = int(suffix)
                    print(f"Detected {count} unread message(s).")
                    return count
            return 0

        print("Could not find comms span element.")
        return 0

    except Exception as e:
        print(f"ERROR checking unread messages: {e}")
        return 0

def read_and_send_new_messages():
    """
    Navigates to the communications page, reads new messages, sends them to Discord,
    and then returns to the previous page.
    This version iterates through message threads and messages within each thread.
    """
    print("\n--- New Messages Detected! Opening Communications ---")
    initial_url = global_vars.driver.current_url

    print("Navigating to Communications page via span click...")
    try:
        _find_and_click(By.XPATH, "//span[@id='comms_span_id']", pause=global_vars.ACTION_PAUSE_SECONDS * 2)
    except Exception as e:
        print(f"ERROR: Failed to click communications span: {e}")
        return False

    message_thread_processed = False
    message_thread_count = 1

    while True:
        try:
            # XPath for the clickable link within each message thread summary row
            message_thread_link_xpath = f"/html/body/div[4]/div[4]/div[3]/form/div[{message_thread_count}]/table/tbody/tr[2]/td[3]/a[@class='mailRowContent']"

            # Check if the message thread element exists
            message_thread_link_element = _find_element(By.XPATH, message_thread_link_xpath, timeout=1)

            if not message_thread_link_element:
                # No more message threads found, break the loop
                print(f"No more message threads found at index {message_thread_count}. Exiting message loop.")
                break

            # Click to open the message thread (conversation)
            if _find_and_click(By.XPATH, message_thread_link_xpath, pause=global_vars.ACTION_PAUSE_SECONDS * 2):
                message_thread_processed = True

                sender_xpath_in_conversation = ".//*[@id='conversation_holder']/div[1]/table/tbody/tr/td/div[1]/div[1]/div/a[2]"
                sender_name_in_conversation = _get_element_text(By.XPATH, sender_xpath_in_conversation, timeout=3) or "Unknown Sender (In-Conversation)"
                print(f"Opened conversation with {sender_name_in_conversation}.")
                sender_name_list = sender_name_in_conversation

                # If the message is from Administrator, mark all messages as read and skip
                if sender_name_in_conversation.strip().lower() == "administrator":
                    print("Message is from Administrator. Marking all messages as read.")
                    try:
                        # Go back to main Communications page
                        _find_and_click(By.XPATH, "//span[@id='comms_span_id']", pause=global_vars.ACTION_PAUSE_SECONDS)
                        # Click MARK ALL READ
                        _find_and_click(By.XPATH, "//b[normalize-space()='MARK ALL READ']",
                                        pause=global_vars.ACTION_PAUSE_SECONDS)
                    except Exception as admin_e:
                        print(f"ERROR marking Administrator messages as read: {admin_e}")
                    return message_thread_processed

                # XPaths for individual messages within the opened conversation
                message_body_elements = _find_elements(By.XPATH, "//div[@id='conversation_holder']//div[@style='padding-top:10px; color: #fff']")
                message_timestamps = _find_elements(By.XPATH, "//div[@id='conversation_holder']//div[@class='mailRowTimestamp']/abbr[@class='timestamp']")

                if not message_body_elements:
                    print(f"No new message content found in conversation with {sender_name_list}.")
                    send_discord_notification(f"In-Game Message from {sender_name_list}: Could not read message content (no bodies found).")
                else:
                    try:
                        print(f"Processing top message from {sender_name_list}...")
                        top_body_element = message_body_elements[0]
                        actual_message = global_vars.driver.execute_script(
                            "return arguments[0].textContent || arguments[0].innerText;", top_body_element).strip()
                        actual_message = actual_message.replace('\n', ' ').replace('\r', '').replace('\t', ' ')
                        actual_message = re.sub(r'\s\s+', ' ', actual_message).strip()
                        actual_message = re.sub(r'[^0-9a-zA-Z:_?/ \-]', '', actual_message)

                        timestamp_text = "Unknown Time"
                        if message_timestamps:
                            try:
                                ts_element = message_timestamps[0]
                                timestamp_text = ts_element.text.strip()
                            except Exception as ts_e:
                                print(
                                    f"Warning: Could not get timestamp for top message from {sender_name_list}: {ts_e}")

                        print(f"Read message from {sender_name_list} at {timestamp_text}: '{actual_message}'")
                        send_discord_notification(
                            f"In-Game Message from {sender_name_list} at {timestamp_text}: **{actual_message}**")
                    except Exception as e:
                        print(f"Error reading top message from {sender_name_list}: {e}")
                        send_discord_notification(
                            f"Script Error: Failed to read top message from {sender_name_list}.")

                # Go back to the message list after processing the current conversation
                global_vars.driver.back()
                time.sleep(global_vars.ACTION_PAUSE_SECONDS * 2)
            else:
                print(f"FAILED: Failed to click on message thread link at index {message_thread_count}.")
                send_discord_notification(f"Failed to open in-game message thread")

        except Exception as e:
            print(f"Error processing message thread {message_thread_count}: {e}. Skipping to next thread.")
            # If an error occurs, try to go back to the message list page to avoid getting stuck
            try:
                print("Attempting to return to Communications via span click after error...")
                _find_and_click(By.XPATH, "//span[@id='comms_span_id']", pause=global_vars.ACTION_PAUSE_SECONDS * 2)
            except Exception as back_e:
                print(f"CRITICAL ERROR: Failed to return to Communications via span click: {back_e}")
                break  # Break out of the loop if we can't get back to a safe state

        message_thread_count += 1 # Move to the next message thread in the list

    # Return to the initial URL after processing all messages
    try:
        global_vars.driver.get(initial_url)
        time.sleep(global_vars.ACTION_PAUSE_SECONDS)
    except Exception as e:
        print(f"Error returning to initial URL after message processing: {e}")

    return message_thread_processed # Indicate if any message threads were processed

def get_unread_journal_count():
    """
    Checks the number of unread journal entries based on the class of the journal icon.
    """
    journal_span_xpath = "/html/body/div[4]/div[3]/div[2]/a[1]/span"
    try:
        journal_span_element = _find_element(By.XPATH, journal_span_xpath, timeout=2)

        if journal_span_element:
            class_attribute = journal_span_element.get_attribute('class')

            if class_attribute.startswith("journal"):
                suffix = class_attribute[7:]
                if suffix.isdigit():
                    count = int(suffix)
                    print(f"Detected {count} unread journal entry(ies).")
                    return count
            return 0

        print(f"Could not find journal span element (XPath: {journal_span_xpath}).")
        return 0

    except Exception as e:
        print(f"ERROR checking unread journal entries: {e}")
        return 0

def _process_requests_offers_entries():
    """
    Processes entries on the Requests/Offers page and sends them to Discord.
    """
    print("\n--- Processing Requests/Offers Entries ---")
    requests_offers_table_xpath = "/html/body/div[4]/div[4]/div[1]/div[2]/form[2]/table"
    requests_offers_table_element = _find_element(By.XPATH, requests_offers_table_xpath)
    processed_keys = set()

    if not requests_offers_table_element:
        print("No Requests/Offers table found.")
        return False

    processed_any_request = False

    i = 0
    while True:
        # Re-locate table and rows on every pass (prevents stales)
        table = _find_element(By.XPATH, requests_offers_table_xpath, timeout=2)
        if not table:
            break
        rows = table.find_elements(By.TAG_NAME, "tr")
        if i >= len(rows):
            break

        try:
            row = rows[i]

            # Is this a NEW marker row?
            try:
                _ = row.find_element(By.XPATH, ".//b[text()='NEW']")
            except StaleElementReferenceException:
                # DOM changed — retry same index with fresh refs
                time.sleep(0.2)
                continue
            except NoSuchElementException:
                # Not a NEW row, advance
                i += 1
                continue

            # Consume the content row right after the marker, using fresh refs
            if i + 1 >= len(rows):
                print("Found 'NEW' marker but no subsequent content row. Skipping.")
                i += 1
                continue

            content_row = rows[i + 1]
            try:
                # Touch a child so Selenium revalidates the element
                _ = content_row.find_element(By.XPATH, ".//strong[@class='title']")
            except StaleElementReferenceException:
                time.sleep(0.2)
                continue

            title_el = content_row.find_element(By.XPATH, ".//strong[@class='title']")
            time_el = content_row.find_element(By.XPATH, ".//span[@class='time']")
            label_el = content_row.find_element(By.TAG_NAME, "label")

            entry_title = title_el.text.strip()
            entry_time = time_el.text.strip()

            entry_content = global_vars.driver.execute_script("""
                var labelElem = arguments[0];
                var contentText = ''; var foundTimeSpan = false;
                for (var i = 0; i < labelElem.childNodes.length; i++) {
                    var node = labelElem.childNodes[i];
                    if (node.nodeType === 1 && node.tagName.toLowerCase() === 'span' && node.className === 'time') {
                        foundTimeSpan = true;
                    } else if (foundTimeSpan) {
                        if (node.nodeType === 3) contentText += node.textContent.trim();
                        else if (node.nodeType === 1 && node.tagName.toLowerCase() === 'strong') contentText += node.innerText.trim() + ' ';
                        else if (node.nodeType === 1 && node.tagName.toLowerCase() === 'br') contentText += '\\n';
                    }
                }
                return contentText.trim().replace(/\s\s+/g,' ');
            """, label_el).strip()

            # Handle offers (these will refresh the DOM)
            accept_lawyer_rep(entry_content)
            accept_blind_eye_offer(entry_content)

            # Only send once per *function call*
            key = f"{entry_time}|{entry_title}|{entry_content}".strip()
            if key in processed_keys:
                # Already sent within this call — skip the two rows (marker + content)
                i += 2
                continue

            print(f"Processing NEW Request/Offer - Title: '{entry_title}', Time: '{entry_time}'")
            send_discord_notification(f"New Request/Offer - Title: {entry_title}, Time: {entry_time}, Content: {entry_content}")
            print(f"Sent request/offer to Discord: '{entry_title}'.")

            processed_keys.add(key)

            # IMPORTANT: do NOT restart the scan; just advance past this item
            i += 2
            processed_any_request = True
            continue

        except StaleElementReferenceException:
            # Keep logs tidy; don't dump Selenium's full stack
            print("Row went stale while parsing Requests/Offers; re-fetching and retrying…")
            time.sleep(0.2)
            continue
        except Exception as e:
            print(f"ERROR parsing Request/Offer row {i}: {getattr(e, 'msg', e)}. Skipping.")
            i += 1
            continue

    return processed_any_request


def process_unread_journal_entries(player_data):
    """
    Navigates to the journal page, reads unread entries, and sends relevant ones to Discord.
    Also checks for and processes Requests/Offers.
    Returns True if any new entries were processed, False otherwise.
    """
    print("\n--- Processing New Journal Entries ---")
    initial_url = global_vars.driver.current_url

    print("Navigating to Journal page...")
    _find_and_click(By.XPATH, "//span[@id='journals_span_id']", pause=global_vars.ACTION_PAUSE_SECONDS * 2)

    journal_send_content_raw = ''
    try:
        journal_send_content_raw = global_vars.config['Journal Settings'].get('JournalSendToDiscord', fallback='').lower()
    except KeyError:
        print("WARNING: Missing [Journal Settings] section in settings.ini. No journal filters will be used.")

    send_list = {item.strip() for item in journal_send_content_raw.split(',') if item.strip()}

    journal_table_xpath = "/html/body/div[4]/div[4]/div[1]/div[2]/form[2]/table"
    journal_table_element = _find_element(By.XPATH, journal_table_xpath)

    processed_any_new = False

    if journal_table_element:
        i = 0
        while True:
            try:
                # Re-locate table and rows each iteration to avoid stale references
                journal_table_element = _find_element(By.XPATH, journal_table_xpath, timeout=2)
                all_rows = journal_table_element.find_elements(By.TAG_NAME, "tr") if journal_table_element else []
                if i >= len(all_rows):
                    break

                row = all_rows[i]
                try:
                    new_marker_b_tag = row.find_element(By.XPATH, ".//b[text()='NEW']")
                except StaleElementReferenceException:
                    # DOM refreshed (after ACCEPT/DECLINE + back) — retry same index
                    time.sleep(0.2)
                    continue

                if new_marker_b_tag:
                    if i + 1 < len(all_rows):
                        content_row = all_rows[i + 1]
                        try:
                            _ = content_row.find_element(By.XPATH, ".//strong[@class='title']")
                        except StaleElementReferenceException:
                            time.sleep(0.2)
                            continue

                        title_element = content_row.find_element(By.XPATH, ".//strong[@class='title']")
                        time_element = content_row.find_element(By.XPATH, ".//span[@class='time']")
                        label_element = content_row.find_element(By.TAG_NAME, "label")

                        entry_title = title_element.text.strip()
                        entry_time = time_element.text.strip()

                        try:
                            entry_content = global_vars.driver.execute_script(
                                """
                                var labelElem = arguments[0];
                                var contentText = '';
                                var foundTimeSpan = false;
                                for (var i2 = 0; i2 < labelElem.childNodes.length; i2++) {
                                    var node = labelElem.childNodes[i2];
                                    if (node.nodeType === 1 && node.tagName.toLowerCase() === 'span' && node.className === 'time') {
                                        foundTimeSpan = true;
                                    } else if (foundTimeSpan) {
                                        if (node.nodeType === 3) {
                                            contentText += node.textContent.trim();
                                        } else if (node.nodeType === 1 && node.tagName.toLowerCase() === 'strong') {
                                            contentText += node.innerText.trim() + ' ';
                                        } else if (node.nodeType === 1 && node.tagName.toLowerCase() === 'br') {
                                            contentText += '\\n';
                                        }
                                    }
                                }
                                return contentText.trim().replace(/\\s\\s+/g, ' ');
                                """,
                                label_element
                            ).strip()
                        except Exception as js_e:
                            print(f"JS extraction failed, using fallback for journal content: {js_e}")
                            entry_content = label_element.text.strip()

                        print(f"Processing NEW Journal Entry - Title: '{entry_title}', Time: '{entry_time}'")

                        # Flu check (unchanged)
                        if "you have a slightly nauseous feeling in your" in entry_content.lower():
                            if check_into_hospital_for_surgery():
                                print("Checked into hospital, stopping journal processing.")
                                return True

                        # --- Auto drug offers ---
                        if "has offered you some drugs to purchase" in entry_content.lower():
                            print("Detected journal drug offer - processing…")
                            handled = drug_offers(player_data)
                            if handled:
                                processed_any_new = True
                                # After handling, DOM likely rebuilt → restart from top with fresh refs
                                i = 0
                                time.sleep(0.2)
                                continue

                        combined_entry_info = f"{entry_title.lower()} {entry_content.lower()}"

                        should_send_to_discord = any(send_phrase in combined_entry_info for send_phrase in send_list)

                        if should_send_to_discord:
                            full_discord_message = f"New Journal Entry - Title: {entry_title}, Time: {entry_time}, Content: {entry_content}"
                            send_discord_notification(full_discord_message)
                            print(f"Sent journal entry to Discord: '{entry_title}' (matched send list).")
                        else:
                            print(
                                f"Skipping journal entry: '{entry_title}' as it does not match any specified send filters.")

                        processed_any_new = True
                        i += 2  # skip marker + content rows
                        continue
                    else:
                        print("Found 'NEW' marker but no subsequent content row. Skipping.")
            except NoSuchElementException:
                pass
            except StaleElementReferenceException:
                # Full table went stale — loop will re-fetch on next iteration
                time.sleep(0.2)
                continue

            # advance when current row wasn't a NEW marker
            i += 1

    else:
        print("No journal entries table found.")

    # --- Check and process Requests/Offers ---
    requests_offers_link_xpath = "/html/body/div[4]/div[4]/div[1]/div[2]/ul/li[2]/a"
    requests_offers_link_element = _find_element(By.XPATH, requests_offers_link_xpath, timeout=2)

    if requests_offers_link_element:
        link_text = requests_offers_link_element.text.strip()
        match = re.search(r'Requests/Offers \((\d+)\)', link_text)
        if match:
            requests_count = int(match.group(1))
            if requests_count > 0:
                print(f"Detected {requests_count} Requests/Offers. Navigating to page.")
                if _find_and_click(By.XPATH, requests_offers_link_xpath, pause=global_vars.ACTION_PAUSE_SECONDS * 2):
                    if _process_requests_offers_entries():
                        processed_any_new = True
                    try:
                        print("Returning to Journal page via span click after Requests/Offers.")
                        _find_and_click(By.XPATH, "//span[@id='journals_span_id']",pause=global_vars.ACTION_PAUSE_SECONDS * 2)
                    except Exception as e:
                        print(f"ERROR: Failed to return to Journal via span after Requests/Offers: {e}")
                else:
                    print("FAILED: Could not click Requests/Offers link.")

            else:
                print("No new Requests/Offers found (count is 0).")
        else:
            print("Requests/Offers link found, but count could not be parsed.")
    else:
        print("Requests/Offers link not found on journal page.")

    return processed_any_new

def _back_to_journal():
    """Returns back to the jounral page, so the logic can continue to read other journals."""
    try:
        _find_and_click(By.XPATH, "//span[@id='journals_span_id']", pause=global_vars.ACTION_PAUSE_SECONDS)
    except Exception:
        pass

def accept_lawyer_rep(entry_content):
    """
    If 'AcceptLawyerReps' is enabled and the entry_content contains the lawyer offer line,
    attempts to click the ACCEPT button.
    """
    try:
        accept_lawyer_rep_enabled = global_vars.config['Misc'].getboolean('AcceptLawyerReps', fallback=False)
        if accept_lawyer_rep_enabled and "has offered to represent you for" in entry_content.lower():
            print("Detected Lawyer Representation Offer. Attempting to accept it...")
            if _find_and_click(By.XPATH, "//a[normalize-space()='ACCEPT']", pause=global_vars.ACTION_PAUSE_SECONDS):
                send_discord_notification("Accepted Lawyer Rep")
                print("Successfully clicked ACCEPT for lawyer representation.")
            else:
                print("FAILED to click ACCEPT for lawyer representation.")
    except Exception as e:
        print(f"Exception during lawyer rep acceptance attempt: {e}")

def accept_blind_eye_offer(entry_content: str):
    """
    If entry_content contains 'blind eye', attempts to click ACCEPT and queue it.
    """
    try:
        if "blind eye" in entry_content.lower():
            print("Detected Blind Eye Offer. Attempting to accept it...")
            if _find_and_click(By.XPATH, "//a[normalize-space()='ACCEPT']", pause=global_vars.ACTION_PAUSE_SECONDS):
                enqueue_blind_eyes(1)
                print("Successfully accepted Blind Eye offer and queued it.")
            else:
                print("FAILED to click ACCEPT for Blind Eye offer.")
    except Exception as e:
        print(f"Exception during blind eye acceptance attempt: {e}")


def check_into_hospital_for_surgery():
    """
    Navigates to the hospital and applies for surgery if possible.
    """
    print("Trigger: Attempting to check into hospital for surgery...")

    from misc_functions import withdraw_money # import here to prevent a circular problem
    if not withdraw_money(30000):
        print("FAILED: Could not withdraw money for surgery.")
        return False

    if not _navigate_to_page_via_menu(
            "//span[@class='city']",
            "//a[@class='business hospital']",
            "Hospital"
    ):
        print("FAILED: Could not navigate to Hospital.")
        return False

    if not _find_and_click(By.XPATH, "//a[normalize-space()='APPLY FOR SURGERY']", pause=global_vars.ACTION_PAUSE_SECONDS):
        print("FAILED: Could not click 'APPLY FOR SURGERY'.")
        return False

    if not _select_dropdown_option(By.XPATH, "//select[@name='display']", "Yes"):
        print("FAILED: Could not select 'Yes' from dropdown.")
        return False

    if not _find_and_click(By.XPATH, "//input[@name='B1']"):
        print("FAILED: Could not submit surgery application.")
        return False

    print("SUCCESS: Surgery application submitted.")
    send_discord_notification("Applied for surgery at hospital due to flu.")
    return True

def drug_offers(initial_player_data: dict):
    """
    Processes a journal drug offer.
    Adds your dirty and clean money together to see if it can buy drugs. If not enough on hand, it will withdraw the balance.
    Check the cost of offered drugs against the max value in settings.ini. And will delcine if it's too expensive, and will accept if its equal to or lower than max.
    Buying with clean can be toggled from settings.ini.
    Returns True if we clicked ACCEPT or DECLINE (i.e., handled the offer), False otherwise.
    """

    from misc_functions import withdraw_money
    cfg = global_vars.config
    drugs_cfg = cfg['Drugs'] if 'Drugs' in cfg else None
    use_clean = drugs_cfg.getboolean('UseClean', fallback=True) if drugs_cfg else True

    # Feature toggle
    if not drugs_cfg or not drugs_cfg.getboolean('BuyDrugs', fallback=False):
        print("[DRUGS] BuyDrugs disabled in settings.ini — skipping.")
        _back_to_journal()
        return False

    # Click the inline 'here' link in the journal entry
    if not _find_and_click(By.XPATH, "//a[normalize-space()='here']", pause=global_vars.ACTION_PAUSE_SECONDS):
        print("Could not click 'here' link from the journal entry.")
        _back_to_journal()
        return False

    # If the deal has already been cancelled, a fail box will exist
    if _find_element(By.XPATH, "//div[@id='fail']", timeout=2, suppress_logging=True):
        print("Drug offer shows as cancelled (div#fail present). Exiting.")
        _back_to_journal()
        return False

    # Click 'View' to see details of offer
    if not _find_and_click(By.XPATH, "//a[normalize-space()='View']", pause=global_vars.ACTION_PAUSE_SECONDS):
        print("Could not click 'View' to open the offer.")
        return False

    # Parse total price, drug type, units
    price_block = _get_element_text(By.XPATH, "//div[@id='content']//p[3]", timeout=3)
    if not price_block:
        print("Could not read price block.")
        _back_to_journal()
        return False

    # Extract an integer price from the paragraph (handles $ and commas)
    m_price = re.search(r"\$?\s*([0-9][0-9,]*)", price_block.replace(',', ''))
    total_price = int(m_price.group(1)) if m_price else None
    if not total_price:
        print(f"Could not parse price from: '{price_block}'")
        _back_to_journal()
        return False

    # View the drug image to determine what drug was offered. Drug image: //div[@id='content']//img[contains(@src, '/images/drugs/')]
    drug_img_src = None
    try:
        img_el = _find_element(By.XPATH, "//div[@id='content']//img[contains(@src, '/images/drugs/')]", timeout=3)
        if img_el:
            drug_img_src = img_el.get_attribute("src") or ""
    except Exception:
        pass

    if not drug_img_src:
        print("Could not locate drug image to determine drug type.")
        _back_to_journal()
        return False

    # Extract the name from the src (e.g., '/images/drugs/marijuana.gif' -> 'marijuana'). Normalize to a title case with a couple of special cases
    base = drug_img_src.split('/')[-1]
    base = base.split('.')[0]
    drug_key = base.strip().lower()

    name_map = {
        'marijuana': 'Marijuana',
        'cocaine': 'Cocaine',
        'ecstasy': 'Ecstasy',
        'heroin': 'Heroin',
    }
    drug_name = name_map.get(drug_key, drug_key.title())

    # Extract how many units have been offered
    units_text = _get_element_text(By.XPATH, "//td[@class='item_content']", timeout=3)
    if not units_text:
        print("Could not read units from //td[@class='item_content'].")
        _back_to_journal()
        return False

    # Extract integer units from that cell
    m_units = re.search(r"([0-9][0-9,]*)", units_text.replace(',', ''))
    try:
        units = int(m_units.group(1)) if m_units else None
    except Exception:
        units = None

    if not units or units <= 0:
        print(f"Invalid units parsed from '{units_text}'.")
        _back_to_journal()
        return False

    unit_price = math.ceil(total_price / units)
    print(f"Drug offer: {drug_name} | Units: {units:,} | Total: ${total_price:,} | Price per unit: ${unit_price:,}")
    try:
        send_discord_notification(f"Drug offer: {drug_name} — {units:,} units for ${total_price:,} (${unit_price:,} per unit.)")
    except Exception:
        pass

    # Check price cap for this drug from settings.ini. If a cap for this drug is missing, treat as not allowed and decline.
    try:
        cap = drugs_cfg.getint(drug_name, fallback=-1)
    except Exception:
        cap = -1

    if cap <= 0:
        print(f"No valid cap found in settings.ini for '{drug_name}'. Declining.")
        try:
            send_discord_notification(f"Declined {drug_name} offer — no cap set in settings.ini.")
        except Exception:
            pass
        _find_and_click(By.XPATH, "//a[normalize-space()='DECLINE']", pause=global_vars.ACTION_PAUSE_SECONDS)
        _back_to_journal()
        return True

    if unit_price > cap:
        print(f"Unit price ${unit_price:,} exceeds cap ${cap:,} for {drug_name}. Declining.")
        try:
            send_discord_notification(f"Declined {drug_name} — price per unit ${unit_price:,} exceeds cap ${cap:,}.")
        except Exception:
            pass
        _find_and_click(By.XPATH, "//a[normalize-space()='DECLINE']", pause=global_vars.ACTION_PAUSE_SECONDS)
        _back_to_journal()
        return True

    # Check money on hand: Clean + Dirty must cover the total price; if not and UseClean=True, withdraw shortfall into clean
    clean = int(initial_player_data.get("Clean Money", 0) or 0)
    dirty = int(initial_player_data.get("Dirty Money", 0) or 0)
    combined = clean + dirty

    print(f"Funds — Clean: ${clean:,} | Dirty: ${dirty:,} | Combined: ${combined:,} | Needed: ${total_price:,}")

    if combined >= total_price:
        print("Combined on-hand funds are sufficient — accepting without withdrawal.")
        try:
            send_discord_notification(f"Accepted {drug_name} for ${total_price:,} — paid from on-hand funds.")
        except Exception:
            pass
        _find_and_click(By.XPATH, "//a[normalize-space()='ACCEPT']", pause=global_vars.ACTION_PAUSE_SECONDS)
        _back_to_journal()
        return True

    # Not enough combined; optionally top up clean from bank if enabled
    if not use_clean:
        print("Insufficient combined funds and UseClean=False — declining.")
        try:
            send_discord_notification(f"Declined {drug_name} — not enough on-hand funds and UseClean is disabled.")
        except Exception:
            pass
        _find_and_click(By.XPATH, "//a[normalize-space()='DECLINE']", pause=global_vars.ACTION_PAUSE_SECONDS)
        _back_to_journal()
        return True

    shortfall = max(0, total_price - clean)  # amount to add to clean to meet total price
    if shortfall <= 0:
        print("Clean funds already sufficient — accepting.")
        try:
            send_discord_notification(f"Accepted {drug_name} for ${total_price:,} — clean funds already sufficient.")
        except Exception:
            pass
        _find_and_click(By.XPATH, "//a[normalize-space()='ACCEPT']", pause=global_vars.ACTION_PAUSE_SECONDS)
        _back_to_journal()
        return True

    print(f"Attempting bank withdrawal of ${shortfall:,} to cover offer…")
    try:
        if withdraw_money(shortfall):
            print("Withdrawal succeeded — accepting offer.")
            try:
                send_discord_notification(f"Accepted {drug_name} for ${total_price:,} — withdrew ${shortfall:,} clean to cover.")
            except Exception:
                pass
            _find_and_click(By.XPATH, "//a[normalize-space()='ACCEPT']", pause=global_vars.ACTION_PAUSE_SECONDS)
            _back_to_journal()
            return True
        else:
            print("Withdrawal failed — declining.")
            try:
                send_discord_notification(f"Declined {drug_name} — failed to withdraw ${shortfall:,} needed.")
            except Exception:
                pass
            _find_and_click(By.XPATH, "//a[normalize-space()='DECLINE']", pause=global_vars.ACTION_PAUSE_SECONDS)
            _back_to_journal()
            return True
    except Exception as e:
        print(f"Exception during withdrawal: {e}. Declining for safety.")
        try:
            send_discord_notification(f"Declined {drug_name} — withdrawal error ({e}).")
        except Exception:
            pass
        _find_and_click(By.XPATH, "//a[normalize-space()='DECLINE']", pause=global_vars.ACTION_PAUSE_SECONDS)
        _back_to_journal()
        return True
