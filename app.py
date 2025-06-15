import streamlit as st
import requests
import time
import json
import pandas as pd
from datetime import datetime, timedelta
import openai
import os

# Set page config
st.set_page_config(
    page_title="Review Round Up",
    page_icon="📊",
    layout="wide"
)

# Initialize session state variables
if 'reviews_loaded' not in st.session_state:
    st.session_state.reviews_loaded = False
if 'reviews_df' not in st.session_state:
    st.session_state.reviews_df = None
if 'summary' not in st.session_state:
    st.session_state.summary = None
if 'report' not in st.session_state:
    st.session_state.report = None
if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = None
if 'start_date' not in st.session_state:
    st.session_state.start_date = None
if 'end_date' not in st.session_state:
    st.session_state.end_date = None
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = None
if 'establishment_name' not in st.session_state:
    st.session_state.establishment_name = None

st.title("Review Round Up 📊")

def trigger_actor(actor_id, api_token, start_url):
    run_url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={api_token}"
    
    # Platform-specific configurations
    if "booking-reviews-scraper" in actor_id:
        sort_by = "review_score_and_price"  # Valid for Booking.com
    elif "expedia-hotels-com-reviews-scraper" in actor_id:
        sort_by = "Most recent"  # Valid for Expedia
    elif "tripadvisor-reviews" in actor_id:
        sort_by = "Most recent"  # Valid for TripAdvisor
    elif "google-maps-reviews-scraper" in actor_id:
        sort_by = "Most recent"  # Valid for Google Maps
    else:
        sort_by = "Most recent"  # Default for other platforms
    
    # Configure the actor to fetch 2 years of reviews
    payload = {
        "startUrls": [{"url": start_url}],
        "maxReviews": 1000,  # Set a high number to ensure we get all reviews
        "maxReviewsPerPage": 100,  # Maximum reviews per page
        "maxPages": 10,  # Maximum number of pages to scrape
        "minRating": 1,  # Include all ratings
        "maxRating": 5,  # Include all ratings
        "sortBy": sort_by,
        "timeRange": "2y"  # Last 2 years
    }
    
    # Add platform-specific configurations
    if "google-maps-reviews-scraper" in actor_id:
        payload["includeReviewOrigin"] = True  # Ensure we get review origin for Google
    
    resp = requests.post(run_url, json=payload)
    resp.raise_for_status()
    run_data = resp.json()
    run_id = run_data["data"]["id"]
    return run_id

def wait_for_run(run_id, api_token):
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={api_token}"
    while True:
        resp = requests.get(status_url)
        resp.raise_for_status()
        data = resp.json()
        status = data["data"]["status"]
        if status in ["SUCCEEDED", "FAILED", "ABORTED"]:
            # Add detailed status information
            if status != "SUCCEEDED":
                st.error(f"Run status: {status}")
                st.error(f"Run details: {json.dumps(data['data'], indent=2)}")
            return data
        time.sleep(5)

def fetch_reviews(dataset_id, api_token):
    dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={api_token}"
    resp = requests.get(dataset_url)
    resp.raise_for_status()
    return resp.json()

