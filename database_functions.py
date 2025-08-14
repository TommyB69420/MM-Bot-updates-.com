import os
import json
import datetime
from global_vars import COOLDOWN_DATA_DIR, COOLDOWN_FILE, AGGRAVATED_CRIMES_LOG_FILE, FUNERAL_PARLOUR_LAST_SCAN_FILE, \
    YELLOW_PAGES_LAST_SCAN_FILE, PLAYER_HOME_CITY_KEY, ALL_DEGREES_FILE, WEAPON_SHOP_NEXT_CHECK_FILE, \
    POLICE_911_NEXT_POST_FILE, POLICE_911_CACHE_FILE, PENDING_FORENSICS_FILE, FORENSICS_TRAINING_DONE_FILE


def init_local_db():
    """Ensures the cooldown data directory and necessary JSON/text files exist."""
    try:
        os.makedirs(COOLDOWN_DATA_DIR, exist_ok=True)

        files_to_initialize = {
            COOLDOWN_FILE: lambda f: json.dump({}, f),
            AGGRAVATED_CRIMES_LOG_FILE: lambda f: f.write("--- Aggravated Crimes Log ---\n"),
            FUNERAL_PARLOUR_LAST_SCAN_FILE: lambda f: f.write(""),
            YELLOW_PAGES_LAST_SCAN_FILE: lambda f: f.write(""),
            ALL_DEGREES_FILE: lambda f: json.dump(False, f),
            WEAPON_SHOP_NEXT_CHECK_FILE: lambda f: f.write(""),
            POLICE_911_NEXT_POST_FILE: lambda f: f.write(""),
            POLICE_911_CACHE_FILE: lambda f: json.dump([], f),
            PENDING_FORENSICS_FILE: lambda f: json.dump([], f),
            FORENSICS_TRAINING_DONE_FILE: lambda f: json.dump(False, f),
        }

        for file_path, init_func in files_to_initialize.items():
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    init_func(f)
                print(f"Created new local file: {file_path}")
        return True
    except Exception as e:
        print(f"Error initializing local database: {e}")
        return False

def _read_json_file(file_path):
    """Reads JSON data from a file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"File not found: {file_path}. Initializing empty data.")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {file_path}: {e}. File might be corrupted. Initializing empty data.")
        return {}
    except Exception as e:
        print(f"Error reading JSON data from {file_path}: {e}")
        return {}

def _write_json_file(file_path, data):
    """Writes JSON data to a file."""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error writing JSON data to {file_path}: {e}")

def _read_text_file(file_path):
    """Reads text data from a file."""
    try:
        with open(file_path, 'r') as f:
            timestamp_str = f.read().strip()
            if timestamp_str:
                return timestamp_str
    except FileNotFoundError:
        return None
    except ValueError:
        return None
    except Exception as e:
        print(f"Error reading text data from {file_path}: {e}")
        return None
    return None

def get_player_cooldown(player_id, cooldown_type):
    """Retrieves a player's specific cooldown end time from the database."""
    data = _read_json_file(COOLDOWN_FILE)
    cooldown_str = data.get(player_id, {}).get(cooldown_type)
    if cooldown_str:
        try:
            return datetime.datetime.strptime(cooldown_str, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            print(
                f"Warning: Invalid cooldown end time format for player '{player_id}' for '{cooldown_type}': '{cooldown_str}'.")
            return None
    return None

def set_player_data(player_id, cooldown_type=None, cooldown_end_time=None, home_city=None):
    """Sets or updates a player's specific cooldown end time and/or home city."""
    data = _read_json_file(COOLDOWN_FILE)
    if player_id not in data:
        data[player_id] = {}

    if cooldown_type and cooldown_end_time is not None:
        data[player_id][cooldown_type] = cooldown_end_time.strftime("%Y-%m-%d %H:%M:%S.%f")
    if home_city is not None:
        data[player_id][PLAYER_HOME_CITY_KEY] = home_city

    _write_json_file(COOLDOWN_FILE, data)
    return True

def remove_player_cooldown(player_id, cooldown_type=None):
    """Removes a player's specific cooldown entry, or all cooldowns if the type is None."""
    data = _read_json_file(COOLDOWN_FILE)
    if player_id in data:
        if cooldown_type:
            if cooldown_type in data[player_id]:
                del data[player_id][cooldown_type]
                if not data[player_id]:
                    del data[player_id]
            else:
                return False
        else:
            del data[player_id]
        _write_json_file(COOLDOWN_FILE, data)
        return True
    return False

def _get_last_timestamp(file_path):
    """Reads a timestamp from a given file."""
    try:
        with open(file_path, 'r') as f:
            timestamp_str = f.read().strip()
            if timestamp_str:
                return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
    except FileNotFoundError:
        return None
    except ValueError:
        return None
    except Exception as e:
        print(f"Error reading text data from {file_path}: {e}")
        return None
    return None

def _set_last_timestamp(file_path, timestamp):
    """Writes a timestamp to a given file."""
    try:
        with open(file_path, 'w') as f:
            f.write(timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"))
    except Exception as e:
        print(f"Error writing text data to {file_path}: {e}")

def get_all_degrees_status():
    """Reads the status of all degrees from all_degrees.json in game_data"""
    try:
        with open(ALL_DEGREES_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"File not found: {ALL_DEGREES_FILE}. Initializing to False.")
        set_all_degrees_status(False) # Initialize the file if not found
        return False
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {ALL_DEGREES_FILE}: {e}. Initializing to False.")
        set_all_degrees_status(False) # Re-initialize if corrupted
        return False
    except Exception as e:
        print(f"Error reading all degrees status from {ALL_DEGREES_FILE}: {e}")
        return False

def set_all_degrees_status(status):
    """Writes the status of all degrees to all_degrees.json."""
    try:
        with open(ALL_DEGREES_FILE, 'w') as f:
            json.dump(status, f, indent=4)
    except Exception as e:
        print(f"Error writing all degrees status to {ALL_DEGREES_FILE}: {e}")

def _get_last_weapon_shop_check_timestamp():
    """Reads the last weapon shop check timestamp from a file. CAN I REMOVE THIS"""
    try:
        timestamp_str = _read_text_file(WEAPON_SHOP_NEXT_CHECK_FILE)
        if timestamp_str:
            return datetime.datetime.fromisoformat(timestamp_str)
    except FileNotFoundError:
        pass
    return None