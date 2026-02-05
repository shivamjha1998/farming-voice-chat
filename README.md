# Streaming AI Voice Chat (Farming Support)

A low-latency, voice-to-voice AI support line for farmers using Twilio Media Streams and OpenAI Realtime API.

## Features
- **Real-time Voice**: Uses OpenAI's Realtime API for sub-second latency.
- **Telephony Integration**: Connects via standard phone calls using Twilio.
- **Farming Expert Persona**: System prompt tailored for agricultural advice.
- **Bidirectional Streaming**: Bridges Twilio (Mulaw 8kHz) and OpenAI (PCM16 24kHz) via WebSockets.

## Requirements
- Python 3.9+
- Twilio Account (Phone Number + Voice capabilities)
- OpenAI API Key (needs access to `gpt-4o-realtime-preview`)
- `ngrok` (for local development tunneling)

## Setup

### 1. Installation

Clone the repository and install dependencies:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=sk-proj-your-key-here
PORT=5050
```

### 3. Usage

Start the server:

```bash
python main.py
```
The server will start on port `5050`.

### 4. Connect to Twilio

1.  **Expose your local server**:
    ```bash
    ngrok http 5050
    ```
2.  **Configure Twilio Webhook**:
    -   Go to Twilio Console -> Active Numbers.
    -   Under **Voice & Fax** -> **A Call Comes In**:
        -   Select **Webhook**.
        -   URL: `https://<your-ngrok-subdomain>.ngrok-free.app/incoming-call`
        -   Method: **POST**
    -   Save.

3.  **Test**: Call your Twilio phone number. You should be connected to the AI Farming Assistant.
