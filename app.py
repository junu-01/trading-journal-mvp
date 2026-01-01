import streamlit as st
from datetime import datetime, timedelta, timezone
import pandas as pd
import plotly.express as px
import openai
import os
import streamlit.components.v1 as components
import base64
import ast
from PIL import Image
import io
from supabase import create_client, Client

# --- 0. Constants & Config ---
COLOR_WIN = '#FF4B4B'
COLOR_LOSS = '#4C78A8'
COLOR_BE = '#808080'
COLOR_PROFIT = '#2E7D32'

st.set_page_config(page_title="Trading Dashboard", layout="wide")

# --- 1. Timezone Setup (KST) ---
# FIX: Define KST explicitly to prevent UTC server issues
KST = timezone(timedelta(hours=9))


# --- [UI Upgrade] Custom CSS Injection ---
def step1_css():
    st.markdown("""
    <style>
        /* 1. Font & Basics */
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600&display=swap');
        
        /* 2. Progress Bar */
        .step-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: relative;
            max-width: 400px;
            margin: 0 auto 30px auto;
        }
        .step-line {
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 2px;
            background: #E0E0E0;
            z-index: 0;
            transform: translateY(-50%);
        }
        .step-circle {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: #F0F2F6;
            color: #B0B0B0;
            display: flex;
            justify-content: center;
            align-items: center;
            font-weight: bold;
            font-family: 'Inter', sans-serif;
            z-index: 1;
            border: 2px solid #fff;
        }
        .step-circle.active {
            background: #8B5CF6; /* Purple */
            color: white;
            box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.2);
        }

        /* 3. Card Headers */
        .input-header {
            font-size: 14px;
            font-weight: 600;
            color: #555;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .input-header-icon {
            font-size: 16px;
        }

        /* 4. Mood Grid Selector (Modified to FIX empty box issue) */
        div[role="radiogroup"] {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }
        div[role="radiogroup"] label {
            background: white;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 10px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            display: flex; /* Flexbox to center content */
            flex-direction: column;
            justify-content: center; 
            align-items: center;
            height: 80px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        /* Hover Effect */
        div[role="radiogroup"] label:hover {
            border-color: #8B5CF6;
            background: #F5F3FF;
        }
        /* Selected State */
        div[role="radiogroup"] label[data-checked="true"] {
            background: #F5F3FF;
            border: 2px solid #8B5CF6;
            color: #8B5CF6;
            font-weight: bold;
        }
        
        /* [CRITICAL FIX] Ensure text inside radio button is visible and dark */
        div[role="radiogroup"] label p {
            color: #333 !important;
            font-weight: 600;
            margin: 0;
        }
        div[role="radiogroup"] label[data-checked="true"] p {
            color: #8B5CF6 !important;
        }

        /* 5. Submit Button (Purple, Wide) */
        div.stButton > button {
            width: 100%;
            background-color: #8B5CF6;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: bold;
            transition: background 0.3s;
        }
        div.stButton > button:hover {
            background-color: #7C3AED;
            color: white;
        }
        div.stButton > button:active {
            background-color: #6D28D9;
        }
        
        /* Secondary Button (Analytics) styling */
        button[kind="secondary"] {
            background-color: transparent;
            border: 1px solid #ccc;
            color: #555;
        }
        
    </style>
    """, unsafe_allow_html=True)

def step2_css():
    st.markdown("""
    <style>
        /* Re-use basic fonts */
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600&display=swap');
        
        /* --- STEP INDICATOR (Fix: Ensure Visibility) --- */
        .step-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: relative;
            max-width: 400px;
            margin: 0 auto 30px auto;
        }
        .step-line {
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 2px;
            background: #E0E0E0;
            z-index: 0;
            transform: translateY(-50%);
        }
        .step-circle {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: #F0F2F6;
            color: #B0B0B0 !important; /* Force grey for inactive */
            display: flex;
            justify-content: center;
            align-items: center;
            font-weight: bold;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            z-index: 2; /* Ensure above line */
            border: 2px solid #fff;
            position: relative;
        }
        .step-circle.active {
            background: #8B5CF6; /* Purple */
            color: white !important; /* Force white for active */
            box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.2);
        }
        
        /* --- TIMER CARD (Dark Blue) --- */
        .timer-card {
            background-color: #1E293B; /* Slate 800 */
            border-radius: 16px;
            padding: 30px;
            text-align: center;
            color: white;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            margin-bottom: 20px;
            position: relative;
        }
        .live-badge {
            position: absolute;
            top: 20px;
            left: 20px;
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            color: #4ADE80; /* Green 400 */
            font-weight: bold;
            background: rgba(255,255,255,0.05);
            padding: 4px 8px;
            border-radius: 20px;
        }
        .live-dot {
            width: 8px;
            height: 8px;
            background-color: #4ADE80;
            border-radius: 50%;
            box-shadow: 0 0 8px #4ADE80;
        }
        .timer-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 48px;
            font-weight: 700;
            margin: 10px 0;
            letter-spacing: 2px;
        }
        .timer-sub {
            color: #94A3B8; /* Slate 400 */
            font-size: 14px;
        }
        
        /* --- STRATEGY CARD --- */
        /* Use container(border=True) but add internal styles */
        .strat-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #F0F0F0;
        }
        .strat-badge {
            background-color: #F3E8FF; /* Purple 100 */
            color: #7C3AED; /* Purple 600 */
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }
        .strat-title {
            font-weight: 600;
            color: #333;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        /* --- WARNING BOX --- */
        .warning-box {
            background-color: #FFFBEB; /* Amber 50 */
            border: 1px solid #FCD34D; /* Amber 300 */
            color: #B45309; /* Amber 700 */
            padding: 12px;
            border-radius: 8px;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 15px;
        }
        
        /* --- MEMO CHAT --- */
        .memo-chat-container {
            max-height: 300px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
            padding: 10px;
        }
        .memo-bubble {
            background-color: #F1F5F9; /* Slate 100 */
            border-radius: 12px;
            padding: 10px 14px;
            font-size: 14px;
            color: #334155;
            align-self: flex-start;
            max-width: 90%;
            border-bottom-left-radius: 2px;
        }
        .memo-time {
            font-size: 11px;
            color: #94A3B8;
            margin-bottom: 2px;
            display: block;
        }
        
        /* --- BUTTONS --- */
        /* Red 'End Trade' Button Override */
        /* We can't easily target just one button by CSS unless we use type="primary" and override primary. 
           Or use unique keys if Streamlit exposed classes. 
           We will use type="heading" or similar trick, OR just override Primary to Red for TRADING stage?
           But 'Back' is secondary. 
           Let's style div.stButton > button based on context if possible, or just accept red global if valid.
           Actually, we can use the 'End Trade' button's specific position? No.
           Solution: Use type="primary" for End Trade and override primary color LOCALLY here. */
        
        div[data-testid="stButton"] button[kind="primary"] {
            background-color: #EF4444; /* Red 500 */
            border-color: #EF4444;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover {
            background-color: #DC2626; /* Red 600 */
            border-color: #DC2626;
        }
        
    </style>
    """, unsafe_allow_html=True)

