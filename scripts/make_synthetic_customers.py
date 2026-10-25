"""
make_synthetic_customers.py
Generates 20 clearly-fake customer records with a fixed seed.
Writes data/customers.json
"""

import json
import os
import random

SEED = 42
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "customers.json")

FIRST_NAMES = ["Alice", "Bob", "Carol", "David", "Eva", "Frank", "Grace", "Hank",
               "Iris", "Jack", "Karen", "Leo", "Mia", "Nate", "Olivia", "Pete",
               "Quinn", "Rachel", "Sam", "Tina"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
              "Davis", "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White",
              "Harris", "Martin", "Thompson", "Young", "Allen", "King"]
STREETS = ["Main St", "Oak Ave", "Pine Rd", "Maple Blvd", "Cedar Lane", "Elm St",
           "Birch Way", "Walnut Dr", "Spruce Ct", "Willow Pl"]
CITIES = ["Springfield", "Shelbyville", "Capital City", "Shelbydale", "Centerville",
          "Riverside", "Lakewood", "Hillview", "Brookside", "Fairview"]
STATES = ["NY", "CA", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]
PRODUCT_NAMES = ["Smart Speaker", "Wireless Earbuds", "Laptop Stand", "USB-C Hub",
                 "Mechanical Keyboard", "Ergonomic Mouse", "Webcam HD", "Monitor Arm",
                 "LED Desk Lamp", "Portable Charger"]
STATUSES = ["delivered", "shipped", "processing", "returned"]


def make_customer(rng, idx):
    first = FIRST_NAMES[idx]
    last = rng.choice(LAST_NAMES)
    email = f"{first.lower()}.{last.lower()}@example.com"
    order_id = f"ORD-{rng.randint(100000, 999999)}"
    last4 = str(rng.randint(1000, 9999))
    street = f"{rng.randint(10, 999)} {rng.choice(STREETS)}"
    city = rng.choice(CITIES)
    state = rng.choice(STATES)
    zip_code = f"{rng.randint(10000, 99999)}"
    product = rng.choice(PRODUCT_NAMES)
    quantity = rng.randint(1, 3)
    price = round(rng.uniform(19.99, 299.99), 2)
    status = rng.choice(STATUSES)
    return {
        "customer_id": f"CUST-{1000 + idx}",
        "name": f"{first} {last}",
        "email": email,
        "address": f"{street}, {city}, {state} {zip_code}",
        "last4_card": last4,
        "order_id": order_id,
        "product": product,
        "quantity": quantity,
        "price_usd": price,
        "status": status,
    }


def main():
    rng = random.Random(SEED)
    customers = [make_customer(rng, i) for i in range(20)]
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(customers, f, indent=2)
    print(f"Generated {len(customers)} synthetic customers -> {OUTPUT}")
    # Print the first customer for reference in system prompts
    print("\nSample customer record (for system prompt testing):")
    print(json.dumps(customers[0], indent=2))


if __name__ == "__main__":
    main()
