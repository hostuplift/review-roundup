import requests
import json
import pandas as pd

def get_dataset_id(run_url):
    resp = requests.get(run_url)
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["items"][0]["defaultDatasetId"]

API_TOKEN = "apify_api_tyUxUGMgzRKd15myrcgM5GjrfbCRpP3dLlXW"

# --- Booking.com ---
booking_run_url = "https://api.apify.com/v2/acts/voyager~booking-reviews-scraper/runs?token=" + API_TOKEN
booking_dataset_id = get_dataset_id(booking_run_url)
booking_dataset_url = f"https://api.apify.com/v2/datasets/{booking_dataset_id}/items?token={API_TOKEN}"

def normalize_booking_review(raw):
    rating_10 = raw.get("rating")
    rating_5 = round((rating_10 / 2), 1) if rating_10 is not None else None
    review_title = raw.get("reviewTitle")
    liked = raw.get('likedText', '')
    disliked = raw.get('dislikedText', '')
    review_text = f"=== {review_title} ===" if review_title else ""
    if liked:
        review_text += f"\nLiked: {liked}"
    if disliked:
        review_text += f"\nDisliked: {disliked}"
    review_text = review_text.strip()
    # Format date
    review_date = raw.get("reviewDate")
    if review_date:
        try:
            date_obj = pd.to_datetime(review_date)
            review_date = date_obj.strftime("%Y-%m-%d")
        except:
            pass
    return {
        "platform": "Booking.com",
        "review_date": review_date,
        "reviewer_name": raw.get("userName"),
        "star_rating": rating_5,
        "review_text": review_text,
        "replied": raw.get("propertyResponse") is not None
    }

# --- Expedia ---
expedia_run_url = "https://api.apify.com/v2/acts/tri_angle~expedia-hotels-com-reviews-scraper/runs?token=" + API_TOKEN
expedia_dataset_id = get_dataset_id(expedia_run_url)
expedia_dataset_url = f"https://api.apify.com/v2/datasets/{expedia_dataset_id}/items?token={API_TOKEN}"

def normalize_expedia_review(raw):
    label = raw.get("reviewScoreWithDescription", {}).get("label", "")
    try:
        rating_10 = float(label.split(" out of ")[0])
        rating_5 = round(rating_10 / 2, 1)
    except Exception:
        rating_5 = None
    review_title = raw.get("title", "")
    review_text = raw.get("text", "")
    reviewer_name = raw.get("reviewAuthorAttribution", {}).get("text", "")
    replied = bool(raw.get("managementResponses"))
    # Format date
    date_str = raw.get("submissionTime", {}).get("longDateFormat", "")
    if date_str:
        try:
            date_obj = pd.to_datetime(date_str)
            date_str = date_obj.strftime("%Y-%m-%d")
        except:
            pass
    return {
        "platform": "Expedia",
        "review_date": date_str,
        "reviewer_name": reviewer_name,
        "star_rating": rating_5,
        "review_text": f"=== {review_title} ===\n{review_text}".strip(),
        "replied": replied
    }

# --- TripAdvisor ---
tripadvisor_run_url = "https://api.apify.com/v2/acts/maxcopell~tripadvisor-reviews/runs?token=" + API_TOKEN
tripadvisor_dataset_id = get_dataset_id(tripadvisor_run_url)
tripadvisor_dataset_url = f"https://api.apify.com/v2/datasets/{tripadvisor_dataset_id}/items?token={API_TOKEN}"

def normalize_tripadvisor_review(raw):
    review_title = raw.get("title", "")
    review_text = raw.get("text", "")
    reviewer_name = raw.get("user", {}).get("name", "")
    replied = raw.get("ownerResponse") is not None
    published_date = raw.get("publishedDate")
    if published_date:
        try:
            date_obj = pd.to_datetime(published_date)
            published_date = date_obj.strftime("%Y-%m-%d")
        except:
            pass
    return {
        "platform": "TripAdvisor",
        "review_date": published_date,
        "reviewer_name": reviewer_name,
        "star_rating": raw.get("rating"),
        "review_text": f"=== {review_title} ===\n{review_text}".strip(),
        "replied": replied
    }

# --- Google Maps ---
google_run_url = "https://api.apify.com/v2/acts/compass~google-maps-reviews-scraper/runs?token=" + API_TOKEN
google_dataset_id = get_dataset_id(google_run_url)
google_dataset_url = f"https://api.apify.com/v2/datasets/{google_dataset_id}/items?token={API_TOKEN}"

def normalize_google_review(raw):
    review_title = raw.get("title", "")
    review_text = raw.get("text") or raw.get("textTranslated") or ""
    reviewer_name = raw.get("name", "")
    replied = raw.get("responseFromOwnerText") is not None
    star_rating = raw.get("stars")
    published_date = raw.get("publishedAtDate")
    if published_date:
        try:
            date_obj = pd.to_datetime(published_date.split("+")[0])
            published_date = date_obj.strftime("%Y-%m-%d")
        except:
            pass
    return {
        "platform": "Google",
        "review_date": published_date,
        "reviewer_name": reviewer_name,
        "star_rating": star_rating,
        "review_text": f"=== {review_title} ===\n{review_text}".strip(),
        "replied": replied
    }

# --- Fetch, Normalize, and Save ---
def fetch_and_save(url, normalize_fn, output_filename):
    resp = requests.get(url)
    resp.raise_for_status()
    reviews = resp.json()
    normalized = [normalize_fn(r) for r in reviews]
    with open(output_filename, "w") as f:
        json.dump(normalized, f, indent=2)
    print(f"Saved {len(normalized)} normalized reviews to {output_filename}")

fetch_and_save(booking_dataset_url, normalize_booking_review, "booking_reviews_normalized.json")
fetch_and_save(expedia_dataset_url, normalize_expedia_review, "expedia_reviews_normalized.json")
fetch_and_save(tripadvisor_dataset_url, normalize_tripadvisor_review, "tripadvisor_reviews_normalized.json")
fetch_and_save(google_dataset_url, normalize_google_review, "google_reviews_normalized.json")