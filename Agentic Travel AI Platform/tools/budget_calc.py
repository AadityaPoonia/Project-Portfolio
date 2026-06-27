"""
Travel Budget Calculator
=========================
Destination-aware pricing with regional tiers, INR/USD support,
group discounts, seasonal pricing, and taxes.
"""

from pydantic import BaseModel, Field
from langchain_core.tools import tool


# ── Input Schemas ─────────────────────────────────────────────────

class TripBudgetInput(BaseModel):
    destination: str = Field(description="Destination city or country (e.g. 'Shimla', 'Goa', 'Paris')")
    nights: str = Field(description="Number of nights staying (e.g. '2')")
    group_size: str = Field(description="Number of travelers (e.g. '1')", default="1")
    season: str = Field(description="Season: 'peak', 'shoulder', or 'off-peak'", default="shoulder")
    accommodation_type: str = Field(
        description="Accommodation type: 'hotel', 'resort', 'hostel', 'airbnb', or 'villa'",
        default="hotel"
    )


class FlightDiscountInput(BaseModel):
    base_fare: str = Field(description="Base fare per person (e.g. '5000')")
    advance_days: str = Field(description="How many days in advance the booking is made (e.g. '30')")
    loyalty_tier: str = Field(
        description="Loyalty tier: 'none', 'bronze', 'silver', 'gold', or 'platinum'",
        default="none"
    )
    num_passengers: str = Field(description="Number of passengers", default="1")
    currency: str = Field(description="Currency: 'INR' or 'USD'", default="INR")


# ── Regional Pricing (per night, base rates) ──────────────────────
# Rates vary by destination region AND accommodation type.

# Indian destinations (INR per night)
INDIA_REGIONS = {
    "hill_station": {
        "cities": [
            "shimla", "manali", "mussoorie", "nainital", "darjeeling",
            "ooty", "kodaikanal", "munnar", "coorg", "leh", "ladakh",
            "srinagar", "gangtok", "shillong", "dharamshala", "mcleodganj",
            "pahalgam", "gulmarg", "kasol", "rishikesh", "dehradun",
            "almora", "lansdowne", "mount abu", "lonavala", "mahabaleshwar",
        ],
        "rates": {"hotel": 2500, "resort": 5500, "hostel": 800, "airbnb": 1800, "villa": 7000},
    },
    "beach": {
        "cities": [
            "goa", "pondicherry", "puducherry", "kovalam", "varkala",
            "gokarna", "puri", "vizag", "visakhapatnam", "andaman",
            "lakshadweep", "alibaug", "tarkarli", "diu", "mangalore",
        ],
        "rates": {"hotel": 3000, "resort": 7000, "hostel": 900, "airbnb": 2200, "villa": 9000},
    },
    "metro": {
        "cities": [
            "delhi", "mumbai", "bangalore", "bengaluru", "chennai",
            "kolkata", "hyderabad", "pune", "ahmedabad", "jaipur",
            "lucknow", "noida", "gurgaon", "gurugram", "chandigarh",
            "indore", "nagpur", "kochi", "cochin",
        ],
        "rates": {"hotel": 3500, "resort": 8000, "hostel": 700, "airbnb": 2000, "villa": 10000},
    },
    "heritage": {
        "cities": [
            "udaipur", "jodhpur", "jaisalmer", "agra", "varanasi",
            "amritsar", "mysore", "mysuru", "hampi", "khajuraho",
            "madurai", "thanjavur", "ajanta", "ellora", "pushkar",
        ],
        "rates": {"hotel": 2800, "resort": 6000, "hostel": 750, "airbnb": 1900, "villa": 8000},
    },
}

# International destinations (USD per night)
INTL_RATES = {"hotel": 150, "resort": 320, "hostel": 45, "airbnb": 110, "villa": 280}

SEASONAL_MULTIPLIER = {
    "peak": 1.35, "shoulder": 1.0, "off-peak": 0.75,
}

