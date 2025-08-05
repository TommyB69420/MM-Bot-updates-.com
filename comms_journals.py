import json
import time
import re
import requests
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from helper_functions import _find_element, _find_elements, _find_and_click, _get_element_text, _navigate_to_page_via_menu, _select_dropdown_option
import global_vars


def send_discord_notification(message):
    """Sends a message to the configured Discord webhook, reading URL from settings.ini."""
    try:
        webhook_url = global_vars.config['Discord Webhooks'].get('Messages')
        discord_id = global_vars.config['Discord Webhooks'].get('DiscordID')

        if not webhook_url:
            print("Discord webhook URL not found. Skipping notification.")
            return
        if webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE":
            print("Discord webhook URL is still the placeholder. Skipping notification.")
            return

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

    if not requests_offers_table_element:
        print("No Requests/Offers table found.")
        return False

    all_rows = requests_offers_table_element.find_elements(By.TAG_NAME, "tr")
    processed_any_request = False

    i = 0
    while i < len(all_rows):
        row = all_rows[i]
        try:
            new_marker_b_tag = row.find_element(By.XPATH, ".//b[text()='NEW']")
            if new_marker_b_tag:
                if i + 1 < len(all_rows):
                    content_row = all_rows[i + 1]
                    title_element_check = content_row.find_element(By.XPATH, ".//strong[@class='title']")

                    title_element = content_row.find_element(By.XPATH, ".//strong[@class='title']")
                    time_element = content_row.find_element(By.XPATH, ".//span[@class='time']")
                    label_element = content_row.find_element(By.TAG_NAME, "label")

                    entry_title = title_element.text.strip()
                    entry_time = time_element.text.strip()

                    entry_content = global_vars.driver.execute_script(
                        """
                        var labelElem = arguments[0];
                        var contentText = '';
                        var foundTimeSpan = false;
                        for (var i = 0; i < labelElem.childNodes.length; i++) {
                            var node = labelElem.childNodes[i];
                            if (node.nodeType === 1 && node.tagName.toLowerCase() === 'span' && node.className === 'time') {
                                foundTimeSpan = true;
                            } else if (foundTimeSpan) {
                                if (node.nodeType === 3) {
                                    contentText += node.textContent.trim();
                                } else if (node.nodeType === 1 && node.tagName.toLowerCase() === 'strong') { // Changed 'and' to '&&'
                                    contentText += node.innerText.trim() + ' ';
                                } else if (node.nodeType === 1 && node.tagName.toLowerCase() === 'br') { // Changed 'and' to '&&'
                                    contentText += '\\n';
                                }
                            }
                        }
                        return contentText.trim().replace(/\\s\\s+/g, ' ');
                        """,
                        label_element
                    )
                    entry_content = entry_content.strip()

                    # Try accepting lawyer rep if enabled
                    accept_lawyer_rep(entry_content)

                    print(f"Processing NEW Request/Offer - Title: '{entry_title}', Time: '{entry_time}'")
                    full_discord_message = f"New Request/Offer - Title: {entry_title}, Time: {entry_time}, Content: {entry_content}"
                    send_discord_notification(full_discord_message)
                    print(f"Sent request/offer to Discord: '{entry_title}'.")
                    processed_any_request = True
                    i += 1
                else:
                    print("Found 'NEW' marker but no subsequent content row for Request/Offer. Skipping.")

        except NoSuchElementException:
            pass
        except Exception as e:
            print(f"ERROR parsing Request/Offer entry: {e}. Skipping row.")
        i += 1
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
        all_rows = journal_table_element.find_elements(By.TAG_NAME, "tr")

        i = 0
        while i < len(all_rows):
            row = all_rows[i]
            try:
                new_marker_b_tag = row.find_element(By.XPATH, ".//b[text()='NEW']")
                if new_marker_b_tag:
                    if i + 1 < len(all_rows):
                        content_row = all_rows[i + 1]
                        title_element_check = content_row.find_element(By.XPATH, ".//strong[@class='title']")

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
                                for (var i = 0; i < labelElem.childNodes.length; i++) {
                                    var node = labelElem.childNodes[i];
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

                        # Check for flu journal entry
                        if "you have a slightly nauseous feeling in your" in entry_content.lower():
                            if check_into_hospital_for_surgery():
                                print("Checked into hospital, stopping journal processing.")
                                return True

                        combined_entry_info = f"{entry_title.lower()} {entry_content.lower()}"

                        should_send_to_discord = False
                        for send_phrase in send_list:
                            if send_phrase in combined_entry_info:
                                should_send_to_discord = True
                                break

                        if should_send_to_discord:
                            full_discord_message = f"New Journal Entry - Title: {entry_title}, Time: {entry_time}, Content: {entry_content}"
                            send_discord_notification(full_discord_message)
                            print(f"Sent journal entry to Discord: '{entry_title}' (matched send list).")
                        else:
                            print(f"Skipping journal entry: '{entry_title}' as it does not match any specified send filters.")

                        processed_any_new = True
                        i += 1
                    else:
                        print("Found 'NEW' marker but no subsequent content row. Skipping.")
            except NoSuchElementException:
                pass
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

    try:
        global_vars.driver.get(initial_url)
        time.sleep(global_vars.ACTION_PAUSE_SECONDS)
    except Exception as e:
        print(f"Error returning to initial URL after journal processing: {e}")

    return processed_any_new

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

