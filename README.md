# Tizilim.gov.kz Login Automation

Clean implementation of automated login for tizilim.gov.kz using Selenium and PyAutoGUI.

## Setup

1. Install dependencies:
```bash
cd tizilim_clean
pip install -r requirements.txt
```

2. Make sure NCALayer is installed and running

3. Update credentials in `config.py` if needed

## Usage

Run the login script:
```bash
python login.py
```

## How it works

1. Opens Chrome browser and navigates to login page
2. Clicks the confirmation checkbox (with multiple selector fallbacks)
3. Starts NCALayer automation in background thread
4. Clicks ECP login button
5. PyAutoGUI automatically handles NCALayer dialogs:
   - Waits for file selection dialog
   - Types certificate path and presses Enter
   - Waits for password dialog
   - Types password and presses Enter
6. Fills in email and password on the website (with fallback selectors)
7. Clicks final login button

## Features

- Multiple selector fallbacks for resilience
- Background threading for NCALayer automation
- Smart wait conditions for page loading
- Comprehensive logging to file and console
- JavaScript click fallback if normal click fails

## Files

- `login.py` - Main login automation script with working patterns
- `ncalayer_handler.py` - NCALayer dialog automation using PyAutoGUI
- `utils.py` - Utility functions for smart waits and fallbacks
- `config.py` - Configuration and credentials
- `requirements.txt` - Python dependencies
