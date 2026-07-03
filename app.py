import streamlit as st
import edge_tts
import asyncio
import tempfile
import os
import re
import json
import uuid
import google.generativeai as genai
from dotenv import load_dotenv

# ============================================
# BASE PATH
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "tts_history.json")
AUDIO_FOLDER = os.path.join(BASE_DIR, "history_audio")

load_dotenv(os.path.join(BASE_DIR, ".env"))

# ============================================
# PAGE CONFIG
# ============================================
st.set_page_config(
    page_title="Agentic TTS Pro",
    page_icon="🤖",
    layout="wide"
)

st.markdown("""
<style>
    .main-header { font-size: 2.8rem; text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); border-radius: 15px; color: white !important; margin-bottom: 2rem; }
    .stButton > button { background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white !important; font-weight: bold; font-size: 1.1rem; padding: 0.75rem 2rem; border-radius: 25px; border: none; }
    .history-box { background-color: #f0f2f6 !important; padding: 10px !important; border-radius: 8px !important; margin-bottom: 5px !important; border-left: 5px solid #2a5298 !important; color: #1e293b !important; font-weight: 500 !important; }
    .agent-card { background: #e8f0fe; padding: 10px 16px; border-radius: 10px; border-left: 5px solid #2a5298; margin: 8px 0; }
    .delete-btn { color: #ef4444 !important; background: transparent !important; border: none !important; padding: 0 4px !important; font-size: 16px !important; }
    .delete-btn:hover { color: #dc2626 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🤖 Agentic TTS Pro</div>', unsafe_allow_html=True)

# ============================================
# SESSION STATE
# ============================================
if 'user_text' not in st.session_state:
    st.session_state.user_text = ""
if 'download_history' not in st.session_state:
    st.session_state.download_history = []
if 'last_params' not in st.session_state:
    st.session_state.last_params = None

# ============================================
# GEMINI SETUP
# ============================================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    st.error("⚠️ GOOGLE_API_KEY not found in .env file.")
    st.stop()

# ============================================
# PERSISTENT HISTORY
# ============================================
if not os.path.exists(AUDIO_FOLDER):
    os.makedirs(AUDIO_FOLDER, exist_ok=True)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # ✅ Ensure all entries have an 'id' field (for older versions)
                for item in data:
                    if isinstance(item, dict) and "id" not in item:
                        item["id"] = uuid.uuid4().hex
                return data
        except:
            return []
    return []

def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        return True
    except:
        return False

def save_audio_file(audio_bytes):
    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(AUDIO_FOLDER, filename)
    with open(filepath, "wb") as f:
        f.write(audio_bytes)
    return filepath

def delete_audio_file(filepath):
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except:
            pass

# Load history on startup
if 'download_history' in st.session_state and not st.session_state.download_history:
    st.session_state.download_history = load_history()
elif 'download_history' not in st.session_state:
    st.session_state.download_history = load_history()

# ============================================
# AGENTIC ENGINE (Gemini Analysis)
# ============================================
def analyze_text_with_gemini(text):
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"""Analyze the tone and emotion of the text provided.

Text: "{text}"

Return ONLY a valid JSON object with these keys:
- "emotion": one of ["happy", "sad", "angry", "neutral", "professional", "excited"]
- "speed": a float between 0.7 and 1.3
- "pitch": an integer between -30 and 30
- "reason": brief reason"""
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0]
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0]
        return json.loads(raw_text)
    except:
        return {"emotion": "neutral", "speed": 1.0, "pitch": 0, "reason": "Fallback"}

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.markdown("### ⚙️ AI Agent Settings")
    st.caption("🤖 Gemini analyzes text & sets speech parameters.")
    
    voice_options = {
        "🇺🇸 Jenny (US)": "en-US-JennyNeural",
        "🇺🇸 Guy (US)": "en-US-GuyNeural",
        "🇬🇧 Sonia (UK)": "en-GB-SoniaNeural",
        "🇮🇳 Neerja (India)": "en-IN-NeerjaNeural",
    }
    selected_voice = st.selectbox("🎤 Voice", options=list(voice_options.keys()), index=0)
    voice_id = voice_options[selected_voice]
    
    st.markdown("---")
    if st.button("🗑️ Clear All History", use_container_width=True):
        for item in st.session_state.download_history:
            if isinstance(item, dict) and item.get("file_path"):
                delete_audio_file(item["file_path"])
        st.session_state.download_history = []
        save_history([])
        st.rerun()

# ============================================
# MAIN UI
# ============================================
st.markdown("### 📝 Input Text")
user_text = st.text_area(
    "Write anything... AI will adjust the voice based on tone!",
    value=st.session_state.user_text,
    placeholder="e.g., 'Congratulations on your promotion!'",
    height=150,
    key="text_input_area"
)
st.session_state.user_text = user_text
char_count = len(user_text)
st.caption(f"Characters: {char_count} / 2000")

if st.session_state.last_params:
    params = st.session_state.last_params
    st.markdown(f"""
    <div class="agent-card">
        🤖 **Agent Decision:** Emotion: **{params['emotion']}** | 
        Speed: **{params['speed']}x** | 
        Pitch: **{params['pitch']}Hz** 
        <br><small>Reason: {params.get('reason', 'N/A')}</small>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    generate_btn = st.button("🤖 Generate with AI Agent", use_container_width=True)

# ============================================
# TTS ENGINE
# ============================================
async def generate_tts(text, voice, speed, pitch):
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'<[^>]+>', '', text).strip()
    if not text:
        text = "Please write some text."

    rate_percentage = int((speed - 1.0) * 100)
    rate_str = f"{'+' if rate_percentage >= 0 else ''}{rate_percentage}%"
    pitch_str = f"{'+' if pitch >= 0 else ''}{pitch}Hz"

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate_str, pitch=pitch_str)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    await communicate.save(temp_file.name)
    return temp_file.name

