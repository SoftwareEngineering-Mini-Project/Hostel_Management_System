# Hostel Management System

A web-based application to manage student records, hostel and room information, room allocation, and check-in/check-out for a college hostel.

## Overview

The Hostel Management System centralizes hostel operations that are otherwise handled manually or across scattered files. Administrators can manage students, hostels, and rooms, allocate rooms while preventing over-allocation, and track check-in/check-out. Students can log in to view their own profile, room availability, and current allocation status.

## Features

- User authentication and role-based access (Administrator / Student)
- Student registration, profile updates, search, and viewing
- Hostel and room management, including capacity tracking
- Real-time room availability calculation
- Room allocation with over-allocation prevention
- Modify and cancel allocations
- Student check-in and check-out recording
- Allocation history
- Basic administrative summary dashboard

## Tech Stack

- **Backend:** Python, Django (Django ORM)
- **Database:** SQLite (development); any Django-supported relational database for deployment
- **Frontend:** Django templates / browser-based UI
- **Version Control:** Git and GitHub

## User Roles

| Role | Responsibilities |
|---|---|
| Student | View own profile, room availability, and allocation status |
| Hostel Administrator | Manage students, hostels, rooms, allocations, check-in/check-out |
| Project Administrator | Application-level access via Django admin during development/deployment |


## Project Scope

This version focuses on hostel room allocation and student detail management. Features such as online fee payment, biometric attendance, visitor management, and integration with external college systems are out of scope for the initial release.

## Documentation

Full functional and non-functional requirements, use-case diagrams, and the requirements traceability matrix are available in the project's Software Requirements Specification (SRS) document in this repo.

## Getting Started

### Requirements

- Python 3.11 or newer
- Git
- An internet connection (the pages load Bootstrap from a CDN)

### Setup

From the project folder:

```bash
# 1. Create and activate a virtual environment
python -m venv venv
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create the database tables
python manage.py migrate

# 4. Create an administrator login (is_staff is set automatically for superusers)
python manage.py createsuperuser

# 5. Start the development server
python manage.py runserver
```

Then open http://127.0.0.1:8000/ in your browser and log in.

### Running the tests

```bash
python manage.py test -v 2
```

To see line coverage (the STP target is 80% on models and services):

```bash
coverage run --source=hostels,rooms,allocations,dashboard,accounts manage.py test
coverage report -m
```

### Configuration

Two environment variables are read from `hms/settings.py`. Set them before deploying, and never commit a real secret key:

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | a development-only key | Secret key for sessions and CSRF tokens |
| `DJANGO_DEBUG` | `True` | Set to `False` for any demo or deployment |

### Pages

| URL | Who can use it | What it does |
|---|---|---|
| `/` | Anyone | Sends you to the login page, the dashboard (admin), or room availability (student) |
| `/accounts/login/` | Anyone | Log in |
| `/dashboard/` | Administrator | Summary metrics (students, hostels, rooms, capacity, occupancy) |
| `/hostels/` | Administrator | List, add, view and edit hostels |
| `/rooms/` | Logged-in users | Room availability, filtered by hostel, floor and status |
| `/rooms/new/` | Administrator | Add a room |
| `/admin/` | Django admin | Data fixes during development |

## How the Code Is Organized

The project is one Django project made of small apps, one per module in the SAD:

| Folder | Purpose |
|---|---|
| `hms/` | Project settings, root URL configuration and WSGI entry point |
| `accounts/` | `admin_required` decorator that restricts pages to administrators |
| `hostels/` | Hostel model, forms, views and tests (HMS-F-006) |
| `rooms/` | Room model with capacity and availability logic, filters, views and tests (HMS-F-007 to F-009) |
| `allocations/` | Allocation model: a student using a bed in a room. Only ACTIVE allocations take up beds |
| `dashboard/` | Read-only admin summary (HMS-F-019) |
| `templates/` | Shared HTML templates (`base.html` has the navigation bar and messages) |
| `docs/` | SRS, SAD and Software Test Plan (PDF) |

Test names contain their test case IDs (for example `test_TC_ROOM_02_...`), so you can match a failing test to the test plan.

## Team

- Samyuktha
- Tanishk
- Atharva
- Krish

## License

This project was developed for academic purposes as part of a software engineering mini project.
