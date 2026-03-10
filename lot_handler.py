"""
Lot handling functions for bidding
"""
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from config import Config
from utils import (
    find_element_with_fallbacks,
    click_element_with_fallbacks,
    wait_for_page_load
)
from ncalayer_handler import automate_ncalayer_in_thread

logger = logging.getLogger(__name__)


def wait_for_lot_to_appear(driver, lot_url, max_wait_hours=None):
    """
    Constantly refresh until lot appears (submit button is visible)

    Args:
        driver: WebDriver instance
        lot_url: URL of the lot
        max_wait_hours: Maximum hours to wait (defaults to Config.LOT_MAX_WAIT_HOURS)

    Returns:
        True if lot appeared, False if timeout
    """
    if max_wait_hours is None:
        max_wait_hours = Config.LOT_MAX_WAIT_HOURS

    logger.info("="*60)
    logger.info("Waiting for Lot Submit Button to Appear")
    logger.info("="*60)
    logger.info(f"Lot URL: {lot_url}")
    logger.info(f"Max wait time: {max_wait_hours} hours")

    start_time = time.time()
    max_wait_time = max_wait_hours * 3600
    poll_interval = Config.LOT_CHECK_INTERVAL_START
    check_count = 0

    submit_button_selectors = [
        (By.CSS_SELECTOR, "button.v-btn.v-theme--light.bg-red.v-btn--density-default.v-btn--size-default.v-btn--variant-flat.mt-3"),
        (By.CSS_SELECTOR, "button.bg-red"),  # Red submit button
        (By.XPATH, "//button[contains(@class, 'bg-red')]"),
        (By.XPATH, "//button[contains(text(), 'Отправить')]"),
        (By.XPATH, "//button[contains(text(), 'Жіберу')]"),  # Kazakh
        (By.CSS_SELECTOR, "button[type='submit']"),
    ]

    while (time.time() - start_time) < max_wait_time:
        check_count += 1
        elapsed = time.time() - start_time

        logger.info(f"Check #{check_count}: Refreshing lot page...")
        driver.refresh()
        wait_for_page_load(driver)

        # Wait extra time for Vue.js to render the form
        time.sleep(2)

        # First check if price fields are present (debugging)
        try:
            start_price_elem = driver.find_element(By.ID, "app-text-field-Стартовая цена")
            logger.debug(f"✓ Starting price field found")
        except:
            logger.debug("✗ Starting price field NOT found")

        try:
            current_price_elem = driver.find_element(By.ID, "app-text-field-Текущая цена")
            logger.debug(f"✓ Current price field found")
        except:
            logger.debug("✗ Current price field NOT found")

        try:
            bid_field_elem = driver.find_element(By.ID, "app-text-field-Сумма")
            logger.debug(f"✓ Bid input field found")
        except:
            logger.debug("✗ Bid input field NOT found")

        # Check if lot is available by looking for submit button
        try:
            for by, selector in submit_button_selectors:
                try:
                    submit_btn = driver.find_element(by, selector)
                    logger.debug(f"Found button with selector: {selector}")
                    logger.debug(f"Button visible: {submit_btn.is_displayed()}, enabled: {submit_btn.is_enabled()}")
                    if submit_btn.is_displayed() and submit_btn.is_enabled():
                        logger.info("="*60)
                        logger.info(f"SUCCESS: Submit button appeared after {check_count} checks!")
                        logger.info(f"Time elapsed: {elapsed/60:.1f} minutes")
                        logger.info("="*60)
                        return True
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
        except Exception as e:
            logger.debug(f"Error checking for submit button: {e}")

        # Not available yet - wait with exponential backoff
        logger.info(f"Submit button not available yet. Waiting {poll_interval}s... (elapsed: {elapsed/60:.1f}min)")
        time.sleep(poll_interval)

        # Exponential backoff
        poll_interval = min(poll_interval * 1.5, Config.LOT_CHECK_INTERVAL_MAX)

    logger.error(f"TIMEOUT: Submit button did not appear after {max_wait_hours} hours")
    return False


def get_current_price(driver):
    """
    Get current price from the auction page

    Args:
        driver: WebDriver instance

    Returns:
        float: Current price, or None if not found
    """
    try:
        current_price_selectors = [
            (By.ID, "app-text-field-Текущая цена"),
            (By.XPATH, "//label[contains(text(), 'Текущая цена')]//following::input[1]"),
        ]

        for by, selector in current_price_selectors:
            try:
                current_price_field = driver.find_element(by, selector)
                current_price_str = current_price_field.get_attribute("value")
                if not current_price_str:
                    current_price_str = current_price_field.text

                if current_price_str:
                    current_price = float(current_price_str.replace(' ', '').replace('₸', '').replace(',', '.').replace('тг', '').strip())
                    return current_price
            except:
                continue

        return None
    except Exception as e:
        logger.error(f"Error getting current price: {e}")
        return None


