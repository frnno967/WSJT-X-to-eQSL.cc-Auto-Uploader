#!/usr/bin/env python3
"""
WSJT-X to eQSL.cc Auto-Uploader
Listens for WSJT-X logged ADIF broadcasts and uploads to eQSL.cc
"""

import socket
import sys
import re
import requests
import json
import os
import threading
import time
import shutil
import select
import termios
import tty
from datetime import datetime
from getpass import getpass

# Version
VERSION = "1.1.0"

# Configuration
UDP_PORT = 2333
LOG_FILE = os.path.expanduser("~/wsjtx2eqsl.log")
CONFIG_FILE = os.path.expanduser("~/.wsjtx2eqsl.conf")

# Global state
contact_count = 0
recent_contacts = []
last_contact = None
upload_status = "Ready"
connection_status = "Listening"
running = True
show_menu = False
DEBUG = False
AUTO_UPLOAD = True

def save_credentials(username, password, auto_upload, udp_port=2333, debug=False):
    """Save credentials to config file"""
    config = {
        'username': username,
        'password': password,
        'auto_upload': auto_upload,
        'udp_port': udp_port,
        'debug': debug
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        os.chmod(CONFIG_FILE, 0o600)
    except Exception as e:
        pass

def load_credentials():
    """Load credentials from config file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            return (config.get('username'), 
                    config.get('password'), 
                    config.get('auto_upload', True),
                    config.get('udp_port', 2333),
                    config.get('debug', False))
        except:
            pass
    return None, None, None, 2333, False

def get_credentials():
    """Get credentials from user or load from saved config"""
    # Try to load saved credentials first
    saved_user, saved_pass, saved_auto, saved_port, saved_debug = load_credentials()
    
    if saved_user and saved_pass:
        # Automatically use saved credentials
        print(f"\033[32m✓ Loaded saved credentials for: {saved_user}\033[0m")
        print(f"\033[36m(Press 'c' during operation to change configuration)\033[0m")
        return saved_user, saved_pass, saved_auto, saved_port, saved_debug
    
    # No saved credentials, get new ones
    print(f"\033[33mConfiguration Setup\033[0m\n")
    
    username = input("Enter your eQSL.cc username (callsign): ").strip()
    if not username:
        print(f"\033[31mError: Username cannot be empty\033[0m")
        sys.exit(1)
    
    password = getpass("Enter your eQSL.cc password (WILL NOT ECHO): ")
    if not password:
        print(f"\033[31mError: Password cannot be empty\033[0m")
        sys.exit(1)
    
    auto_upload = input("\nEnable auto-upload to eQSL.cc? (y/n): ").strip().lower() in ['y', 'yes']
    
    port_input = input(f"UDP port for WSJT-X logged ADIF (default 2333): ").strip()
    udp_port = int(port_input) if port_input.isdigit() else 2333
    
    debug = input("Enable debug logging? (y/n): ").strip().lower() in ['y', 'yes']
    
    # Ask if they want to save credentials
    print()
    save = input("Save configuration for next time? (y/n): ").strip().lower()
    if save in ['y', 'yes']:
        save_credentials(username, password, auto_upload, udp_port, debug)
    else:
        print(f"\033[33mConfiguration will not be saved\033[0m")
    
    print()
    return username, password, auto_upload, udp_port, debug

def parse_adif(adif_text, field):
    """Extract field value from ADIF format"""
    pattern = f'<{field}:(\\d+)>\\s*([^<]*)'
    match = re.search(pattern, adif_text, re.IGNORECASE)
    if match:
        length = int(match.group(1))
        value = match.group(2).strip()[:length]
        return value
    return None

def parse_all_adif(adif_text):
    """Parse all ADIF fields"""
    fields = {}
    pattern = r'<(\w+):(\d+)>\s*([^<]*)'
    for match in re.finditer(pattern, adif_text, re.IGNORECASE):
        field_name = match.group(1).lower()
        length = int(match.group(2))
        value_text = match.group(3).strip()
        # Use the declared length from ADIF, not strip length
        value = value_text[:length] if value_text else ''
        fields[field_name] = value
    return fields

def format_frequency(freq_str):
    """Format frequency to 7 characters (including decimal) with space and MHz suffix"""
    if not freq_str:
        return 'N/A'
    
    # Keep numeric characters and decimal point
    freq_clean = ''.join(c for c in freq_str if c.isdigit() or c == '.')
    
    # Limit to 7 characters (including decimal point)
    freq_clean = freq_clean[:7]
    
    # Add space and MHz
    return f"{freq_clean} MHz" if freq_clean else 'N/A'

def upload_to_eqsl(adif_data, username, password):
    """Upload ADIF data to eQSL.cc"""
    global upload_status
    
    upload_status = "Uploading..."
    
    if DEBUG:
        log_message("=== DEBUG: Upload Request ===")
        log_message(f"Username: {username}")
        log_message(f"ADIF Data: {adif_data}")
    
    try:
        response = requests.post(
            'https://www.eqsl.cc/qslcard/ImportADIF.cfm',
            data={
                'EQSL_USER': username,
                'EQSL_PSWD': password,
                'ADIFData': adif_data
            },
            timeout=10
        )
        
        if DEBUG:
            log_message(f"Response Status Code: {response.status_code}")
            log_message(f"Response Headers: {dict(response.headers)}")
            log_message(f"Response Text: {response.text}")
        
        response_text = response.text.lower()
        
        if 'result: 1' in response_text or 'success' in response_text:
            upload_status = "Upload OK"
            log_message("Upload successful")
            if DEBUG:
                log_message("=== DEBUG: Upload Success ===")
            return True
        else:
            upload_status = "Upload Failed"
            log_message(f"Upload failed - {response.text[:100]}")
            if DEBUG:
                log_message("=== DEBUG: Upload Failed ===")
            # Show error to user
            show_upload_error(response.text, adif_data, username, password)
            return False
            
    except Exception as e:
        upload_status = f"Error: {str(e)[:20]}"
        log_message(f"Upload error - {e}")
        if DEBUG:
            log_message(f"=== DEBUG: Upload Exception ===")
            log_message(f"Exception Type: {type(e).__name__}")
            log_message(f"Exception Details: {str(e)}")
        # Show error to user
        show_upload_error(str(e), adif_data, username, password)
        return False

def show_upload_error(error_msg, adif_data, username, password):
    """Show upload error and offer retry"""
    global show_menu
    
    show_menu = True
    
    # Save terminal settings
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        # Show cursor and clear screen
        print("\033[?25h\033[2J\033[1;1H")
        
        print(f"\033[31m╔════════════════════════════════════════════╗\033[0m")
        print(f"\033[31m║            *** Upload Error ***            ║\033[0m")
        print(f"\033[31m╚════════════════════════════════════════════╝\033[0m")
        print()
        print(f"\033[33mFailed to upload to eQSL.cc\033[0m")
        print()
        print(f"Error: {error_msg[:200]}")
        print()
        print(f"\033[36mPress (R) to retry upload, or any other key to ignore...\033[0m")
        
        # Set to raw mode for single character input
        tty.setcbreak(sys.stdin.fileno())
        
        # Wait for key press
        key = sys.stdin.read(1).lower()
        
        if key == 'r':
            print("\n\033[33mRetrying upload...\033[0m")
            time.sleep(1)
            # Retry the upload
            upload_to_eqsl(adif_data, username, password)
        
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        show_menu = False
        # Hide cursor again
        print("\033[?25l", end='')

def log_message(message):
    """Log message to file"""
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(f"{datetime.utcnow()}: {message}\n")
            f.flush()  # Force write to disk
    except Exception as e:
        # If logging fails, don't crash the program
        # Could optionally print to stderr for debugging
        pass

def timed_input(prompt, timeout_seconds):
    """Get user input with a timeout (thread-safe version)"""
    print(prompt, end='', flush=True)
    
    # Use select to wait for input with timeout
    ready, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
    
    if ready:
        # Input is available, read it
        line = sys.stdin.readline().rstrip('\n')
        return line
    else:
        # Timeout occurred
        print()  # Move to new line
        return None

def manage_credentials():
    """Interactive menu to manage saved credentials"""
    global DEBUG, AUTO_UPLOAD
    
    # Show cursor and clear screen
    print("\033[?25h\033[2J\033[1;1H")
    
    print(f"\033[36m╔════════════════════════════════════════════╗\033[0m")
    print(f"\033[36m║              Configuration                 ║\033[0m")
    print(f"\033[36m╚════════════════════════════════════════════╝\033[0m")
    print()
    print("1. View current settings")
    print("2. Change credentials")
    print("3. Toggle auto-upload")
    print("4. Change UDP port")
    print("5. Toggle debug logging")
    print("6. Delete saved configuration")
    print("7. Return to monitoring")
    print()
    print("\033[33m(Auto-return to monitoring in 2 minutes if no selection)\033[0m")
    print()
    
    choice = timed_input("Select option (1-7): ", 120)  # 2 minute timeout
    
    if choice is None:
        print("\n\033[33mTimeout - returning to monitoring...\033[0m")
        time.sleep(1)
        return False
    
    choice = choice.strip()
    
    if choice == '1':
        saved_user, _, saved_auto, saved_port, saved_debug = load_credentials()
        if saved_user:
            print(f"\n\033[32mUsername:      {saved_user}\033[0m")
            print(f"\033[32mAuto-upload:   {saved_auto}\033[0m")
            print(f"\033[32mUDP Port:      {saved_port}\033[0m")
            print(f"\033[32mDebug logging: {saved_debug}\033[0m")
        else:
            print(f"\n\033[33mNo saved configuration found\033[0m")
        input("\nPress Enter to continue...")
        # Return to configuration menu
        return manage_credentials()
    
    elif choice == '2':
        print(f"\n\033[33mEnter new credentials:\033[0m\n")
        username = input("Enter your eQSL.cc username (callsign): ").strip()
        if username:
            password = getpass("Enter your eQSL.cc password: ")
            if password:
                saved_user, saved_pass, saved_auto, saved_port, saved_debug = load_credentials()
                auto_upload = input("Enable auto-upload? (y/n): ").strip().lower() in ['y', 'yes']
                save_credentials(username, password, auto_upload, saved_port or 2333, saved_debug)
                print(f"\n\033[32m✓ Credentials updated! Please restart the script to use them.\033[0m")
                input("\nPress Enter to continue...")
                return True  # Signal to restart
        return False
    
    elif choice == '3':
        saved_user, saved_pass, saved_auto, saved_port, saved_debug = load_credentials()
        if saved_user and saved_pass:
            new_auto = not saved_auto
            save_credentials(saved_user, saved_pass, new_auto, saved_port or 2333, saved_debug)
            AUTO_UPLOAD = new_auto  # Update global AUTO_UPLOAD immediately
            status = "enabled" if new_auto else "disabled"
            print(f"\n\033[32m✓ Auto-upload {status}!\033[0m")
            log_message(f"Auto-upload {status}")
            input("\nPress Enter to continue...")
            return manage_credentials()  # Return to configuration menu
        else:
            print(f"\n\033[33mNo saved configuration found\033[0m")
            input("\nPress Enter to continue...")
        return False
    
    elif choice == '4':
        saved_user, saved_pass, saved_auto, saved_port, saved_debug = load_credentials()
        if saved_user and saved_pass:
            print(f"\n\033[36mDefault WSJT-X UDP port:  2333\033[0m")
            print(f"\033[33mCurrent UDP port: {saved_port}\033[0m")
            new_port = input("Enter new UDP port (1-65535, or press Enter to keep current): ").strip()
            
            # If empty, don't change
            if not new_port:
                print(f"\n\033[36mUDP port unchanged ({saved_port})\033[0m")
                input("\nPress Enter to continue...")
                return manage_credentials()  # Return to configuration menu
            # Check if it's a valid port number
            elif new_port.isdigit() and 1 <= int(new_port) <= 65535:
                new_port_num = int(new_port)
                # If same as current, don't change
                if new_port_num == saved_port:
                    print(f"\n\033[36mUDP port unchanged ({saved_port})\033[0m")
                    input("\nPress Enter to continue...")
                    return manage_credentials()  # Return to configuration menu
                else:
                    save_credentials(saved_user, saved_pass, saved_auto, new_port_num, saved_debug)
                    print(f"\n\033[32m✓ UDP port changed to {new_port_num}! Please restart the script to apply.\033[0m")
                    input("\nPress Enter to continue...")
                    return True  # Signal to restart
            else:
                print(f"\n\033[31mInvalid port number. Must be between 1 and 65535.\033[0m")
                input("\nPress Enter to continue...")
                return manage_credentials()  # Return to configuration menu
        else:
            print(f"\n\033[33mNo saved configuration found\033[0m")
            input("\nPress Enter to continue...")
        return False
    
    elif choice == '5':
        saved_user, saved_pass, saved_auto, saved_port, saved_debug = load_credentials()
        if saved_user and saved_pass:
            new_debug = not saved_debug
            save_credentials(saved_user, saved_pass, saved_auto, saved_port or 2333, new_debug)
            DEBUG = new_debug  # Update global DEBUG immediately
            status = "enabled" if new_debug else "disabled"
            print(f"\n\033[32m✓ Debug logging {status}!\033[0m")
            log_message(f"Debug logging {status}")
            input("\nPress Enter to continue...")
            return manage_credentials()  # Return to configuration menu
        else:
            print(f"\n\033[33mNo saved configuration found\033[0m")
            input("\nPress Enter to continue...")
        return False
    
    elif choice == '6':
        confirm = input(f"\n\033[31mDelete saved configuration? (y/n): \033[0m").strip().lower()
        if confirm in ['y', 'yes']:
            try:
                os.remove(CONFIG_FILE)
                print(f"\033[32m✓ Configuration deleted! Please restart the script.\033[0m")
                input("\nPress Enter to continue...")
                return True  # Signal to restart
            except:
                print(f"\033[33mNo configuration file found\033[0m")
                input("\nPress Enter to continue...")
        return False
    
    elif choice == '7':
        return False  # Return to monitoring
    
    return False


def process_qso(adif_data, username, password):
    """Process a QSO"""
    global contact_count, recent_contacts, last_contact, upload_status
    
    if DEBUG:
        log_message("=== DEBUG: Processing QSO ===")
        log_message(f"Raw ADIF Data: {adif_data}")
    
    fields = parse_all_adif(adif_data)
    
    if DEBUG:
        log_message(f"Parsed ADIF Fields: {fields}")
    
    contact = {
        'call': fields.get('call', 'N/A'),
        'mode': fields.get('mode', 'N/A'),
        'band': fields.get('band', 'N/A'),
        'freq': fields.get('freq', None),
        'grid': fields.get('gridsquare', None),
        'rst_sent': fields.get('rst_sent', None),
        'rst_rcvd': fields.get('rst_rcvd', None),
        'qso_date': fields.get('qso_date', None),
        'time_on': fields.get('time_off', None) or fields.get('time_on', None),  # Prefer time_off
        'comment': fields.get('comment', None),
        'timestamp': datetime.utcnow()
    }
    
    if DEBUG:
        log_message(f"Contact Object: {contact}")
    
    contact_count += 1
    recent_contacts.insert(0, contact)
    recent_contacts = recent_contacts[:10]
    last_contact = contact
    
    log_message(f"QSO with {contact['call']} on {contact['mode']}/{contact['band']}")
    
    if AUTO_UPLOAD:
        # Upload the complete ADIF data (includes all fields including comments)
        upload_to_eqsl(adif_data, username, password)
    else:
        upload_status = "Manual mode"
        if DEBUG:
            log_message("DEBUG: Auto-upload disabled, skipping upload")

def get_terminal_size():
    """Get current terminal size"""
    try:
        size = shutil.get_terminal_size()
        return size.columns, size.lines
    except:
        return 80, 24  # Default fallback

def draw_box(x, y, width, height, title=""):
    """Draw a box at position with title"""
    if width < 4 or height < 2:
        return
    
    # Top border
    print(f"\033[{y};{x}H┌{'─' * (width-2)}┐", end='')
    if title and len(title) + 4 < width:
        title_pos = x + 2
        print(f"\033[{y};{title_pos}H {title} ", end='')
    
    # Sides
    for i in range(1, height-1):
        print(f"\033[{y+i};{x}H│{' ' * (width-2)}│", end='')
    
    # Bottom border
    print(f"\033[{y+height-1};{x}H└{'─' * (width-2)}┘", end='')

def draw_status_screen(username):
    """Draw the main status screen"""
    global contact_count, recent_contacts, last_contact, upload_status, connection_status, running, show_menu
    
    # Clear screen and hide cursor
    print("\033[2J\033[?25l", end='')
    
    while running:
        if show_menu:
            time.sleep(0.1)
            continue
            
        # Get current terminal size
        width, height = get_terminal_size()
        
        # Minimum size check
        if width < 60 or height < 20:
            print("\033[2J\033[1;1H\033[31mTerminal too small! Minimum 60x20\033[0m", end='')
            sys.stdout.flush()
            time.sleep(1)
            continue
        
        # Clear screen
        print("\033[2J", end='')
        
        # Header (full width)
        print("\033[1;1H\033[44m\033[97m" + " " * width, end='')
        print("\033[1;3H WSJT-X to eQSL.cc Auto-Uploader v" + VERSION + " by K5JCJ", end='')
        website_str = "www.jaycrutti.com"
        website_pos = width - len(website_str) - 2
        print(f"\033[1;{website_pos}H{website_str}\033[0m", end='')
        
        # Calculate layout based on terminal size
        half_width = width // 2
        
        # Status box (top left) - starts at row 2 (no blank line)
        status_width = half_width - 1
        draw_box(1, 2, status_width, 6, "STATUS")
        conn_text = f"Listening,UDP Port {UDP_PORT}"
        print(f"\033[3;3HConnection: \033[32m{conn_text[:status_width-14]}\033[0m", end='')
        print(f"\033[4;3HUsername:   \033[33m{username[:status_width-14]}\033[0m", end='')
        print(f"\033[5;3HAuto-upload: \033[33m{'ON' if AUTO_UPLOAD else 'OFF'}\033[0m", end='')
        print(f"\033[5;25H QSOs: \033[36m{contact_count}\033[0m", end='')
        print(f"\033[6;3HLast Upload: \033[33m{upload_status[:status_width-15]}\033[0m", end='')
        
        # Time/Date box (top right) - starts at row 2 (no blank line)
        time_box_x = half_width + 1
        time_box_width = width - half_width
        draw_box(time_box_x, 2, time_box_width, 6, "TIME & DATE")
        utc_now = datetime.utcnow()
        local_now = datetime.now()
        
        # Fixed column positions - column 2 starts at a fixed offset from column 1
        col1_start = time_box_x + 2
        col2_start = time_box_x + 23  # Fixed position for column 2
        
        # Row 1: Column Headers (centered - offset by 6 spaces)
        print(f"\033[3;{col1_start + 6}H\033[1mUTC\033[0m", end='')
        print(f"\033[3;{col2_start + 6}H\033[1mLOCAL\033[0m", end='')
        
        # Row 2: UTC Time and Local Time
        print(f"\033[4;{col1_start}HUTC Time: \033[36m{utc_now.strftime('%H:%M:%S')}\033[0m", end='')
        print(f"\033[4;{col2_start}HTime: \033[33m{local_now.strftime('%H:%M:%S')}\033[0m", end='')
        
        # Row 3: UTC Date and Local Date
        print(f"\033[5;{col1_start}HUTC Date: \033[36m{utc_now.strftime('%Y-%m-%d')}\033[0m", end='')
        print(f"\033[5;{col2_start}HDate: \033[33m{local_now.strftime('%Y-%m-%d')}\033[0m", end='')
        
        # Row 4: UTC Day and Local Day
        print(f"\033[6;{col1_start}HUTC Day:  \033[36m{utc_now.strftime('%A')}\033[0m", end='')
        print(f"\033[6;{col2_start}HDay:  \033[33m{local_now.strftime('%A')}\033[0m", end='')
        
        # Last contact box (full width) - starts at row 8 (no blank line)
        last_contact_height = 6  # Fixed height: title + 4 content rows + bottom border
        draw_box(1, 8, width, last_contact_height, "LAST CONTACT")
        
        if last_contact:
            # Calculate available rows (subtract top border, title, and bottom border)
            available_rows = last_contact_height - 2
            
            # Layout depends on available width
            if width >= 80:
                # Wide layout - 3 columns
                col2_pos = width // 3 + 2
                col3_pos = 2 * width // 3 + 2
                
                # Calculate max text positions to stay within box (width - 3 for right border and padding)
                max_x = width - 3
                
                current_row = 9  # Start row for content
                max_row = 8 + last_contact_height - 1  # Don't print on or past bottom border
                
                # Row 1: Callsign, Mode, Band
                if current_row < max_row:
                    print(f"\033[{current_row};2H Callsign: \033[33m{last_contact['call']}\033[0m", end='')
                    
                    mode_text = f"Mode:     \033[33m{last_contact['mode']}\033[0m"
                    if col2_pos < max_x:
                        print(f"\033[{current_row};{col2_pos}H{mode_text[:col3_pos-col2_pos-1]}", end='')
                    
                    band_text = f"Band: \033[33m{last_contact['band']}\033[0m"
                    if col3_pos < max_x:
                        print(f"\033[{current_row};{col3_pos}H{band_text}", end='')
                    current_row += 1
                
                # Row 2: Grid, Freq, Date
                if current_row < max_row:
                    print(f"\033[{current_row};2H Grid:     \033[33m{last_contact['grid'] or 'N/A'}\033[0m", end='')
                    
                    if last_contact['freq'] and col2_pos < max_x:
                        freq_formatted = format_frequency(last_contact['freq'])
                        freq_text = f"Freq:     \033[33m{freq_formatted}\033[0m"
                        print(f"\033[{current_row};{col2_pos}H{freq_text[:col3_pos-col2_pos-1]}", end='')
                    
                    # Date in third column
                    if last_contact['qso_date'] and col3_pos < max_x:
                        date_text = f"\033[97mDate:\033[0m \033[33m{last_contact['qso_date']}\033[0m"
                        print(f"\033[{current_row};{col3_pos}H{date_text}", end='')
                    current_row += 1
                
                # Row 3: RST Sent, RST Rcvd, Time
                if current_row < max_row:
                    if last_contact['rst_sent']:
                        print(f"\033[{current_row};2H \033[97mRST Sent:\033[0m \033[33m{last_contact['rst_sent']}\033[0m", end='')
                    
                    if last_contact['rst_rcvd'] and col2_pos < max_x:
                        rst_r_text = f"RST Rcvd: \033[33m{last_contact['rst_rcvd']}\033[0m"
                        print(f"\033[{current_row};{col2_pos}H{rst_r_text[:col3_pos-col2_pos-1]}", end='')
                    
                    # Time in third column
                    if last_contact['time_on'] and col3_pos < max_x:
                        time_text = f"\033[97mTime:\033[0m \033[33m{last_contact['time_on']}\033[0m"
                        print(f"\033[{current_row};{col3_pos}H{time_text}", end='')
                    current_row += 1
                
                # Row 4: Logged, Comment
                if current_row < max_row:
                    ts = last_contact['timestamp'].strftime('%H:%M:%S UTC')
                    print(f"\033[{current_row};2H \033[97mLogged:\033[0m   \033[36m{ts}\033[0m", end='')
                    
                    # Comment in second and third columns
                    if last_contact.get('comment') and col2_pos < max_x:
                        comment_text = f"Comment:  \033[32m{last_contact['comment']}\033[0m"
                        print(f"\033[{current_row};{col2_pos}H{comment_text[:max_x-col2_pos]}", end='')
                    current_row += 1
            else:
                # Narrow layout - stacked
                print(f"\033[13;2H Call: \033[33m{last_contact['call']}\033[0m  Mode: \033[33m{last_contact['mode']}\033[0m  Band: \033[33m{last_contact['band']}\033[0m", end='')
                print(f"\033[14;2H Grid: \033[33m{last_contact['grid'] or 'N/A'}\033[0m", end='')
                if last_contact['freq']:
                    freq_formatted = format_frequency(last_contact['freq'])
                    print(f"  Freq: \033[33m{freq_formatted}\033[0m", end='')
                
                line = 15
                if last_contact['rst_sent'] or last_contact['rst_rcvd']:
                    print(f"\033[{line};2H RST: \033[33m{last_contact['rst_sent'] or 'N/A'}/{last_contact['rst_rcvd'] or 'N/A'}\033[0m", end='')
                    line += 1
                
                ts = last_contact['timestamp'].strftime('%H:%M:%S UTC')
                print(f"\033[{line};2H Logged: \033[36m{ts}\033[0m", end='')
                line += 1
                
                # Display comment if present
                if last_contact.get('comment') and line < 12 + last_contact_height - 1:
                    comment_display = last_contact['comment'][:width-5]
                    print(f"\033[{line};3H Comment: \033[32m{comment_display}\033[0m", end='')
        else:
            center_y = 8 + last_contact_height // 2
            center_x = width // 2 - 8
            print(f"\033[{center_y};{center_x}H \033[90mNo contacts yet\033[0m", end='')
        
        # Recent contacts list (full width, remaining space) - starts immediately after LAST CONTACT
        recent_y = 8 + last_contact_height
        recent_height = height - recent_y
        
        if recent_height >= 4:
            draw_box(1, recent_y, width, recent_height, "RECENT CONTACTS")
            
            # Header
            header_y = recent_y + 1
            if width >= 100:
                # Wide layout with comments
                print(f"\033[{header_y};2H \033[1mCall       Mode  Band   Grid   RST   Time    Comment\033[0m", end='')
            elif width >= 70:
                # Medium layout with comments
                print(f"\033[{header_y};2H \033[1mCall       Mode  Band   Grid   RST   Time    Comment\033[0m", end='')
            else:
                # Narrow layout without comments
                print(f"\033[{header_y};2H \033[1mCall       Mode  Band   Time\033[0m", end='')
            
            # Contacts (as many as fit)
            max_contacts = min(10, recent_height - 3)
            for i, contact in enumerate(recent_contacts[:max_contacts]):
                y = header_y + 1 + i
                call = contact['call'][:8].ljust(8)
                mode = contact['mode'][:5].ljust(5)
                band = contact['band'][:6].ljust(6)
                time_str = (contact['time_on'][:6] if contact['time_on'] else 'N/A').ljust(6)
                
                if width >= 100:
                    # Wide layout with all fields including comment
                    grid = (contact['grid'] or 'N/A')[:6].ljust(6)
                    rst = (contact['rst_rcvd'] or 'N/A')[:5].ljust(5)
                    comment = (contact.get('comment') or '')[:width-55]
                    print(f"\033[{y};2H \033[33m{call}\033[0m   {mode} {band} {grid} {rst} {time_str}  \033[32m{comment}\033[0m", end='')
                elif width >= 70:
                    # Medium layout with comments
                    grid = (contact['grid'] or 'N/A')[:6].ljust(6)
                    rst = (contact['rst_rcvd'] or 'N/A')[:5].ljust(5)
                    comment = (contact.get('comment') or '')[:width-50]
                    print(f"\033[{y};2H \033[33m{call}\033[0m   {mode} {band} {grid} {rst} {time_str}  \033[32m{comment}\033[0m", end='')
                else:
                    # Narrow layout without comments
                    print(f"\033[{y};2H \033[33m{call}\033[0m   {mode} {band} {time_str}", end='')
        
        # Footer (full width)
        footer_y = height
        print(f"\033[{footer_y};1H\033[44m\033[97m" + " " * width, end='')
        print(f"\033[{footer_y};3H Commands: (C)onfiguration | (Q)uit", end='')
        print("\033[0m", end='')
        
        sys.stdout.flush()
        time.sleep(1)

def listen_udp(username, password, udp_port):
    """Listen for UDP packets from WSJT-X"""
    global connection_status
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(1.0)
    
    try:
        sock.bind(('0.0.0.0', udp_port))
        connection_status = "Listening"
        if DEBUG:
            log_message(f"DEBUG: UDP listener started on port {udp_port}")
    except Exception as e:
        connection_status = f"Error: {str(e)[:20]}"
        if DEBUG:
            log_message(f"DEBUG: Failed to bind UDP socket: {e}")
        sys.exit(1)
    
    try:
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                
                if DEBUG:
                    log_message(f"=== DEBUG: Raw UDP Packet Received ===")
                    log_message(f"Source Address: {addr}")
                    log_message(f"Data Length: {len(data)} bytes")
                    log_message(f"Raw Bytes (first 200): {data[:200]}")
                
                message = data.decode('utf-8', errors='ignore').strip()
                
                if DEBUG:
                    log_message(f"Decoded Message: {message}")
                
                if '<call:' in message.lower() or ('<' in message and ':' in message and '>' in message):
                    if DEBUG:
                        log_message("DEBUG: Message contains ADIF data, processing...")
                    process_qso(message, username, password)
                else:
                    if DEBUG:
                        log_message("DEBUG: Message does not contain ADIF data, ignoring")
                    
            except socket.timeout:
                continue
                
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        if DEBUG:
            log_message("DEBUG: UDP listener stopped")

def handle_keyboard(username):
    """Handle keyboard input"""
    global running, show_menu
    
    # Set terminal to raw mode for single character input
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setcbreak(sys.stdin.fileno())
        
        while running:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                cmd = sys.stdin.read(1).lower()
                
                if cmd == 'q':
                    running = False
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                    print("\033[2J\033[?25h\033[1;1H")
                    print("\n\033[33mShutting down...\033[0m")
                    print(f"\033[32mTotal QSOs logged: {contact_count}\033[0m")
                    print(f"\033[36mLog file: {LOG_FILE}\033[0m\n")
                    print("73!\n")
                    os._exit(0)
                    
                elif cmd == 'c':
                    show_menu = True
                    # Restore normal terminal mode temporarily
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                    
                    # Show menu
                    should_restart = manage_credentials()
                    
                    if should_restart:
                        running = False
                        print("\n\033[33mPlease restart the script: python3 wsjt-eqsl.py\033[0m\n")
                        os._exit(0)
                    
                    # Return to raw mode
                    tty.setcbreak(sys.stdin.fileno())
                    show_menu = False
                    
            time.sleep(0.1)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def main():
    global UDP_PORT, DEBUG, AUTO_UPLOAD
    
    print("\033[2J\033[1;1H")
    print("\033[36m╔════════════════════════════════════════════════╗\033[0m")
    print(f"\033[36m║  WSJT-X to eQSL.cc Auto-Uploader v{VERSION}        ║\033[0m")
    print("\033[36m║  Copyright 2025 John A. Crutti, Jr. K5JCJ      ║\033[0m")
    print("\033[36m║  www.jaycrutti.com                             ║\033[0m")
    print("\033[36m║  Comments? recstudio@gmail.com                 ║\033[0m")
    print("\033[36m╚════════════════════════════════════════════════╝\033[0m\n")
    
    username, password, auto_upload, udp_port, debug = get_credentials()
    UDP_PORT = udp_port  # Update global UDP_PORT
    DEBUG = debug  # Update global DEBUG
    AUTO_UPLOAD = auto_upload  # Update global AUTO_UPLOAD
    
    print(f"\n\033[32m✓ Starting...\033[0m\n")
    time.sleep(1)
    
    log_message("=== WSJT-X to eQSL.cc Uploader Started ===")
    if DEBUG:
        log_message("DEBUG: Debug logging is ENABLED")
    
    # Start UDP listener in background thread
    udp_thread = threading.Thread(target=listen_udp, args=(username, password, udp_port), daemon=True)
    udp_thread.start()
    
    # Start keyboard handler in background thread
    kb_thread = threading.Thread(target=handle_keyboard, args=(username,), daemon=True)
    kb_thread.start()
    
    # Run status screen in main thread
    try:
        draw_status_screen(username)
    except KeyboardInterrupt:
        print("\033[2J\033[?25h\033[1;1H")
        print("\n\033[33mShutting down...\033[0m")
        print(f"\033[32mTotal QSOs logged: {contact_count}\033[0m")
        print(f"\033[36mLog file: {LOG_FILE}\033[0m\n")
        print("73!\n")

if __name__ == '__main__':
    main()
