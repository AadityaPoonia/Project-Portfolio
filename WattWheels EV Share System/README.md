# WattWheels — Electric Vehicle Share System

A functional end-to-end prototype of an electric vehicle sharing programme, supporting three distinct user roles — **customers**, **operators**, and **managers** — over a shared vehicle fleet, with secure authentication and a reporting dashboard.

Built for the Programming & Systems Development course in the MSc Data Science programme at the University of Glasgow (2023–24).

## What It Does

**Customers** rent a vehicle from any city location where a working one is available, return it anywhere in the city (billed by rental duration and vehicle type), report defective vehicles, and settle outstanding charges on their account.

**Operators** track every vehicle's location across the city, charge depleted batteries, repair reported defects, and redistribute vehicles to locations where demand is higher.

**Managers** generate activity reports over any defined time period, rendered as visualizations and exportable as PDF.

## Design Notes

- **Security** — passwords are hashed with **Argon2**, the current password-hashing standard, rather than stored or hashed with a fast general-purpose algorithm.
- **Role separation** — each role gets its own UI surface (`Pages/client.py`, `Pages/operator.py`, `Pages/manager.py`), so a user only ever sees the operations they're authorised to perform.
- **Persistence** — all state (vehicles, charging points, city locations, customers, rentals) lives in a SQLite database behind a dedicated data-access layer in `database/database.py`.

## Getting Started

**Prerequisites** — Python 3 with `pip` on your PATH.

```bash
pip install pandas matplotlib argon2-cffi
```

**First run** — create and seed the database with default data:

```bash
python test.py
```

**Start the app:**

```bash
python mainApp.py
```

## Demo Credentials

The seeded database includes pre-populated randomized data for each role:

| Role | Email | Password |
|---|---|---|
| Customer | `user1@ecs14.com` | `password` |
| Operator | `op1@ecs14.com` | `password` |
| Manager | `manager1@ecs14.com` | `password` |

## Project Structure

```text
.
├── mainApp.py              # Application entry point
├── test.py                 # Database creation and seeding
├── database/
│   ├── database.py         # Data access layer
│   └── Database.db         # SQLite database
├── Pages/
│   ├── login.py            # Authentication
│   ├── signup.py           # Registration
│   ├── client.py           # Customer interface
│   ├── operator.py         # Operator interface
│   ├── manager.py          # Manager interface + reporting
│   └── renting.py          # Rental flow
└── Plots/pyplots.py        # Report visualizations
```

## Tech Stack

Python, Tkinter, SQLite, Argon2, pandas, Matplotlib