def extract_and_submit_bid(driver, wait, start_price):
    """
    Extract current price, calculate bid, submit with NCALayer signing

    Args:
        driver: WebDriver instance
        wait: WebDriverWait instance
        start_price: Starting price (to determine deduction amount)

    Returns:
        True if submitted successfully
    """
    logger.info("="*60)
    logger.info("Extract Price and Submit Bid")
    logger.info("="*60)

    try:
        # Get current price
        current_price = get_current_price(driver)
        if current_price is None:
            logger.error("Could not get current price")
            return False

        logger.info(f"Starting price: {start_price:,.2f} tenge")
        logger.info(f"Current price: {current_price:,.2f} tenge")

        # Calculate deduction amount based on starting price threshold
        if start_price > Config.BID_THRESHOLD:
            # High price: deduct 100,000 tenge
            deduction_amount = Config.BID_REDUCTION
            logger.info(f"Starting price > {Config.BID_THRESHOLD:,} tenge - deduction: {Config.BID_REDUCTION:,} tenge")
        else:
            # Low price: deduct 1% of starting price
            deduction_amount = start_price * 0.01
            logger.info(f"Starting price <= {Config.BID_THRESHOLD:,} tenge - deduction: 1% of start = {deduction_amount:,.2f} tenge")

        # Calculate our bid: current price - deduction amount
        our_bid = current_price - deduction_amount
        logger.info(f"Our bid: {our_bid:,.2f} tenge (current - {deduction_amount:,.2f})")

        # Find bid input field (where we enter our bid)
        bid_input_selectors = [
            (By.ID, "app-text-field-Сумма"),  # Bid sum field
            (By.CSS_SELECTOR, "input[type='number']"),
            (By.XPATH, "//label[contains(text(), 'Сумма')]//following::input[1]"),
        ]

        logger.info("Looking for bid input field...")
        bid_field = find_element_with_fallbacks(driver, bid_input_selectors, "bid input field", timeout=10)

        # Enter bid
        bid_field.clear()
        bid_field.send_keys(str(int(our_bid)))  # Use integer for cleaner input
        logger.info("Entered bid amount")
        time.sleep(0.1)

        # Find submit button (red button)
        submit_selectors = [
            (By.CSS_SELECTOR, "button.v-btn.v-theme--light.bg-red.v-btn--density-default.v-btn--size-default.v-btn--variant-flat.mt-3"),
            (By.CSS_SELECTOR, "button.bg-red"),
            (By.XPATH, "//button[contains(@class, 'bg-red')]"),
            (By.XPATH, "//button[contains(text(), 'Отправить')]"),
            (By.XPATH, "//button[contains(text(), 'Жіберу')]"),
            (By.CSS_SELECTOR, "button[type='submit']"),
        ]

        logger.info("Looking for submit button...")

        # Start NCALayer automation in background BEFORE clicking submit
        logger.info("Starting NCALayer automation for bid signing...")
        automation_thread = automate_ncalayer_in_thread()

        # Click submit button
        click_element_with_fallbacks(driver, submit_selectors, "submit button", timeout=10)
        logger.info("Submit button clicked!")

        logger.info("NCALayer automation is handling bid signing...")

        # Wait for automation to complete
        automation_thread.join(timeout=60)

        logger.info("NCALayer thread finished, waiting for all keypresses to complete...")
        time.sleep(0.1)

        logger.info("="*60)
        logger.info("BID SUBMITTED SUCCESSFULLY!")
        logger.info("="*60)

        return True

    except Exception as e:
        logger.error(f"Failed to submit bid: {e}", exc_info=True)
        return False


def continuous_bidding(driver, wait):
    """
    Continuously bid until current price reaches 80% of starting price

    Args:
        driver: WebDriver instance
        wait: WebDriverWait instance

    Returns:
        True if bidding completed successfully
    """
    logger.info("="*60)
    logger.info("Starting Continuous Bidding")
    logger.info("="*60)

    try:
        # Get starting price (only once at the beginning)
        start_price_selectors = [
            (By.ID, "app-text-field-Стартовая цена"),
            (By.XPATH, "//label[contains(text(), 'Стартовая цена')]//following::input[1]"),
        ]

        logger.info("Looking for starting price field...")
        start_price_field = find_element_with_fallbacks(driver, start_price_selectors, "starting price field", timeout=10)

        start_price_str = start_price_field.get_attribute("value")
        if not start_price_str:
            start_price_str = start_price_field.text

        if not start_price_str:
            logger.error("Could not extract starting price")
            return False

        start_price = float(start_price_str.replace(' ', '').replace('₸', '').replace(',', '.').replace('тг', '').strip())
        target_price = start_price * 0.8  # 80% of starting price

        logger.info(f"Starting price: {start_price:,.2f} tenge")
        logger.info(f"Target price (80%): {target_price:,.2f} tenge")
        logger.info(f"Will bid until current price <= {target_price:,.2f} tenge")

        bid_count = 0

        while True:
            bid_count += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"BID #{bid_count}")
            logger.info(f"{'='*60}")

            # Get current price before bidding
            current_price = get_current_price(driver)
            if current_price is None:
                logger.error("Could not get current price")
                return False

            logger.info(f"Current price: {current_price:,.2f} tenge")

            # Check if we've reached the target
            if current_price <= target_price:
                logger.info("="*60)
                logger.info(f"TARGET REACHED!")
                logger.info(f"Current price ({current_price:,.2f}) <= Target price ({target_price:,.2f})")
                logger.info("="*60)
                return True

            logger.info(f"Current price ({current_price:,.2f}) > Target ({target_price:,.2f}) - continuing to bid...")

            # Submit a bid (pass start_price for deduction calculation)
            if not extract_and_submit_bid(driver, wait, start_price):
                logger.error("Failed to submit bid")
                return False

            # Wait for bid to be processed and page to update
            logger.info("Waiting for bid to be processed...")
            time.sleep(3)

            # Refresh page to get updated price
            logger.info("Refreshing page to check new price...")
            driver.refresh()
            wait_for_page_load(driver)
            time.sleep(2)  # Wait for Vue.js to render

    except Exception as e:
        logger.error(f"Error in continuous bidding: {e}", exc_info=True)
        return False
