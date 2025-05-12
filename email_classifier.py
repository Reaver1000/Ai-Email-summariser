import os
import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from joblib import dump, load

class EmailClassifier:
    def __init__(self, model_path='email_classifier.joblib'):
        self.model_path = model_path
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            class_weight='balanced'
        )
        self.pipeline = Pipeline([
            ('vectorizer', self.vectorizer),
            ('classifier', self.classifier)
        ])
        self.labels = ['junk', 'important']
        
        # Load existing model if available
        if os.path.exists(model_path):
            self.load_model()
    
    def extract_features(self, email):
        """Extract features from email content"""
        subject = email.get('subject', '')
        from_ = email.get('from', '')
        body = email.get('body', '')
        
        # Combine subject and body for classification
        text = f"{subject} {from_} {body}"
        return text
    
    def train(self, emails, labels):
        """Train the classifier with new labeled emails"""
        if not emails or not labels:
            return False
            
        # Extract features from emails
        texts = [self.extract_features(email) for email in emails]
        
        # Fit the model
        self.pipeline.fit(texts, labels)
        self.save_model()
        return True
    
    def predict(self, email):
        """Predict if an email is important or junk"""
        text = self.extract_features(email)
        
        try:
            # Get prediction probabilities
            probas = self.pipeline.predict_proba([text])[0]
            prediction = self.pipeline.predict([text])[0]
            confidence = max(probas)
            
            return {
                'prediction': self.labels[prediction],
                'confidence': float(confidence),
                'probas': {
                    'junk': float(probas[0]),
                    'important': float(probas[1])
                }
            }
        except Exception as e:
            # If prediction fails, return neutral prediction
            return {
                'prediction': 'important',
                'confidence': 0.5,
                'probas': {
                    'junk': 0.5,
                    'important': 0.5
                }
            }
    
    def save_model(self):
        """Save the trained model to disk"""
        dump(self.pipeline, self.model_path)
    
    def load_model(self):
        """Load a trained model from disk"""
        try:
            self.pipeline = load(self.model_path)
            self.vectorizer = self.pipeline.named_steps['vectorizer']
            self.classifier = self.pipeline.named_steps['classifier']
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False

class EmailFeedbackManager:
    def __init__(self, feedback_file='email_feedback.json'):
        self.feedback_file = feedback_file
        self.feedback = self._load_feedback()
    
    def _load_feedback(self):
        """Load feedback data from file"""
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading feedback: {e}")
        return {'emails': [], 'labels': []}
    
    def add_feedback(self, email, is_important):
        """Add new feedback for an email"""
        # Store a unique identifier for the email (subject + from + first 100 chars of body)
        email_id = f"{email.get('subject', '')[:50]}_{email.get('from', '')[:30]}_{hash(str(email.get('body', '')[:100]))}"
        
        # Check if we already have feedback for this email
        for i, existing_email in enumerate(self.feedback['emails']):
            if existing_email.get('id') == email_id:
                # Update existing feedback
                self.feedback['labels'][i] = int(is_important)
                self._save_feedback()
                return
        
        # Add new feedback
        self.feedback['emails'].append({
            'id': email_id,
            'subject': email.get('subject', ''),
            'from': email.get('from', ''),
            'body_preview': str(email.get('body', ''))[:200] + '...',
            'full_data': email
        })
        self.feedback['labels'].append(int(is_important))
        self._save_feedback()
    
    def _save_feedback(self):
        """Save feedback data to file"""
        try:
            with open(self.feedback_file, 'w') as f:
                json.dump(self.feedback, f, indent=2)
        except Exception as e:
            print(f"Error saving feedback: {e}")
    
    def get_training_data(self):
        """Get training data for the classifier"""
        return self.feedback.get('emails', []), self.feedback.get('labels', [])
