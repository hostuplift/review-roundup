# Review Analysis App

A Streamlit application for analyzing and managing reviews from multiple platforms.

## Features
- Load reviews from multiple platforms (Google, TripAdvisor)
- Generate AI-powered summaries of reviews
- Identify reviews that violate platform policies
- Filter reviews by date range
- Export reviews to CSV

## Deployment Instructions

1. Create a Streamlit Cloud account at https://streamlit.io/cloud
2. Connect your GitHub repository
3. Deploy the app with the following secrets:
   - `APIFY_API_TOKEN`: Your Apify API token
   - `OPENAI_API_KEY`: Your OpenAI API key

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the app:
```bash
streamlit run app.py
```

## Environment Variables
- `APIFY_API_TOKEN`: Required for fetching reviews from Apify
- `OPENAI_API_KEY`: Required for AI-powered analysis 