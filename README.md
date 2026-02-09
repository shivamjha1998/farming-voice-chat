# Streaming AI Voice Chat (Farming Support)

A low-latency, voice-to-voice AI support line for farmers using Twilio Media Streams and Google Gemini API.

## 🎯 Features
- **Real-time Voice**: Sub-second latency voice conversations
- **Telephony Integration**: Standard phone calls via Twilio
- **Farming Expert Persona**: System prompt tailored for agricultural advice
- **Bidirectional Streaming**: Bridges Twilio (μ-law 8kHz) and AI APIs (PCM16 16/24kHz)
- **API**: Gemini 2.5 Flash Native Audio Preview API

## 📋 Requirements
- Python 3.9+
- Twilio Account (Phone Number + Voice capabilities)
- **Either** Gemini API Key OR OpenAI API Key
- `ngrok` (for local development tunneling)

## 🚀 Setup

### 1. Installation

```bash
# Clone or download the repository
cd git@github.com:shivamjha1998/farming-voice-chat.git

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the root directory:

**Option A: Using Gemini (Recommended)**
```env
GEMINI_API_KEY=your-gemini-api-key-here
PORT=5050
```

### 3. Get API Keys

**Gemini API:**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Ensure you have access to Gemini 2.0 models

## 🎮 Usage

### Start the Server

**Using Gemini:**
```bash
python main.py
```

The server will start on port `5050` and display:
```
Starting server on port 5050...
Gemini API Key present: True
INFO:     Started server process
```

### Connect to Twilio

1. **Expose your local server**:
   ```bash
   ngrok http 5050
   ```
   Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

2. **Configure Twilio Webhook**:
   - Go to [Twilio Console](https://console.twilio.com/) → Phone Numbers → Active Numbers
   - Click on your phone number
   - Under **Voice & Fax** → **A Call Comes In**:
     - Select **Webhook**
     - URL: `https://abc123.ngrok-free.app/incoming-call`
     - Method: **POST**
   - Click **Save**

3. **Test**: 
   - Call your Twilio phone number
   - You should hear: "Hello. Connecting you to the farming expert system."
   - After a brief pause, start speaking!
   - Example: "Can you help me with crop diseases?"

## 🔍 Troubleshooting

### Problem: No audio response after greeting

**Check server logs** - You should see:
```
✓ Connected to Gemini API
✓ Sent initial setup to Gemini
✓ Gemini setup complete
✓ Twilio stream started: MZ123...
```

**If you see errors:**

1. **"ERROR: GEMINI_API_KEY not found"**
   - Check your `.env` file exists
   - Verify the key is spelled correctly

2. **"ERROR: Failed to connect to Gemini API - 401"**
   - API key is invalid
   - API key doesn't have access to Gemini 2.0

3. **"WARNING: No stream_sid available yet"**
   - Timing issue (usually resolves itself)
   - If persistent, restart the server

### Problem: Garbled or robotic audio

**Cause:** Audio format conversion issue

**Fix:** The code handles conversions automatically. If problems persist:
- Check your internet connection (packet loss causes distortion)

### Problem: Delayed responses (>3 seconds)

**Solutions:**
- Use `gemini-2.5-flash-exp` (fastest Gemini model)
- Check network latency to API servers
- Ensure server has sufficient resources

### Problem: Connection drops mid-call

**Check:**
- ngrok tunnel is still active
- Server didn't crash (check terminal)
- Twilio account has sufficient credits

## 📁 File Structure

```
.
├── main.py              # Gemini version (recommended)
├── requirements.txt     # Python dependencies
├── .env                 # Your API keys (create this)
├── .gitignore          # Git ignore rules
├── README.md           # This file
```

## 🎤 Audio Pipeline

### Input (Caller → AI):
1. Caller speaks → Twilio receives audio (μ-law, 8kHz)
2. Server receives base64 μ-law
3. Convert μ-law → PCM16
4. Resample 8kHz → 16kHz (Gemini) or 24kHz (OpenAI)
5. Send to AI API

### Output (AI → Caller):
1. AI generates audio (PCM16, 24kHz)
2. Server receives base64 PCM16
3. Resample 24kHz → 8kHz
4. Convert PCM16 → μ-law
5. Send to Twilio → Caller hears response

## 🛠️ Advanced Configuration

### Change AI Voice

**Gemini** (`main.py` line 113):
```python
"voice_name": "Puck"  # Options: Puck, Charon, Kore, Fenrir, Aoede
```

### Customize System Prompt

Edit `SYSTEM_MESSAGE` in either file (lines 16-22):
```python
SYSTEM_MESSAGE = (
    "You are a helpful farming assistant specializing in..."
)
```

### Adjust Response Temperature

**Gemini:** Add to `generation_config` in `main.py`:
```python
"temperature": 0.8,  # 0.0-1.0 (higher = more creative)
```

## 🐛 Debug Mode

Enable verbose logging:

```bash
# Run with full debug output
python main.py 2>&1 | tee server.log
```

This saves all output to `server.log` for analysis.

## 📚 Additional Resources

- [Gemini API Documentation](https://ai.google.dev/docs)
- [OpenAI Realtime API Guide](https://platform.openai.com/docs/guides/realtime)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/twiml/stream)
- [Full Troubleshooting Guide](TROUBLESHOOTING.md)

## ⚠️ Common Pitfalls

1. **Don't commit `.env` file** - It contains your API keys!
2. **ngrok URL changes** - Update Twilio webhook when restarting ngrok
3. **API quotas** - Monitor your usage to avoid hitting limits
4. **Model availability** - Some models may not be available in all regions

## 📞 Testing Commands

```bash
# Test server is running
curl http://localhost:5050/

# Test Twilio webhook
curl -X POST http://localhost:5050/incoming-call

# Check what's listening on port 5050
lsof -i :5050
```

## 🤝 Getting Help

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed debugging
2. Review server logs carefully
3. Test API keys work independently of this code

## 📝 License

This project is for educational and development purposes.

---

**Last Updated:** February 2026
**Tested With:** Python 3.11, Gemini 2.5 Flash Native Audio Preview.