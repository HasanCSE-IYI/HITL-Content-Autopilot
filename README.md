# 🛒 HITL Content Autopilot (Amazon Affiliate)

An end-to-end, **Human-In-The-Loop (HITL) Content Generation & Publishing Autopilot** specifically engineered for Amazon Affiliate niche website owners.

It automates the heavy lifting—product data extraction, feature comparison, SEO drafting, pros/cons breakdown, FTC compliance, and schema generation—while giving you full editorial control through an interactive Python Streamlit dashboard before one-click publishing to WordPress.

---

## 🌟 Key Features

- **Hybrid Amazon Product Sourcing**:
  - Automatically extracts product title, pricing, specs, images, ratings, and customer reviews from any Amazon URL or ASIN.
  - Supports **Smart Scraper fallback** (no PA-API approval required) + optional **Amazon PA-API 5.0** for high-volume accounts.
- **AI Content Generation (Google Gemini)**:
  - **Roundups**: "Top X Best [Keyword] in 2026: Tested & Reviewed" with comparison tables and quick picks.
  - **Single Reviews**: Deep-dive product testing breakdown, who it's for, and score rating.
  - **Comparisons**: Head-to-head "Product A vs Product B" category showdown.
- **FTC & Amazon Associates Compliance**:
  - Automatically prepends mandatory FTC Affiliate Disclosure banner at the top of every post.
  - Injects `rel="nofollow sponsored"` and `target="_blank"` on all affiliate links.
  - Displays dynamic Amazon price and availability disclaimer.
- **Google Rich Results Schema**:
  - Generates valid `schema.org` JSON-LD markup for `ItemList`, `Product`, and `FAQPage` for star ratings in Google SERP.
- **HITL Streamlit Review Dashboard**:
  - Review drafts side-by-side with product data & live previews.
  - Markdown editor with instant live preview.
  - **AI Section Regenerator**: refine, expand, or adjust tone of specific sections using Gemini.
- **WordPress REST API Publishing**:
  - Direct 1-click publishing or drafting using WordPress Application Passwords.
  - Automatically uploads product hero images to the WP Media Library and sets as Featured Image.
  - Automatically maps SEO titles and descriptions to Yoast SEO and Rank Math.

---

## 🚀 Quick Start Guide

### 1. Installation
Clone the repository and install requirements:
```powershell
pip install -r requirements.txt
```

### 2. Configure Credentials
Copy `.env.example` to `.env` or configure directly inside the dashboard's **Settings** tab:
```powershell
cp .env.example .env
```
Key settings:
- `GEMINI_API_KEY`: Get your key from [Google AI Studio](https://aistudio.google.com/).
- `AMAZON_ASSOCIATE_TAG`: Your Amazon Associates tag (e.g., `mysite-20`).
- `WORDPRESS_URL`, `WORDPRESS_USERNAME`, `WORDPRESS_APP_PASSWORD`: For 1-click publishing.

### 3. Launch the Dashboard
```powershell
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 🛠️ Project Structure

```
HITL-Content-Autopilot/
├── app.py                      # Streamlit application entrypoint
├── core/
│   ├── config.py               # Environment configuration
│   ├── models.py               # Pydantic models (Product, Draft, Status)
│   └── database.py             # SQLite persistence layer
├── services/
│   ├── amazon/
│   │   ├── parser.py           # ASIN extractor & affiliate link builder
│   │   ├── scraper.py          # Smart scraper for Amazon product pages
│   │   ├── paapi.py            # Amazon PA-API 5.0 client
│   │   └── extractor.py        # Hybrid data sourcing router
│   ├── generator/
│   │   ├── gemini_client.py    # Google Gemini API connector
│   │   ├── prompts.py          # High-converting affiliate templates
│   │   ├── roundup.py          # 'Best X' roundup generator
│   │   ├── review.py           # Single product review generator
│   │   ├── comparison.py       # 'Product A vs Product B' generator
│   │   └── schema.py           # JSON-LD Schema markup generator
│   ├── compliance/
│   │   └── rules.py            # FTC & Amazon Operating Agreement rules
│   └── publisher/
│       └── wordpress.py        # WordPress REST API publisher
├── ui/
│   ├── tab_generate.py         # Article generation interface
│   ├── tab_review.py           # HITL review queue & editor
│   ├── tab_publish.py          # WordPress publisher & history
│   └── tab_settings.py         # Credentials & configuration
├── tests/                      # Automated test suite
└── requirements.txt
```

---

## 🧪 Running Tests
```powershell
pytest
```
