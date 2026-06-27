"""
Data Generation Script
=======================
Generates synthetic but realistic datasets for the multi-agent system:
  1. tourism_trends.csv  — 10,000 rows of global tourism data (for CSV agent)
  2. airlines.sqlite     — 8-table relational database (for SQL agent)

Run once: python setup_data.py
"""

import csv
import random
import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

# ── Seed for reproducibility ─────────────────────────────────────
random.seed(42)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════════
#  PART 1: Tourism Trends CSV (10,000 rows)
# ══════════════════════════════════════════════════════════════════

def generate_tourism_csv():
    """Generate a realistic tourism trends dataset."""
    filepath = DATA_DIR / "tourism_trends.csv"

    # --- Dimension Values ---
    origins = [
        "United States", "United Kingdom", "Germany", "France", "China",
        "Japan", "India", "Brazil", "Canada", "Australia",
        "South Korea", "Mexico", "Italy", "Spain", "Netherlands",
        "Russia", "Turkey", "Saudi Arabia", "UAE", "Singapore",
    ]

    destinations = [
        "France", "Spain", "Italy", "Thailand", "Japan",
        "Greece", "Turkey", "Mexico", "Indonesia", "Morocco",
        "Portugal", "Switzerland", "New Zealand", "Iceland", "Peru",
        "Egypt", "South Africa", "Vietnam", "Croatia", "Maldives",
    ]

    purposes = ["Leisure", "Business", "Adventure", "Cultural", "Medical", "Education"]
    accommodations = ["Hotel", "Resort", "Hostel", "Airbnb", "Villa", "Guesthouse"]
    transport_modes = ["Flight", "Train", "Car", "Bus", "Cruise"]
    booking_channels = ["Online Travel Agency", "Direct Booking", "Travel Agent", "Mobile App"]
    seasons = ["Spring", "Summer", "Autumn", "Winter"]
    traveler_types = ["Solo", "Couple", "Family", "Group", "Business Team"]
    satisfaction_levels = ["Very Satisfied", "Satisfied", "Neutral", "Dissatisfied", "Very Dissatisfied"]

    # --- Pricing Lookup ---
    base_accommodation_cost = {
        "Hotel": 150, "Resort": 320, "Hostel": 45,
        "Airbnb": 110, "Villa": 280, "Guesthouse": 65,
    }
    seasonal_multiplier = {"Spring": 1.0, "Summer": 1.35, "Autumn": 0.9, "Winter": 0.85}

    columns = [
        "trip_id", "year", "month", "season", "origin_country", "destination_country",
        "travel_purpose", "traveler_type", "num_travelers", "trip_duration_days",
        "accommodation_type", "accommodation_cost_per_night", "total_accommodation_cost",
        "transport_mode", "transport_cost", "food_budget_daily", "total_food_cost",
        "activities_cost", "total_trip_cost", "booking_channel", "advance_booking_days",
        "is_repeat_visitor", "satisfaction_rating", "satisfaction_label",
        "visa_required", "travel_insurance", "eco_friendly_trip",
        "sustainability_score", "carbon_footprint_kg", "social_media_shared",
        "group_discount_pct", "loyalty_points_earned", "currency_exchange_loss_pct",
    ]

    rows = []
    for i in range(1, 10001):
        year = random.choice([2019, 2020, 2021, 2022, 2023, 2024])
        month = random.randint(1, 12)
        season = seasons[(month % 12) // 3]

        origin = random.choice(origins)
        dest = random.choice([d for d in destinations if d != origin] or destinations)
        purpose = random.choice(purposes)
        trav_type = random.choice(traveler_types)

        num_travelers = {
            "Solo": 1, "Couple": 2, "Family": random.randint(3, 6),
            "Group": random.randint(4, 12), "Business Team": random.randint(2, 8),
        }[trav_type]

        duration = random.randint(2, 21)
        accom = random.choice(accommodations)
        accom_base = base_accommodation_cost[accom]
        accom_per_night = round(accom_base * seasonal_multiplier[season] * random.uniform(0.8, 1.3), 2)
        total_accom = round(accom_per_night * duration, 2)

        transport_cost = round(random.uniform(150, 2500) * (1.2 if season == "Summer" else 1.0), 2)
        food_daily = round(random.uniform(20, 120), 2)
        total_food = round(food_daily * duration, 2)
        activities = round(random.uniform(50, 800), 2)

        # Group discount
        if num_travelers >= 6:
            group_discount = random.choice([10, 12, 15])
        elif num_travelers >= 3:
            group_discount = random.choice([5, 7])
        else:
            group_discount = 0

        subtotal = total_accom + transport_cost + total_food + activities
        total_cost = round(subtotal * (1 - group_discount / 100) * num_travelers, 2)

        advance_days = random.randint(1, 180)
        repeat = random.choice([True, False])
        rating = round(random.uniform(1.0, 5.0), 1)
        sat_label = (
            "Very Satisfied" if rating >= 4.5 else
            "Satisfied" if rating >= 3.5 else
            "Neutral" if rating >= 2.5 else
            "Dissatisfied" if rating >= 1.5 else
            "Very Dissatisfied"
        )
        visa = random.choice([True, False])
        insurance = random.choice([True, False])
        eco = random.choice([True, False])
        sustainability = random.randint(1, 100)
        carbon = round(random.uniform(50, 3000), 1)
        social = random.choice([True, False])
        loyalty = random.randint(100, 5000)
        fx_loss = round(random.uniform(0.5, 5.0), 2)

        rows.append([
            f"TRP-{i:06d}", year, month, season, origin, dest,
            purpose, trav_type, num_travelers, duration,
            accom, accom_per_night, total_accom,
            random.choice(transport_modes), transport_cost,
            food_daily, total_food, activities, total_cost,
            random.choice(booking_channels), advance_days,
            repeat, rating, sat_label, visa, insurance, eco,
            sustainability, carbon, social, group_discount, loyalty, fx_loss,
        ])

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    print(f"[OK] Created {filepath} -- {len(rows):,} rows, {len(columns)} columns")
    return filepath


# ══════════════════════════════════════════════════════════════════
#  PART 2: Airlines SQLite Database (8 tables)
# ══════════════════════════════════════════════════════════════════

def generate_airlines_db():
    """Generate a realistic airlines SQLite database."""
    filepath = DATA_DIR / "airlines.sqlite"

    # Remove old DB if exists
    if filepath.exists():
        os.remove(filepath)

    conn = sqlite3.connect(str(filepath))
    cursor = conn.cursor()

    # ── Table 1: aircrafts ────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE aircrafts (
            aircraft_code TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            range_km INTEGER NOT NULL,
            seats_total INTEGER NOT NULL
        )
    """)
    aircrafts = [
        ("773", "Boeing 777-300", 11120, 350),
        ("763", "Boeing 767-300", 7400, 260),
        ("319", "Airbus A319", 6850, 128),
        ("320", "Airbus A320", 6100, 180),
        ("321", "Airbus A321", 5950, 220),
        ("733", "Boeing 737-300", 4200, 149),
        ("738", "Boeing 737-800", 5400, 189),
        ("SU9", "Sukhoi SuperJet 100", 3000, 97),
        ("CR2", "Bombardier CRJ-200", 2700, 50),
        ("CN1", "Cessna 208 Caravan", 2000, 12),
    ]
    cursor.executemany("INSERT INTO aircrafts VALUES (?, ?, ?, ?)", aircrafts)

    # ── Table 2: airports ─────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE airports (
            airport_code TEXT PRIMARY KEY,
            airport_name TEXT NOT NULL,
            city TEXT NOT NULL,
            country TEXT NOT NULL,
            timezone TEXT NOT NULL
        )
    """)
    airports = [
        ("JFK", "John F. Kennedy International", "New York", "United States", "America/New_York"),
        ("LAX", "Los Angeles International", "Los Angeles", "United States", "America/Los_Angeles"),
        ("LHR", "London Heathrow", "London", "United Kingdom", "Europe/London"),
        ("CDG", "Charles de Gaulle", "Paris", "France", "Europe/Paris"),
        ("DXB", "Dubai International", "Dubai", "UAE", "Asia/Dubai"),
        ("HND", "Tokyo Haneda", "Tokyo", "Japan", "Asia/Tokyo"),
        ("SIN", "Singapore Changi", "Singapore", "Singapore", "Asia/Singapore"),
        ("SYD", "Sydney Kingsford Smith", "Sydney", "Australia", "Australia/Sydney"),
        ("DEL", "Indira Gandhi International", "Delhi", "India", "Asia/Kolkata"),
        ("FRA", "Frankfurt am Main", "Frankfurt", "Germany", "Europe/Berlin"),
        ("IST", "Istanbul Airport", "Istanbul", "Turkey", "Europe/Istanbul"),
        ("GRU", "São Paulo–Guarulhos", "São Paulo", "Brazil", "America/Sao_Paulo"),
        ("ORD", "O'Hare International", "Chicago", "United States", "America/Chicago"),
        ("MIA", "Miami International", "Miami", "United States", "America/New_York"),
        ("BKK", "Suvarnabhumi Airport", "Bangkok", "Thailand", "Asia/Bangkok"),
    ]
    cursor.executemany("INSERT INTO airports VALUES (?, ?, ?, ?, ?)", airports)

    airport_codes = [a[0] for a in airports]

    # ── Table 3: flights (5,000 flights) ──────────────────────────
    cursor.execute("""
        CREATE TABLE flights (
            flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_no TEXT NOT NULL,
            departure_airport TEXT NOT NULL REFERENCES airports(airport_code),
            arrival_airport TEXT NOT NULL REFERENCES airports(airport_code),
            aircraft_code TEXT NOT NULL REFERENCES aircrafts(aircraft_code),
            scheduled_departure TEXT NOT NULL,
            scheduled_arrival TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Scheduled','On Time','Delayed','Cancelled','Arrived')),
            delay_minutes INTEGER DEFAULT 0
        )
    """)

    statuses = ["On Time", "On Time", "On Time", "On Time", "Delayed", "Delayed", "Cancelled", "Arrived", "Arrived", "Arrived"]
    flight_records = []
    base_date = datetime(2024, 1, 1)
    airlines_codes = ["AA", "BA", "LH", "EK", "SQ", "QF", "AI", "TK", "JL", "UA"]

    for i in range(5000):
        airline = random.choice(airlines_codes)
        flight_no = f"{airline}{random.randint(100, 999)}"
        dep = random.choice(airport_codes)
        arr = random.choice([a for a in airport_codes if a != dep])
        aircraft = random.choice(aircrafts)[0]
        dep_time = base_date + timedelta(days=random.randint(0, 364), hours=random.randint(0, 23), minutes=random.choice([0, 15, 30, 45]))
        duration_hrs = random.uniform(1.5, 16)
        arr_time = dep_time + timedelta(hours=duration_hrs)
        status = random.choice(statuses)
        delay = random.randint(10, 240) if status == "Delayed" else 0

        flight_records.append((
            flight_no, dep, arr, aircraft,
            dep_time.strftime("%Y-%m-%d %H:%M:%S"),
            arr_time.strftime("%Y-%m-%d %H:%M:%S"),
            status, delay,
        ))

    cursor.executemany("""
        INSERT INTO flights (flight_no, departure_airport, arrival_airport, aircraft_code,
                            scheduled_departure, scheduled_arrival, status, delay_minutes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, flight_records)

    # ── Table 4: passengers (3,000 passengers) ────────────────────
    cursor.execute("""
        CREATE TABLE passengers (
            passenger_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            loyalty_tier TEXT CHECK(loyalty_tier IN ('Bronze','Silver','Gold','Platinum','None'))
        )
    """)

    first_names = ["James", "Mary", "Robert", "Jennifer", "Michael", "Linda", "David", "Sarah", "Ahmed", "Yuki",
                   "Carlos", "Priya", "Wei", "Fatima", "Oliver", "Emma", "Noah", "Ava", "Liam", "Sophia",
                   "Raj", "Mei", "Hassan", "Anna", "Ivan", "Kenji", "Maria", "Chen", "Aisha", "Thomas"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Wilson", "Moore",
                  "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Lee", "Kumar", "Singh",
                  "Tanaka", "Wang", "Ali", "Kim", "Mueller", "Rossi", "Dubois", "Santos", "Petrov", "Sato"]
    tiers = ["Bronze", "Silver", "Gold", "Platinum", "None", "None", "None", "Bronze", "Silver", "None"]

    passengers = []
    for i in range(3000):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        email = f"{fn.lower()}.{ln.lower()}{random.randint(1,999)}@email.com"
        phone = f"+{random.randint(1,99)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        tier = random.choice(tiers)
        passengers.append((fn, ln, email, phone, tier))

    cursor.executemany("""
        INSERT INTO passengers (first_name, last_name, email, phone, loyalty_tier)
        VALUES (?, ?, ?, ?, ?)
    """, passengers)

    # ── Table 5: bookings (8,000 bookings) ────────────────────────
    cursor.execute("""
        CREATE TABLE bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_ref TEXT NOT NULL UNIQUE,
            passenger_id INTEGER NOT NULL REFERENCES passengers(passenger_id),
            booking_date TEXT NOT NULL,
            total_amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            status TEXT CHECK(status IN ('Confirmed','Cancelled','Pending','Refunded'))
        )
    """)

    booking_statuses = ["Confirmed", "Confirmed", "Confirmed", "Confirmed", "Confirmed",
                        "Cancelled", "Pending", "Refunded"]
    bookings = []
    for i in range(8000):
        ref = f"BK{200000 + i}"
        pid = random.randint(1, 3000)
        bdate = (base_date + timedelta(days=random.randint(-90, 364))).strftime("%Y-%m-%d")
        amount = round(random.uniform(150, 5000), 2)
        currency = random.choice(["USD", "EUR", "GBP", "INR", "JPY", "AED"])
        status = random.choice(booking_statuses)
        bookings.append((ref, pid, bdate, amount, currency, status))

    cursor.executemany("""
        INSERT INTO bookings (booking_ref, passenger_id, booking_date, total_amount, currency, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, bookings)

    # ── Table 6: tickets ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL REFERENCES bookings(booking_id),
            flight_id INTEGER NOT NULL REFERENCES flights(flight_id),
            seat_number TEXT,
            fare_class TEXT CHECK(fare_class IN ('Economy','Premium Economy','Business','First')),
            fare_amount REAL NOT NULL
        )
    """)

    fare_classes = ["Economy", "Economy", "Economy", "Economy", "Premium Economy", "Business", "First"]
    fare_multiplier = {"Economy": 1.0, "Premium Economy": 1.8, "Business": 3.5, "First": 6.0}
    tickets = []
    for i in range(10000):
        bid = random.randint(1, 8000)
        fid = random.randint(1, 5000)
        row = random.randint(1, 40)
        seat_letter = random.choice("ABCDEF")
        seat = f"{row}{seat_letter}"
        fare_cls = random.choice(fare_classes)
        base_fare = random.uniform(100, 1500)
        fare = round(base_fare * fare_multiplier[fare_cls], 2)
        tickets.append((bid, fid, seat, fare_cls, fare))

    cursor.executemany("""
        INSERT INTO tickets (booking_id, flight_id, seat_number, fare_class, fare_amount)
        VALUES (?, ?, ?, ?, ?)
    """, tickets)

    # ── Table 7: boarding_passes ──────────────────────────────────
    cursor.execute("""
        CREATE TABLE boarding_passes (
            pass_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id),
            boarding_no INTEGER NOT NULL,
            gate TEXT
        )
    """)

    gates = [f"{chr(65+i)}{j}" for i in range(5) for j in range(1, 20)]
    passes = []
    for i in range(1, 8001):
        gate = random.choice(gates)
        boarding_no = random.randint(1, 300)
        passes.append((i, boarding_no, gate))

    cursor.executemany("""
        INSERT INTO boarding_passes (ticket_id, boarding_no, gate)
        VALUES (?, ?, ?)
    """, passes)

    # ── Table 8: seat_map ─────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE seat_map (
            aircraft_code TEXT NOT NULL REFERENCES aircrafts(aircraft_code),
            seat_number TEXT NOT NULL,
            fare_class TEXT CHECK(fare_class IN ('Economy','Premium Economy','Business','First')),
            PRIMARY KEY (aircraft_code, seat_number)
        )
    """)

    seat_entries = []
    for ac_code, _, _, total_seats in aircrafts:
        for row in range(1, (total_seats // 6) + 2):
            for letter in "ABCDEF":
                if row <= 2:
                    cls = "First"
                elif row <= 6:
                    cls = "Business"
                elif row <= 10:
                    cls = "Premium Economy"
                else:
                    cls = "Economy"
                seat_entries.append((ac_code, f"{row}{letter}", cls))

    cursor.executemany("""
        INSERT OR IGNORE INTO seat_map (aircraft_code, seat_number, fare_class)
        VALUES (?, ?, ?)
    """, seat_entries)

    conn.commit()

    # ── Print summary ─────────────────────────────────────────────
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"\n[OK] Created {filepath} -- {len(tables)} tables:")
    for (table_name,) in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"   - {table_name}: {count:,} rows")

    conn.close()
    return filepath


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  Data Generation Script")
    print("=" * 60)
    print()

    generate_tourism_csv()
    print()
    generate_airlines_db()

    print()
    print("=" * 60)
    print("  [OK] All data generated successfully!")
    print("=" * 60)
