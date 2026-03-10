"""
Clean implementation of Tizilim.gov.kz login automation
"""
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from config import Config
from utils import (
    click_element_with_fallbacks,
    find_element_with_fallbacks,
    wait_for_page_load,
    safe_send_keys
)
from ncalayer_handler import automate_ncalayer_in_thread
from lot_handler import wait_for_lot_to_appear, continuous_bidding

# Setup logging with UTF-8 encoding
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('login.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def setup_driver():
    """Initialize and configure Chrome WebDriver"""
    logger.info("Setting up Chrome WebDriver...")

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.page_load_strategy = 'normal'

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    logger.info("Chrome WebDriver ready")
    return driver


def authorize_with_ecp(driver, wait, skip_navigation=False):
    """
    Step 1: Authorize using ECP

    This clicks the ECP button on the website. The website's JavaScript
    will communicate with NCALayer and show the certificate selection dialog.
    NCALayer automation will automatically enter the password.

    Args:
        skip_navigation: If True, assumes we're already on login page
    """
    logger.info("="*60)
    logger.info("STEP 1: ECP Authorization")
    logger.info("="*60)

    try:
        if not skip_navigation:
            driver.get(Config.LOGIN_URL)
            wait_for_page_load(driver)
        else:
            logger.info("Already on login page, skipping navigation")
            time.sleep(1)

        # First, check the terms checkbox to enable ECP button
        logger.info("Looking for terms checkbox...")
        checkbox_selectors = [
            (By.CSS_SELECTOR, "input[type='checkbox']"),
            (By.CSS_SELECTOR, ".v-checkbox input"),
            (By.XPATH, "//input[@type='checkbox']"),
            (By.XPATH, "//div[contains(@class, 'v-checkbox')]//input"),
        ]

        try:
            click_element_with_fallbacks(driver, checkbox_selectors, "terms checkbox", timeout=10)
            logger.info("Terms checkbox checked!")
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Could not find/click checkbox (may not be required): {e}")

        # Find and click ECP button
        ecp_button_selectors = [
            (By.CSS_SELECTOR, "button.v-btn.bg-main-light-blue"),
            (By.XPATH, "//button[contains(@class, 'bg-main-light-blue')]"),
            (By.XPATH, "//span[contains(text(), 'ЭЦҚ')]//parent::button"),
            (By.XPATH, "//button[contains(text(), 'ЭЦП')]"),
        ]

        logger.info("Looking for ECP button...")

        # Start NCALayer automation in background BEFORE clicking button
        logger.info("Starting NCALayer automation in background...")
        automation_thread = automate_ncalayer_in_thread()

        # Click ECP button
        click_element_with_fallbacks(driver, ecp_button_selectors, "ECP button", timeout=15)
        logger.info("ECP button clicked!")

        logger.info("NCALayer automation is handling certificate selection and password...")
        logger.info("Waiting for ECP signing to complete...")

        # Wait for automation to complete
        automation_thread.join(timeout=60)

        logger.info("NCALayer thread finished, waiting for all keypresses to complete...")

        # Important: Wait for all NCALayer keypresses to finish before proceeding
        # The automation does Enter-Tab-Enter at the end, we need to ensure
        # those keypresses don't interfere with the login form
        time.sleep(0.5)

        logger.info("ECP authorization completed!")
        time.sleep(0.1)

    except Exception as e:
        logger.error(f"Error in ECP authorization: {e}", exc_info=True)
        raise


def authorize_with_credentials(driver, wait):
    """
    Step 2: Login with email and password

    After ECP signing, the website shows a login form.
    This function fills in the email and password.
    """
    logger.info("="*60)
    logger.info("STEP 2: Login with Credentials")
    logger.info("="*60)

    try:
        # Wait for login form to appear
        logger.info("Waiting for login form...")
        time.sleep(3)

        # Fill in email
        logger.info("Looking for email field...")
        email_selectors = [
            (By.ID, "app-text-field-Электрондық пошта"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.XPATH, "//input[contains(@id, 'пошта')]"),
            (By.XPATH, "//input[@type='email']"),
        ]

        email_field = find_element_with_fallbacks(driver, email_selectors, "email field", timeout=15)
        safe_send_keys(email_field, Config.EMAIL)
        logger.info(f"Entered email: {Config.EMAIL}")
        time.sleep(0.1)

        # Fill in password
        logger.info("Looking for password field...")
        password_selectors = [
            (By.ID, "app-text-field-Құпия сөз"),
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.XPATH, "//input[contains(@id, 'сөз')]"),
            (By.XPATH, "//input[@type='password']"),
        ]

        password_field = find_element_with_fallbacks(driver, password_selectors, "password field", timeout=10)
        safe_send_keys(password_field, Config.PASSWORD)
        logger.info("Entered password")
        time.sleep(0.1)

        # Click login button - must be more specific to avoid clicking ECP button
        logger.info("Looking for login button in modal/form...")
        login_button_selectors = [
            # Look for button near the password field (in same form/container)
            (By.XPATH, "//input[@type='password']/ancestor::form//button[contains(@class, 'bg-main-light-blue')]"),
            (By.XPATH, "//input[@type='password']/ancestor::div[contains(@class, 'v-card')]//button[contains(@class, 'bg-main-light-blue')]"),
            # Look for button with specific size (login button is size-default, ECP is size-large)
            (By.CSS_SELECTOR, "button.v-btn.bg-main-light-blue.v-btn--size-default"),
            # Look for submit button
            (By.CSS_SELECTOR, "button[type='submit']"),
            # Last resort - text match
            (By.XPATH, "//button[contains(text(), 'Кіру')]"),
        ]

        click_element_with_fallbacks(driver, login_button_selectors, "login button", timeout=10)
        logger.info("Login button clicked!")

        logger.info("Login completed successfully!")
        time.sleep(3)

    except Exception as e:
        logger.error(f"Error in credential authorization: {e}", exc_info=True)
        raise


