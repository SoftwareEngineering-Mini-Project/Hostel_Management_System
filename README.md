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

## Team

- Samyuktha
- Tanishk
- Atharva
- Krish

## License

This project was developed for academic purposes as part of a software engineering mini project.