# ============================================
# EXECUTION
# ============================================
if generate_btn:
    if not user_text.strip():
        st.error("❌ Please enter some text first!")
    elif char_count > 2000:
        st.error("⚠️ Text exceeds 2000 characters limit!")
    else:
        with st.spinner("🧠 AI Agent is thinking..."):
            try:
                params = analyze_text_with_gemini(user_text)
                st.session_state.last_params = params
                
                emotion = params.get("emotion", "neutral")
                speed = float(params.get("speed", 1.0))
                pitch = int(params.get("pitch", 0))
                
                st.info(f"🤖 AI Detected: **{emotion.upper()}** tone")
                
                with st.spinner("🎙️ Generating Speech..."):
                    temp_path = asyncio.run(generate_tts(user_text, voice_id, speed, pitch))
                    
                    if temp_path and os.path.exists(temp_path):
                        with open(temp_path, "rb") as f:
                            audio_bytes = f.read()
                        
                        saved_path = save_audio_file(audio_bytes)
                        
                        preview = user_text[:60] + "..." if len(user_text) > 60 else user_text
                        entry_id = uuid.uuid4().hex  # 🔥 Unique ID for this entry
                        history_entry = {
                            "id": entry_id,
                            "text": preview,
                            "file_path": saved_path,
                            "emotion": emotion,
                            "speed": speed,
                            "pitch": pitch
                        }
                        st.session_state.download_history.append(history_entry)
                        save_history(st.session_state.download_history)

                        st.success("✅ Speech generated successfully!")
                        st.markdown("#### 🔊 Audio Player")
                        st.audio(audio_bytes, format="audio/mp3")

                        st.download_button(
                            label="📥 Download MP3",
                            data=audio_bytes,
                            file_name="ai_speech.mp3",
                            mime="audio/mpeg",
                            use_container_width=True
                        )

                        os.remove(temp_path)
                        
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# ============================================
# 🔥 HISTORY DISPLAY (with Individual Delete)
# ============================================
if st.session_state.download_history:
    st.markdown("---")
    st.markdown(f"### 📜 Recent Conversions ({len(st.session_state.download_history)})")

    # Show last 10 items (newest first)
    for item in reversed(st.session_state.download_history[-10:]):
        if isinstance(item, str):
            text = item
            file_path = None
            entry_id = None
        else:
            text = item.get("text", "Unknown")
            file_path = item.get("file_path")
            emotion = item.get("emotion", "N/A")
            entry_id = item.get("id")

        # Display text box
        st.markdown(f"<div class='history-box'>🤖 {emotion.upper()} - {text}</div>", unsafe_allow_html=True)
        
        # Row: Audio Player | Download | Delete
        if file_path and os.path.exists(file_path):
            col1, col2, col3 = st.columns([2.5, 1, 0.6])
            with col1:
                st.audio(file_path, format="audio/mp3")
            with col2:
                with open(file_path, "rb") as f:
                    audio_bytes = f.read()
                st.download_button(
                    label="📥 Download",
                    data=audio_bytes,
                    file_name=f"history_audio.mp3",
                    mime="audio/mpeg",
                    key=f"dl_{entry_id}"
                )
            with col3:
                # 🔥 INDIVIDUAL DELETE BUTTON
                if st.button("❌", key=f"del_{entry_id}", help="Delete this entry"):
                    # Delete audio file
                    delete_audio_file(file_path)
                    # Remove from session state
                    st.session_state.download_history = [
                        h for h in st.session_state.download_history 
                        if h.get("id") != entry_id
                    ]
                    # Save to JSON
                    save_history(st.session_state.download_history)
                    st.rerun()
        else:
            st.caption("🔊 Audio file not found.")
            # Delete button even if file missing
            if entry_id:
                if st.button("❌", key=f"del_missing_{entry_id}"):
                    st.session_state.download_history = [
                        h for h in st.session_state.download_history 
                        if h.get("id") != entry_id
                    ]
                    save_history(st.session_state.download_history)
                    st.rerun()
        
        st.markdown("---")

else:
    st.markdown("---")
    st.info("ℹ️ No conversions yet. Generate some speech to see history here!")

st.caption("🤖 Agentic TTS Pro | Gemini + Edge TTS")