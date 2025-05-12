import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from email_summarizer import EmailSummarizer
from email_classifier import EmailClassifier, EmailFeedbackManager
from gmail_integration import GmailService

class TestEmailClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = EmailClassifier(model_path='test_classifier.joblib')
        self.test_email = {
            'subject': 'Important Meeting',
            'from': 'boss@company.com',
            'body': 'We need to discuss the project deadline tomorrow.'
        }
    
    def test_initial_prediction(self):
        """Test that the classifier returns a valid prediction structure"""
        result = self.classifier.predict(self.test_email)
        self.assertIn('prediction', result)
        self.assertIn('confidence', result)
        self.assertIn('probas', result)
        self.assertIn('important', result['probas'])
        self.assertIn('junk', result['probas'])
    
    def test_train_classifier(self):
        """Test training the classifier with sample data"""
        emails = [self.test_email, self.test_email]
        labels = [1, 1]  # Both marked as important
        self.classifier.train(emails, labels)
        
        # Verify the model file was created
        self.assertTrue(os.path.exists('test_classifier.joblib'))
        os.remove('test_classifier.joblib')  # Clean up

class TestEmailFeedbackManager(unittest.TestCase):
    def setUp(self):
        self.feedback_file = 'test_feedback.json'
        self.manager = EmailFeedbackManager(self.feedback_file)
        self.test_email = {
            'subject': 'Test Email',
            'from': 'test@example.com',
            'body': 'This is a test email.'
        }
    
    def tearDown(self):
        if os.path.exists(self.feedback_file):
            os.remove(self.feedback_file)
    
    def test_add_feedback(self):
        """Test adding feedback to the manager"""
        self.manager.add_feedback(self.test_email, True)
        emails, labels = self.manager.get_training_data()
        self.assertEqual(len(emails), 1)
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0], 1)
    
    def test_duplicate_feedback(self):
        """Test that duplicate feedback updates existing entry"""
        self.manager.add_feedback(self.test_email, True)
        self.manager.add_feedback(self.test_email, False)  # Update to not important
        emails, labels = self.manager.get_training_data()
        self.assertEqual(len(emails), 1)
        self.assertEqual(labels[0], 0)  # Should be updated to not important

class TestEmailSummarizerIntegration(unittest.TestCase):
    @patch('email_summarizer.GmailService')
    def test_gmail_integration(self, mock_gmail_service):
        """Test Gmail integration with mocked service"""
        # Setup mock
        mock_service = MagicMock()
        mock_gmail_service.return_value = mock_service
        
        # Mock Gmail API response
        mock_email = {
            'id': 'test123',
            'subject': 'Test Email',
            'from': 'test@example.com',
            'date': 'Mon, 12 May 2025 12:00:00 +0000',
            'body': 'This is a test email.',
            'snippet': 'This is a test email.',
            'labels': ['INBOX']
        }
        mock_service.get_emails.return_value = [mock_email]
        
        # Test the summarizer
        summarizer = EmailSummarizer()
        summarizer.use_gmail = True
        summarizer.gmail_service = mock_service
        
        emails = summarizer.get_emails()
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]['subject'], 'Test Email')

class TestEdgeCases(unittest.TestCase):
    def test_empty_email(self):
        """Test with empty email content"""
        classifier = EmailClassifier()
        result = classifier.predict({
            'subject': '',
            'from': '',
            'body': ''
        })
        self.assertIn('prediction', result)
    
    def test_very_long_email(self):
        """Test with very long email content"""
        long_body = 'x' * 10000  # 10k characters
        classifier = EmailClassifier()
        result = classifier.predict({
            'subject': 'Long Email',
            'from': 'test@example.com',
            'body': long_body
        })
        self.assertIn('prediction', result)
    
    def test_special_characters(self):
        """Test with special characters in email"""
        classifier = EmailClassifier()
        result = classifier.predict({
            'subject': 'Test with special chars !@#$%^&*()',
            'from': 'test@example.com',
            'body': 'Email with special characters: äöüß 你好 こんにちは'
        })
        self.assertIn('prediction', result)

if __name__ == '__main__':
    unittest.main()
