# Render.com Deployment Setup

## Step 1: Set Environment Variables

In your Render.com dashboard, go to your service and add these environment variables:

### Required API Keys:
- FIRECRAWL_API_KEY - Get from https://firecrawl.dev
- CEREBRAS_API_KEY - Get from https://cerebras.ai
- GROQ_API_KEY - Get from https://console.groq.com

### System Variables:
- PYTHONUNBUFFERED=1

## Step 2: Deploy

Push to GitHub and Render will automatically rebuild.

## Step 3: Test

Visit your Render URL and test the harvest endpoint.

## Troubleshooting 503 Errors:

1. Check Render logs for missing API keys
2. Verify all environment variables are set
3. Ensure Firecrawl account has credits
4. Check that server.py uses PORT env var (already fixed)
