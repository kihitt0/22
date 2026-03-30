"""
Configuration file for Tizilim login automation
"""

class Config:
    """Configuration settings"""

    # Platform credentials
    EMAIL = "w.nurda@mail.ru"
    PASSWORD = "Ora200405$"

    # ECP certificate settings
    ECP_KEY_PATH = r"C:\Users\Алан\Documents\GOST512_ad720e1e8fe2cb142db34624bf672da65812a6eb.p12"
    ECP_KEY_PASSWORD = "A1234a"

    # URLs
    LOGIN_URL = "https://tizilim.gov.kz/auth/login"

    # Mail.ru settings for waiting on lot invitation emails
    MAIL_EMAIL = "w.nurda@mail.ru"
    MAIL_PASSWORD = "VKZz8x0er7TAk1Hpw6fe"
    MAIL_IMAP_HOST = "imap.mail.ru"
    MAIL_IMAP_PORT = 993
    MAIL_FOLDER = "INBOX"
    MAIL_POLL_INTERVAL = 2
    MAIL_MAX_WAIT_MINUTES = 60
    MAIL_SUBJECT_CONTAINS = ""
    MAIL_FROM_CONTAINS = "no-reply@tizilim.gov.kz"
    MAIL_BODY_CONTAINS = "Заказчик приглашает Вас принять участие в аукционе"
    MAIL_ACCEPT_ANY_ROOM_LINK = True
    MAIL_CHECK_UNSEEN_FIRST = True
    MAIL_UNSEEN_ONLY = True
    MAIL_RECENT_MESSAGES_LIMIT = 5

    # Lot URLs to process after login
    LOT_URLS = [
        "https://tizilim.gov.kz/ru/auction/rooms/2588",
        # Add more lot URLs here as needed
    ]

    # Bidding settings
    BID_REDUCTION = 100000  # Reduce bid by 100,000 tenge from current price (if > 12.5M)
    BID_PERCENTAGE = 0.99  # Reduce by 1% (if <= 12.5M)
    BID_THRESHOLD = 12500000  # Threshold price in tenge (12.5 million)

    # Lot polling settings
    LOT_CHECK_INTERVAL_START = 7  # Start checking every 7 seconds
    LOT_CHECK_INTERVAL_MAX = 30   # Max 30 seconds between checks
    LOT_MAX_WAIT_HOURS = 24       # Maximum wait time for lot to appear

    # Timeouts (seconds)
    DEFAULT_TIMEOUT = 20
    NCALAYER_TIMEOUT = 60

    # NCALayer automation settings
    NCALAYER_BACKEND = "pywinauto"
    NCALAYER_USE_SAVED_STORAGE = True
    NCALAYER_START_DELAY = 0.05
    NCALAYER_WINDOW_POLL_INTERVAL = 0.05
    NCALAYER_ACTION_DELAY = 0.05
    NCALAYER_KEY_INTERVAL = 0.01
    NCALAYER_PASSWORD_FIELD_X_RATIO = 0.63
    NCALAYER_PASSWORD_FIELD_Y_RATIO = 0.73
    NCALAYER_OPEN_BUTTON_X_RATIO = 0.30
    NCALAYER_OPEN_BUTTON_Y_RATIO = 0.89
    NCALAYER_KEY_LIST_X_RATIO = 0.25
    NCALAYER_KEY_LIST_Y_RATIO = 0.20
    NCALAYER_SIGN_BUTTON_X_RATIO = 0.33
    NCALAYER_SIGN_BUTTON_Y_RATIO = 0.93