def process_lot(driver, wait, lot_url):
    """
    Process a single lot URL

    Args:
        driver: WebDriver instance
        wait: WebDriverWait instance
        lot_url: URL of the lot to process
    """
    logger.info("="*60)
    logger.info(f"PROCESSING LOT: {lot_url}")
    logger.info("="*60)

    try:
        # Navigate to lot URL (will redirect to login if not authenticated)
        logger.info(f"Navigating to lot: {lot_url}")
        driver.get(lot_url)

        # Wait a bit for potential redirect
        logger.info("Waiting for potential redirect to login page...")
        time.sleep(3)

        wait_for_page_load(driver)
        time.sleep(2)

        # Check if we're on login page
        current_url = driver.current_url
        logger.info(f"Current URL after navigation: {current_url}")
        logger.info(f"Page title: {driver.title}")

        if "auth/login" in current_url:
            logger.info("Detected redirect to login page, waiting for page to fully load...")

            # Wait for login page to fully load
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                logger.info("Login page fully loaded")
            except Exception as e:
                logger.warning(f"Page load wait timeout: {e}")

            # Additional wait for any JavaScript to initialize
            time.sleep(2)

            logger.info("Proceeding with authentication")

            # Authorize with ECP (skip navigation since we're already there)
            authorize_with_ecp(driver, wait, skip_navigation=True)

            # Login with credentials
            authorize_with_credentials(driver, wait)

            logger.info("Authentication completed!")
            time.sleep(2)

            # Check where we ended up after login
            current_url = driver.current_url
            logger.info(f"After login, current URL: {current_url}")

            # If not on lot page, navigate to it manually
            if "/lots/" not in current_url:
                logger.info(f"Not on lot page, navigating to lot URL: {lot_url}")
                driver.get(lot_url)
                wait_for_page_load(driver)
                time.sleep(2)
                logger.info(f"Navigated to lot page: {driver.current_url}")

        # Now we should be on the lot page
        logger.info(f"Successfully on lot page: {driver.title}")

        # Wait for submit button to appear (lot to become active)
        logger.info("Waiting for submit button to appear...")
        if not wait_for_lot_to_appear(driver, lot_url):
            logger.error("Submit button did not appear - lot may not be active yet")
            return False

        # Start continuous bidding until target price reached
        logger.info("Submit button is available, starting continuous bidding...")
        if not continuous_bidding(driver, wait):
            logger.error("Failed to complete bidding")
            return False

        logger.info("Lot processed successfully!")
        return True

    except Exception as e:
        logger.error(f"Error processing lot {lot_url}: {e}", exc_info=True)
        return False


def main():
    """Main flow: Navigate to lots first, authenticate when needed"""
    driver = setup_driver()
    wait = WebDriverWait(driver, Config.DEFAULT_TIMEOUT)

    try:
        # Process each lot URL
        for i, lot_url in enumerate(Config.LOT_URLS, 1):
            logger.info(f"\nProcessing lot {i}/{len(Config.LOT_URLS)}")
            success = process_lot(driver, wait, lot_url)

            if success:
                logger.info(f"[OK] Lot {i} processed successfully")
            else:
                logger.warning(f"[FAILED] Lot {i} failed")

            # Wait between lots
            if i < len(Config.LOT_URLS):
                time.sleep(2)

        logger.info("="*60)
        logger.info("ALL LOTS PROCESSED!")
        logger.info("="*60)

        # Keep browser open
        input("Press Enter to close browser...")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        input("Press Enter to close browser...")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
