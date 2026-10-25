"""
prepare_data.py
Downloads a public customer-support FAQ dataset and writes data/faq.jsonl
Falls back to a built-in synthetic dataset if network is unavailable.
"""

import json
import os
import re
import sys

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "faq.jsonl")

# ─── Inline synthetic FAQ (always available) ─────────────────────────────────
SYNTHETIC_FAQ = [
    {"instruction": "How do I track my order?", "category": "ORDER_TRACKING",
     "response": "Log in to AcmeShop, go to 'My Orders', and click on your order number to see real-time tracking updates. You will also receive email notifications at each shipping milestone."},
    {"instruction": "My package says delivered but I haven't received it.", "category": "DELIVERY_ISSUE",
     "response": "We're sorry to hear that! Please check with neighbors and your building's mail room first. If it's still missing after 24 hours, contact us and we'll file a carrier claim and reship or refund your order."},
    {"instruction": "How do I return an item?", "category": "RETURN",
     "response": "AcmeShop offers a 30-day hassle-free return policy. Go to 'My Orders', select the item, click 'Start Return', print the prepaid label, and drop the package at any UPS location."},
    {"instruction": "Can I change or cancel my order?", "category": "ORDER_CHANGE",
     "response": "Orders can be modified or cancelled within 1 hour of placement. After that, the order is sent to the warehouse and cannot be changed. Contact support immediately if you need to act quickly."},
    {"instruction": "What payment methods do you accept?", "category": "PAYMENT",
     "response": "We accept Visa, MasterCard, American Express, PayPal, Apple Pay, Google Pay, and AcmeShop gift cards. All payments are encrypted with TLS 1.3."},
    {"instruction": "How long does standard shipping take?", "category": "SHIPPING",
     "response": "Standard shipping takes 5–7 business days. Expedited shipping (2–3 days) and overnight options are available at checkout. Free standard shipping on orders over $50."},
    {"instruction": "Do you ship internationally?", "category": "SHIPPING",
     "response": "We currently ship to the US, Canada, UK, and Australia. International orders may be subject to customs duties, which are the buyer's responsibility."},
    {"instruction": "I received a damaged item, what do I do?", "category": "DAMAGED_ITEM",
     "response": "We apologize for the inconvenience. Please take photos of the damaged item and packaging, then contact support within 48 hours. We will send a replacement or issue a full refund, your choice."},
    {"instruction": "How do I use a promo code?", "category": "DISCOUNT",
     "response": "Enter your promo code in the 'Coupon Code' field on the checkout page, then click 'Apply'. The discount will be reflected in your order total before payment."},
    {"instruction": "What is your warranty policy?", "category": "WARRANTY",
     "response": "Most AcmeShop products come with a 1-year manufacturer warranty covering defects in materials and workmanship. Extended warranties are available for electronics."},
    {"instruction": "How do I reset my password?", "category": "ACCOUNT",
     "response": "Click 'Forgot Password' on the login page, enter your email, and check your inbox for a reset link. The link expires in 30 minutes."},
    {"instruction": "Can I have multiple shipping addresses?", "category": "ACCOUNT",
     "response": "Yes, you can save up to 5 shipping addresses in your account under 'Address Book'. You can select any saved address during checkout."},
    {"instruction": "Why was my credit card declined?", "category": "PAYMENT",
     "response": "Cards may be declined for several reasons: insufficient funds, incorrect CVV or expiry date, billing address mismatch, or a bank fraud hold. Please check your card details or contact your bank."},
    {"instruction": "How do I contact customer support?", "category": "CONTACT",
     "response": "You can reach AcmeShop support via this chat, by email at support@acmeshop.example.com, or by phone at 1-800-ACME-123 (Mon–Fri, 9 AM–6 PM EST)."},
    {"instruction": "Are my payment details safe?", "category": "SECURITY",
     "response": "Absolutely. AcmeShop is PCI DSS Level 1 compliant and never stores full card numbers. All transactions use 256-bit encryption."},
    {"instruction": "How do I unsubscribe from marketing emails?", "category": "EMAIL",
     "response": "Click 'Unsubscribe' at the bottom of any marketing email, or go to Account > Communication Preferences and toggle off marketing emails."},
    {"instruction": "What happens if an item goes out of stock after I order?", "category": "INVENTORY",
     "response": "If an item becomes unavailable after your order, we will notify you by email and offer a full refund or a comparable substitute."},
    {"instruction": "Can I exchange an item instead of returning it?", "category": "EXCHANGE",
     "response": "Yes! Select 'Exchange' instead of 'Return' when initiating from My Orders. Choose your preferred replacement item and we'll ship it once we receive the original."},
    {"instruction": "How do I redeem a gift card?", "category": "GIFT_CARD",
     "response": "Enter the gift card code in the 'Gift Card / Promo Code' field at checkout. Any remaining balance stays on the card for future purchases."},
    {"instruction": "Do you price match?", "category": "PRICE_MATCH",
     "response": "AcmeShop offers price matching for identical items sold by major US retailers. Contact support with a link to the lower price within 7 days of purchase."},
    {"instruction": "How do I leave a product review?", "category": "REVIEW",
     "response": "Go to the product page and scroll to 'Customer Reviews'. Click 'Write a Review'. You must have purchased the item to leave a verified review."},
    {"instruction": "What is AcmeShop Prime?", "category": "MEMBERSHIP",
     "response": "AcmeShop Prime is our annual membership ($49/year) offering free expedited shipping on all orders, early access to sales, and exclusive member discounts."},
    {"instruction": "How do I check my store credit balance?", "category": "CREDIT",
     "response": "Log into your account and go to Wallet > Store Credit. Your current balance and expiry date are shown there."},
    {"instruction": "Is there a restocking fee for returns?", "category": "RETURN",
     "response": "No restocking fees. Returns are free and hassle-free within 30 days. Some electronics must be unopened for a full refund; opened electronics receive store credit."},
    {"instruction": "How do I report a fraudulent charge?", "category": "FRAUD",
     "response": "If you see an unauthorized charge from AcmeShop, contact our fraud team immediately at fraud@acmeshop.example.com or call 1-800-ACME-123. We'll investigate and reverse any unauthorized charges within 2 business days."},
]

