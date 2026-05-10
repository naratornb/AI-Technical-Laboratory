import pandas as pd
import random
from datetime import datetime, timedelta

# Configuration
NUM_RECORDS = 2500
# City to Country Mapping for Data Integrity
CITY_COUNTRY_MAP = {
    "New York": "USA", "London": "UK", "Tokyo": "Japan", "Paris": "France", 
    "Dubai": "UAE", "Singapore": "Singapore", "Hong Kong": "China", 
    "Los Angeles": "USA", "Berlin": "Germany", "Rome": "Italy", 
    "Toronto": "Canada", "Mumbai": "India", "Seoul": "South Korea", 
    "Istanbul": "Turkey", "Barcelona": "Spain", "Amsterdam": "Netherlands", 
    "Bangkok": "Thailand", "San Francisco": "USA", "Zurich": "Switzerland", 
    "Cape Town": "South Africa"
}

CITIES = list(CITY_COUNTRY_MAP.keys())
AIRLINES = ["Emirates", "Delta", "Singapore Airlines", "British Airways", "Lufthansa", "Qatar Airways"]
HOTEL_BRANDS = ["Hilton", "Marriott", "InterContinental", "Sheraton", "Hyatt", "Four Seasons"]

def generate_flights():
    data = []
    for i in range(1, NUM_RECORDS + 1):
        origin, dest = random.sample(CITIES, 2)
        duration = random.randint(60, 960)
        depart = datetime(2026, 1, 1) + timedelta(minutes=random.randint(0, 525600))
        arrival = depart + timedelta(minutes=duration)
        cabin = random.choice(["Economy", "Business", "First"])
        price_base = {"Economy": 600, "Business": 2500, "First": 6000}
        
        data.append({
            "flight_id": f"INT-FL-{i:05d}",
            "airline": random.choice(AIRLINES),
            "origin": origin,
            "origin_country": CITY_COUNTRY_MAP[origin],
            "destination": dest,
            "destination_country": CITY_COUNTRY_MAP[dest],
            "departure_datetime": depart.strftime('%Y-%m-%d %H:%M'),
            "arrival_datetime": arrival.strftime('%Y-%m-%d %H:%M'),
            "duration_minutes": duration,
            "cabin_class": cabin,
            "price_aud": price_base[cabin] + random.randint(0, 1500),
            "seats_available": random.randint(0, 300),
            "booking_class": random.choice(["Saver", "Flex", "Premium"])
        })
    return pd.DataFrame(data)

def generate_accommodation():
    data = []
    for i in range(1, NUM_RECORDS + 1):
        city = random.choice(CITIES)
        stars = random.randint(3, 5)
        data.append({
            "hotel_id": f"INT-HT-{i:05d}",
            "hotel_name": f"{random.choice(HOTEL_BRANDS)} {city}",
            "city": city,
            "country": CITY_COUNTRY_MAP[city],
            "property_type": random.choice(["Hotel", "Resort", "Boutique"]),
            "star_rating": stars,
            "room_type": random.choice(["Standard", "Deluxe", "Suite"]),
            "price_per_night_aud": (stars * 120) + random.randint(0, 500),
            "max_guests": random.randint(1, 4),
            "amenities": "wifi,AC,concierge",
            "availability_start": "2026-01-01",
            "availability_end": "2026-12-31"
        })
    return pd.DataFrame(data)

def generate_activities():
    data = []
    acts = ["City Tour", "Museum Pass", "Cooking Class", "River Cruise"]
    for i in range(1, NUM_RECORDS + 1):
        city = random.choice(CITIES)
        data.append({
            "activity_id": f"INT-AC-{i:05d}",
            "activity_name": f"{city} {random.choice(acts)}",
            "city": city,
            "country": CITY_COUNTRY_MAP[city],
            "category": random.choice(["Adventure", "Culture", "Food"]),
            "duration_hours": random.randint(1, 6),
            "price_aud": random.randint(50, 400),
            "rating": round(random.uniform(4.0, 5.0), 1),
            "suitable_for": random.choice(["Solo", "Couple", "Group"]),
            "availability": "Year-round"
        })
    return pd.DataFrame(data)

# Execution
generate_flights().to_csv("flights_intl_v2.csv", index=False)
generate_accommodation().to_csv("accommodation_intl_v2.csv", index=False)
generate_activities().to_csv("activities_intl_v2.csv", index=False)