<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/drive/1_SC4W7eLEp6CGClc0739-752fqZ2TTG-

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`



Flask API Created: api/script_generator.py
Endpoints:

POST /api/generate-script - Generate video scripts (~$0.02/call)
POST /api/transcribe-video - On-demand transcription (~$0.10/call)
POST /api/analyze-video - Deep content analysis (included)
POST /api/generate-audio - Text-to-speech (placeholder for TTS)
How to Run:

# Install dependencies
pip install -r requirements-api.txt

# Start server
python3 api/script_generator.py
# Runs on http://localhost:5000