import os
import json
import base64
import audioop
import asyncio
import uvicorn
import websockets
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

PORT = int(os.getenv("PORT", 5050))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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
    print("=" * 50)
    print("Client connected to /media-stream")
    await websocket.accept()

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not found in .env file")
        await websocket.close()
        return

    # Gemini Live API WebSocket URL
    url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"
    
    print(f"Connecting to Gemini Live API...")

    try:
        async with websockets.connect(
            url,
            additional_headers={"Content-Type": "application/json"},
            ping_interval=20,
            ping_timeout=20
        ) as gemini_ws:
            print("✓ Connected to Gemini Live API")
            await send_initial_setup(gemini_ws)
            
            # Send initial text to trigger a response (Testing Audio)
            print("Sending initial greeting request...")
            await gemini_ws.send(json.dumps({
                "clientContent": {
                    "turns": [{
                        "role": "user",
                        "parts": [{ "text": "Hello, please introduce yourself briefly to verify audio is working." }]
                    }],
                    "turnComplete": True
                }
            }))
            print("✓ Initial greeting request sent")
            
            stream_sid = None
            input_chunks_count = 0
            
            async def receive_from_twilio():
                nonlocal stream_sid, input_chunks_count
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        
                        if data["event"] == "media":
                            # 1. Receive Twilio Audio (base64 mulaw 8000Hz)
                            audio_chunk = base64.b64decode(data["media"]["payload"])
                            
                            # 2. Convert u-law to PCM16
                            pcm_8k = audioop.ulaw2lin(audio_chunk, 2)
                            
                            # Calculate RMS (volume/energy)
                            rms = audioop.rms(pcm_8k, 2)
                            if rms > 1000:  # Threshold for "sound"
                                print(f"🔊 Input energy: {rms}")
                            
                            # 3. Resample 8k -> 16k (Gemini Live API uses 16kHz input)
                            pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
                            
                            # 4. Send to Gemini with correct camelCase keys
                            msg = {
                                "realtimeInput": {
                                    "mediaChunks": [{
                                        "mimeType": "audio/pcm;rate=16000",
                                        "data": base64.b64encode(pcm_16k).decode("utf-8")
                                    }]
                                }
                            }
                            await gemini_ws.send(json.dumps(msg))
                            
                            input_chunks_count += 1
                            # if input_chunks_count % 50 == 0:
                            #    print(f"🎤 Sent {input_chunks_count} chunks to Gemini")
                            
                        elif data["event"] == "start":
                            stream_sid = data["start"]["streamSid"]
                            print(f"✓ Twilio stream started: {stream_sid}")
                        
                        elif data["event"] == "stop":
                            print("Twilio stream stopped")
                            break
                        
                        elif data["event"] == "mark":
                            pass
                        else:
                            print(f"Twilio event: {data['event']}")
                            
                except websockets.exceptions.ConnectionClosed:
                    print("Twilio WebSocket closed")
                except Exception as e:
                    print(f"ERROR in receive_from_twilio: {e}")
                    import traceback
                    traceback.print_exc()

            async def receive_from_gemini():
                nonlocal stream_sid
                try:
                    async for message in gemini_ws:
                        data = json.loads(message)
                        
                        # Log message type
                        msg_type = list(data.keys())[0] if data else "unknown"
                        
                        # Handle setup completion
                        if "setupComplete" in data:
                            print("✓ Gemini setup complete - ready for audio!")
                            continue
                        
                        # Handle server content
                        if "serverContent" in data:
                            server_content = data["serverContent"]
                            
                            # Check if there's a model turn
                            if "modelTurn" in server_content:
                                model_turn = server_content["modelTurn"]
                                parts = model_turn.get("parts", [])
                                
                                print(f"🎙️ Model turn with {len(parts)} parts")
                                
                                for part in parts:
                                    # Handle audio data
                                    if "inlineData" in part:
                                        inline_data = part["inlineData"]
                                        mime_type = inline_data.get("mimeType", "")
                                        
                                        print(f"🔊 Receiving audio: {mime_type}")
                                        
                                        # Decode audio
                                        audio_data = base64.b64decode(inline_data["data"])
                                        
                                        # Gemini outputs PCM16 at 24kHz
                                        # Resample to 8kHz for Twilio
                                        pcm_8k, _ = audioop.ratecv(audio_data, 2, 1, 24000, 8000, None)
                                        
                                        # Convert to u-law
                                        ulaw_chunk = audioop.lin2ulaw(pcm_8k, 2)
                                        
                                        # Send to Twilio
                                        if stream_sid:
                                            await websocket.send_json({
                                                "event": "media",
                                                "streamSid": stream_sid,
                                                "media": {
                                                    "payload": base64.b64encode(ulaw_chunk).decode("utf-8")
                                                }
                                            })
                                            print("✓ Audio sent to caller")
                                        else:
                                            print("⚠️  No stream_sid yet")
                                    
                                    # Handle text (for debugging)
                                    elif "text" in part:
                                        print(f"💬 Gemini: {part['text'][:100]}...")
                            
                            # Check for turn complete
                            if "turnComplete" in server_content:
                                print("✓ Turn complete")
                        
                        # Handle tool calls
                        elif "toolCall" in data:
                            print(f"🔧 Tool call: {data['toolCall']}")
                        
                        # Handle errors
                        elif "error" in data:
                            error = data["error"]
                            print(f"❌ Gemini error: {error}")
                        
                        # Handle other messages
                        else:
                            if msg_type not in ["setupComplete"]:
                                print(f"📨 {msg_type}")
                            
                except websockets.exceptions.ConnectionClosedError as e:
                    print(f"❌ Gemini WebSocket closed with error: {e}")
                except websockets.exceptions.ConnectionClosed:
                    print("Gemini WebSocket closed normally")
                except Exception as e:
                    print(f"❌ ERROR in receive_from_gemini: {e}")
                    import traceback
                    traceback.print_exc()

            # Run both tasks concurrently
            print("🚀 Starting bidirectional streaming...")
            await asyncio.gather(
                receive_from_twilio(), 
                receive_from_gemini(),
                return_exceptions=True
            )
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Failed to connect to Gemini API: {e}")
        print("Check: 1) API key is valid, 2) Has Gemini API access")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Client disconnected")
        print("=" * 50)

