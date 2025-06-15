import json
import requests

API_TOKEN = "apify_api_tyUxUGMgzRKd15myrcgM5GjrfbCRpP3dLlXW"

def get_dataset_id(run_url):
    resp = requests.get(run_url)
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["items"][0]["defaultDatasetId"]

def test_all_scrapers_raw():
    # Apify actor run URLs
    booking_run_url = "https://api.apify.com/v2/acts/voyager~booking-reviews-scraper/runs?token=" + API_TOKEN
    expedia_run_url = "https://api.apify.com/v2/acts/tri_angle~expedia-hotels-com-reviews-scraper/runs?token=" + API_TOKEN
    tripadvisor_run_url = "https://api.apify.com/v2/acts/maxcopell~tripadvisor-reviews/runs?token=" + API_TOKEN
    google_run_url = "https://api.apify.com/v2/acts/compass~google-maps-reviews-scraper/runs?token=" + API_TOKEN

    # Get dataset IDs
    booking_dataset_id = get_dataset_id(booking_run_url)
    expedia_dataset_id = get_dataset_id(expedia_run_url)
    tripadvisor_dataset_id = get_dataset_id(tripadvisor_run_url)
    google_dataset_id = get_dataset_id(google_run_url)

    # Construct dataset URLs
    booking_dataset_url = f"https://api.apify.com/v2/datasets/{booking_dataset_id}/items?token={API_TOKEN}"
    expedia_dataset_url = f"https://api.apify.com/v2/datasets/{expedia_dataset_id}/items?token={API_TOKEN}"
    tripadvisor_dataset_url = f"https://api.apify.com/v2/datasets/{tripadvisor_dataset_id}/items?token={API_TOKEN}"
    google_dataset_url = f"https://api.apify.com/v2/datasets/{google_dataset_id}/items?token={API_TOKEN}"

    print("\n=== RAW Booking.com Review ===")
    try:
        resp = requests.get(booking_dataset_url)
        resp.raise_for_status()
        reviews = resp.json()
        if reviews:
            print(json.dumps(reviews[0], indent=2))
    except Exception as e:
        print(f"Booking.com Error: {str(e)}")

    print("\n=== RAW Expedia Review ===")
    try:
        resp = requests.get(expedia_dataset_url)
        resp.raise_for_status()
        reviews = resp.json()
        if reviews:
            print(json.dumps(reviews[0], indent=2))
    except Exception as e:
        print(f"Expedia Error: {str(e)}")

    print("\n=== RAW TripAdvisor Review ===")
    try:
        resp = requests.get(tripadvisor_dataset_url)
        resp.raise_for_status()
        reviews = resp.json()
        if reviews:
            print(json.dumps(reviews[0], indent=2))
    except Exception as e:
        print(f"TripAdvisor Error: {str(e)}")

    print("\n=== RAW Google Maps Review ===")
    try:
        resp = requests.get(google_dataset_url)
        resp.raise_for_status()
        reviews = resp.json()
        if reviews:
            print(json.dumps(reviews[0], indent=2))
    except Exception as e:
        print(f"Google Maps Error: {str(e)}")

if __name__ == "__main__":
    test_all_scrapers_raw() 