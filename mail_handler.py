"""
Mail handling helpers for waiting on tizilim invitation links in mail.ru.
"""
import email
import imaplib
import logging
import re
import time
from email.header import decode_header
from urllib.parse import unquote
from urllib.request import Request, urlopen

from config import Config

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
ANY_ROOM_LINK_PATTERN = re.compile(
    r"https?://tizilim\.gov\.kz[^\s\"'<>)]*/auction/rooms/\d+[^\s\"'<>)]*",
    re.IGNORECASE,
)


def _decode_header_value(value):
    if not value:
        return ""

    decoded_parts = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or "utf-8", errors="ignore"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


def _extract_room_id(lot_url):
    match = re.search(r"/rooms/(\d+)", lot_url)
    if not match:
        raise ValueError(f"Could not extract room id from lot URL: {lot_url}")
    return match.group(1)


def _build_room_link_pattern(room_id):
    return re.compile(
        rf"https?://tizilim\.gov\.kz[^\s\"'<>)]*/auction/rooms/{re.escape(room_id)}[^\s\"'<>)]*",
        re.IGNORECASE,
    )


def _build_link_pattern(expected_lot_url=None):
    if Config.MAIL_ACCEPT_ANY_ROOM_LINK or not expected_lot_url:
        return ANY_ROOM_LINK_PATTERN
    room_id = _extract_room_id(expected_lot_url)
    return _build_room_link_pattern(room_id)


def _clean_url(url):
    return unquote(url).rstrip(').,;\"\'')


def _extract_urls(text):
    return [_clean_url(match.group(0)) for match in URL_PATTERN.finditer(text)]


def _resolve_shared_mail_link(candidate_url, room_link_pattern):
    try:
        request = Request(candidate_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            final_url = response.geturl()
            page_body = response.read().decode("utf-8", errors="ignore")

        direct_match = room_link_pattern.search(final_url)
        if direct_match:
            return direct_match.group(0)

        body_match = room_link_pattern.search(page_body)
        if body_match:
            return body_match.group(0)
    except Exception as exc:
        logger.debug(f"Could not resolve shared mail link {candidate_url}: {exc}")

    return None


def _extract_matching_lot_link(message_text, room_link_pattern):
    direct_match = room_link_pattern.search(message_text)
    if direct_match:
        return direct_match.group(0)

    for candidate_url in _extract_urls(message_text):
        if "sharing.mail.ru" not in candidate_url.lower():
            continue

        resolved_link = _resolve_shared_mail_link(candidate_url, room_link_pattern)
        if resolved_link:
            return resolved_link

    return None


def _extract_message_text(message):
    payloads = []

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition.lower():
                continue

            if content_type in {"text/plain", "text/html"}:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    payloads.append(payload.decode(charset, errors="ignore"))
    else:
        payload = message.get_payload(decode=True)
        if payload:
            charset = message.get_content_charset() or "utf-8"
            payloads.append(payload.decode(charset, errors="ignore"))

    return "\n".join(payloads)


def _message_matches_filters(message):
    subject = _decode_header_value(message.get("Subject", ""))
    sender = _decode_header_value(message.get("From", ""))

    if Config.MAIL_SUBJECT_CONTAINS and Config.MAIL_SUBJECT_CONTAINS.lower() not in subject.lower():
        return False

    if Config.MAIL_FROM_CONTAINS and Config.MAIL_FROM_CONTAINS.lower() not in sender.lower():
        return False

    return True


def _message_text_matches_filters(message_text):
    if Config.MAIL_BODY_CONTAINS and Config.MAIL_BODY_CONTAINS.lower() not in message_text.lower():
        return False
    return True


def _search_message_ids(mailbox):
    search_queries = []

    if Config.MAIL_UNSEEN_ONLY:
        search_queries.append(("UNSEEN",))
    else:
        if Config.MAIL_CHECK_UNSEEN_FIRST:
            search_queries.append(("UNSEEN",))
        search_queries.append(("ALL",))

    seen_ids = set()
    ordered_ids = []
    had_search_error = False

    for query in search_queries:
        status, data = mailbox.search(None, *query)
        if status != "OK":
            had_search_error = True
            logger.warning(f"IMAP search failed for query {query}: status={status}, data={data}")
            continue

        raw_ids = data[0] if data else b""
        message_ids = raw_ids.split()
        for message_id in reversed(message_ids[-Config.MAIL_RECENT_MESSAGES_LIMIT:]):
            if message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            ordered_ids.append(message_id)

    return ordered_ids, had_search_error


def wait_for_lot_link_in_mail(expected_lot_url=None):
    """Wait for an email that contains a tizilim link for the expected room and return that link."""
    link_pattern = _build_link_pattern(expected_lot_url)
    deadline = time.time() + (Config.MAIL_MAX_WAIT_MINUTES * 60)

    logger.info("=" * 60)
    logger.info("WAITING FOR MAIL.RU LOT LINK")
    logger.info("=" * 60)
    if Config.MAIL_ACCEPT_ANY_ROOM_LINK or not expected_lot_url:
        logger.info("Accepting any tizilim auction room link from mail")
    else:
        logger.info(f"Expected lot URL pattern for room {_extract_room_id(expected_lot_url)}")

    while time.time() < deadline:
        mailbox = None
        try:
            mailbox = imaplib.IMAP4_SSL(Config.MAIL_IMAP_HOST, Config.MAIL_IMAP_PORT)
            mailbox.login(Config.MAIL_EMAIL, Config.MAIL_PASSWORD)
            select_status, select_data = mailbox.select(Config.MAIL_FOLDER)
            if select_status != "OK":
                logger.warning(f"Could not open mailbox folder {Config.MAIL_FOLDER}: status={select_status}, data={select_data}")
                time.sleep(Config.MAIL_POLL_INTERVAL)
                continue

            message_ids, had_search_error = _search_message_ids(mailbox)
            if not message_ids:
                if had_search_error:
                    logger.warning("Mailbox search returned no usable results because IMAP search failed")
                else:
                    logger.info("Mailbox checked successfully, but no suitable unread messages were found yet")
                time.sleep(Config.MAIL_POLL_INTERVAL)
                continue

            for message_id in message_ids:
                fetch_status, message_data = mailbox.fetch(message_id, "(BODY.PEEK[])")
                if fetch_status != "OK":
                    continue

                raw_email = None
                for response_part in message_data:
                    if isinstance(response_part, tuple):
                        raw_email = response_part[1]
                        break

                if not raw_email:
                    continue

                message = email.message_from_bytes(raw_email)
                if not _message_matches_filters(message):
                    continue

                message_text = _extract_message_text(message)
                if not _message_text_matches_filters(message_text):
                    continue

                matched_link = _extract_matching_lot_link(message_text, link_pattern)
                if matched_link:
                    logger.info(f"Found matching lot link in mail: {matched_link}")
                    return matched_link

            logger.info("No matching email yet, waiting before next mailbox poll...")
        except Exception as exc:
            logger.warning(f"Mail polling attempt failed: {exc}")
        finally:
            if mailbox is not None:
                try:
                    mailbox.logout()
                except Exception:
                    pass

        time.sleep(Config.MAIL_POLL_INTERVAL)

    raise TimeoutError(
        f"No mail with a matching tizilim room link appeared within {Config.MAIL_MAX_WAIT_MINUTES} minutes"
    )