LOYALTY_DISCOUNT = {
    "none": 0.0, "bronze": 0.03, "silver": 0.07,
    "gold": 0.12, "platinum": 0.18,
}

# Taxes
INDIA_GST_RATE = 0.12       # 12% GST on hotels
INTL_TAX_RATE = 0.12        # 12% accommodation tax
INDIA_TOURISM_LEVY = 200    # ₹200/person
INTL_TOURISM_LEVY = 35      # $35/person


# ── Helpers ───────────────────────────────────────────────────────

def _detect_india_region(destination: str) -> tuple:
    """Returns (region_name, rates_dict, currency) or None if not Indian."""
    dest_lower = destination.lower().strip()
    for region_name, region_data in INDIA_REGIONS.items():
        for city in region_data["cities"]:
            if city in dest_lower or dest_lower in city:
                return region_name, region_data["rates"], "INR"
    # Check if "india" is mentioned generically
    if "india" in dest_lower:
        return "metro", INDIA_REGIONS["metro"]["rates"], "INR"
    return None


# ── Tools ─────────────────────────────────────────────────────────

@tool(args_schema=TripBudgetInput)
def calculate_trip_budget(
    destination: str,
    nights: str,
    group_size: str = "1",
    season: str = "shoulder",
    accommodation_type: str = "hotel"
) -> str:
    """Calculate a detailed travel budget with destination-aware pricing.

    Automatically detects Indian destinations and uses INR pricing.
    International destinations use USD pricing.

    Includes: regional rates, seasonal multipliers, group discounts, taxes.

    Use this tool when the user asks about trip costs, budgets, or accommodation pricing.
    """
    # Validate accommodation type
    accom_key = accommodation_type.lower()
    season_key = season.lower()

    valid_accom = ["hotel", "resort", "hostel", "airbnb", "villa"]
    if accom_key not in valid_accom:
        return f"Unknown accommodation type: '{accommodation_type}'. Choose from: {valid_accom}"
    if season_key not in SEASONAL_MULTIPLIER:
        return f"Unknown season: '{season}'. Choose from: peak, shoulder, off-peak"

    try:
        nights_int = int(str(nights).strip())
        group_size_int = int(str(group_size).strip())
    except ValueError:
        return "Error: nights and group_size must be numbers."

    # Detect destination region
    india_result = _detect_india_region(destination)
    if india_result:
        region_name, rates, currency = india_result
        base_nightly = rates.get(accom_key, rates["hotel"])
        tax_rate = INDIA_GST_RATE
        tourism_levy_pp = INDIA_TOURISM_LEVY
        symbol = "₹"
        region_label = region_name.replace("_", " ").title()
    else:
        currency = "USD"
        base_nightly = INTL_RATES.get(accom_key, INTL_RATES["hotel"])
        tax_rate = INTL_TAX_RATE
        tourism_levy_pp = INTL_TOURISM_LEVY
        symbol = "$"
        region_label = "International"

    # Seasonal adjustment
    seasonal = SEASONAL_MULTIPLIER[season_key]
    adjusted_nightly = base_nightly * seasonal

    # Group discount
    if group_size_int >= 11:
        group_disc = 0.15
    elif group_size_int >= 6:
        group_disc = 0.10
    elif group_size_int >= 3:
        group_disc = 0.05
    else:
        group_disc = 0.0

    # Calculations
    accommodation_subtotal = adjusted_nightly * nights_int * (1 - group_disc)
    tax = accommodation_subtotal * tax_rate
    tourism_levy = tourism_levy_pp * group_size_int
    per_person_total = accommodation_subtotal + tax + tourism_levy_pp
    grand_total = (accommodation_subtotal + tax) * group_size_int + tourism_levy

    return (
        f"=== Trip Budget for {destination} ===\n"
        f"Region: {region_label} | Currency: {currency}\n"
        f"Accommodation: {accommodation_type.title()} ({season_key} season)\n"
        f"Duration: {nights_int} nights | Group: {group_size_int} travelers\n"
        f"---\n"
        f"Base nightly rate:       {symbol}{base_nightly:,.2f}\n"
        f"Seasonal multiplier:     x{seasonal:.2f} ({season_key})\n"
        f"Adjusted nightly rate:   {symbol}{adjusted_nightly:,.2f}\n"
        f"Group discount:          {group_disc*100:.0f}%\n"
        f"---\n"
        f"Accommodation subtotal:  {symbol}{accommodation_subtotal:,.2f}\n"
        f"Tax ({tax_rate*100:.0f}%):              {symbol}{tax:,.2f}\n"
        f"Tourism levy:            {symbol}{tourism_levy:,.2f} ({symbol}{tourism_levy_pp}/person)\n"
        f"---\n"
        f"Per-person cost:         {symbol}{per_person_total:,.2f}\n"
        f"GRAND TOTAL:             {symbol}{grand_total:,.2f}\n"
    )


