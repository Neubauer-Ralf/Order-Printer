#!/usr/bin/env python3
"""
KuraKura Order Printer
Monitors an iCloud Mail inbox for Squarespace order notifications
and prints a receipt on a thermal printer via CUPS.
"""

import imaplib
import email
from email.header import decode_header
import subprocess
import textwrap
import time
import re
import logging
import os
from datetime import datetime
from html.parser import HTMLParser

# ============================================================
# CONFIGURATION
# Load from environment variables or fall back to defaults.
# Set these in your .env file or export them in your shell.
# ============================================================

def load_env_file():
    """Load .env file from the script's directory if it exists."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env_file()

ICLOUD_EMAIL = os.environ.get("ICLOUD_EMAIL", "your-email@icloud.com")
ICLOUD_APP_PASSWORD = os.environ.get("ICLOUD_APP_PASSWORD", "xxxx-xxxx-xxxx-xxxx")

IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.mail.me.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))

PRINTER_NAME = os.environ.get("PRINTER_NAME", "your-printer-name")
PRINT_WIDTH = int(os.environ.get("PRINT_WIDTH", "32"))

CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "120"))

SENDER_FILTER = os.environ.get("SENDER_FILTER", "squarespace")
SUBJECT_FILTER = os.environ.get("SUBJECT_FILTER", "kura kura")

LOG_FILE = os.environ.get("LOG_FILE", os.path.expanduser("~/kurakura-orders.log"))

# ============================================================
# HTML TEXT EXTRACTOR
# ============================================================

class HTMLTextExtractor(HTMLParser):
    """Extract readable text from HTML email content."""

    def __init__(self):
        super().__init__()
        self.result = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip = True
        if tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self.result.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = False
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self.result.append("\n")
        if tag == "td":
            self.result.append("  ")

    def handle_data(self, data):
        if not self.skip:
            self.result.append(data.strip())

    def get_text(self):
        return " ".join(self.result)


def html_to_text(html_content):
    """Convert HTML to plain text."""
    extractor = HTMLTextExtractor()
    extractor.feed(html_content)
    text = extractor.get_text()
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()


# ============================================================
# EMAIL PARSING
# ============================================================

def decode_mime_header(header):
    """Decode a MIME-encoded email header."""
    if header is None:
        return ""
    decoded_parts = decode_header(header)
    parts = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(part)
    return " ".join(parts)


def get_email_body(msg):
    """Extract the text body from an email message."""
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
            elif content_type == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = html_to_text(payload.decode(charset, errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            if msg.get_content_type() == "text/html":
                body = html_to_text(payload.decode(charset, errors="replace"))
            else:
                body = payload.decode(charset, errors="replace")

    return body


def parse_order_info(subject, body):
    """Extract order details from the email."""
    info = {}

    order_match = re.search(r'\((\d+)\)', subject)
    if order_match:
        info["order_number"] = order_match.group(1)
    else:
        info["order_number"] = "Unknown"

    info["body_preview"] = body[:500] if body else "No content"

    total_match = re.search(r'(?:total|gesamt)[:\s]*[€$]?\s*([\d.,]+)', body, re.IGNORECASE)
    if total_match:
        info["total"] = total_match.group(1)

    name_match = re.search(r'(?:name|kunde|customer)[:\s]*([A-Za-zÄÖÜäöüß\s]+)', body, re.IGNORECASE)
    if name_match:
        info["customer"] = name_match.group(1).strip()

    return info


# ============================================================
# RECEIPT FORMATTING
# ============================================================

def separator(char="="):
    return char * PRINT_WIDTH

def center(text):
    return text.center(PRINT_WIDTH)

def wrap(text, indent=0):
    prefix = " " * indent
    return "\n".join(textwrap.wrap(
        text, width=PRINT_WIDTH,
        initial_indent=prefix,
        subsequent_indent=prefix
    ))


def format_order_receipt(order_info, subject):
    """Format order info as a thermal printer receipt."""
    now = datetime.now()
    lines = []

    lines.append("")
    lines.append(separator("="))
    lines.append(center("~ KURA KURA ~"))
    lines.append(center("NEW ORDER!"))
    lines.append(separator("="))
    lines.append("")
    lines.append(f"  Order #: {order_info.get('order_number', 'N/A')}")
    lines.append(f"  Time:    {now.strftime('%H:%M - %d.%m.%Y')}")

    if "customer" in order_info:
        lines.append(f"  Customer: {order_info['customer']}")

    if "total" in order_info:
        lines.append(f"  Total:   {order_info['total']}")

    lines.append("")
    lines.append(separator("-"))
    lines.append(" ORDER DETAILS:")
    lines.append(separator("-"))

    preview = order_info.get("body_preview", "")
    preview_lines = [l.strip() for l in preview.split("\n") if l.strip()]
    for line in preview_lines[:15]:
        lines.append(wrap(line, indent=1))

    lines.append("")
    lines.append(separator("="))
    lines.append(center("Time to pack some coffee!"))
    lines.append(separator("="))
    lines.append("")
    lines.append("")

    return "\n".join(lines)


# ============================================================
# PRINTING
# ============================================================

def print_receipt(text):
    """Send text to the thermal printer via CUPS."""
    try:
        # ESC/POS cut command: GS V 1 (partial cut)
        cut_command = b'\x1d\x56\x01'
        data = text.encode("utf-8") + b'\n\n\n' + cut_command

        process = subprocess.run(
            ["lp", "-d", PRINTER_NAME, "-o", "raw"],
            input=data,
            capture_output=True,
            timeout=30,
        )
        if process.returncode == 0:
            logging.info("Receipt printed successfully")
            return True
        else:
            logging.error(f"Print error: {process.stderr.decode()}")
            return False
    except Exception as e:
        logging.error(f"Failed to print: {e}")
        return False


# ============================================================
# MAIN LOOP
# ============================================================

def check_for_orders():
    """Connect to iCloud IMAP and check for new order emails."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(ICLOUD_EMAIL, ICLOUD_APP_PASSWORD)
        mail.select("INBOX")

        status, messages = mail.search(None, '(UNSEEN)')
        if status != "OK":
            logging.warning("Failed to search mailbox")
            mail.logout()
            return

        email_ids = messages[0].split() if messages[0] else []
        if not email_ids:
            logging.debug("No new emails")
            mail.logout()
            return

        logging.info(f"Found {len(email_ids)} unread email(s)")

        for eid in email_ids:
            status, msg_data = mail.fetch(eid, "(BODY.PEEK[])")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = decode_mime_header(msg["Subject"])
            sender = decode_mime_header(msg["From"]).lower()

            is_order = (
                SENDER_FILTER.lower() in sender or
                SUBJECT_FILTER.lower() in subject.lower()
            )

            if is_order:
                logging.info(f"Order email found: {subject}")

                mail.store(eid, "+FLAGS", "\\Seen")

                body = get_email_body(msg)
                order_info = parse_order_info(subject, body)
                receipt = format_order_receipt(order_info, subject)

                print(receipt)
                print_receipt(receipt)

                logging.info(f"Order #{order_info.get('order_number')} processed")
            else:
                logging.debug(f"Skipping non-order email: {subject}")

        mail.logout()

    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


def main():
    """Main loop - continuously check for new orders."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )

    logging.info("=" * 40)
    logging.info("KuraKura Order Printer started!")
    logging.info(f"Checking every {CHECK_INTERVAL}s")
    logging.info(f"Printer: {PRINTER_NAME}")
    logging.info("=" * 40)

    while True:
        try:
            check_for_orders()
        except KeyboardInterrupt:
            logging.info("Shutting down...")
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
