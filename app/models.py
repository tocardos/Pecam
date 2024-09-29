from . import db

# Database Models
class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alias = db.Column(db.String(80), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    connected = db.Column(db.Boolean, default=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    sms_send = db.Column(db.Boolean, default=False)

class SignalGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alias = db.Column(db.String(80), unique=True, nullable=False)
    group_name = db.Column(db.String(80), nullable=False)
    participants = db.Column(db.Text, nullable=False)  # Comma-separated participant list
    
class Recording(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(120), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)