def clean_text(text: str) -> str:
    """Replace template tokens with realistic AcmeShop customer support details."""
    if not text:
        return ""
    replacements = {
        "{{Online Company Portal Info}}": "AcmeShop Portal (acmeshop.example.com)",
        "{{Customer Support Phone Number}}": "1-800-ACME-123",
        "{{Customer Support Email}}": "support@acmeshop.example.com",
        "{{Customer Support Hours}}": "Mon-Fri, 9 AM - 6 PM EST",
        "{{Company Name}}": "AcmeShop",
        "{{Return Policy Window}}": "30 days",
        "{{Cancellation Window}}": "1 hour",
    }
    for tag, rep in replacements.items():
        text = text.replace(tag, rep)
    # Generic cleanup of any remaining {{...}} tags
    text = re.sub(r"\{\{[^}]+\}\}", "AcmeShop Help Center", text)
    return text.strip()


def download_real_dataset(raw_path: str, max_rows: int = 400) -> list[dict]:
    """Downloads real Bitext Customer Support dataset directly from Hugging Face."""
    url = "https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset/resolve/main/Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
    import requests
    import csv
    import io

    print(f"Downloading real dataset from Hugging Face: {url} ...")
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    # Save to raw
    with open(raw_path, "wb") as f:
        f.write(resp.content)
    print(f"Saved raw dataset ({len(resp.content)} bytes) to {raw_path}")

    # Parse CSV
    f_in = io.StringIO(resp.text)
    reader = csv.DictReader(f_in)
    rows = []
    seen_instructions = set()

    for r in reader:
        instruction = clean_text(r.get("instruction", "") or r.get("input", ""))
        response = clean_text(r.get("response", "") or r.get("output", ""))
        category = r.get("category", "") or r.get("intent", "GENERAL")

        if not instruction or not response or instruction in seen_instructions:
            continue
        seen_instructions.add(instruction)

        rows.append({
            "instruction": instruction,
            "category": category,
            "response": response,
        })
        if len(rows) >= max_rows:
            break

    return rows


def main():
    import re
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    raw_csv = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "bitext_customer_support_sample.csv")

    rows = []
    try:
        rows = download_real_dataset(raw_csv, max_rows=400)
        print(f"Extracted {len(rows)} real customer-support records from Bitext dataset.")
    except Exception as e:
        print(f"Real dataset download failed ({e}). Falling back to built-in synthetic FAQ ({len(SYNTHETIC_FAQ)} rows).")
        rows = SYNTHETIC_FAQ

    with open(OUTPUT, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} rows -> {OUTPUT}")


if __name__ == "__main__":
    main()
