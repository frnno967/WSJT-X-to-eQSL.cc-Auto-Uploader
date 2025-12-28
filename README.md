# WSJT-X to eQSL.cc Auto-Uploader

**Version 1.1.0**  
**Author:** John A. Crutti, Jr. (K5JCJ)  
**Website:** www.jaycrutti.com  
**Contact:** recstudio@gmail.com

---

<img width="866" height="557" alt="image" src="https://github.com/user-attachments/assets/c17c1bb3-313d-4826-8ac6-896fb80b4b15" />

## Overview

WSJT-X to eQSL.cc Auto-Uploader is a Python-based tool for Amateur Radio that automatically listens for WSJT-X logged network ADIF broadcasts over UDP and uploads them to your eQSL.cc account in real-time. The program features a clean, terminal-based user interface that displays contact information, statistics, and upload status.

## Features

- **Automatic QSO Upload**: Automatically uploads contacts to eQSL.cc as they are logged in WSJT-X from anywhere on your local network
- **Real-time Monitoring**: Live display of contact information including callsign, mode, band, frequency, grid square, RST reports, and comments
- **Contact History**: View your last contacts in the recent contacts list
- **Configuration Management**: Save your eQSL.cc credentials and settings for later use
- **Retro BBS Style**: Simple and lightweight program interface inspired by retro BBS interfaces
- **Upload Statistics**: Track total QSOs logged for the session 
- **Error Handling**: Retry failed uploads with interactive error dialogs
- **Debug Mode**: Extensive logging of debug information if needed

## Requirements

- Python 3.6 or higher
- Linux operating system (tested on Ubuntu)
- Terminal window with minimum size of 60x20 characters (80x24 or larger recommended)
- Active internet connection for eQSL.cc uploads
- WSJT-X configured to broadcast logged ADIF data via UDP

### Python Dependencies

The following Python packages are required:

```bash
pip install requests
```

Standard library modules used (no installation needed):
- socket
- sys
- re
- json
- os
- threading
- time
- shutil
- select
- termios
- tty
- datetime
- getpass

## Installation

1. Download the `wsjtx2eqsl.py` file
2. Make the script executable:
   ```bash
   chmod +x wsjtx2eqsl.py
   ```
3. Install required dependencies:
   ```bash
   pip install requests
   ```

## WSJT-X Configuration

Before using this program, you need to configure WSJT-X to broadcast logged ADIF data:

1. Open WSJT-X
2. Go to **File → Settings**
3. Select the **Reporting** tab
4. Check the box for **Enable logged contact ADIF broadcast**
5. Set the UDP Server port to **2333** (or your preferred port)
6. Click **OK** to save settings

## Usage

### First Time Setup

1. Run the program:
   ```bash
   python3 wsjtx2eqsl.py
   ```
   or
   ```bash
   ./wsjtx2eqsl.py
   ```

2. You will be prompted to enter:
   - **eQSL.cc username** (your callsign)
   - **eQSL.cc password**
   - **Auto-upload preference** (y/n)
   - **UDP port** (default: 2333)
   - **Save configuration** (y/n)

3. If you choose to save your configuration, your credentials will be stored in `~/.wsjtx2eqsl.conf` (permissions set to 600 for security)

### Running the Program

Once configured, the program will:

1. Load your saved credentials automatically
2. Start listening for WSJT-X broadcasts on the configured UDP port
3. Display a real-time status screen with:
   - **STATUS** panel: Connection status, username, auto-upload setting, QSO count, and upload status
   - **TIME & DATE** panel: UTC and local time/date information
   - **LAST CONTACT** panel: Detailed information about the most recent QSO
   - **RECENT CONTACTS** panel: List of the last contacts

### Keyboard Commands

While the program is running, you can use the following commands:

- **C** - Open Configuration menu
- **Q** - Quit the program

### Configuration Menu

Press **C** to access the configuration menu with these options:

1. **View current settings** - Display saved username, auto-upload status, and UDP port
2. **Change credentials** - Update your eQSL.cc username and password
3. **Toggle auto-upload** - Enable/disable automatic uploading to eQSL.cc
4. **Change UDP port** - Modify the UDP port for WSJT-X broadcasts
5. **Toggle debug logging** - Save comprehensive debug information to log file
6. **Delete saved configuration** - Remove stored credentials
7. **Return to monitoring** - Go back to the main screen