async def send_initial_setup(gemini_ws):
    """Configure the Gemini Live API session."""
    setup_msg = {
        "setup": {
            "model": "models/gemini-2.5-flash-native-audio-preview-12-2025",
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": "Puck"
                        }
                    }
                }
            },
            "systemInstruction": {
                "parts": [{
                    "text": SYSTEM_MESSAGE
                }]
            }
        }
    }
    
    print(f"📤 Sending setup config...")
    await gemini_ws.send(json.dumps(setup_msg))
    print("✓ Setup config sent, waiting for confirmation...")
    
    # Wait for setup response
    try:
        response = await asyncio.wait_for(gemini_ws.recv(), timeout=10.0)
        response_data = json.loads(response)
        
        if "setupComplete" in response_data:
            print("✓ Setup confirmed by Gemini!")
        elif "error" in response_data:
            print(f"❌ Setup error: {response_data['error']}")
        else:
            print(f"⚠️  Unexpected setup response: {list(response_data.keys())}")
    except asyncio.TimeoutError:
        print("⚠️  Setup response timeout - but continuing anyway")
    except Exception as e:
        print(f"⚠️  Setup response error: {e}")

if __name__ == "__main__":
    print(f"Starting server on port {PORT}...")
    print(f"Gemini API Key present: {bool(GEMINI_API_KEY)}")
    print(f"Model: gemini-2.5-flash-native-audio-preview-12-2025")
    uvicorn.run(app, host="0.0.0.0", port=PORT)