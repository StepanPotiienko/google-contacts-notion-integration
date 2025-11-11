# AgroprideOS

AgroprideOS is an automation system that integrates Google Contacts, Gmail, Notion, and Telegram to manage customer relationships, track orders, and maintain clean contact databases.

## 🌟 Features

### 1. **Google Contacts Integration**

- Sync contacts from Google Contacts to Notion CRM
- Incremental sync support using sync tokens
- Full and partial synchronization modes
- Automatic duplicate detection

### 2. **Order Tracking from Website**

- Monitor Gmail for new order notifications
- Parse order details from HTML emails
- Send real-time notifications via Telegram
- Track order history to prevent duplicate notifications
- Multi-recipient Telegram support

### 3. **Notion Database Management**

- Excel/CSV to Notion database import
- Automated duplicate detection and cleanup
- Contact deduplication by phone number
- Batch operations with progress tracking
- Archive duplicate entries (reversible)

### 4. **Docker Support**

- Containerized deployment for duplicate cleanup
- Easy-to-use shell script for Docker operations
- Volume mounting for persistent data

## 📋 Project Structure

```
AgroprideOS/
├── google-contacts-integration/    # Google Contacts sync module
│   ├── main.py                     # Main sync logic
├── notion/                         # Notion CRM operations
│   ├── excel_to_notion_db.py       # Import contacts from CSV/Excel
│   ├── delete_duplicates.py        # Duplicate cleanup tool
│   ├── notion_controller.py        # Notion API wrapper
│   ├── Dockerfile                   # Docker configuration
│   └── run_docker.sh               # Docker helper script
├── website/                        # Order tracking module
│   ├── orders_from_website.py      # Gmail order monitoring
├── requirements.txt                # Python dependencies
└── run_duplicate_cleanup.py        # CLI for duplicate cleanup
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Docker (optional, for containerized deployment)
- Google Cloud Platform account with APIs enabled
- Notion account with API access
- Telegram Bot (for notifications)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/StepanPotiienko/google-contacts-notion-integration.git
   cd AgroprideOS
   ```

2. **Install dependencies**

   ```bash
   python -m venv venv
   source ./.venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   Create a `.env` file in the project root with the following variables:

   ```env
   # Google API Credentials
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   GOOGLE_REFRESH_TOKEN=your_refresh_token

   # Gmail API Credentials
   GMAIL_TOKEN=your_gmail_token
   GMAIL_REFRESH_TOKEN=your_gmail_refresh_token
   GMAIL_CLIENT_ID=your_gmail_client_id
   GMAIL_CLIENT_SECRET=your_gmail_client_secret
   GMAIL_TOKEN_URI=https://oauth2.googleapis.com/token

   # Notion API
   NOTION_API_KEY=your_notion_api_key
   CRM_DATABASE_ID=your_crm_database_id
   PRODUCTION_DATABASE_ID=your_production_database_id

   # Telegram Bot
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id  # Can be comma-separated for multiple recipients

   # Debug Mode (optional)
   DEBUG=False
   ```

4. **Configure Google Cloud Platform**

   - Enable Google Contacts API and Gmail API
   - Create OAuth 2.0 credentials
   - Download `credentials.json` to `google-contacts-integration/`

5. **Set up Notion Integration**
   - Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Share your CRM database with the integration
   - Copy the database ID from the database URL

## 📖 Usage

### Google Contacts Sync

Sync contacts from Google Contacts to Notion CRM:

```bash
cd google-contacts-integration
python main.py
```

The script will:

- Perform a full sync on first run
- Use incremental sync on subsequent runs
- Update Notion database with new/modified contacts
- Save sync tokens for efficient future syncs

### Order Tracking

Monitor Gmail for new orders and send Telegram notifications:

```bash
cd website
python orders_from_website.py
```

Features:

- Parses order details from HTML emails
- Extracts customer information and order items
- Sends formatted notifications to Telegram
- Prevents duplicate notifications

### Import Contacts from CSV/Excel

Import contacts from a CSV file to Notion:

```bash
cd notion
python excel_to_notion_db.py clients.csv
```

CSV format:

```csv
ПОКУПЕЦЬ;АДРЕСА
Customer Name;Customer Address
```

### Clean Up Duplicates

Remove duplicate entries from your Notion CRM:

**Using Python:**

```bash
python run_duplicate_cleanup.py
```

**Using Docker:**

```bash
cd notion
./run_docker.sh
```

The cleanup tool will:

- Scan the database for duplicates based on phone numbers
- Compare contact content using hash algorithms
- Archive older duplicate entries
- Preserve the most recent contact information
- Provide progress feedback

## 🔧 Configuration

### Notion Database Schema

Your Notion CRM database should have the following properties:

- **Name** (Title): Contact name
- **Phone Numbers** (Phone): Contact phone number(s)
- **Addresses** (Rich Text): Contact addresses
- **Email Addresses** (Email): Contact email(s)
- **Archived** (Checkbox): Duplicate/archived status

### Docker Configuration

The `run_docker.sh` script provides several options:

```bash
./run_docker.sh [OPTIONS]

Options:
  --rebuild    Force rebuild the Docker image
  --logs       Show container logs after starting
  --cleanup    Remove stopped containers
```

### Sync Token Management

The Google Contacts sync uses tokens to track changes:

- `sync_token.txt`: Stores the last successful sync state
- Delete this file to force a full resync
- Automatically updated after each successful sync

## 🔍 Features in Detail

### Intelligent Duplicate Detection

The duplicate cleanup system uses multiple strategies:

1. **Phone Number Matching**: Primary identifier for contacts
2. **Content Hashing**: Detects identical contact information
3. **Fuzzy Matching**: Identifies similar entries
4. **Batch Processing**: Handles large databases efficiently

### Error Handling

- Automatic retry with exponential backoff
- Rate limit handling for API calls
- Progress tracking for long-running operations
- Detailed error logging and reporting

### Telegram Notifications

Formatted order notifications include:

- Order number and timestamp
- Customer contact details
- Itemized order list with quantities
- Delivery information
- Payment details

## 🐛 Troubleshooting

### Common Issues

**"Missing required environment variable"**

- Ensure all required variables are set in `.env`
- Check for typos in variable names

**"Invalid sync token"**

- Delete `sync_token.txt` to force a full resync
- Verify Google API credentials are valid

**"Notion API timeout"**

- The system automatically retries with backoff
- Check your internet connection
- Verify Notion integration permissions

**"No messages found in Gmail"**

- Verify Gmail API is enabled
- Check search query matches your email format
- Ensure OAuth tokens have correct scopes

### Code Style

The project follows Python best practices:

- Type hints for function signatures
- Docstrings for all modules and functions
- Error handling with try-except blocks
- Modular design with reusable components

## 📝 License

### 👤 Author

**Stepan Potiienko**

- GitHub: [@StepanPotiienko](https://github.com/StepanPotiienko)

## 🤝 Contributing

This is a private project. For questions or suggestions, please contact the repository owner.

## ⚠️ Important Notes

- **Backup your data**: Always backup your Notion database before running cleanup operations
- **Test in development**: Use a test database for initial setup and testing
- **Monitor rate limits**: Google and Notion APIs have rate limits; the system handles these automatically
- **Secure credentials**: Never commit `.env` files or credential files to version control
- **Review archives**: Check archived contacts before permanently deleting

---

**Last Updated**: November 11, 2025