def step3_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600&display=swap');
        
        /* 1. Step Indicator */
        .step-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: relative;
            max-width: 400px;
            margin: 0 auto 30px auto;
        }
        .step-line {
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 2px;
            background: #E0E0E0;
            z-index: 0;
            transform: translateY(-50%);
        }
        .step-circle {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: #F0F2F6;
            color: #B0B0B0;
            display: flex;
            justify-content: center;
            align-items: center;
            font-weight: bold;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            z-index: 2;
            border: 2px solid #fff;
        }
        .step-circle.active {
            background: #8B5CF6; /* Purple */
            color: white !important;
            box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.2);
        }
        
        /* 2. Card Header Style */
        .card-header {
            font-size: 14px;
            font-weight: 600;
            color: #555;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        /* 3. Trade Result Buttons (Horizontal Radio) */
        div[role="radiogroup"] {
            display: flex;
            gap: 10px;
            width: 100%;
        }
        div[role="radiogroup"] label {
            flex: 1;
            background: white;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            justify-content: center;
            align-items: center;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        
        /* Win (First Option) */
        div[role="radiogroup"] label:nth-of-type(1):hover {
            border-color: #22C55E; background: #F0FDF4;
        }
        div[role="radiogroup"] label:nth-of-type(1)[data-checked="true"] {
            border-color: #22C55E; background: #F0FDF4; color: #15803D;
        }
        /* Break-even (Second Option) */
        div[role="radiogroup"] label:nth-of-type(2):hover {
            border-color: #9CA3AF; background: #F9FAFB;
        }
        div[role="radiogroup"] label:nth-of-type(2)[data-checked="true"] {
            border-color: #9CA3AF; background: #F9FAFB; color: #4B5563;
        }
        /* Loss (Third Option) */
        div[role="radiogroup"] label:nth-of-type(3):hover {
            border-color: #EF4444; background: #FEF2F2;
        }
        div[role="radiogroup"] label:nth-of-type(3)[data-checked="true"] {
            border-color: #EF4444; background: #FEF2F2; color: #B91C1C;
        }
        
        /* Ensure text visibility inside labels */
        div[role="radiogroup"] label p {
            color: inherit !important;
            font-weight: inherit !important;
            margin: 0;
        }
        
        /* 4. Inputs & Text Area */
        .stTextInput input, .stTextArea textarea, .stNumberInput input {
            border-radius: 8px;
            border: 1px solid #E5E7EB;
            padding: 10px;
        }
        
        /* 5. Save Button (Green Primary Override) */
        div[data-testid="stButton"] button[kind="primary"] {
            background-color: #10B981; /* Emerald 500 */
            border-color: #10B981;
            width: 100%;
            padding: 12px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            color: white;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover {
            background-color: #059669; /* Emerald 600 */
            border-color: #059669;
        }
        
    </style>
    """, unsafe_allow_html=True)

# Session State Initialization
if "stage" not in st.session_state:
    st.session_state.stage = "PRE_TRADING"

if "trade_data" not in st.session_state:
    st.session_state.trade_data = {}

if "memos" not in st.session_state:
    st.session_state.memos = []

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "history" not in st.session_state:
    st.session_state.history = []

if "full_history" not in st.session_state:
    st.session_state.full_history = []

if "user_id" not in st.session_state:
    st.session_state.user_id = ""

if "is_premium" not in st.session_state:
    st.session_state.is_premium = False

# --- 1. Supabase Helpers ---

@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase Init Error: {e}")
        return None

def optimize_image_high_quality(uploaded_file):
    try:
        image = Image.open(uploaded_file)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        output_io = io.BytesIO()
        image.save(output_io, format="WEBP", lossless=True, quality=100) 
        output_io.seek(0)
        return output_io
    except Exception as e:
        st.error(f"Image Optimization Error: {e}")
        return None

def upload_image_to_supabase(supabase: Client, image_file, bucket_name="trade_images"):
    try:
        filename = f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}.webp"
        mime_type = "image/webp"
        image_file.seek(0)
        file_bytes = image_file.read() 
        res = supabase.storage.from_(bucket_name).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": mime_type}
        )
        return supabase.storage.from_(bucket_name).get_public_url(filename)
    except Exception as e:
        st.error(f"Supabase Upload Error: {e}")
        return None

def load_data_from_supabase(supabase: Client, user_id):
    try:
        response = supabase.table("trades") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("entry_time", desc=False) \
            .execute()
        data = response.data
        if not data: return [], []
        for row in data:
            if "memos" in row and isinstance(row["memos"], str):
                 try: row["memos"] = ast.literal_eval(row["memos"])
                 except: row["memos"] = []
            if "strategy_name" not in row or not row["strategy_name"]:
                row["strategy_name"] = "General"
            if "ticker" not in row or not row["ticker"]:
                row["ticker"] = "Unknown"
        full_history = data
        recent_history = full_history[-20:] if len(full_history) > 20 else full_history
        return full_history, recent_history
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return [], []

def save_trade_to_supabase(supabase: Client, trade_data, user_id):
    try:
        payload = {
            "user_id": str(user_id).strip(),
            "entry_time": trade_data.get("entry_time").isoformat() if isinstance(trade_data.get("entry_time"), datetime) else trade_data.get("entry_time"),
            "exit_time": trade_data.get("exit_time").isoformat() if isinstance(trade_data.get("exit_time"), datetime) else trade_data.get("exit_time"),
            "ticker": trade_data.get("ticker", "Unknown"),
            "strategy_name": trade_data.get("strategy_name", "General"),
            "strategy_detail": trade_data.get("strategy", ""),
            "mood": trade_data.get("mood", ""),
            "start_balance": trade_data.get("start_balance", 0.0),
            "final_balance": trade_data.get("final_balance", 0.0),
            "profit": trade_data.get("profit", 0.0),
            "roi": trade_data.get("roi", 0.0),
            "result_status": trade_data.get("result_status", ""),
            "review": trade_data.get("review", ""),
            "satisfaction": trade_data.get("satisfaction", 5),
            "chart_url": trade_data.get("chart_url", ""),
            "duration_minutes": trade_data.get("duration_minutes", 0.0),
            "memos": trade_data.get("memos", [])
        }
        supabase.table("trades").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Save to Supabase Error: {e}")
        return False

# --- 2. Sidebar (User & Settings) ---

def check_user_exists(supabase: Client, user_id):
    try:
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        return len(res.data) > 0
    except: return False

def verify_user(supabase: Client, user_id, password):
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).eq("password", password).execute()
        return res.data 
    except: return []

def submit_exchange_uid(supabase: Client, user_id, uid):
    try:
        supabase.table("users").update({"exchange_uid": uid}).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"UID Submit Error: {e}")
        return False

def register_user(supabase: Client, user_id, password):
    try:
        supabase.table("users").insert({"user_id": user_id, "password": password, "is_premium": False}).execute()
        return True
    except: return False

# [Mobile Optimization] Check Login Status FIRST
if not st.session_state.user_id:
    st.write("")
    col1, col2, col3 = st.columns([1, 6, 1])
    with col2:
        st.title("After The Trade")
        st.markdown("### Professional Trading Journal")
        st.divider()
        
        tab_login, tab_reg = st.tabs(["Login", "Register"])
        
        with tab_login:
            with st.form("login_form_main"):
                uid_input = st.text_input("Nickname (ID)", key="login_id_main").strip()
                pw_input = st.text_input("Password", type="password", key="login_pw_main").strip()
                
                if st.form_submit_button("Login", type="primary", use_container_width=True):
                    supabase = init_supabase()
                    if not uid_input or not pw_input:
                        st.error("Enter ID and Password.")
                    else:
                        user_data = verify_user(supabase, uid_input, pw_input)
                        if user_data:
                            st.session_state.user_id = uid_input
                            st.session_state.is_premium = user_data[0].get("is_premium", False)
                            with st.spinner(f"☁️ Syncing data..."):
                                full, recent = load_data_from_supabase(supabase, uid_input)
                                st.session_state.full_history = full
                                st.session_state.history = recent
                            st.success("Login Success!")
                            st.rerun()
                        else:
                            st.error("Invalid ID or Password.")

        with tab_reg:
            with st.form("register_form_main"):
                new_uid = st.text_input("New ID", key="reg_id_main").strip()
                new_pw = st.text_input("New Password", type="password", key="reg_pw_main").strip()
                
                if st.form_submit_button("Register New Account", use_container_width=True):
                    supabase = init_supabase()
                    if not new_uid or not new_pw:
                        st.error("Enter ID and Password.")
                    else:
                        if check_user_exists(supabase, new_uid):
                            st.error("User ID already exists. Try logging in.")
                        else:
                            if register_user(supabase, new_uid, new_pw):
                                st.session_state.user_id = new_uid
                                st.session_state.full_history = []
                                st.session_state.history = []
                                st.success("Registered & Logged in!")
                                st.rerun()
                            else:
                                st.error("Registration failed.")
        
    st.write("")
    st.info("🔒 Please Login to access your dashboard.")
    st.stop()

# --- Everything below this line only runs if Logged In ---

with st.sidebar:
    st.header("👤 User Profile")
    st.success(f"**Welcome, {st.session_state.user_id}!**")
    
    if st.button("🚪 Logout", type="secondary"):
        st.session_state.user_id = ""
        st.session_state.history = []
        st.session_state.full_history = []
        st.rerun()
        
    st.divider()
    st.header("⚙️ Settings")
    
    is_hit_limit = len(st.session_state.full_history) >= 20
    show_unlock_section = st.session_state.is_premium or is_hit_limit

    if show_unlock_section:
        st.markdown("##### 🔓 Unlock Full Access")
        if st.session_state.is_premium:
            st.success("👑 **Premium Member** (Unlimited Access)")
        else:
            with st.expander("Submit UID"):
                st.caption("Sign up via our link & submit UID to bypass limits.")
                ex_uid = st.text_input("Exchange UID", placeholder="e.g. 12345678")
                if st.button("Submit Request"):
                    supabase = init_supabase()
                    if submit_exchange_uid(supabase, st.session_state.user_id, ex_uid):
                        st.info("✅ Request sent! Waiting for admin approval.")
            st.divider()

    api_key_input = st.text_input("OpenAI API Key", type="password")
    if api_key_input:
        openai.api_key = api_key_input
    st.divider()
    
    is_premium = st.session_state.get("is_premium", False)
    if (len(st.session_state.full_history) >= 18) and (not is_premium):
        st.info("🟢 This journal focuses on your most recent 20 trades by design.\nOlder trades are safely archived.")
    
    st.markdown("---") 
    
    is_locked_user = (len(st.session_state.full_history) > 20) and (not is_premium)
    discord_link_sidebar = "https://discord.gg/QRZAh6Zj" 

    if is_locked_user:
        btn_text = "Access Trade Archive"
        btn_sub = "Optional. No impact on your current journaling flow."
        btn_color = "#FF4B4B"
        btn_color_hover = "#D93A3A"
    else:
        btn_text = "💬 Join Community"
        btn_sub = "Share strategies & chat"
        btn_color = "#5865F2" 
        btn_color_hover = "#4752C4"

    st.markdown(f"""
        <a href="{discord_link_sidebar}" target="_blank" style="text-decoration: none;">
            <div style="
                width: 100%;
                background-color: {btn_color}; 
                color: white;
                padding: 12px 15px;
                border-radius: 8px;
                text-align: center;
                margin-top: 10px;
                margin-bottom: 20px;
                box-shadow: 0 3px 6px rgba(0,0,0,0.2);
                border: 1px solid rgba(255,255,255,0.1);
                transition: all 0.3s ease;
            " onmouseover="this.style.backgroundColor='{btn_color_hover}'; this.style.transform='translateY(-2px)';" 
              onmouseout="this.style.backgroundColor='{btn_color}'; this.style.transform='translateY(0px)';">
                <div style="font-weight: bold; font-size: 16px;">{btn_text}</div>
                <div style="font-size: 11px; opacity: 0.9; margin-top: 2px;">{btn_sub}</div>
            </div>
        </a>
    """, unsafe_allow_html=True)

# --- 3. Main Pipeline ---
st.title("📊 Trading Dashboard")

# [Step 1] Preparation
if st.session_state.stage == "PRE_TRADING":
    step1_css()
    
    # 1. Analytics Shortcut (Prominent Top Button)
    if st.button("📊 View Performance Analytics (Skip)", type="secondary", use_container_width=True):
        st.session_state.stage = "ANALYTICS"
        st.rerun()
    
    st.write("") # Spacer

    # 2. Progress Bar
    st.markdown("""
        <div class="step-container">
            <div class="step-line"></div>
            <div class="step-circle active">1</div>
            <div class="step-circle">2</div>
            <div class="step-circle">3</div>
        </div>
        <div style="text-align: center; margin-bottom: 20px; color: #888; font-size: 14px; font-weight: 500;">
            New Trade Entry: Preparation
        </div>
    """, unsafe_allow_html=True)
    
    supabase = init_supabase()
    if not st.session_state.full_history and supabase and st.session_state.user_id:
        with st.spinner(f"☁️ Syncing data..."):
            full, recent = load_data_from_supabase(supabase, st.session_state.user_id)
            if full:
                st.session_state.full_history = full
                st.session_state.history = recent
            else: pass
    elif st.session_state.history:
        if st.button("🔄 Force Resync"):
             st.session_state.full_history = []
             st.session_state.history = []
             st.rerun()
    
    with st.form("pre_trading_form"):
        default_balance = 0.0
        if st.session_state.full_history:
            default_balance = st.session_state.full_history[-1].get("final_balance", 0.0)
        
        # Card 1: Start Balance
        with st.container(border=True):
            st.markdown('<div class="input-header"><span class="input-header-icon">💲</span> Start Balance Details</div>', unsafe_allow_html=True)
            start_balance = st.number_input("Start Balance", min_value=0.0, step=100.0, value=float(default_balance), label_visibility="collapsed")
        
        # Card 2: Ticker
        with st.container(border=True):
            st.markdown('<div class="input-header"><span class="input-header-icon">🎯</span> Ticker / Asset</div>', unsafe_allow_html=True)
            existing_tickers = sorted(list(set([str(h.get('ticker', 'Unknown')) for h in st.session_state.full_history]))) if st.session_state.full_history else []
            ticker_option = st.selectbox("Ticker Select", ["Create New..."] + existing_tickers, label_visibility="collapsed")
            if ticker_option == "Create New...":
                st.markdown("<div style='height: 5px'></div>", unsafe_allow_html=True) 
                ticker_input = st.text_input("New Ticker Name", placeholder="e.g. BTCUSDT", label_visibility="collapsed").upper()
            else:
                ticker_input = ticker_option

        # Card 3: Strategy
        with st.container(border=True):
            st.markdown('<div class="input-header"><span class="input-header-icon">📄</span> Strategy</div>', unsafe_allow_html=True)
            existing_strategies = list(set([str(h.get('strategy_name', 'General')) for h in st.session_state.full_history])) if st.session_state.full_history else []
            if "General" not in existing_strategies: existing_strategies.append("General")
            
            strategy_option = st.selectbox("Strat Select", ["Create New..."] + sorted([str(x) for x in existing_strategies]), label_visibility="collapsed")
            if strategy_option == "Create New...":
                 st.markdown("<div style='height: 5px'></div>", unsafe_allow_html=True)
                 strategy_name = st.text_input("New Strat Name", placeholder="e.g. Trend Breakout", label_visibility="collapsed")
            else:
                strategy_name = strategy_option
            
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
            strategy_detail = st.text_area("Details", height=100, placeholder="Strategy Details (Setup, Entry, Exit)...", label_visibility="collapsed")

        # Card 4: Mood (Grid)
        with st.container(border=True):
            st.markdown('<div class="input-header">Current Mood</div>', unsafe_allow_html=True)
            # English Mood Options
            mood_options = ["😌 Calm", "💪 Confident", "😨 Anxious", "😱 FOMO", "🥵 Revenge", "😴 Bored"]
            mood_selection = st.radio("Mood", mood_options, label_visibility="collapsed")
            mood = mood_selection 

        st.write("")
        
        submitted = st.form_submit_button("▷ Start Trading")
        
        if submitted:
            if not strategy_name.strip() or not strategy_detail.strip() or not ticker_input.strip():
                st.error("Please fill in Ticker, Strategy Name, and Details!")
            else:
                st.session_state.trade_data = {
                    "start_balance": start_balance,
                    "ticker": ticker_input,
                    "strategy_name": strategy_name,
                    "strategy": strategy_detail,
                    "mood": mood,
                    "entry_time": datetime.now(KST), # FIX: Use KST
                    "entry_time_str": datetime.now(KST).strftime("%H:%M:%S") # FIX: Use KST
                }
                st.session_state.stage = "TRADING"
                st.session_state.analysis_result = None
                st.session_state.memos = [] 
                st.rerun()

# [Step 2] Live Trading
elif st.session_state.stage == "TRADING":
    step2_css()
    
    # 1. Spacer
    st.write("")
    
    # 2. Progress Bar (Step 2 Active)
    st.markdown("""
        <div class="step-container">
            <div class="step-line"></div>
            <div class="step-circle">1</div>
            <div class="step-circle active">2</div>
            <div class="step-circle">3</div>
        </div>
        <div style="text-align: center; margin-bottom: 20px; color: #888; font-size: 14px; font-weight: 500;">
            Live Trading in Progress
        </div>
    """, unsafe_allow_html=True)
    
    data = st.session_state.get("trade_data", {})

    datetime_now_kst = datetime.now(KST)
    
    # Calculate Start Time
    entry_time = data.get("entry_time", datetime_now_kst)
    if isinstance(entry_time, str):
        try: entry_time = datetime.fromisoformat(entry_time)
        except: entry_time = datetime_now_kst
    
    # Ensure entry_time is aware (Handle legacy data)
    if entry_time.tzinfo is None:
        entry_time = entry_time.replace(tzinfo=KST)
        
    start_time_iso = entry_time.isoformat()
    # FIX: Pass Epoch Milliseconds to JS to avoid parsing ambiguity
    start_time_ts = int(entry_time.timestamp() * 1000)
    
    start_time_display = entry_time.strftime("%p %I:%M Start")

    # 3. Real-time JS Timer (Fixed Timezone)
    # Note: Streamlit styling doesn't pass to iframe, so we must inline CSS.
    timer_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@700&family=Inter:wght@400;600&display=swap');
            body {{
                margin: 0;
                background-color: transparent;
                font-family: 'Inter', sans-serif;
            }}
            .timer-card {{
                background-color: #1E293B;
                border-radius: 16px;
                padding: 20px;
                text-align: center;
                color: white;
                position: relative;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                height: 140px;
                box-sizing: border-box;
                box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            }}
            .live-badge {{
                position: absolute;
                top: 15px;
                left: 15px;
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 12px;
                color: #4ADE80;
                font-weight: bold;
                background: rgba(255,255,255,0.05);
                padding: 4px 8px;
                border-radius: 20px;
            }}
            .live-dot {{
                width: 8px;
                height: 8px;
                background-color: #4ADE80;
                border-radius: 50%;
                box-shadow: 0 0 8px #4ADE80;
            }}
            .timer-value {{
                font-family: 'JetBrains Mono', monospace;
                font-size: 48px;
                font-weight: 700;
                margin: 5px 0;
                letter-spacing: 2px;
                line-height: 1.2;
            }}
            .timer-sub {{
                color: #94A3B8;
                font-size: 14px;
                opacity: 0.8;
            }}
        </style>
    </head>
    <body>
        <div class="timer-card">
            <div class="live-badge">
                <div class="live-dot"></div> LIVE
            </div>
            <div class="timer-value" id="timer">00:00:00</div>
            <div class="timer-sub">{start_time_display}</div>
        </div>
        <script>
            // FIX: Use Epoch Milliseconds directly
            const startTime = {start_time_ts};
            
            function updateTimer() {{
                const now = new Date().getTime();
                const diff = now - startTime;
                
                if (diff < 0) {{
                    document.getElementById("timer").innerText = "00:00:00";
                    return;
                }}
                
                const totalSeconds = Math.floor(diff / 1000);
                const hours = Math.floor(totalSeconds / 3600);
                const remainder = totalSeconds % 3600;
                const minutes = Math.floor(remainder / 60);
                const seconds = totalSeconds % 60;
                
                const h = hours.toString().padStart(2, '0');
                const m = minutes.toString().padStart(2, '0');
                const s = seconds.toString().padStart(2, '0');
                
                document.getElementById("timer").innerText = `${{h}}:${{m}}:${{s}}`;
            }}
            
            setInterval(updateTimer, 1000);
            updateTimer();
        </script>
    </body>
    </html>
    """
    components.html(timer_html, height=160)
    
    # 4. Strategy Card
    with st.container(border=True):
        # Custom Header inside Card
        st.markdown(f"""
            <div class="strat-header">
                <div class="strat-title">◎ My Strategy</div>
                <div class="strat-badge">{data.get('strategy_name', 'General')}</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"**Details:**\n\n{data.get('strategy', '')}")
        st.markdown(f"**Current Mood:** {data.get('mood', 'Neutral')}")
        
        # Warning Box
        st.markdown("""
            <div class="warning-box">
                ⚠️ <strong>NO IMPULSIVE TRADING:</strong> Stick to your plan. Emotional trading is the fastest way to lose.
            </div>
        """, unsafe_allow_html=True)

    # 5. Live Memos (Chat Style)
    with st.container(border=True):
        st.markdown('<div class="strat-title" style="margin-bottom:10px">💬 Live Memos</div>', unsafe_allow_html=True)
        
        # Display Memos
        if not st.session_state.memos:
            st.caption("No memos yet. Note your thoughts...")
            st.markdown("<div style='height: 50px'></div>", unsafe_allow_html=True)
        else:
            chat_html = '<div class="memo-chat-container">'
            for memo in st.session_state.memos: # Chronological order is better for chat? usually bottom is new.
                # Use st.session_state.memos (append puts new at end). 
                # Chat usually shows new at bottom.
                # Clean HTML construction, preventing double-indentation issues
                safe_text = memo['text'].replace("<", "&lt;").replace(">", "&gt;") # Basic sanitize
                chat_html += f"<div class='memo-bubble'><span class='memo-time'>{memo['time']}</span> {safe_text}</div>"
            chat_html += "</div>"
            st.markdown(chat_html, unsafe_allow_html=True)
        
        st.write("")
        # Input Form
        with st.form(key="memo_form", clear_on_submit=True):
            col_in1, col_in2 = st.columns([5, 1])
            with col_in1:
                memo_text = st.text_input("Memo Input", placeholder="What are you thinking right now?", label_visibility="collapsed")
            with col_in2:
                submit_memo = st.form_submit_button("➤")
            
            if submit_memo and memo_text:
                now_str = datetime.now().strftime("%H:%M:%S")
                if "memos" not in st.session_state: st.session_state.memos = [] 
                st.session_state.memos.append({"time": now_str, "text": memo_text})
                st.rerun()

    st.write("")
    
    # 6. Action Buttons
    c_end1, c_end2 = st.columns([1, 2])
    with c_end1:
        if st.button("⬅️ Back", use_container_width=True):
            st.session_state.stage = "PRE_TRADING"
            st.rerun()
    with c_end2:
        # Styled Red via CSS (primary)
        if st.button("⏹ End Trade", type="primary", use_container_width=True):
            st.session_state.trade_data["exit_time"] = datetime.now(KST) # FIX: KST
            st.session_state.trade_data["exit_time_str"] = datetime.now(KST).strftime("%H:%M:%S")
            st.session_state.trade_data["memos"] = st.session_state.memos
            st.session_state.stage = "POST_TRADING"
            st.rerun()

# [Step 3] Review & Result
elif st.session_state.stage == "POST_TRADING":
    step3_css()
    
    if st.session_state.analysis_result is None:
        # 1. Spacer
        st.write("")
        
        # 2. Progress Bar (Step 3 Active)
        st.markdown("""
            <div class="step-container">
                <div class="step-line"></div>
                <div class="step-circle">1</div>
                <div class="step-circle">2</div>
                <div class="step-circle active">3</div>
            </div>
            <div style="text-align: center; margin-bottom: 20px; color: #888; font-size: 14px; font-weight: 500;">
                Review & Save
            </div>
        """, unsafe_allow_html=True)
        
        data = st.session_state.trade_data
        
        # 3. Final Balance Card
        with st.container(border=True):
            st.markdown('<div class="card-header">💰 Final Balance</div>', unsafe_allow_html=True)
            final_balance = st.number_input(
                "Final Balance", 
                min_value=0.0, 
                step=100.0, 
                value=float(data.get('start_balance', 0.0)),
                label_visibility="collapsed"
            )
        
        # 4. Trade Result Card (Horizontal Buttons)
        with st.container(border=True):
            st.markdown('<div class="card-header">📊 Trade Result</div>', unsafe_allow_html=True)
            
            # Auto-detect logic
            temp_profit = final_balance - data.get('start_balance', 0.0)
            default_idx = 1 # Break-even
            if temp_profit > 0: default_idx = 0 # Win
            elif temp_profit < 0: default_idx = 2 # Loss
            
            result_status_option = st.radio(
                "Result",
                ["Win", "Break-even", "Loss"],
                index=default_idx,
                label_visibility="collapsed",
                horizontal=True
            )
            
        # 5. Live Memos (Reference)
        if data.get("memos"):
            with st.container(border=True):
                st.markdown('<div class="card-header">🧠 Live Memos (Reference)</div>', unsafe_allow_html=True)
                for m in data["memos"]:
                    st.caption(f"[{m['time']}] {m['text']}")

        # 6. Review Note Card
        with st.container(border=True):
            st.markdown('<div class="card-header">📝 Review Note</div>', unsafe_allow_html=True)
            
            review_note = st.text_area(
                "Review Note",
                value="",
                placeholder="Write your trade review here...",
                height=150,
                label_visibility="collapsed"
            )
            
        # 6. Screenshot Upload
        with st.container(border=True):
            st.markdown('<div class="card-header">🖼️ Chart Screenshot</div>', unsafe_allow_html=True)
            uploaded_file = st.file_uploader(
                "Upload Image",
                type=['png', 'jpg', 'jpeg'],
                label_visibility="collapsed"
            )
            
        # 7. Satisfaction Slider
        with st.container(border=True):
            satisfaction = st.slider("⭐ Satisfaction Score", 1, 10, 5)

        st.write("")
        
        # 8. Footer Buttons
        c_back, c_save = st.columns([1, 2])
        
        with c_back:
            if st.button("⬅️ Back"):
                st.session_state.stage = "TRADING"
                st.rerun()
                
        with c_save:
            if st.button("💾 Save Trade", type="primary", use_container_width=True):
                supabase = init_supabase()
                
                # Image Upload
                chart_url = ""
                if uploaded_file is not None:
                    if supabase:
                        with st.spinner("Optimizing & Uploading Image..."):
                            try:
                                optimized_io = optimize_image_high_quality(uploaded_file)
                                if optimized_io:
                                    url = upload_image_to_supabase(supabase, optimized_io, bucket_name="trade_images")
                                    if url:
                                        chart_url = url
                                        st.success("✅ Image Uploaded!")
                                    else:
                                        st.error("Upload failed.")
                            except Exception as e:
                                st.warning(f"Image upload skipped: {e}")
                    else:
                        st.error("Supabase not connected.")
                
                # Update Session Data
                profit = final_balance - data['start_balance']
                roi = (profit / data['start_balance'] * 100) if data['start_balance'] > 0 else 0
                
                # Calculate Duration
                entry_dt = data.get("entry_time", datetime.now(KST))
                if isinstance(entry_dt, str):
                    try: entry_dt = datetime.fromisoformat(entry_dt)
                    except: entry_dt = datetime.now(KST)
                
                # Ensure entry_dt is aware
                if entry_dt.tzinfo is None:
                    entry_dt = entry_dt.replace(tzinfo=KST)
                    
                exit_dt = datetime.now(KST) # FIX: KST
                duration = exit_dt - entry_dt
                minutes_duration = duration.total_seconds() / 60

                st.session_state.trade_data.update({
                    "final_balance": final_balance,
                    "profit": profit,
                    "roi": roi,
                    "result_status": result_status_option,
                    "review": review_note,
                    "satisfaction": satisfaction,
                    "memos": st.session_state.memos,
                    "chart_url": chart_url,
                    "duration_minutes": minutes_duration,
                    "exit_time": exit_dt
                })
                
                # AI Feedback
                ai_feedback = "AI Feedback not available (API Key missing)."
                if openai.api_key:
                    try:
                        memo_str = "\n".join([f"- {m['time']} {m['text']}" for m in st.session_state.memos]) if st.session_state.memos else "None"
                        prompt = f"""
                        [Trade Data]
                        Strategy: {data.get('strategy_name', 'Unknown')}
                        Result: {result_status_option} (${profit:,.0f}, {roi:.2f}%)
                        Review: {review_note}
                        Memos: {memo_str}
                        
                        Provide 3 concise, bullet-pointed feedback items for this trader in English.
                        """
                        with st.spinner("🤖 AI Coach Analyzing..."):
                            response = openai.chat.completions.create(
                                model="gpt-4",
                                messages=[
                                    {"role": "system", "content": "You are a professional trading coach. Be concise and constructive."},
                                    {"role": "user", "content": prompt}
                                ]
                            )
                            ai_feedback = response.choices[0].message.content
                    except Exception as e:
                        ai_feedback = f"AI Error: {e}"
                
                st.session_state.analysis_result = ai_feedback

                # Save to Database
                if supabase:
                    with st.spinner("Saving to Database..."):
                        success = save_trade_to_supabase(supabase, st.session_state.trade_data, st.session_state.user_id)
                        if success:
                            # Refresh History
                            full, recent = load_data_from_supabase(supabase, st.session_state.user_id)
                            st.session_state.full_history = full
                            st.session_state.history = recent
                            st.success("✅ Trade Saved Successfully!")
                            st.rerun()
                else:
                    st.error("Database connection missing. Trade stored locally in session only.")
                    st.rerun()

    else:
        r_data = st.session_state.trade_data
        
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Profit", f"${r_data['profit']:+,.0f}")
        with col2: st.metric("ROI", f"{r_data['roi']:+.2f}%")
        with col3: st.metric("Satisfaction", f"{r_data['satisfaction']}/10")
            
        st.divider()
        st.subheader("💡 AI Coach Feedback")
        st.info(st.session_state.analysis_result)
        
        st.markdown("#### 📝 My Review")
        st.write(r_data['review'])
        
        if 'memos' in r_data and r_data['memos']:
            st.markdown("#### 🧠 Real-time Memos")
            for m in r_data['memos']:
                st.caption(f"[{m.get('time', '')}] {m.get('text', '')}")
        
        st.write("")
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            if st.button("🔄 Start New Trade"):
                st.session_state.stage = "PRE_TRADING"
                st.session_state.analysis_result = None
                st.session_state.memos = []
                st.rerun()
        with col_res2:
            if st.button("📊 Go to Analytics"):
                st.session_state.stage = "ANALYTICS"
                st.rerun()

# [Step 4] Performance Analytics
elif st.session_state.stage == "ANALYTICS":
    st.subheader("📊 Performance Analytics")
    
    is_premium = st.session_state.get("is_premium", False)
    if (len(st.session_state.full_history) >= 18) and (not is_premium):
        st.warning("🟢 **Focused analysis based on your most recent trades.**")
    
    full_data = st.session_state.full_history if st.session_state.full_history else []
    
    if not full_data:
        st.info("No trade records found yet.")
        if st.button("Go Back"):
            st.session_state.stage = "PRE_TRADING"
            st.rerun()
    else:
        df_all = pd.DataFrame(full_data)
        
        df_all['datetime_obj'] = pd.to_datetime(df_all['entry_time'], utc=True)
        df_all['date_str'] = df_all['datetime_obj'].dt.strftime('%m/%d')
        
        if 'strategy_name' not in df_all.columns: df_all['strategy_name'] = "General"
        df_all['strategy_name'] = df_all['strategy_name'].fillna("General")
        
        if 'ticker' not in df_all.columns: df_all['ticker'] = "Unknown"
        df_all['ticker'] = df_all['ticker'].fillna("Unknown").astype(str)
        
        if "profit" not in df_all.columns: df_all['profit'] = 0.0
        if "roi" not in df_all.columns: df_all['roi'] = 0.0
        
        total_count = len(df_all)
        recent_limit = 20
        df_all['is_locked'] = False
        
        if (not is_premium) and (total_count > recent_limit):
             df_all.loc[:total_count-recent_limit-1, 'is_locked'] = True
        
        if is_premium:
             df_analytics = df_all.copy()
        else:
             df_analytics = df_all.iloc[-recent_limit:].copy()
        
        top_left, top_right = st.columns([1, 1], gap="medium")
        
        with top_left:
            st.markdown("##### ⚙️ Filters & Metrics")
            
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                period_options = ["All Time", "Last 7 Days", "Last 30 Days", "Last 30 Trades"]
                period_filter = st.selectbox("Filter by Period", period_options)
            with f_col2:
                all_strats = sorted([str(x) for x in df_analytics['strategy_name'].unique()])
                strategy_filter = st.multiselect("Filter by Strategy", all_strats, default=all_strats)
            with f_col3:
                all_tickers = sorted([str(x) for x in df_analytics['ticker'].unique()])
                ticker_filter = st.multiselect("Filter by Ticker", all_tickers, default=all_tickers)
        
            df_filtered = df_analytics.copy()
            
            if strategy_filter:
                df_filtered = df_filtered[df_filtered['strategy_name'].astype(str).isin(strategy_filter)]
            
            if ticker_filter:
                df_filtered = df_filtered[df_filtered['ticker'].isin(ticker_filter)]
            
            if period_filter == "Last 7 Days":
                cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                df_filtered = df_filtered[df_filtered['datetime_obj'] >= cutoff]
            elif period_filter == "Last 30 Days":
                cutoff = datetime.now(timezone.utc) - timedelta(days=30)
                df_filtered = df_filtered[df_filtered['datetime_obj'] >= cutoff]

            if df_filtered.empty:
                st.caption("No recent trades match filters.")
                
            total_profit = df_filtered['profit'].sum()
            
            real_current_balance = 0.0
            if not df_all.empty:
                real_current_balance = df_all.iloc[-1]['final_balance']

            win_count = len(df_filtered[df_filtered['profit'] > 0])
            total_count_filtered = len(df_filtered)
            win_rate = (win_count / total_count_filtered * 100) if total_count_filtered > 0 else 0
            avg_holding = df_filtered['duration_minutes'].mean() if 'duration_minutes' in df_filtered.columns else 0

            m_r1_c1, m_r1_c2, m_r1_c3 = st.columns(3)
            with m_r1_c1:
                st.metric("💰 Current Balance", f"${real_current_balance:,.0f}", help="Total Account Balance")
            with m_r1_c2:
                profit_color = COLOR_PROFIT if total_profit > 0 else (COLOR_LOSS if total_profit < 0 else "black")
                profit_str = f"${total_profit:+,.0f}"
                font_size = "28px" if len(profit_str) < 8 else "20px"
                st.markdown(f"""
                    <div style="font-size: 14px; margin-bottom: 2px;">🏆 Recent Profit</div>
                    <div style="font-size: {font_size}; font-weight: bold; color: {profit_color}; line-height: 1.2;">
                        {profit_str}
                    </div>
                """, unsafe_allow_html=True)
            with m_r1_c3:
                st.metric(f"📈 Win Rate", f"{win_rate:.1f}%")
            
            st.write("")
            
            m_r2_c1, m_r2_c2, m_r2_c3 = st.columns(3)
            avg_win = df_filtered[df_filtered['profit'] > 0]['profit'].mean() if not df_filtered[df_filtered['profit'] > 0].empty else 0
            avg_loss = abs(df_filtered[df_filtered['profit'] < 0]['profit'].mean()) if not df_filtered[df_filtered['profit'] < 0].empty else 0
            pl_ratio = avg_win / avg_loss if avg_loss > 0 else 0
            
            with m_r2_c1: st.metric("⚖️ Avg P/L Ratio", f"{pl_ratio:.2f}")
            with m_r2_c2: st.metric("⏳ Avg Holding", f"{avg_holding:.0f}m")
        
        with top_right:
            st.markdown("### 💸 Equity Curve (Recent 20)")
            chart_df = df_filtered.reset_index(drop=True)
            chart_df['trade_num'] = range(1, len(chart_df) + 1)
            chart_df['trade_label'] = chart_df.apply(lambda x: f"{x['trade_num']} ({str(x['date_str'])})", axis=1)
            
            fig = px.area(chart_df, x='trade_label', y='final_balance', markers=True)
            fig.update_traces(line_color='#AB63FA', line_shape='spline', fillcolor='rgba(171, 99, 250, 0.2)')
            fig.update_layout(xaxis_title=None, yaxis_title="Balance ($)", height=400, margin=dict(l=20, r=20, t=10, b=20))
            
            if not chart_df.empty:
                min_bal = chart_df['final_balance'].min()
                max_bal = chart_df['final_balance'].max()
                diff = max_bal - min_bal
                padding = diff * 0.5 if diff > 0 else (min_bal * 0.05 if min_bal != 0 else 100)
                fig.update_yaxes(range=[min_bal - padding, max_bal + padding])
            
            st.plotly_chart(fig, use_container_width=True)

        st.write("")
        
        col_mid1, col_mid2, col_mid3 = st.columns(3)
        
        with col_mid1:
            st.markdown("###### ⏳ Time Edge")
            def get_duration_bin(minutes):
                if minutes <= 60: return "0-1h"
                elif minutes <= 180: return "1-3h"
                elif minutes <= 360: return "3-6h"
                elif minutes <= 720: return "6-12h"
                elif minutes <= 1440: return "12-24h"
                else: return "24h+"
            
            if 'duration_minutes' in df_filtered.columns:
                df_filtered['duration_bin'] = df_filtered['duration_minutes'].apply(get_duration_bin)
                bin_stats = []
                for b in ["0-1h", "1-3h", "3-6h", "6-12h", "12-24h", "24h+"]:
                    subset = df_filtered[df_filtered['duration_bin'] == b]
                    if not subset.empty:
                        wins = len(subset[subset['profit'] > 0])
                        rate = (wins / len(subset)) * 100
                        bin_stats.append({'Duration': b, 'Win Rate': rate})
                    else:
                        bin_stats.append({'Duration': b, 'Win Rate': 0.0})
                bin_df = pd.DataFrame(bin_stats)
                fig_time = px.bar(bin_df, x='Duration', y='Win Rate', text='Win Rate', color='Win Rate', color_continuous_scale='RdBu', range_y=[0, 100])
                fig_time.update_traces(texttemplate='%{text:.0f}%', textposition='outside')
                fig_time.update_layout(yaxis_title=None, xaxis_title=None, height=300, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig_time, use_container_width=True)
            else: st.caption("No duration data.")

        with col_mid2:
            st.markdown("###### 📊 Win/Loss")
            win_loss_df = df_filtered['result_status'].value_counts().reset_index()
            win_loss_df.columns = ['Result', 'Count']
            fig_pie = px.pie(win_loss_df, values='Count', names='Result', color='Result', hole=0.5,
                             color_discrete_map={'Win':COLOR_WIN, 'Loss':COLOR_LOSS, 'Break-even':COLOR_BE})
            fig_pie.update_layout(showlegend=False, height=300, margin=dict(t=10, b=10, l=10, r=10))
            fig_pie.update_traces(textinfo='percent+label', textposition='inside',textfont_color='white')
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_mid3:
            st.markdown("###### ⚖️ R:R Ratio")
            rr_data = {'Type': ['Avg Loss', 'Avg Win'], 'Amount': [avg_loss, avg_win], 'ColorLabel': ['Loss', 'Win']}
            fig_rr = px.bar(pd.DataFrame(rr_data), x='Amount', y='Type', orientation='h', color='ColorLabel', text='Amount',
                            color_discrete_map={'Win':COLOR_WIN, 'Loss':COLOR_LOSS})
            fig_rr.update_traces(texttemplate='$%{x:,.0f}', textposition='outside', cliponaxis=False)
            max_rr_val = max(avg_win, avg_loss) if (avg_win > 0 or avg_loss > 0) else 100
            fig_rr.update_layout(showlegend=False, xaxis=dict(showgrid=False, showticklabels=False, range=[0, max_rr_val * 1.4]),
                                 yaxis_title=None, height=300, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig_rr, use_container_width=True)

        st.divider()
        
        st.markdown("### 📋 Trade History (Full History)")
        st.caption("Older trades are archived to save space and focus on current performance.")
        
        df_table = df_all.copy()
        
        df_table = df_table.sort_values('entry_time', ascending=False).reset_index(drop=True)
        
        df_table['is_locked'] = False
        is_premium = st.session_state.get('is_premium', False)
        
        if (not is_premium) and (len(df_table) > 20):
            df_table.loc[20:, 'is_locked'] = True 
            
        if 'strategy_detail' in df_table.columns: df_table['Detail'] = df_table['strategy_detail']
        elif 'strategy' in df_table.columns: df_table['Detail'] = df_table['strategy']
        else: df_table['Detail'] = ""
        
        for idx in df_table.index:
            if df_table.loc[idx, 'is_locked']:
                df_table.loc[idx, 'ticker'] = "🔒 Archived"
                df_table.loc[idx, 'strategy_name'] = "****"
                df_table.loc[idx, 'result_status'] = "Archived"
                df_table.loc[idx, 'profit'] = 0.0
                df_table.loc[idx, 'roi'] = 0.0
                df_table.loc[idx, 'mood'] = "🔒"
                df_table.loc[idx, 'Detail'] = "This trade is archived to keep your review focused."
        
        if strategy_filter:
            mask_strategy = df_table['strategy_name'].astype(str).isin(strategy_filter)
            mask_locked = df_table['is_locked'] == True
            df_table = df_table[mask_strategy | mask_locked]

        if ticker_filter:
             mask_ticker = df_table['ticker'].isin(ticker_filter)
             mask_locked = df_table['is_locked'] == True
             df_table = df_table[mask_ticker | mask_locked]

        if period_filter == "Last 7 Days":
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            df_table = df_table[df_table['datetime_obj'] >= cutoff]
        elif period_filter == "Last 30 Days":
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            df_table = df_table[df_table['datetime_obj'] >= cutoff]
        elif period_filter == "Last 30 Trades":
            df_table = df_table.head(30)

        
        display_cols = ['date_str', 'ticker', 'strategy_name', 'result_status', 'profit', 'roi', 'mood', 'Detail']
        display_df = df_table[display_cols].copy()
        display_df.columns = ['Date', 'Ticker', 'Tag', 'Result', 'Profit($)', 'ROI(%)', 'Mood', 'Detail']
        
        def color_result(val):
            if val == 'Locked' or val == 0.0 or val == 0: 
                return 'color: #888'
            
            try:
                text = str(val).replace('$', '').replace(',', '').replace('%', '')
                val_num = float(text)
                
                if val_num > 0:
                    return f'color: {COLOR_WIN}'
                elif val_num < 0:
                    return f'color: {COLOR_LOSS}' 
                else:
                    return f'color: {COLOR_BE}'
            except:
                return 'color: #888'
            
        def color_status_text(val):
            if val == 'Locked': return 'color: #888; font-style: italic;'
            if val == 'Win' or val == '익절': return f'color: {COLOR_WIN}; font-weight: bold;'
            elif val == 'Loss' or val == '손절': return f'color: {COLOR_LOSS}; font-weight: bold;'
            elif val == 'Break-even' or val == '본절': return f'color: {COLOR_BE}; font-weight: bold;'
            return 'color: black;'

        styled_df = display_df.style.format({
            'Profit($)': '${:,.0f}',
            'ROI(%)': '{:+.2f}%'
        }).map(color_result, subset=['Profit($)', 'ROI(%)'])\
          .map(color_status_text, subset=['Result'])
        
        event = st.dataframe(
            styled_df, 
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        st.divider()
        
        if len(event.selection.rows) > 0:
            selected_row_idx = event.selection.rows[0]
            record = df_table.iloc[selected_row_idx]
            
            if record['is_locked']:
                with st.container():
                     st.warning("**Archived Trade**")
                     st.info("This trade is archived to keep your review focused.\nSupport is optional — join the Discord to access full history and shared trading ideas.")
                     
                     discord_link = "https://discord.gg/QRZAh6Zj" 

                     st.markdown(f"""
                        <a href="{discord_link}" target="_blank" style="text-decoration: none;">
                            <div style="
                                width: 100%;
                                background-color: #5865F2; 
                                color: white;
                                padding: 12px 20px;
                                border-radius: 10px;
                                text-align: center;
                                font-weight: bold;
                                font-size: 16px;
                                margin-top: 10px;
                                box-shadow: 0 4px 6px rgba(0,0,0,0.2);
                                transition: all 0.3s ease;
                                border: 1px solid #4752C4;
                            " onmouseover="this.style.backgroundColor='#4752C4'; this.style.transform='translateY(-2px)';" 
                              onmouseout="this.style.backgroundColor='#5865F2'; this.style.transform='translateY(0px)';">
                                💬 Join Discord
                            </div>
                        </a>
                    """, unsafe_allow_html=True)
            else:
                with st.container():
                    st.info(f"📌 Detailed Trade Report ({record['date_str']})")
                    d1, d2, d3 = st.columns(3)
                    d1.write(f"**Strategy:** [{record.get('strategy_name','General')}] {record.get('Detail','')}")
                    d2.write(f"**Result:** {record['result_status']} (${record['profit']:+,.0f})")
                    d3.write(f"**Mood:** {record['mood']}")
                    st.write("") 

                    col_d1, col_d2, col_d3 = st.columns(3)
                    def render_dt_html(label, dt_val):
                        if not dt_val: date_str, time_str = "-", "-"
                        else:
                            if isinstance(dt_val, str):
                                try: dt_obj = datetime.fromisoformat(dt_val)
                                except: dt_obj = datetime.now()
                            else: dt_obj = dt_val
                            date_str = dt_obj.strftime('%Y-%m-%d')
                            time_str = dt_obj.strftime('%H:%M:%S')
                        return f"""<p style="font-size: 14px; margin-bottom: 0px; color: #555;">{label}</p>
                            <div style="line-height:1.2;">
                                <span style="font-size:0.8em; color:#888;">{date_str}</span><br>
                                <span style="font-size:1.1em; font-weight:bold;">{time_str}</span>
                            </div>"""
                    col_d1.markdown(render_dt_html("Entry Time", record.get('entry_time')), unsafe_allow_html=True)
                    col_d2.markdown(render_dt_html("Exit Time", record.get('exit_time')), unsafe_allow_html=True)
                    
                    dur_minutes = int(record.get('duration_minutes', 0))
                    dur_h, dur_m = divmod(dur_minutes, 60)
                    col_d3.markdown(f"""
                        <p style="font-size: 14px; margin-bottom: 0px; color: #555;">Holding Time</p>
                        <div style="line-height:1.2; padding-top: 5px;">
                            <span style="font-size:1.1em; font-weight:bold;">{dur_h}h {dur_m}m</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.divider()
                    st.markdown("#### 📷 Trade Chart")
                    if 'chart_url' in record and record['chart_url']:
                        st.image(record['chart_url'], caption="Chart Image", use_container_width=True)
                        st.markdown(f"[🔗 Open Original]({record['chart_url']})")
                    else: st.caption("📷 No chart image available.")
                    
                    st.write("")
                    st.markdown("#### 📝 Real-time Memos")
                    memos_data = record.get('memos', [])
                    if isinstance(memos_data, str):
                        try: memos_data = ast.literal_eval(memos_data)
                        except: memos_data = []
                    if isinstance(memos_data, list) and memos_data:
                        for m in memos_data:
                            if isinstance(m, dict): st.caption(f"[{m.get('time','')}] {m.get('text','')}")
                            else: st.caption(str(m))
                    else: st.caption("No memos recorded")
                    
                    st.markdown("#### 💬 Final Review")
                    st.write(record['review'])
                    
        else:
            st.caption("👆 Click on a trade in the table above to view details.")
        
        st.write("")
        st.write("")
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("🔄 Start New Trade (to Step 1)"):
                st.session_state.stage = "PRE_TRADING"
                st.session_state.analysis_result = None
                st.session_state.memos = []
                st.rerun()
        
        with c_btn2:
             st.success("✅ Cloud Synced (Supabase)")