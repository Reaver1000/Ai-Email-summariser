import os
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
import openai
from dotenv import load_dotenv
import textwrap
from bs4 import BeautifulSoup
import pyfiglet
from colorama import init, Fore
import json
import webbrowser
from email_classifier import EmailClassifier, EmailFeedbackManager
from gmail_integration import GmailService, SCOPES

# Initialize colorama for colored console output
init()

# Load environment variables
load_dotenv()

class EmailSummarizer:
    def __init__(self):
        # Initialize OpenAI API
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        # Initialize email classifier and feedback manager
        self.classifier = EmailClassifier()
        self.feedback_manager = EmailFeedbackManager()
        
        # Initialize Gmail service
        self.gmail_service = None
        self.use_gmail = os.getenv("USE_GMAIL", "true").lower() == "true"
        
        # Initialize email configuration based on whether we're using Gmail or IMAP
        if self.use_gmail:
            self._setup_gmail()
        else:
            # IMAP configuration
            self.email_address = os.getenv("EMAIL_ADDRESS")
            self.email_password = os.getenv("EMAIL_PASSWORD")
            self.imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")
            self.imap_port = int(os.getenv("IMAP_PORT", 993))
            
            if not all([self.email_address, self.email_password]):
                raise ValueError("Please set EMAIL_ADDRESS and EMAIL_PASSWORD in .env file")
        
        # Train the classifier with any existing feedback
        self._train_classifier()
        
        if not openai.api_key:
            raise ValueError("Please set OPENAI_API_KEY in .env file")
    
    def connect_to_email(self):
        """Connect to the email server and return the connection"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            mail.select("inbox")
            return mail
        except Exception as e:
            print(Fore.RED + f"Error connecting to email: {e}" + Fore.RESET)
            return None
    
    def _setup_gmail(self):
        """Set up Gmail service with OAuth2"""
        try:
            self.gmail_service = GmailService()
            self.gmail_service.authenticate()
            print(Fore.GREEN + "✓ Successfully connected to Gmail" + Fore.RESET)
        except Exception as e:
            print(Fore.RED + f"Error setting up Gmail: {e}" + Fore.RESET)
            print("Falling back to IMAP...")
            self.use_gmail = False
            self.email_address = os.getenv("EMAIL_ADDRESS")
            self.email_password = os.getenv("EMAIL_PASSWORD")
            self.imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")
            self.imap_port = int(os.getenv("IMAP_PORT", 993))
    
    def get_emails(self, days=7, max_emails=5):
        """Fetch emails using Gmail API or IMAP"""
        if self.use_gmail and self.gmail_service:
            return self._get_emails_gmail(max_emails)
        else:
            return self._get_emails_imap(days, max_emails)
    
    def _get_emails_gmail(self, max_emails=5):
        """Fetch emails using Gmail API"""
        try:
            gmail_emails = self.gmail_service.get_emails(max_results=max_emails)
            emails = []
            
            for gmail_email in gmail_emails:
                # Classify the email
                classification = self.classifier.predict({
                    'subject': gmail_email['subject'],
                    'from': gmail_email['from'],
                    'body': gmail_email['body']
                })
                
                # Mark as read
                self.gmail_service.mark_as_read(gmail_email['id'])
                
                emails.append({
                    'id': gmail_email['id'],
                    'subject': gmail_email['subject'],
                    'from': gmail_email['from'],
                    'date': gmail_email['date'],
                    'body': gmail_email['body'],
                    'snippet': gmail_email['snippet'],
                    'classification': classification,
                    'labels': gmail_email.get('labels', []),
                    'is_gmail': True
                })
            
            return emails
            
        except Exception as e:
            print(Fore.RED + f"Error fetching emails from Gmail: {e}" + Fore.RESET)
            return []
    
    def _get_emails_imap(self, days=1, max_emails=5):
        """Fetch emails using IMAP"""
        mail = self.connect_to_email()
        if not mail:
            return []
        
        try:
            # Calculate date N days ago
            date_since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
            
            # Search for emails
            status, messages = mail.search(None, f'(SINCE "{date_since}")')
            if status != 'OK':
                print(Fore.RED + "No messages found!" + Fore.RESET)
                return []
            
            # Get the list of email IDs
            email_ids = messages[0].split()
            email_ids = email_ids[-max_emails:]  # Get only the latest N emails
            
            emails = []
            for email_id in email_ids:
                try:
                    # Fetch the email
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    if status != 'OK':
                        continue
                        
                    # Parse the email
                    msg = email.message_from_bytes(msg_data[0][1])
                    
                    # Decode email subject
                    subject = self._decode_header(msg["subject"])
                    
                    # Get email sender
                    from_ = self._decode_header(msg["from"])
                    
                    # Get email date
                    date = self._decode_header(msg["date"])
                    
                    # Get email body
                    body = self._get_email_body(msg)
                    
                    # Create a snippet (first 100 chars of body)
                    snippet = ' '.join(body.split()[:20])
                    if len(body.split()) > 20:
                        snippet += "..."
                    
                    # Classify the email
                    classification = self.classifier.predict({
                        'subject': subject,
                        'from': from_,
                        'body': body
                    })
                    
                    emails.append({
                        'id': email_id,
                        'subject': subject,
                        'from': from_,
                        'date': date,
                        'body': body,
                        'snippet': snippet,
                        'classification': classification,
                        'labels': [],
                        'is_gmail': False
                    })
                except Exception as e:
                    print(Fore.YELLOW + f"Error processing email: {e}" + Fore.RESET)
                    continue
                    
            return emails
            
        except Exception as e:
            print(Fore.RED + f"Error fetching emails: {e}" + Fore.RESET)
            return []
        finally:
            mail.logout()
    
    def _decode_header(self, header):
        """Decode email header"""
        if header is None:
            return ""
            
        try:
            decoded = []
            for part, encoding in email.header.decode_header(header):
                if isinstance(part, bytes):
                    part = part.decode(encoding or 'utf-8', errors='replace')
                decoded.append(part)
            return ' '.join(decoded)
        except Exception:
            return str(header)
    
    def _get_email_body(self, msg):
        """Extract email body"""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode()
                        return body
                    except:
                        pass
                
                # If no plain text version, try to get HTML version
                if content_type == "text/html" and "attachment" not in content_disposition:
                    try:
                        html = part.get_payload(decode=True).decode()
                        # Remove HTML tags and extra whitespace
                        soup = BeautifulSoup(html, "html.parser")
                        return soup.get_text(separator='\n', strip=True)
                    except:
                        pass
        else:
            # Not multipart - just get the payload
            try:
                return msg.get_payload(decode=True).decode()
            except:
                return "[Unable to decode email body]"
        
        return "[No content]"
    
    def summarize_email(self, email_content):
        """Generate a summary of the email using OpenAI"""
        try:
            # Truncate the email content if it's too long
            max_length = 12000  # Leave some room for the prompt
            if len(email_content) > max_length:
                email_content = email_content[:max_length] + "... [truncated]"
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes emails concisely."},
                    {"role": "user", "content": f"Please summarize the following email in 3-5 bullet points. Focus on the main points, actions required, and any important details.\n\nEmail:\n{email_content}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message['content'].strip()
            
        except Exception as e:
            print(Fore.RED + f"Error generating summary: {e}" + Fore.RESET)
            return "[Summary generation failed]"

def clear_screen():
    """Clear the console screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Print the application header"""
    clear_screen()
    print(Fore.CYAN + "=" * 80)
    print(pyfiglet.figlet_format("Email Summarizer", font="slant"))
    print(" " * 20 + "Your AI-powered email assistant")
    print("=" * 80 + Fore.RESET)
    print()

    def _process_feedback(self, email, is_important):
        """Process user feedback for an email"""
        # Store the feedback
        self.feedback_manager.add_feedback(email, is_important)
        
        # If using Gmail, move to appropriate label
        if email.get('is_gmail') and self.gmail_service:
            try:
                label_name = "Important" if is_important else "Junk"
                self.gmail_service.move_to_label(email['id'], label_name)
                print(Fore.GREEN + f"✓ Moved to {label_name} label in Gmail" + Fore.RESET)
            except Exception as e:
                print(Fore.YELLOW + f"Warning: Could not move email in Gmail: {e}" + Fore.RESET)
        
        # Retrain the classifier with updated feedback
        self._train_classifier()
    
    def _train_classifier(self):
        """Train the classifier with current feedback"""
        emails, labels = self.feedback_manager.get_training_data()
        if emails and labels:
            self.classifier.train(emails, labels)

def print_gmail_setup_instructions():
    """Print instructions for setting up Gmail API"""
    print(Fore.YELLOW + "=" * 80)
    print("GMAIL API SETUP INSTRUCTIONS")
    print("=" * 80 + Fore.RESET)
    print("\nTo use Gmail integration, please follow these steps:")
    print("1. Go to the Google Cloud Console: https://console.cloud.google.com/")
    print("2. Create a new project")
    print("3. Enable the Gmail API")
    print("4. Configure the OAuth consent screen")
    print("5. Create OAuth 2.0 credentials (Desktop app)")
    print("6. Download the credentials and save as 'credentials.json' in this directory")
    print("\nFor detailed instructions, visit: https://developers.google.com/gmail/api/quickstart/python")
    print("\n" + "=" * 80 + "\n")
    
    input("Press Enter to open the Google Cloud Console in your browser, or Ctrl+C to cancel...")
    webbrowser.open("https://console.cloud.google.com/apis/credentials/consent")


def main():
    try:
        print("Initializing Email Summarizer...")
        
        # Check if we should use Gmail
        use_gmail = os.getenv("USE_GMAIL", "true").lower() == "true"
        
        if use_gmail and not os.path.exists('credentials.json'):
            print(Fore.YELLOW + "Gmail API credentials not found!" + Fore.RESET)
            print_gmail_setup_instructions()
            return
        
        summarizer = EmailSummarizer()
        
        while True:
            print_header()
            print("Fetching your latest emails...\n")
            
            # Get emails from the last 7 days, max 5 emails
            try:
                emails = summarizer.get_emails(days=7, max_emails=5)
            except Exception as e:
                print(Fore.RED + f"Error fetching emails: {e}" + Fore.RESET)
                if summarizer.use_gmail:
                    print(Fore.YELLOW + "Falling back to IMAP..." + Fore.RESET)
                    summarizer.use_gmail = False
                    continue
                else:
                    print("Please check your internet connection and try again.")
                    input("Press Enter to continue...")
                    continue
            
            if not emails:
                print(Fore.YELLOW + "No emails found or error fetching emails." + Fore.RESET)
                input("\nPress Enter to try again...")
                continue
            
            # Display email list
            for i, email in enumerate(emails, 1):
                # Determine color based on classification
                if email['classification']['prediction'] == 'important':
                    importance_color = Fore.GREEN
                else:
                    importance_color = Fore.YELLOW
                
                print(importance_color + f"\n[{i}] {email['subject']}" + Fore.RESET)
                print(f"   From: {email['from']}")
                print(f"   Date: {email['date']}")
                print(f"   Status: {email['classification']['prediction'].upper()} "
                      f"(Confidence: {email['classification']['confidence']*100:.1f}%)")
                
                # Show the email snippet
                print(f"   {email['snippet']}")
            
            print("\n" + "-" * 80)
            print("\nOptions:")
            print("  [1-5] - View and summarize email")
            print("  [i#]  - Mark email # as important")
            print("  [j#]  - Mark email # as junk")
            print("  [r]   - Refresh email list")
            print("  [q]   - Quit")
            
            choice = input("\nEnter your choice: ").strip().lower()
            
            if choice == 'q':
                print("\nGoodbye!")
                break
                
            if choice == 'r':
                continue
                
            # Handle marking emails as important/junk
            if len(choice) == 2 and choice[0].lower() in ['i', 'j'] and choice[1:].isdigit():
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(emails):
                    is_important = (choice[0].lower() == 'i')
                    self._process_feedback(emails[idx], is_important)
                    status = "marked as IMPORTANT" if is_important else "marked as JUNK"
                    print(Fore.GREEN + f"\nEmail has been {status} and used for training the classifier." + Fore.RESET)
                    input("Press Enter to continue...")
                continue
                
            if choice.isdigit() and 1 <= int(choice) <= len(emails):
                email_index = int(choice) - 1
                selected_email = emails[email_index]
                
                print_header()
                print(Fore.GREEN + f"Subject: {selected_email['subject']}" + Fore.RESET)
                print(f"From: {selected_email['from']}")
                print(f"Date: {selected_email['date']}")
                print("\n" + "-" * 80)
                
                # Show summary
                print("\n" + Fore.CYAN + "🔍 Generating summary..." + Fore.RESET)
                summary = summarizer.summarize_email(selected_email['body'])
                print("\n" + Fore.YELLOW + "📝 Summary:" + Fore.RESET)
                print(summary)
                
                # Show full email content
                print("\n" + Fore.YELLOW + "📧 Full Email:" + Fore.RESET)
                print("\n".join(textwrap.wrap(selected_email['body'], width=100)))
                
                print("\n" + "-" * 80)
                print("Options:")
                print(f"  [i] - Mark this email as important")
                print(f"  [j] - Mark this email as junk")
                print(f"  [b] - Back to email list")
                
                action = input("\nEnter your choice: ").strip().lower()
                
                if action == 'i':
                    self._process_feedback(selected_email, True)
                    print(Fore.GREEN + "\nEmail marked as IMPORTANT and used for training the classifier." + Fore.RESET)
                    input("Press Enter to continue...")
                elif action == 'j':
                    self._process_feedback(selected_email, False)
                    print(Fore.YELLOW + "\nEmail marked as JUNK and used for training the classifier." + Fore.RESET)
                    input("Press Enter to continue...")
            
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
    except Exception as e:
        print(Fore.RED + f"\nAn error occurred: {e}" + Fore.RESET)
        input("Press Enter to exit...")

def create_env_file():
    """Create a default .env file if it doesn't exist"""
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write("""# Email Summarizer Configuration

# Required: Your OpenAI API key
OPENAI_API_KEY=your_openai_api_key_here

# Gmail API (recommended) - set to false to use IMAP instead
USE_GMAIL=true

# IMAP Configuration (only used if USE_GMAIL=false)
# EMAIL_ADDRESS=your_email@example.com
# EMAIL_PASSWORD=your_email_password_or_app_password
# IMAP_SERVER=imap.gmail.com
# IMAP_PORT=993
""")

if __name__ == "__main__":
    # Create default .env file if it doesn't exist
    create_env_file()
    
    # Load environment variables
    load_dotenv()
    
    # Run the application
    main()
