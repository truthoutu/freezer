# Deployment Guide - The Harvester

## Quick Start

1. Clone the repository
2. Install dependencies: pip install -r requirements.txt
3. Copy .env.example to .env and add your API keys
4. Run: python server.py
5. Open http://localhost:5000

## Environment Variables

Required in .env file or deployment platform:

- FIRECRAWL_API_KEY - Get from https://firecrawl.dev
- CEREBRAS_API_KEY - Get from https://cerebras.ai
- GROQ_API_KEY - Get from https://console.groq.com
- PORT - Server port (default: 5000)

## Deploy to Render.com

1. Push code to GitHub
2. Connect repository to Render
3. Set environment variables in Render dashboard
4. Deploy

## Deploy to Other Platforms

Works on any platform that supports Python/Flask:
- Heroku
- Railway
- Fly.io
- DigitalOcean App Platform
- AWS/GCP/Azure

## Build Rust Binary (Optional)

For the fallback crawler:
- Install Rust: https://rustup.rs/
- Run: cargo build --release
- Binary will be at: target/release/harvester.exe (Windows) or harvester (Linux/Mac)

## API Usage

POST /api/harvest
{
    "country": "United States",
    "occupation": "Nurse",
    "gender": "Female",
    "limit": 20,
    "custom_urls": ["https://example.com"]
}

## Troubleshooting

503 Error: Check Firecrawl API key and credits
No contacts found: Try different filters or check target URLs
Slow response: Normal - takes 10-30 seconds for AI extraction
