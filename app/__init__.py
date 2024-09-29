from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    #app = Flask(__name__)
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.secret_key = 'supersecretkey'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    db.init_app(app)

    with app.app_context():
        from .models import Recording, Contact,SignalGroup
        db.create_all()

    return app
