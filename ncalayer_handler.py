"""
NCALayer dialog automation using Windows UI automation with a PyAutoGUI fallback.
"""
import logging
import os
import threading
import time

import pyautogui
import pygetwindow as gw

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    pyperclip = None
    PYPERCLIP_AVAILABLE = False

from config import Config

try:
    from pywinauto import Desktop
    from pywinauto.keyboard import send_keys
    PYWINAUTO_AVAILABLE = True
except ImportError:
    Desktop = None
    send_keys = None
    PYWINAUTO_AVAILABLE = False

logger = logging.getLogger(__name__)

# Safety settings
pyautogui.FAILSAFE = True
pyautogui.PAUSE = Config.NCALAYER_ACTION_DELAY

WINDOW_KEYWORDS_NCALAYER = ["NCALayer", "Аутентификация"]
WINDOW_KEYWORDS_FILE = ["Выберите файл", "Открыть", "Open"]
OPEN_BUTTON_KEYWORDS = ["Ашу", "Открыть", "Open", "OK", "ОК"]
KEY_SELECTION_TEXTS = ["Кілтті таңдаңыз", "Выберите ключ", "Select key"]
SIGN_BUTTON_KEYWORDS = ["Қол қою", "Подписать", "Sign"]


def _matches_window(title, keywords):
    return bool(title) and any(keyword.lower() in title.lower() for keyword in keywords)


def _sleep(delay=None):
    time.sleep(Config.NCALAYER_ACTION_DELAY if delay is None else delay)


def _focus_window_by_title(window_title):
    try:
        windows = gw.getWindowsWithTitle(window_title)
        if not windows:
            return False
        window = windows[0]
        if getattr(window, "isMinimized", False):
            window.restore()
            _sleep()
        window.activate()
        _sleep()
        return True
    except Exception as exc:
        logger.debug(f"Could not focus window '{window_title}': {exc}")
        return False


def _get_window_by_title(window_title):
    try:
        windows = gw.getWindowsWithTitle(window_title)
        return windows[0] if windows else None
    except Exception as exc:
        logger.debug(f"Could not get window '{window_title}': {exc}")
        return None


def _click_relative_in_window(window_title, x_ratio, y_ratio):
    window = _get_window_by_title(window_title)
    if window is None:
        return False

    try:
        x = int(window.left + (window.width * x_ratio))
        y = int(window.top + (window.height * y_ratio))
        pyautogui.click(x, y)
        _sleep()
        return True
    except Exception as exc:
        logger.debug(f"Could not click relative position in '{window_title}': {exc}")
        return False


def _get_window_bounds(window_title):
    window = _get_window_by_title(window_title)
    if window is None:
        return None
    return (window.left, window.top, window.width, window.height)


def _focus_desktop_window(window):
    try:
        if window.is_minimized():
            window.restore()
            _sleep()
        window.set_focus()
        _sleep()
        return True
    except Exception as exc:
        logger.debug(f"Could not focus window via pywinauto: {exc}")
        return False


def _wait_for_desktop_window(window_keywords, timeout=30):
    if not PYWINAUTO_AVAILABLE:
        return None

    desktop = Desktop(backend="uia")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            for window in desktop.windows():
                title = window.window_text()
                if _matches_window(title, window_keywords):
                    logger.info(f"Found window via pywinauto: {title}")
                    return window
        except Exception as exc:
            logger.debug(f"Desktop scan failed: {exc}")
        time.sleep(Config.NCALAYER_WINDOW_POLL_INTERVAL)
    return None


def _window_contains_any_text(window, expected_texts):
    try:
        texts = []
        for control in window.descendants():
            text = control.window_text()
            if text:
                texts.append(text)
        joined = "\n".join(texts).lower()
        return any(expected.lower() in joined for expected in expected_texts)
    except Exception as exc:
        logger.debug(f"Window text scan failed: {exc}")
        return False


def _wait_for_key_selection_window_fast(timeout=10):
    if not PYWINAUTO_AVAILABLE:
        return None

    start_time = time.time()
    desktop = Desktop(backend="uia")
    while time.time() - start_time < timeout:
        try:
            for window in desktop.windows():
                title = window.window_text()
                if _matches_window(title, WINDOW_KEYWORDS_NCALAYER) and _window_contains_any_text(window, KEY_SELECTION_TEXTS):
                    logger.info(f"Found key selection window via pywinauto: {title}")
                    return window
        except Exception as exc:
            logger.debug(f"Key selection scan failed: {exc}")
        time.sleep(Config.NCALAYER_WINDOW_POLL_INTERVAL)

    return None


