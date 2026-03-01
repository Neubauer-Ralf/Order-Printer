# KuraKura Order Printer 🖨️☕

A lightweight Python script that monitors an email inbox (via IMAP) for Squarespace order notifications and prints a receipt on a thermal printer. Designed to run on a Raspberry Pi.

## How It Works

1. Connects to your email inbox via IMAP every 2 minutes
2. Checks for unread emails matching Squarespace order notifications
3. Parses the order number, customer info, and details
4. Prints a formatted receipt on a thermal printer via CUPS
5. Marks the email as read to avoid reprinting

## Hardware

- Raspberry Pi (any model with network access)
- ESC/POS thermal receipt printer (tested with Epson TM-T20II)
- Printer connected via USB and configured in CUPS

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Neubauer-Ralf/kurakura-order-printer.git
cd kurakura-order-printer
```

### 2. Create your environment file

```bash
cp .env.example .env
nano .env
```

Fill in your credentials and printer name. See [Configuration](#configuration) below.

### 3. Test it

```bash
python3 order_printer.py
```

Send yourself a test email with "kura kura" in the subject to verify it picks it up and prints.

### 4. Install as a system service

```bash
# Copy and edit the service file (update User and paths if needed)
sudo cp kurakura-orders.service /etc/systemd/system/
sudo nano /etc/systemd/system/kurakura-orders.service

# Enable and start
sudo systemctl enable kurakura-orders
sudo systemctl start kurakura-orders

# Verify it's running
sudo systemctl status kurakura-orders
```

## Configuration

All configuration is done via environment variables. Copy `.env.example` to `.env` and fill in your values.

| Variable | Description | Default |
|---|---|---|
| `ICLOUD_EMAIL` | Your iCloud email address (must be `@icloud.com`, not a custom domain) | — |
| `ICLOUD_APP_PASSWORD` | App-specific password ([generate here](https://account.apple.com)) | — |
| `IMAP_SERVER` | IMAP server address | `imap.mail.me.com` |
| `IMAP_PORT` | IMAP port | `993` |
| `PRINTER_NAME` | CUPS printer name (find with `lpstat -p`) | — |
| `PRINT_WIDTH` | Thermal printer character width | `32` |
| `CHECK_INTERVAL` | Seconds between inbox checks | `120` |
| `SENDER_FILTER` | Filter emails by sender (matched against From header) | `squarespace` |
| `SUBJECT_FILTER` | Filter emails by subject (matched against Subject header) | `kura kura` |
| `LOG_FILE` | Path to log file | `~/kurakura-orders.log` |

### iCloud Custom Domain Note

If you use a custom email domain with iCloud+ (e.g. `you@yourdomain.com`), you still need to use your underlying `@icloud.com` address as the IMAP username. Your custom domain emails will be in the same inbox.

### App-Specific Password

Apple requires an app-specific password for third-party IMAP access:

1. Go to [account.apple.com](https://account.apple.com)
2. **Sign-In and Security** → **App-Specific Passwords**
3. Generate a new password and copy it to your `.env` file

## Useful Commands

```bash
# Check service status
sudo systemctl status kurakura-orders

# View live logs
journalctl -u kurakura-orders -f

# Restart after config changes
sudo systemctl restart kurakura-orders

# Stop the service
sudo systemctl stop kurakura-orders
```

## Customization

- **Receipt format**: Edit the `format_order_receipt()` function in `order_printer.py`
- **Email parsing**: Adjust regex patterns in `parse_order_info()` to match your email format
- **Cut command**: If the partial cut doesn't work, change `b'\x1d\x56\x01'` to `b'\x1d\x56\x00'` for a full cut
- **Print width**: Adjust `PRINT_WIDTH` for your paper size (32 for 58mm, 48 for 80mm)

## Receipt Output

```
================================
        ~ KURA KURA ~
          NEW ORDER!
================================

  Order #: 00042
  Time:    14:30 - 01.03.2026
  Customer: Max Mustermann
  Total:   24,90

--------------------------------
 ORDER DETAILS:
--------------------------------
 ...

================================
   Time to pack some coffee!
================================
```

## Requirements

- Python 3.7+
- No external pip packages needed (uses only stdlib)
- CUPS configured with your thermal printer

## License

MIT