# Normalization functions
def normalize_date(date_str):
    """Helper function to normalize dates across all platforms"""
    if not date_str:
        return None
    try:
        # Try different date formats
        for fmt in ["%Y-%m-%d", "%d %b %Y", "%b %d, %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                date_obj = pd.to_datetime(date_str, format=fmt)
                return date_obj.strftime("%Y-%m-%d")
            except:
                continue
        # If none of the specific formats work, try pandas' automatic parsing
        date_obj = pd.to_datetime(date_str)
        return date_obj.strftime("%Y-%m-%d")
    except:
        return None

def normalize_booking_review(raw):
    rating_10 = raw.get("rating")
    rating_5 = round((rating_10 / 2), 1) if rating_10 is not None else None
    review_title = raw.get("reviewTitle")
    liked = raw.get('likedText', '')
    disliked = raw.get('dislikedText', '')
    
    # Format review text with clear sections
    review_parts = []
    if review_title:
        review_parts.append(f"Title: {review_title}")
    if liked:
        review_parts.append(f"Liked: {liked}")
    if disliked:
        review_parts.append(f"Disliked: {disliked}")
    
    review_text = "\n".join(review_parts)
    
    return {
        "platform": "Booking.com",
        "review_date": normalize_date(raw.get("reviewDate")),
        "reviewer_name": raw.get("userName"),
        "star_rating": rating_5,
        "review_text": review_text,
        "replied": raw.get("propertyResponse") is not None
    }

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
    
    # Format review text with title only if it exists
    if review_title:
        review_text = f"Title: {review_title}\n{review_text}"
    
    # Get and format the date
    date_str = raw.get("submissionTime", {}).get("longDateFormat", "")
    
    return {
        "platform": "Expedia",
        "review_date": normalize_date(date_str),
        "reviewer_name": reviewer_name,
        "star_rating": rating_5,
        "review_text": review_text.strip(),
        "replied": replied
    }

def normalize_tripadvisor_review(raw):
    review_title = raw.get("title", "")
    review_text = raw.get("text", "")
    reviewer_name = raw.get("user", {}).get("name", "")
    replied = raw.get("ownerResponse") is not None
    published_date = raw.get("publishedDate")
    
    # Format review text with title only if it exists
    if review_title:
        review_text = f"Title: {review_title}\n{review_text}"
    
    return {
        "platform": "TripAdvisor",
        "review_date": normalize_date(published_date),
        "reviewer_name": reviewer_name,
        "star_rating": raw.get("rating"),
        "review_text": review_text.strip(),
        "replied": replied
    }

def normalize_google_review(raw):
    # Only process reviews that have "Google" as their origin
    if raw.get("reviewOrigin") != "Google":
        return None
        
    review_title = raw.get("title", "")
    review_text = raw.get("text") or raw.get("textTranslated") or ""
    reviewer_name = raw.get("name", "")
    replied = raw.get("responseFromOwnerText") is not None
    star_rating = raw.get("stars")  # Use stars field directly
    published_date = raw.get("publishedAtDate")
    
    return {
        "platform": "Google",
        "review_date": normalize_date(published_date),
        "reviewer_name": reviewer_name,
        "star_rating": star_rating,
        "review_text": review_text.strip(),  # Remove title/establishment name
        "replied": replied
    }

def generate_summary(filtered_df, start_date, end_date, api_key):
    if not api_key:
        st.error("Please enter your OpenAI API key.")
        return
    
    with st.spinner("Generating summary..."):
        try:
            # Prepare the reviews data for ChatGPT
            reviews_text = []
            
            for _, row in filtered_df.iterrows():
                # Full review text with clear formatting
                review_info = f"Date: {row['review_date'].strftime('%Y-%m-%d')}\n"
                review_info += f"Platform: {row['platform']}\n"
                review_info += f"Rating: {row['star_rating']} stars\n"
                review_info += f"Review: {row['review_text']}\n"
                review_info += f"Replied: {'Yes' if row['replied'] else 'No'}\n"
                review_info += "---\n"
                reviews_text.append(review_info)
            
            # Combine all reviews into a single text
            combined_reviews = "\n".join(reviews_text)
            
            # Create the prompt for ChatGPT
            prompt = f"""Analyze these reviews from {start_date} to {end_date} and provide a structured summary with the following sections:

1. Overall Sentiment
2. Positive Highlights
3. Areas for Improvement
4. Actionable Suggestions
5. Unreplied Reviews (if any)

Reviews to analyze:
{combined_reviews}

Please provide a professional, concise, and solution-oriented summary that helps managers take efficient actions based on customer feedback insights."""

            # Call ChatGPT API
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional business analyst specializing in customer feedback analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Store the summary in session state
            st.session_state.summary = response.choices[0].message.content
            
        except Exception as e:
            st.error(f"Error generating summary: {str(e)}")

def generate_report(filtered_df, start_date, end_date, api_key):
    if not api_key:
        st.error("Please enter your OpenAI API key.")
        return
    
    with st.spinner("Analyzing reviews for potential violations..."):
        try:
            # Prepare the reviews data for ChatGPT
            reviews_text = []
            
            for _, row in filtered_df.iterrows():
                # Full review text with clear formatting
                review_info = f"Date: {row['review_date'].strftime('%Y-%m-%d')}\n"
                review_info += f"Platform: {row['platform']}\n"
                review_info += f"Rating: {row['star_rating']} stars\n"
                review_info += f"Review: {row['review_text']}\n"
                review_info += f"Replied: {'Yes' if row['replied'] else 'No'}\n"
                review_info += "---\n"
                reviews_text.append(review_info)
            
            # Combine all reviews into a single text
            combined_reviews = "\n".join(reviews_text)
            
            # Create the prompt for ChatGPT
            prompt = f"""Analyze these reviews from {start_date} to {end_date} and identify ONLY reviews that have clear, legitimate grounds for removal based on platform policies. For each flagged review, provide:

1. Review Details (date, platform, rating)
2. Specific Violation(s) Identified
3. Evidence from the review text
4. Draft message to the platform requesting removal

IMPORTANT: Only flag reviews that have CLEAR and UNDENIABLE violations. Do not include reviews that are simply negative or critical but legitimate. Focus strictly on identifying:

- Fake or fraudulent reviews (e.g., reviewer never stayed)
- Reviews from non-guests (e.g., competitors, non-customers)
- Offensive language or hate speech
- Personal attacks or threats
- Confidential information exposure
- Reviews for wrong business
- Reviews from canceled bookings/no-shows

Reviews to analyze:
{combined_reviews}

Please provide a professional, evidence-based analysis that ONLY includes reviews with clear violations of platform policies. If no reviews meet these strict criteria, state that no reviews were found that could be legitimately challenged."""

            # Call ChatGPT API
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional review policy compliance analyst specializing in identifying reviews that violate platform terms and conditions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Store the report in session state
            st.session_state.report = response.choices[0].message.content
            
        except Exception as e:
            st.error(f"Error generating report: {str(e)}")

# Main app logic
if not st.session_state.reviews_loaded:
    # Initial review loading section
    st.session_state.establishment_name = st.text_input("Enter Establishment Name", value="Snake Catcher")
    col1, col2 = st.columns(2)
    with col1:
        API_TOKEN = st.text_input("Enter your Apify API token", type="password", value=os.getenv("APIFY_API_TOKEN", ""))
    with col2:
        st.session_state.openai_api_key = st.text_input("Enter your OpenAI API key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    
    platforms = [
        ("Booking.com", "voyager~booking-reviews-scraper", normalize_booking_review),
        ("Expedia", "tri_angle~expedia-hotels-com-reviews-scraper", normalize_expedia_review),
        ("TripAdvisor", "maxcopell~tripadvisor-reviews", normalize_tripadvisor_review),
        ("Google Maps", "compass~google-maps-reviews-scraper", normalize_google_review),
    ]

    # Default URLs
    default_urls = {
        "Booking.com": "https://www.booking.com/hotel/gb/stanwell-house.en-gb.html",
        "Expedia": "https://www.expedia.co.uk/Lymington-Hotels-STANWELL-HOUSE.h98042345.Hotel-Information?chkin=2025-05-27&chkout=2025-05-28&x_pwa=1&rfrr=HSR&pwa_ts=1747135613727&referrerUrl=aHR0cHM6Ly93d3cuZXhwZWRpYS5jby51ay9Ib3RlbC1TZWFyY2g%3D&useRewards=true&rm1=a2&regionId=181548&destination=Lymington%2C%20England%2C%20United%20Kingdom&destType=MARKET&selected=98042345&latLong=51.4933%2C-0.1141&sort=RECOMMENDED&top_dp=250&top_cur=GBP&gclid=EAIaIQobChMIlOmRq6ugjQMVjZZQBh07OSj5EAAYASAAEgLQ4vD_BwE&semcid=UK.UB.GOOGLE.PT-c-EN.HOTEL&semdtl=a115307813601.b1162875154881.g1kwd-12792998642.e1c.m1EAIaIQobChMIlOmRq6ugjQMVjZZQBh07OSj5EAAYASAAEgLQ4vD_BwE.r1.c1.j19045901.k1.d1722170184544.h1p.i1.l1.n1.o1.p1.q1.s1.t1.x1.f1.u1.v1.w1&userIntent=&selectedRoomType=322914384&selectedRatePlan=399722335&searchId=5fc2ed39-341d-49f6-ad8a-da91dd9374d2",
        "TripAdvisor": "https://www.tripadvisor.co.uk/Hotel_Review-g190774-d250548-Reviews-Stanwell_House_Hotel-Lymington_New_Forest_National_Park_Hampshire_Hampshire_England.html",
        "Google Maps": "https://maps.app.goo.gl/9PKnWdh6gnDcERsY8"
    }

    # Create input fields for each platform
    inputs = {}
    for name, _, _ in platforms:
        inputs[name] = st.text_input(f"Paste the {name} URL", 
                                   value=default_urls[name],
                                   help=f"Enter the {name} URL for the establishment")

    if st.button("Load Reviews", use_container_width=True):
        if not API_TOKEN:
            st.error("Please enter your Apify API token.")
        elif not st.session_state.openai_api_key:
            st.error("Please enter your OpenAI API key.")
        else:
            all_reviews = []
            for name, actor_id, normalize_fn in platforms:
                public_url = inputs[name]
                if public_url:
                    try:
                        st.write(f"Triggering Apify actor for {name}...")
                        run_id = trigger_actor(actor_id, API_TOKEN, public_url)
                        st.write(f"Waiting for {name} run to finish...")
                        run_data = wait_for_run(run_id, API_TOKEN)
                        if run_data["data"]["status"] != "SUCCEEDED":
                            st.error(f"{name} run failed or was aborted.")
                            if "meta" in run_data["data"]:
                                st.error(f"Error details: {json.dumps(run_data['data']['meta'], indent=2)}")
                            continue
                        dataset_id = run_data["data"]["defaultDatasetId"]
                        st.write(f"Fetching reviews for {name}...")
                        reviews = fetch_reviews(dataset_id, API_TOKEN)
                        if not reviews:
                            st.warning(f"No reviews found for {name}. This might indicate an issue with the URL or scraper.")
                        normalized = [r for r in [normalize_fn(r) for r in reviews] if r is not None]
                        all_reviews.extend(normalized)
                    except Exception as e:
                        st.error(f"Error fetching {name}: {str(e)}")
                        if hasattr(e, 'response'):
                            try:
                                error_details = e.response.json()
                                st.error(f"Error details: {json.dumps(error_details, indent=2)}")
                            except:
                                st.error(f"Error response: {e.response.text}")
                        else:
                            st.error(f"Error details: {str(e)}")

            if all_reviews:
                # Convert to DataFrame and sort by date
                df = pd.DataFrame(all_reviews)
                df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
                df = df.sort_values(by='review_date', ascending=False)
                
                # Store in session state
                st.session_state.reviews_df = df
                st.session_state.reviews_loaded = True
                st.rerun()

else:
    # Main review analysis section
    df = st.session_state.reviews_df
    
    # Initialize dates if not set
    if st.session_state.start_date is None:
        st.session_state.start_date = pd.Timestamp.now() - pd.Timedelta(days=30)
    if st.session_state.end_date is None:
        st.session_state.end_date = pd.Timestamp.now()
    
    # Display the main header with establishment name
    st.title(f"{st.session_state.establishment_name} Reviews")
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.start_date = st.date_input("Start Date", value=st.session_state.start_date)
    with col2:
        st.session_state.end_date = st.date_input("End Date", value=st.session_state.end_date)
    
    # Filter reviews based on date range
    mask = (df['review_date'].dt.date >= st.session_state.start_date) & (df['review_date'].dt.date <= st.session_state.end_date)
    filtered_df = df.loc[mask]
    st.session_state.filtered_df = filtered_df

    # Calculate and display platform statistics
    st.subheader("Review Statistics")
    
    # Get unique platforms in the filtered data
    platforms = filtered_df['platform'].unique()
    
    # Create columns for the statistics
    cols = st.columns(len(platforms) + 1)  # +1 for overall stats
    
    # Calculate and display stats for each platform
    platform_stats = {}
    for i, platform in enumerate(platforms):
        platform_df = filtered_df[filtered_df['platform'] == platform]
        avg_rating = platform_df['star_rating'].mean()
        review_count = len(platform_df)
        platform_stats[platform] = {'avg_rating': avg_rating, 'count': review_count}
        
        # Display platform stats with custom styling
        with cols[i]:
            st.markdown(f"### {platform}")
            st.markdown(f"<h2 style='margin: 0;'>{avg_rating:.1f} ⭐</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='color: #666; margin: 0;'>{review_count:,} Reviews</p>", unsafe_allow_html=True)
    
    # Calculate and display overall stats
    if platform_stats:
        overall_avg = sum(stat['avg_rating'] * stat['count'] for stat in platform_stats.values()) / sum(stat['count'] for stat in platform_stats.values())
        total_reviews = sum(stat['count'] for stat in platform_stats.values())
        
        # Display overall stats with custom styling
        with cols[-1]:
            st.markdown("### Overall")
            st.markdown(f"<h2 style='margin: 0;'>{overall_avg:.1f} ⭐</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='color: #666; margin: 0;'>{total_reviews:,} Reviews</p>", unsafe_allow_html=True)
    
    # Add a divider for visual separation
    st.divider()
    
    # Action buttons in a row
    col1, col2, col3 = st.columns(3)
    with col1:
        # Check date range only when generating summary
        date_range = st.session_state.end_date - st.session_state.start_date
        if date_range.days > 365:
            st.warning("Summary generation is limited to 1 year of reviews. Please adjust the date range to generate a summary.")
        if st.button("Generate Summary", use_container_width=True, disabled=date_range.days > 365):
            generate_summary(filtered_df, st.session_state.start_date, st.session_state.end_date, st.session_state.openai_api_key)
    with col2:
        if st.button("Report Review", use_container_width=True, disabled=date_range.days > 365):
            generate_report(filtered_df, st.session_state.start_date, st.session_state.end_date, st.session_state.openai_api_key)
    with col3:
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="reviews.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    # Display the filtered reviews
    st.subheader("Review Table")
    
    st.dataframe(
        filtered_df,
        hide_index=True,
        column_config={
            "review_text": st.column_config.TextColumn(
                "Review Text",
                width="large",
                help="Full review text",
            ),
            "review_date": st.column_config.DateColumn(
                "Review Date",
                format="YYYY-MM-DD",
            ),
            "star_rating": st.column_config.NumberColumn(
                "Rating",
                format="%.1f ⭐",
            ),
            "platform": st.column_config.TextColumn(
                "Platform",
                width="medium",
            ),
            "reviewer_name": st.column_config.TextColumn(
                "Reviewer",
                width="medium",
            ),
            "replied": st.column_config.CheckboxColumn(
                "Replied",
                width="small",
            ),
        },
        use_container_width=True,
    )
    
    # Display summary if available
    if st.session_state.summary:
        st.markdown("### 📊 Summary")
        st.markdown(st.session_state.summary)
    
    # Display report if available
    if st.session_state.report:
        st.markdown("### ⚠️ Review Violation Report")
        st.markdown(st.session_state.report)

    # Add reset button at the bottom
    if st.button("Reset and Load New Reviews", use_container_width=True):
        st.session_state.reviews_loaded = False
        st.session_state.reviews_df = None
        st.session_state.summary = None
        st.session_state.report = None
        st.session_state.filtered_df = None
        st.session_state.start_date = None
        st.session_state.end_date = None
        st.session_state.establishment_name = None
        st.rerun()