**Note:** Changes to credentials or UDP port require restarting the program to take effect.

## Understanding the Display

### STATUS Panel
- **Connection**: Shows listening status and UDP port
- **Username**: Your eQSL.cc username 
- **Auto-upload**: ON/OFF status
- **QSOs**: Total number of contacts logged for the session 
- **Last Upload**: Status of the most recent upload attempt

### TIME & DATE Panel
- **UTC Time/Date/Day**: Current UTC time (used for logging)
- **Time/Date/Day**: Your local time

### LAST CONTACT Panel
Displays detailed information about the most recent QSO:
- **Callsign**: Station contacted
- **Mode**: Operating mode (FT8, FT4, etc.)
- **Band**: Frequency band (40m, 20m, etc.)
- **Grid**: Maidenhead grid square
- **Freq**: Operating frequency in MHz
- **Date**: QSO date (YYYYMMDD format)
- **RST Sent**: Signal report sent
- **RST Rcvd**: Signal report received
- **Time**: QSO time (HHMMSS format)
- **Logged**: Timestamp when the QSO was received by this program
- **Comment**: Additional comments (typically includes sent/received reports for FT8)

### RECENT CONTACTS Panel
Shows a scrolling list of your last 10 contacts with:
- Callsign
- Mode
- Band
- Grid square
- RST received
- Time
- Comment

## Log File

All activity is logged to `wsjtx2eqsl.log` in the user's home directory. This includes:
- Program start/stop events
- QSO logging events
- Upload successes and failures

## Troubleshooting

### No contacts appearing
- Verify WSJT-X has 'Enable logged contact ADIF broadcast' under Secondary UDP Server checked
- Check that the UDP port matches between WSJT-X and this program
- Ensure WSJT-X is actually logging contacts (QSO must be logged, not just decoded)

### Upload failures
- Verify your eQSL.cc credentials are correct
- Check your internet connection
- Review the error message displayed
- Press **R** when prompted to retry the upload
- Check `wsjtx2eqsl.log` for detailed error information

### Terminal display issues
- Ensure your terminal is at least 60x20 characters (80x24 or larger recommended)
- Some terminal emulators may not display box-drawing characters correctly
- Try using a different terminal emulator if display issues persist

### Configuration file location
The configuration file is stored at: `~/.wsjtx2eqsl.conf`

To manually remove it:
```bash
rm ~/.wsjtx2eqsl.conf
```

## Security Notes

- Your eQSL.cc password is stored in plain text in `~/.wsjtx2eqsl.conf`
- The file permissions are set to 600 (read/write for owner only)
- Keep this configuration file secure
- Do not share your configuration file with others
- Consider using a unique password for eQSL.cc

## Testing Mode

If you disable auto-upload (set to OFF), the program will:
- Still receive and display contacts from WSJT-X
- Log all QSOs to the log file
- NOT automatically upload to eQSL.cc

This is useful for:
- Testing the program

## Tips for Best Results

1. **Terminal Size**: Use at least an 80x24 ANSI terminal for the best display experience
2. **Run in Background**: Consider running in a terminal multiplexer (tmux/screen) so you can keep it running while operating
3. **Monitor Log File**: Check `wsjtx2eqsl.log` periodically for any issues
4. **Auto-upload**: Enable auto-upload for hands-free eQSL logging
5. **Backup Credentials**: Remember your eQSL.cc password in case you need to reconfigure

## Exiting the Program

To exit the program safely:
1. Press **Q** 
2. The program will display:
   - Total QSOs logged during this session
   - Location of the log file
   - A friendly "73!" sign-off

You can also use **Ctrl+C** to exit, though using **Q** is preferred for a clean shutdown.

## Version History

**Version 1.1.0** (2025)
- Adjusted formatting of fields in windows
- Fixed input validation of UDP config dialog
- Eliminated need to restart after changing the auto-upload setting
- Made debugging output more comprehensive
- Moved log file to user's home directory with config file

**Version 1.0.0** (2025)
- Initial release
- Automatic ADIF upload to eQSL.cc
- Real-time contact monitoring
- Configuration management
- Error handling and retry capability

## Support

For questions, comments, or bug reports:
- Email: recstudio@gmail.com
- Website: www.jaycrutti.com

## License

Copyright 2025 John A. Crutti, Jr. (K5JCJ)

---

**73 and see you on the bands!**
