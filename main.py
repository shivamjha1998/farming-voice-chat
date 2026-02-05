import os
import json
import base64
import audioop
import uvicorn
import websockets
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

PORT = int(os.getenv("PORT", 5050))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SYSTEM_MESSAGE = (
    "You are a helpful and knowledgeable farming assistant. "
    "You speak with a warm, encouraging tone. "
    "Expertise: Crop disease diagnosis, irrigation planning, pest control, and market prices. "
    "Keep responses concise and suitable for a voice conversation. "
    "Avoid using markdown or special formatting in your output."
)

@app.get("/", response_class=HTMLResponse)
async def index_page():
    return "Farming Voice Chat Realtime Server is running!"

@app.post("/incoming-call")
async def handle_incoming_call(request: Request):
    """Handle incoming calls from Twilio."""
    response = VoiceResponse()
    response.say("Hello. Connecting you to the farming expert system.")
    response.pause(length=1)
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connection for media streaming."""
    print("Client connected")
    await websocket.accept()

    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        await send_session_update(openai_ws)
        
        stream_sid = None
        
        async def receive_from_twilio():
            nonlocal stream_sid
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data["event"] == "media":
                        # 1. Receive Twilio Audio (base64 mulaw 8000Hz)
                        audio_chunk = base64.b64decode(data["media"]["payload"])
                        
                        # 2. Convert default u-law to PCM16
                        pcm_8k = audioop.ulaw2lin(audio_chunk, 2)
                        
                        # 3. Resample 8k -> 24k using linear interpolation
                        # ratecv(fragment, width, nchannels, inrate, outrate, state)
                        pcm_24k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 24000, None)
                        
                        # 4. Send to OpenAI
                        await openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(pcm_24k).decode("utf-8")
                        }))
                        
                    elif data["event"] == "start":
                        stream_sid = data["start"]["streamSid"]
                        print(f"Stream started: {stream_sid}")
                        
            except Exception as e:
                print(f"Error receiving from Twilio: {e}")

        async def receive_from_openai():
            try:
                async for message in openai_ws:
                    data = json.loads(message)
                    if data["type"] == "response.audio.delta":
                        # 1. Receive OpenAI Audio (base64 PCM16 24000Hz)
                        audio_chunk = base64.b64decode(data["delta"])
                        
                        # 2. Resample 24k -> 8k
                        pcm_8k, _ = audioop.ratecv(audio_chunk, 2, 1, 24000, 8000, None)
                        
                        # 3. Convert PCM16 to u-law
                        ulaw_chunk = audioop.lin2ulaw(pcm_8k, 2)
                        
                        # 4. Send to Twilio
                        if stream_sid:
                            await websocket.send_json({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": base64.b64encode(ulaw_chunk).decode("utf-8")
                                }
                            })
                    
                    elif data["type"] == "response.audio.done":
                        pass
                        
            except Exception as e:
                print(f"Error receiving from OpenAI: {e}")

        # Run both tasks concurrently
        import asyncio
        await asyncio.gather(receive_from_twilio(), receive_from_openai())

async def send_session_update(openai_ws):
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "voice": "alloy",
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
        }
    }
    await openai_ws.send(json.dumps(session_update))
