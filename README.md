# TutorLink: Peer Tutoring and Learning Support System
TutorLink; Link students with needed support with students who can provide it. 
Volunteers; list what tutoring they are able to provide. Students search for and book sessions. 
An administrator manages the tutors and sessions through a dashboard on a computer. 
The system is designed around the "Tanglaw"

## Features

**Students**
-Search/upcoming sessions by topic/subject and Tutor
-Book and cancel sessions. Sessions have real-time availability and cannot be double-booked
-Rate and review sessions you have attended.

**Tutors**
-Register as a tutor and wait for administrator approval
-Post, edit, complete and delete sessions
-See who booked, and track their average rating

**Administrator (Tkinter desktop dashboard)**
-Approve or reject tutor applications
-Manage subjects and sessions (full CRUD)
-View all bookings and statistics: sessions per subject, top-rated tutors, total tutoring hours

## Tech stack
-**Backend:** Python, Django, SQLite
-**Web UI:** Django templates with a custom CSS theme (Fraunces, Instrument Sans, DM Mono)
**Admin client:** Tkinter, talking to the server through `urllib` and `xml.etree`
-**API:** token-authenticated XML endpoints 

## Getting started
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

Then open http://127.0.0.1:8000/. To use the admin dashboard, run
`python main.py` inside `tkinter_dashboard/` and log in as `admin`.
