"""
Utility functions for tizilim automation

This module provides smart wait conditions and helper functions
to make Selenium automation more reliable.
"""

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging
import time

logger = logging.getLogger(__name__)


class SmartWaits:
    """Custom wait conditions for tizilim.gov.kz"""

    @staticmethod
    def element_ready_to_interact(locator):
        """Wait until element is present, visible, and enabled"""
        def check(driver):
            try:
                elem = driver.find_element(*locator)
                return elem.is_displayed() and elem.is_enabled()
            except:
                return False
        return check

    @staticmethod
    def modal_with_inputs_loaded(modal_selector):
        """Wait for modal to appear with input fields"""
        def check(driver):
            try:
                modal = driver.find_element(*modal_selector)
                inputs = modal.find_elements(By.TAG_NAME, "input")
                return modal.is_displayed() and len(inputs) > 0
            except:
                return False
        return check

    @staticmethod
    def url_contains_not(text):
        """Wait until URL does NOT contain text (useful for detecting redirects)"""
        def check(driver):
            return text not in driver.current_url
        return check


def find_element_with_fallbacks(driver, locators, description, timeout=10):
    """
    Try multiple selectors until one works

    Args:
        driver: Selenium WebDriver instance
        locators: List of (By, selector) tuples to try
        description: Description of element for logging
        timeout: Timeout for each selector attempt

    Returns:
        WebElement if found

    Raises:
        NoSuchElementException if none of the selectors work
    """
    wait = WebDriverWait(driver, timeout)

    for i, (by, selector) in enumerate(locators):
        try:
            logger.debug(f"Trying selector {i+1}/{len(locators)} for {description}: {selector}")
            element = wait.until(EC.presence_of_element_located((by, selector)))
            logger.info(f"Found {description} using selector {i+1}")
            return element
        except TimeoutException:
            if i == len(locators) - 1:
                logger.error(f"Could not find {description} with any of {len(locators)} selectors")
                raise NoSuchElementException(f"Could not find {description} with any selector")
            continue


def click_element_with_fallbacks(driver, locators, description, timeout=10):
    """
    Find element with fallbacks and click it

    Args:
        driver: Selenium WebDriver instance
        locators: List of (By, selector) tuples to try
        description: Description of element for logging
        timeout: Timeout for finding element

    Returns:
        True if clicked successfully

    Raises:
        NoSuchElementException if element not found
    """
    element = find_element_with_fallbacks(driver, locators, description, timeout)

    try:
        # Try normal click first
        element.click()
        logger.info(f"Clicked {description}")
        return True
    except Exception as e:
        logger.warning(f"Normal click failed for {description}, trying JavaScript click: {e}")
        # Fallback to JavaScript click
        driver.execute_script("arguments[0].click();", element)
        logger.info(f"Clicked {description} using JavaScript")
        return True


def retry_with_backoff(func, max_attempts=3, initial_delay=1, backoff_factor=2, exceptions=(Exception,)):
    """
    Retry function with exponential backoff

    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each attempt
        exceptions: Tuple of exceptions to catch

    Returns:
        Result of func() if successful

    Raises:
        Last exception if all attempts fail
    """
    delay = initial_delay

    for attempt in range(max_attempts):
        try:
            return func()
        except exceptions as e:
            if attempt == max_attempts - 1:
                raise
            logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {e}")
            logger.info(f"Retrying in {delay}s...")
            time.sleep(delay)
            delay *= backoff_factor


def wait_for_page_load(driver, timeout=30):
    """
    Wait for page to finish loading

    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait

    Returns:
        True if page loaded, False if timeout
    """
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        logger.debug("Page loaded completely")
        return True
    except TimeoutException:
        logger.warning(f"Page did not finish loading after {timeout}s")
        return False


def safe_send_keys(element, text, clear_first=True):
    """
    Safely send keys to element

    Args:
        element: WebElement to send keys to
        text: Text to send
        clear_first: Whether to clear element first

    Returns:
        True if successful
    """
    try:
        if clear_first:
            element.clear()
        element.send_keys(text)
        return True
    except Exception as e:
        logger.error(f"Failed to send keys: {e}")
        return False