def _wait_for_key_selection_window_fallback(timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        windows = gw.getWindowsWithTitle("NCALayer")
        if windows:
            selection_window = max(windows, key=lambda window: window.width * window.height)
            logger.info(f"Using key selection window fallback: {selection_window.title}")
            return selection_window.title
        time.sleep(Config.NCALAYER_WINDOW_POLL_INTERVAL)

    return None


def _handle_key_selection_fast():
    selection_window = _wait_for_key_selection_window_fast(timeout=10)
    if selection_window is None:
        logger.warning("Key selection window did not appear")
        return False

    _focus_desktop_window(selection_window)

    try:
        key_items = [
            control for control in selection_window.descendants()
            if control.control_type() in {"ListItem", "DataItem"} and control.is_visible() and control.is_enabled()
        ]
        if key_items:
            key_items[0].click_input()
            _sleep()
    except Exception as exc:
        logger.debug(f"Direct key selection failed: {exc}")

    if _click_button_by_title(selection_window, SIGN_BUTTON_KEYWORDS):
        return True

    try:
        selection_window.set_focus()
        _send_keys_fast("{ENTER}")
        return True
    except Exception as exc:
        logger.debug(f"Key selection Enter fallback failed: {exc}")
        return False


def _handle_key_selection_fallback():
    selection_window_title = _wait_for_key_selection_window_fallback(timeout=10)
    if not selection_window_title:
        logger.warning("Key selection window did not appear in fallback mode")
        return False

    _focus_window_by_title(selection_window_title)

    # Click the first key row, then click the sign button.
    _click_relative_in_window(
        selection_window_title,
        Config.NCALAYER_KEY_LIST_X_RATIO,
        Config.NCALAYER_KEY_LIST_Y_RATIO,
    )
    _click_relative_in_window(
        selection_window_title,
        Config.NCALAYER_SIGN_BUTTON_X_RATIO,
        Config.NCALAYER_SIGN_BUTTON_Y_RATIO,
    )
    return True


def _find_edit_control(window):
    try:
        edits = [control for control in window.descendants(control_type="Edit") if control.is_visible() and control.is_enabled()]
        if edits:
            return edits[-1]
    except Exception as exc:
        logger.debug(f"Edit control lookup failed: {exc}")
    return None


def _find_edit_controls(window):
    try:
        return [control for control in window.descendants(control_type="Edit") if control.is_visible() and control.is_enabled()]
    except Exception as exc:
        logger.debug(f"Edit controls lookup failed: {exc}")
        return []


def _click_button_by_title(window, title_keywords):
    try:
        buttons = [control for control in window.descendants(control_type="Button") if control.is_visible() and control.is_enabled()]
        for keyword in title_keywords:
            for button in buttons:
                if keyword.lower() in button.window_text().lower():
                    button.click_input()
                    _sleep()
                    return True
    except Exception as exc:
        logger.debug(f"Button lookup failed: {exc}")
    return False


def _set_text_fast(window, text):
    edit_control = _find_edit_control(window)
    if not edit_control:
        return False

    try:
        edit_control.set_edit_text(text)
        _sleep()
        return True
    except Exception as exc:
        logger.debug(f"set_edit_text failed: {exc}")
        return False


def _send_keys_fast(keys):
    send_keys(keys, with_spaces=True, pause=Config.NCALAYER_KEY_INTERVAL)
    _sleep()


def _paste_text(text):
    if not PYPERCLIP_AVAILABLE:
        return False

    try:
        pyperclip.copy(text)
        _sleep()
        pyautogui.hotkey('ctrl', 'v')
        _sleep()
        return True
    except Exception as exc:
        logger.debug(f"Clipboard paste failed: {exc}")
        return False


def wait_for_window(window_keywords, timeout=30):
    """Wait for a window with specific keywords in title."""
    logger.info(f"Waiting for window with keywords: {window_keywords}")

    desktop_window = _wait_for_desktop_window(window_keywords, timeout)
    if desktop_window is not None:
        return desktop_window.window_text()

    start_time = time.time()
    while time.time() - start_time < timeout:
        all_titles = gw.getAllTitles()
        for title in all_titles:
            if _matches_window(title, window_keywords):
                logger.info(f"Found window: {title}")
                return title
        time.sleep(Config.NCALAYER_WINDOW_POLL_INTERVAL)

    logger.warning(f"Window not found after {timeout} seconds")
    return None


def automate_ncalayer_dialog_fast(cert_path, cert_password):
    """Fast path using pywinauto for direct window interaction."""
    if not PYWINAUTO_AVAILABLE:
        logger.info("pywinauto is not available, skipping fast backend")
        return False

    try:
        logger.info("Fast NCALayer path: waiting for authentication dialog...")
        ncalayer_dialog = _wait_for_desktop_window(WINDOW_KEYWORDS_NCALAYER, timeout=Config.NCALAYER_TIMEOUT)
        if ncalayer_dialog is None:
            logger.error("NCALayer dialog did not appear")
            return False

        _focus_desktop_window(ncalayer_dialog)

        edit_controls = _find_edit_controls(ncalayer_dialog)
        if len(edit_controls) >= 2:
            storage_edit = edit_controls[0]
            password_edit = edit_controls[-1]

            try:
                current_storage = storage_edit.get_value()
            except Exception:
                current_storage = storage_edit.window_text()

            if not Config.NCALAYER_USE_SAVED_STORAGE or not current_storage.strip():
                storage_edit.set_edit_text(os.path.dirname(cert_path))
                _sleep()

            password_edit.set_edit_text(cert_password)
            _sleep()
        else:
            logger.warning("Could not map NCALayer fields directly, using keyboard fallback")
            if Config.NCALAYER_USE_SAVED_STORAGE:
                _send_keys_fast("{TAB 4}")
            else:
                _send_keys_fast("{TAB 2}")
                _send_keys_fast(os.path.dirname(cert_path))
                _send_keys_fast("{TAB 2}")
            _send_keys_fast(cert_password)

        if not _click_button_by_title(ncalayer_dialog, OPEN_BUTTON_KEYWORDS):
            _send_keys_fast("{TAB 2}{SPACE}")

        _handle_key_selection_fast()

        logger.info("Fast NCALayer automation completed successfully")
        return True
    except Exception as exc:
        logger.error(f"Fast NCALayer automation failed: {exc}", exc_info=True)
        return False


def automate_ncalayer_dialog(cert_path, cert_password):
    """
    Automate NCALayer dialog using the saved storage path.
    """
    try:
        if Config.NCALAYER_BACKEND == "pywinauto" and automate_ncalayer_dialog_fast(cert_path, cert_password):
            return True

        logger.warning("Fast backend unavailable or failed, falling back to PyAutoGUI flow")

        # Step 1: Wait for NCALayer authentication dialog
        logger.info("Step 1: Waiting for NCALayer authentication dialog...")
        ncalayer_dialog = wait_for_window(WINDOW_KEYWORDS_NCALAYER, timeout=30)

        if not ncalayer_dialog:
            logger.error("NCALayer dialog did not appear")
            return False

        _focus_window_by_title(ncalayer_dialog)
        _sleep()

        # Step 2: Focus password field directly.
        logger.info("Step 2: Focusing password field...")
        focused_with_click = _click_relative_in_window(
            ncalayer_dialog,
            Config.NCALAYER_PASSWORD_FIELD_X_RATIO,
            Config.NCALAYER_PASSWORD_FIELD_Y_RATIO,
        )

        if not focused_with_click:
            logger.info("Password field click fallback failed, using keyboard navigation")
            if Config.NCALAYER_USE_SAVED_STORAGE:
                pyautogui.press('tab', presses=4, interval=Config.NCALAYER_KEY_INTERVAL)
            else:
                pyautogui.press('tab', presses=2, interval=Config.NCALAYER_KEY_INTERVAL)
                pyautogui.write(os.path.dirname(cert_path), interval=Config.NCALAYER_KEY_INTERVAL)
                _sleep()
                pyautogui.press('tab', presses=2, interval=Config.NCALAYER_KEY_INTERVAL)
        _sleep()

        # Step 3: Type password.
        logger.info("Step 3: Typing password...")
        pyautogui.hotkey('ctrl', 'a')
        _sleep()
        if not _paste_text(cert_password):
            pyautogui.write(cert_password, interval=Config.NCALAYER_KEY_INTERVAL)
        _sleep()

        # Step 4: Click the open button.
        logger.info("Step 4: Clicking open button...")
        open_clicked = _click_relative_in_window(
            ncalayer_dialog,
            Config.NCALAYER_OPEN_BUTTON_X_RATIO,
            Config.NCALAYER_OPEN_BUTTON_Y_RATIO,
        )
        if not open_clicked:
            pyautogui.press('tab', presses=2, interval=Config.NCALAYER_KEY_INTERVAL)
            pyautogui.press('space')
        _sleep()

        # Step 5: Select the key in the separate selection window.
        logger.info("Step 5: Waiting for key selection window...")
        _handle_key_selection_fallback()
        _sleep()

        logger.info("NCALayer automation completed successfully!")

        # Final wait to ensure all dialogs close and keypresses complete
        _sleep()

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
    def automation_task():
        if not os.path.exists(Config.ECP_KEY_PATH):
            logger.error(f"Certificate file does not exist: {Config.ECP_KEY_PATH}")
            return
        time.sleep(Config.NCALAYER_START_DELAY)
        automate_ncalayer_dialog(Config.ECP_KEY_PATH, Config.ECP_KEY_PASSWORD)

    thread = threading.Thread(target=automation_task, daemon=True)
    thread.start()
    logger.info("NCALayer automation thread started")
    return thread
