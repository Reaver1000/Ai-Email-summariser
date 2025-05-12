import os
import base64
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup

# If modifying these scopes, delete the file token.pickle.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

class GmailService:
    def __init__(self, credentials_file='credentials.json', token_file='token.pickle'):
        self.credentials = None
        self.service = None
        self.credentials_file = credentials_file
        self.token_file = token_file
    
    def authenticate(self):
        """Authenticate and create Gmail API service"""
        creds = None
        
        # The file token.pickle stores the user's access and refresh tokens
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file '{self.credentials_file}' not found. "
                        "Please enable the Gmail API and download the credentials.json file."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        self.credentials = creds
        self.service = build('gmail', 'v1', credentials=creds, static_discovery=False)
        return self.service
    
    def get_emails(self, max_results=10, label_ids=None):
        """Get a list of messages from the user's Gmail account"""
        if not self.service:
            self.authenticate()
        
        try:
            results = self.service.users().messages().list(
                userId='me',
                maxResults=max_results,
                labelIds=label_ids if label_ids else ['INBOX']
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for msg in messages:
                email_data = self.get_email(msg['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except Exception as e:
            print(f"An error occurred: {e}")
            return []
    
    def get_email(self, msg_id):
        """Get a specific email message by ID"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = {}
            for header in message['payload'].get('headers', []):
                headers[header['name']] = header['value']
            
            # Get email body
            body = self._get_email_body(message['payload'])
            
            # Get labels
            labels = message.get('labelIds', [])
            
            return {
                'id': msg_id,
                'threadId': message.get('threadId'),
                'snippet': message.get('snippet', ''),
                'subject': headers.get('Subject', '(No subject)'),
                'from': headers.get('From', 'Unknown'),
                'to': headers.get('To', ''),
                'date': headers.get('Date', ''),
                'body': body,
                'labels': labels,
                'raw': message
            }
            
        except Exception as e:
            print(f"Error getting email {msg_id}: {e}")
            return None
    
    def _get_email_body(self, payload):
        """Extract email body from the payload"""
        if 'parts' in payload:
            parts = payload['parts']
            for part in parts:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    return self._decode_base64(data)
                elif part['mimeType'] == 'text/html':
                    data = part['body'].get('data', '')
                    html = self._decode_base64(data)
                    soup = BeautifulSoup(html, 'html.parser')
                    return soup.get_text(separator='\n', strip=True)
                elif 'parts' in part:
                    # Handle nested parts
                    return self._get_email_body(part)
        
        # If no parts or not found in parts, try the body directly
        if 'body' in payload and 'data' in payload['body']:
            return self._decode_base64(payload['body']['data'])
            
        return ''
    
    @staticmethod
    def _decode_base64(data):
        """Decode base64 with proper padding"""
        try:
            # Add padding if needed
            missing_padding = len(data) % 4
            if missing_padding:
                data += '=' * (4 - missing_padding)
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Error decoding base64: {e}")
            return ''
    
    def mark_as_read(self, msg_id):
        """Mark an email as read"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            return True
        except Exception as e:
            print(f"Error marking email as read: {e}")
            return False
    
    def move_to_label(self, msg_id, label_name):
        """Move an email to a specific label"""
        try:
            # First, get or create the label
            label_id = self._get_or_create_label(label_name)
            if not label_id:
                return False
                
            # Apply the label
            self.service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            return True
            
        except Exception as e:
            print(f"Error moving email to label {label_name}: {e}")
            return False
    
    def _get_or_create_label(self, label_name):
        """Get or create a Gmail label"""
        try:
            # Try to get the label
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            for label in labels:
                if label['name'].lower() == label_name.lower():
                    return label['id']
            
            # Label doesn't exist, create it
            label = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            
            created_label = self.service.users().labels().create(
                userId='me',
                body=label
            ).execute()
            
            return created_label['id']
            
        except Exception as e:
            print(f"Error getting/creating label {label_name}: {e}")
            return None
