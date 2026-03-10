"""
NCALayer dialog automation using PyAutoGUI
"""
import time
import logging
import threading
import pyautogui
import pygetwindow as gw

logger = logging.getLogger(__name__)

# Safety settings
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5


def wait_for_window(window_keywords, timeout=30):
    """Wait for a window with specific keywords in title"""
    logger.info(f"Waiting for window with keywords: {window_keywords}")
    start_time = time.time()

    while time.time() - start_time < timeout:
        all_titles = gw.getAllTitles()
        for title in all_titles:
            for keyword in window_keywords:
                if keyword.lower() in title.lower():
                    logger.info(f"Found window: {title}")
                    return title
        time.sleep(0.5)

    logger.warning(f"Window not found after {timeout} seconds")
    return None


def automate_ncalayer_dialog(cert_path, cert_password):
    """
    Automate NCALayer dialog:
    1. Wait for NCALayer authentication dialog
    2. Click folder icon to open file browser
    3. Type certificate path in file browser and press Enter
    4. Type password in password field
    5. Click Открыть button
    """
    try:
        # Step 1: Wait for NCALayer authentication dialog
        logger.info("Step 1: Waiting for NCALayer authentication dialog...")
        ncalayer_dialog = wait_for_window(["NCALayer", "Аутентификация"], timeout=30)

        if not ncalayer_dialog:
            logger.error("NCALayer dialog did not appear")
            return False

        time.sleep(0.5)

        # Step 2: Click on folder icon to open file browser
        logger.info("Step 2: Clicking folder icon to browse for certificate...")
        # Tab through the dialog to reach the folder button
        # Order: Просмотр данных -> Тип хранилища -> Обновить -> Место хранения -> Folder button
        pyautogui.press('tab')
        pyautogui.press('tab')
        pyautogui.press('tab')
        pyautogui.press('tab')
        pyautogui.press('space')  # Click the folder button
        time.sleep(0.5)

        # Step 3: Wait for file browser dialog
        logger.info("Step 3: Waiting for file browser dialog...")
        file_browser = wait_for_window(["Выберите файл", "Открыть", "Open"], timeout=20)

        if not file_browser:
            logger.error("File browser dialog did not appear")
            return False

        time.sleep(0.3)

        # Focus on filename field at the bottom using Alt+N or just click in it
        logger.info("Focusing on 'Имя файла' field...")
        pyautogui.hotkey('alt', 'n')  # Alt+N focuses on filename field in Windows dialogs
        time.sleep(0.1)

        # Extract just the filename from the full path
        import os
        cert_filename = os.path.basename(cert_path)

        # Type just the certificate filename (not full path)
        logger.info(f"Typing certificate filename: {cert_filename}")
        pyautogui.write(cert_filename)
        time.sleep(0.1)

        # Press Enter to select the file
        logger.info("Pressing Enter to select certificate...")
        pyautogui.press('enter')
        time.sleep(0.5)

        # Step 4: Back to NCALayer dialog - enter password
        logger.info("Step 4: Entering password in NCALayer dialog...")
        # Tab to password field
        pyautogui.press('tab')
        time.sleep(0.1)

        # Type password (keep typing for password, don't paste)
        logger.info("Typing password...")
        pyautogui.write(cert_password)
        time.sleep(0.1)

        # Step 5: Click Открыть button (press Enter)
        logger.info("Step 5: Clicking Открыть button...")
        pyautogui.press('enter')
        time.sleep(0.3)

        # Step 6: Select the key - Enter, Tab, Enter sequence
        logger.info("Step 6: Selecting key with Enter-Tab-Enter sequence...")
        pyautogui.press('enter')
        time.sleep(0.1)
        pyautogui.press('tab')
        time.sleep(0.1)
        pyautogui.press('enter')
        time.sleep(0.3)

        logger.info("NCALayer automation completed successfully!")

        # Final wait to ensure all dialogs close and keypresses complete
        time.sleep(0.1)

        return True

    except Exception as e:
        logger.error(f"Error in NCALayer automation: {e}", exc_info=True)
        return False


def automate_ncalayer_in_thread():
    """
    Start NCALayer automation in a background thread
    This should be called BEFORE clicking the button that triggers NCALayer

    Reads configuration from config.py
    """
    from config import Config

    def automation_task():
        time.sleep(1)  # Small delay before starting automation
        automate_ncalayer_dialog(Config.ECP_KEY_PATH, Config.ECP_KEY_PASSWORD)

    thread = threading.Thread(target=automation_task, daemon=True)
    thread.start()
    logger.info("NCALayer automation thread started")
    return thread
