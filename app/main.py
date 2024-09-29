from flask import Flask, render_template, request, redirect, url_for, session, Response,send_from_directory,flash
from flask_sqlalchemy import SQLAlchemy

from . import db,create_app
from .models import Recording,Contact,SignalGroup
from .camera import Camera
import random
import subprocess
import os # to be able to delete files 
#app = Flask(__name__)
#app.secret_key = 'supersecretkey'  # Replace with a secure key in production
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
#db = SQLAlchemy(app)

app = create_app()

'''
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

# Create the database tables within the application context
with app.app_context():
    db.create_all()
'''
camera = Camera(app)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status():
    if 'pin' in session:
        pin = session['pin']
    else:
        pin = None
    network_status = check_4g_status()
    return render_template('status.html', pin=pin, network_status=network_status)

@app.route('/toggle_session', methods=['POST'])
def toggle_session():
    camera.toggle_processing()
    if request.form.get('toggle') == 'on':
        session['pin'] = ''.join([random.choice('0123456789') for _ in range(6)])
    else:
        session.pop('pin', None)
    return redirect(url_for('status'))
#------------------------------------------------------------------------------
#
#   SETTINGS
#
#------------------------------------------------------------------------------
@app.route('/settings')
def settings():
    return render_template('settings.html')



@app.route('/signal')
def signal():
    groups = SignalGroup.query.all()
    return render_template('signal.html', groups=groups)
#--------------------------------------------------------------
#
#				HISTORY
#
#--------------------------------------------------------------
@app.route('/history')
def history():
    recordings = Recording.query.order_by(Recording.timestamp.desc()).all()
    return render_template('history.html', recordings=recordings)

@app.route('/recordings/<filename>')
def recordings(filename):
    return send_from_directory('recordings', filename)

@app.route('/delete_recording/<int:recording_id>', methods=['POST'])
def delete_recording(recording_id):
    recording = Recording.query.get_or_404(recording_id)
    try:
        db.session.delete(recording)
        db.session.commit()
        recording_path = os.path.join('recordings', recording.filename)
        if os.path.exists(recording_path):
            os.remove(recording_path)
        flash('Recording deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting recording: {e}', 'danger')
    return redirect(url_for('history'))


@app.route('/rotate_camera', methods=['POST'])
def rotate_camera():
    angle = request.form.get('angle', 0)
    camera.rotate(int(angle))
    return redirect(url_for('settings'))
#-----------------------------------------------------------------
#
#			CONTACT
#
#-----------------------------------------------------------------
@app.route('/contact')
def contact():
    contacts = Contact.query.all()
    return render_template('contact.html', contacts=contacts)
# Route to display the Add Contact page
@app.route('/add_contact')
def add_contact():
    return render_template('add_contact.html')
# Route to handle the form submission and add the contact
@app.route('/create_contact', methods=['POST'])
def create_contact():
    alias = request.form['alias']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    phone = request.form['phone']

    # Create new contact object and save to the database
    new_contact = Contact(alias=alias, first_name=first_name, last_name=last_name, email=email, phone=phone)
    db.session.add(new_contact)
    db.session.commit()

    flash('Contact added successfully!', 'success')
    return redirect(url_for('contact'))
'''
@app.route('/add_contact', methods=['POST'])
def add_contact():
    alias = request.form['alias']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    phone = request.form['phone']
    contact = Contact(alias=alias, first_name=first_name, last_name=last_name, email=email, phone=phone)
    db.session.add(contact)
    db.session.commit()
    return redirect(url_for('contact'))
'''
@app.route('/update_contact/<int:id>', methods=['POST'])
def update_contact(id):
    contact = Contact.query.get(id)
    contact.connected = 'connected' in request.form
    contact.sms_send = 'sms_send' in request.form
    db.session.commit()
    return redirect(url_for('contact'))

@app.route('/update_contact_checkbox', methods=['POST'])
def update_contact_checkbox():
    contact_id = request.form.get('id')
    field = request.form.get('field')
    value = request.form.get('value')

    contact = Contact.query.get(contact_id)
    if contact:
        if field == 'connected':
            contact.connected = True if value == '1' else False
        elif field == 'sms_send':
            contact.sms_send = True if value == '1' else False
        db.session.commit()

    return redirect(url_for('contact'))

@app.route('/edit_contact/<int:id>', methods=['GET','POST'])
def edit_contact(id):
    contact = Contact.query.get_or_404(id)
    if request.method == 'POST':
        contact.first_name = request.form.get('first_name')
        contact.last_name = request.form.get('last_name')
        contact.email = request.form.get('email')
        contact.phone = request.form.get('phone')
        db.session.commit()
        return redirect(url_for('contact'))
    # Render the edit_contact.html template with the contact data
    return render_template('edit_contact.html', contact=contact)

@app.route('/delete_contact/<int:id>', methods=['POST'])
def delete_contact(id):
    contact = Contact.query.get_or_404(id)
    try:
        db.session.delete(contact)
        db.session.commit()
        flash('Contact deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting contact: {e}', 'danger')
    return redirect(url_for('contact'))
#------------------------------------------------------------------
#
#			SIGNAL
#
#------------------------------------------------------------------
@app.route('/add_signal_group', methods=['POST'])
def add_signal_group():
    alias = request.form['alias']
    group_name = request.form['group_name']
    participants = request.form['participants']
    group = SignalGroup(alias=alias, group_name=group_name, participants=participants)
    db.session.add(group)
    db.session.commit()
    return redirect(url_for('signal'))

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            frame = camera.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
            else:
                break
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def check_4g_status():
    try:
        output = subprocess.check_output(['nmcli', 'device', 'status']).decode('utf-8')
        if 'eth1' in output:
            return 'Connected'
        else:
            return 'Disconnected'
    except Exception as e:
        return 'Error checking status'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
