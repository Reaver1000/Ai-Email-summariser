# AI Email Summarizer with Gmail Integration

A powerful Python application that connects to your Gmail account (or any IMAP server), classifies emails as important or junk using machine learning, and generates AI-powered summaries using OpenAI's GPT-3.5-turbo model.

## Features

- **Gmail API Integration**: Secure OAuth2 authentication with Gmail
- **Smart Email Classification**: ML-powered classification of emails as important or junk
- **AI-Powered Summaries**: Concise summaries of your emails using OpenAI
- **Interactive Learning**: Improves classification based on your feedback
- **Gmail Labels**: Automatically organizes emails into Important/Junk labels
- **Fallback to IMAP**: Works with any email provider that supports IMAP
- **Clean Command-Line Interface**: Easy to use and navigate

## Prerequisites

- Python 3.8 or higher
- A Gmail account (recommended) or any email with IMAP access
- An OpenAI API key

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in the project directory with your OpenAI API key:

```ini
# Required: Your OpenAI API key
OPENAI_API_KEY=your_openai_api_key_here

# Gmail API (recommended) - set to false to use IMAP instead
USE_GMAIL=true

# IMAP Configuration (only used if USE_GMAIL=false)
# EMAIL_ADDRESS=your_email@example.com
# EMAIL_PASSWORD=your_email_password_or_app_password
# IMAP_SERVER=imap.gmail.com
# IMAP_PORT=993
```

### 3. Gmail API Setup (Recommended)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Gmail API
4. Configure the OAuth consent screen
   - Set User Type to "External"
   - Add your email as a test user
5. Create OAuth 2.0 credentials (Desktop app)
6. Download the credentials and save as `credentials.json` in the project directory

## Usage

Run the application:

```bash
python email_summarizer.py
```

### Interface

- The application will display a list of your latest emails
- Important emails are shown in green, junk in yellow
- Each email shows the classification confidence percentage

### Commands

- `[1-5]` - View and summarize email
- `i#` - Mark email # as important (e.g., `i1`)
- `j#` - Mark email # as junk (e.g., `j2`)
- `r` - Refresh email list
- `q` - Quit

When viewing an email:
- `i` - Mark as important
- `j` - Mark as junk
- `b` - Back to email list

## How It Works

1. **Email Classification**: Uses a Random Forest classifier with TF-IDF features
2. **Learning**: Improves based on your feedback (important/junk marks)
3. **Gmail Integration**: Automatically applies labels and marks emails as read
4. **AI Summarization**: Uses OpenAI's GPT-3.5-turbo to generate concise summaries

## Security Notes

- Never commit your `.env` file or `credentials.json` to version control
- The application only requests read access to your emails
- All data processing happens locally on your machine
- Your OpenAI API key is only used for generating summaries

## Troubleshooting

### Gmail API Issues
- Make sure you've enabled the Gmail API in Google Cloud Console
- Ensure you've added your email as a test user in the OAuth consent screen
- Check that your `credentials.json` file is in the project directory

### IMAP Fallback
If Gmail API fails, the application will fall back to IMAP. For Gmail, you'll need to:
1. Enable IMAP in Gmail settings
2. Generate an "App Password" if you have 2FA enabled
   - Go to your Google Account > Security > App passwords
   - Generate a new app password for "Mail" and use that as your `EMAIL_PASSWORD`

## License

This project is open source and available under the [MIT License](LICENSE).
