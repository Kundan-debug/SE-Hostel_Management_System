"""Create or reset a warden account: python seed_warden.py --email warden@example.com --name 'Hostel Warden'"""
import argparse
import getpass
from app import create_app, db
from app.models import Warden
from werkzeug.security import generate_password_hash

parser = argparse.ArgumentParser()
parser.add_argument("--email", required=True)
parser.add_argument("--name", required=True)
args = parser.parse_args()
password = getpass.getpass("Warden password (min 12 characters): ")
if len(password) < 12:
    raise SystemExit("Password must be at least 12 characters.")
app = create_app()
with app.app_context():
    db.create_all()
    email = args.email.strip().lower()
    warden = Warden.query.filter_by(email=email).first()
    if warden is None:
        warden = Warden(email=email, full_name=args.name.strip(),
                        password_hash=generate_password_hash(password))
        db.session.add(warden)
    else:
        warden.full_name = args.name.strip()
        warden.password_hash = generate_password_hash(password)
    db.session.commit()
    print(f"Warden account ready for {email}")
