Taxi Web App

Simple web application for taxi, delivery and classifieds.

Built for learning FastAPI, SQLAlchemy and full-stack basics.

⸻

Features
	•	Taxi orders
	•	Delivery orders
	•	Drivers and couriers moderation
	•	Classifieds (ads) with phone number
	•	Admin panel
	•	Mobile friendly UI

⸻

Tech
	•	Python + FastAPI
	•	SQLAlchemy
	•	PostgreSQL or SQLite
	•	Jinja2 templates
	•	HTML / CSS / JS

⸻

Run locally

Create virtual environment:

python -m venv venv
source venv/bin/activate

Install dependencies:

pip install -r requirements.txt

Set database in .env:

SQLite:

DATABASE_URL=sqlite:///./app.db

PostgreSQL:

DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname

Run app:

uvicorn app.main:app --reload

Open:

http://127.0.0.1:8000


⸻

Admin pages

/admin/drivers
/admin/couriers
/board/moderation


⸻

Notes

Learning and practice project deployed on an Aeza server with Cloudflare DNS and a custom domain