@tool(args_schema=FlightDiscountInput)
def calculate_flight_discount(
    base_fare: str,
    advance_days: str,
    loyalty_tier: str = "none",
    num_passengers: str = "1",
    currency: str = "INR"
) -> str:
    """Calculate discounted flight price with early-bird, loyalty, and group savings.

    Formula:
      early_bird = 25% off (60+ days), 15% (30-59), 5% (14-29), 0% (<14)
      loyalty = Bronze 3%, Silver 7%, Gold 12%, Platinum 18%
      group = 8% off for 4+ passengers
      final_per_person = base x (1-early_bird) x (1-loyalty) x (1-group)
      total = final_per_person x num_passengers

    Use this tool when the user asks about flight pricing, discounts, or booking calculations.
    """
    tier_key = loyalty_tier.lower()
    if tier_key not in LOYALTY_DISCOUNT:
        return f"Unknown loyalty tier: '{loyalty_tier}'. Choose from: {list(LOYALTY_DISCOUNT.keys())}"

    try:
        base_fare_f = float(str(base_fare).strip())
        advance_days_i = int(str(advance_days).strip())
        num_passengers_i = int(str(num_passengers).strip())
    except ValueError:
        return "Error: base_fare, advance_days, and num_passengers must be valid numbers."

    symbol = "₹" if currency.upper() == "INR" else "$"

    # Early bird discount
    if advance_days_i >= 60:
        early_bird = 0.25
    elif advance_days_i >= 30:
        early_bird = 0.15
    elif advance_days_i >= 14:
        early_bird = 0.05
    else:
        early_bird = 0.0

    loyalty = LOYALTY_DISCOUNT[tier_key]
    group_disc = 0.08 if num_passengers_i >= 4 else 0.0

    final_per_person = base_fare_f * (1 - early_bird) * (1 - loyalty) * (1 - group_disc)
    total = final_per_person * num_passengers_i
    total_savings = (base_fare_f * num_passengers_i) - total
    savings_pct = (total_savings / (base_fare_f * num_passengers_i)) * 100 if base_fare_f > 0 else 0

    return (
        f"=== Flight Discount Calculation ===\n"
        f"Currency: {currency.upper()}\n"
        f"Base fare:           {symbol}{base_fare_f:,.2f}/person\n"
        f"Advance booking:     {advance_days_i} days\n"
        f"Loyalty tier:        {loyalty_tier.title()}\n"
        f"Passengers:          {num_passengers_i}\n"
        f"---\n"
        f"Early-bird discount: {early_bird*100:.0f}%\n"
        f"Loyalty discount:    {loyalty*100:.0f}%\n"
        f"Group discount:      {group_disc*100:.0f}%\n"
        f"---\n"
        f"Final per person:    {symbol}{final_per_person:,.2f}\n"
        f"TOTAL:               {symbol}{total:,.2f}\n"
        f"YOU SAVE:            {symbol}{total_savings:,.2f} ({savings_pct:.1f}%)\n"
    )
