import streamlit as st
from datetime import datetime, timedelta, timezone
import pandas as pd
import plotly.express as px
import openai
import os
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

# Session State Initialization
if "stage" not in st.session_state:
    st.session_state.stage = "PRE_TRADING"  # PRE_TRADING, TRADING, POST_TRADING

if "trade_data" not in st.session_state:
    st.session_state.trade_data = {}

if "memos" not in st.session_state:
    st.session_state.memos = []

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "history" not in st.session_state:
    st.session_state.history = []  # "Goldfish" History (Last 20)

if "full_history" not in st.session_state:
    st.session_state.full_history = []  # Full History for Balance Calculation

if "user_id" not in st.session_state:
    st.session_state.user_id = ""

if "is_premium" not in st.session_state:
    st.session_state.is_premium = False

# --- 1. Supabase Helpers ---

@st.cache_resource
def init_supabase():
    """Initialize Supabase Client"""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase Init Error: {e}")
        return None

def optimize_image_high_quality(uploaded_file):
    """Optimize image using Lossless WebP"""
    try:
        image = Image.open(uploaded_file)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        output_io = io.BytesIO()
        # Lossless WebP for original quality with smaller size
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
        
        # [CRITICAL FIX] Ensure pointer is at start and read as bytes
        image_file.seek(0)
        file_bytes = image_file.read()  # Use .read() for safety
        
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
    """
    Fetch ALL data for user_id to calculate correct balance.
    Returns: (full_history, recent_20_history)
    """
    try:
        # Fetch all records for the user, ordered by entry time
        response = supabase.table("trades") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("entry_time", desc=False) \
            .execute()
        
        data = response.data
        
        if not data:
            return [], []

        # Ensure memos are parsed if they came as string (Supabase JSONB comes as dict/list usually, but handling edge cases)
        for row in data:
            if "memos" in row and isinstance(row["memos"], str):
                 try: row["memos"] = ast.literal_eval(row["memos"])
                 except: row["memos"] = []
            # Backfill defaults
            if "strategy_name" not in row or not row["strategy_name"]:
                row["strategy_name"] = "General"
            if "ticker" not in row or not row["ticker"]:
                row["ticker"] = "Unknown"

        full_history = data
        # Goldfish Strategy: Last 20 items
        recent_history = full_history[-20:] if len(full_history) > 20 else full_history
        
        return full_history, recent_history

    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return [], []

def save_trade_to_supabase(supabase: Client, trade_data, user_id):
    try:
        # Construct payload manually to guarantee NO extra keys match schema
        payload = {
            "user_id": str(user_id).strip(),
            "entry_time": trade_data.get("entry_time").isoformat() if isinstance(trade_data.get("entry_time"), datetime) else trade_data.get("entry_time"),
            "exit_time": trade_data.get("exit_time").isoformat() if isinstance(trade_data.get("exit_time"), datetime) else trade_data.get("exit_time"),
            "ticker": trade_data.get("ticker", "Unknown"),
            "strategy_name": trade_data.get("strategy_name", "General"),
            "strategy_detail": trade_data.get("strategy", ""), # Map 'strategy' -> 'strategy_detail'
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
    except:
        return False

def verify_user(supabase: Client, user_id, password):
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).eq("password", password).execute()
        return res.data # Return list of user data
    except:
        return []

def submit_exchange_uid(supabase: Client, user_id, uid):
    try:
        supabase.table("users").update({"exchange_uid": uid}).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"UID Submit Error: {e}")
        return False

# --- 2. Sidebar (User & Settings) ---
with st.sidebar:
    st.header("👤 User Profile")
    
    # [Auth System] Implementation
    if st.session_state.user_id:
        st.success(f"**Welcome, {st.session_state.user_id}!**")
        if st.button("🚪 Logout", type="secondary"):
            st.session_state.user_id = ""
            st.session_state.history = []
            st.session_state.full_history = []
            st.rerun()
    else:
        with st.form("login_form"):
            uid_input = st.text_input("Nickname (ID)", key="login_id").strip()
            pw_input = st.text_input("Password", type="password", key="login_pw").strip()
            
            c1, c2 = st.columns(2)
            with c1:
                btn_login = st.form_submit_button("Login", type="primary")
            with c2:
                btn_register = st.form_submit_button("Register New")

            if btn_login:
                supabase = init_supabase()
                if not uid_input or not pw_input:
                    st.error("Enter ID and Password.")
                else:
                    user_data = verify_user(supabase, uid_input, pw_input)
                    if user_data:
                        # SUCCESS LOGIN
                        st.session_state.user_id = uid_input
                        # Check Premium Status (Default False if key missing)
                        st.session_state.is_premium = user_data[0].get("is_premium", False)
                        
                        # Load Data immediately
                        with st.spinner(f"☁️ Syncing data..."):
                            full, recent = load_data_from_supabase(supabase, uid_input)
                            st.session_state.full_history = full
                            st.session_state.history = recent
                        st.success("Login Success!")
                        st.rerun()
                    else:
                        st.error("Invalid ID or Password.")

            if btn_register:
                supabase = init_supabase()
                if not uid_input or not pw_input:
                    st.error("Enter ID and Password.")
                else:
                    if check_user_exists(supabase, uid_input):
                        st.error("User ID already exists. Try logging in.")
                    else:
                        if register_user(supabase, uid_input, pw_input):
                            # SUCCESS REGISTER
                            st.session_state.user_id = uid_input
                            st.session_state.full_history = []
                            st.session_state.history = []
                            st.success("Registered & Logged in!")
                            st.rerun()
                        else:
                            st.error("Registration failed.")
        
    st.divider()
    
    if st.session_state.user_id:
        st.header("⚙️ Settings")
        
        # Unlock Full Access (UID Submission)
        # Show ONLY if Premium (Badge) OR if User hit the limit (Input Form)
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
    
    # [Conditional] Only show Goldfish Banner if trades >= 18
    # [Conditional] Only show Goldfish Banner if trades >= 18 and NOT premium
    is_premium = st.session_state.get("is_premium", False)
    if (len(st.session_state.full_history) >= 18) and (not is_premium):
        st.info("🟢 **Displaying recent 20 trades only.\n(Unlimited history is saved securely)")
    
    st.markdown("---") # Divider
    
    # [Smart Logic] 유저 상태에 따라 멘트와 색상 변경
    # 1. 기록이 20개 넘어서 잠긴 사람 -> "Unlock" 강조 (빨간맛/보라맛)
    # 2. 아직 널널한 사람 -> "Community" 강조 (파란맛/편안함)
    
    is_premium = st.session_state.get("is_premium", False)
    is_locked_user = (len(st.session_state.full_history) > 20) and (not is_premium)
    discord_link_sidebar = "https://discord.gg/QRZAh6Zj" # 형님 초대 링크

    if is_locked_user:
        # [Case A] 잠긴 유저 (Unlock 유도)
        btn_text = "🔓 Unlock Full Access"
        btn_sub = "Recover your archives"
        btn_color = "#FF4B4B" # 빨간색 (경고/주목)
        hover_color = "#D93A3A"
    else:
        # [Case B] 일반 유저 (커뮤니티 홍보)
        btn_text = "💬 Join Community"
        btn_sub = "Share strategies & chat"
        btn_color = "#5865F2" # 디스코드 근본 보라색
        hover_color = "#4752C4"

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
            " onmouseover="this.style.backgroundColor='{hover_color}'; this.style.transform='translateY(-2px)';" 
              onmouseout="this.style.backgroundColor='{btn_color}'; this.style.transform='translateY(0px)';">
                <div style="font-weight: bold; font-size: 16px;">{btn_text}</div>
                <div style="font-size: 11px; opacity: 0.9; margin-top: 2px;">{btn_sub}</div>
            </div>
        </a>
    """, unsafe_allow_html=True)
    
    # [Crucial] Gate the Main Pipeline at the VERY END of Sidebar
    if not st.session_state.user_id:
        st.info("🔒 Please Login/Register to access your dashboard.")
        st.stop()

# --- 3. Main Pipeline ---
st.title("📊 Trading Dashboard")

# [Step 1] Preparation
if st.session_state.stage == "PRE_TRADING":
    st.subheader("STEP 1: Preparation")
    
    # [Conditional] Only show Warning if trades >= 18
    if len(st.session_state.full_history) >= 18:
        st.warning("🟢 **Showing recent 20 trades only.(Unlimited inputs are saved safely).**")

    # Analytics Shortcut
    if st.button("📊 View Performance Analytics (Skip to Dashboard)"):
        st.session_state.stage = "ANALYTICS"
        st.rerun()

    # Init Supabase
    supabase = init_supabase()
    
    # Auto-load if empty
    if not st.session_state.full_history and supabase and st.session_state.user_id:
        with st.spinner(f"☁️ Syncing data for '{st.session_state.user_id}'..."):
            full, recent = load_data_from_supabase(supabase, st.session_state.user_id)
            if full:
                st.session_state.full_history = full
                st.session_state.history = recent
                st.success(f"✅ Synced: {len(full)} total trades (Showing last {len(recent)}).")
            else:
                st.warning("No trade history found.")
    elif st.session_state.history:
        st.success(f"✅ Ready: Showing recent {len(st.session_state.history)} trades.")
        if st.button("🔄 Force Resync"):
             st.session_state.full_history = []
             st.session_state.history = []
             st.rerun()
    
    st.divider()
    
    with st.form("pre_trading_form"):
        # Calculate Start Balance from Full History
        default_balance = 0.0
        if st.session_state.full_history:
            default_balance = st.session_state.full_history[-1].get("final_balance", 0.0)
        
        start_balance = st.number_input("Start Balance ($)", min_value=0.0, step=100.0, value=float(default_balance))
        
        # Ticker Selection
        existing_tickers = sorted(list(set([str(h.get('ticker', 'Unknown')) for h in st.session_state.full_history]))) if st.session_state.full_history else []
        ticker_option = st.selectbox("Ticker / Asset", ["Create New..."] + existing_tickers)
        
        if ticker_option == "Create New...":
            ticker_input = st.text_input("Enter New Ticker", placeholder="e.g. BTCUSDT").upper()
        else:
            ticker_input = ticker_option

        # Strategy Selection
        existing_strategies = list(set([str(h.get('strategy_name', 'General')) for h in st.session_state.full_history])) if st.session_state.full_history else []
        if "General" not in existing_strategies:
            existing_strategies.append("General")
            
        strategy_option = st.selectbox("Strategy Name (Tag)", ["Create New..."] + sorted([str(x) for x in existing_strategies]))
        
        if strategy_option == "Create New...":
            strategy_name = st.text_input("Enter New Strategy Name", placeholder="e.g. Trend Breakout")
        else:
            strategy_name = strategy_option
            
        strategy_detail = st.text_area("Strategy Details (Setup, Entry, Exit)", height=150, placeholder="Ex: BTC 15m trend breakout long. Stop -1.5%, Target +3%")
        mood = st.selectbox("Psychological State", ["Calm", "Confident", "Anxious", "FOMO", "Revenge", "Bored"])
        
        submitted = st.form_submit_button("🚀 Start Trading")
        
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
                    "entry_time": datetime.now(),
                    "entry_time_str": datetime.now().strftime("%H:%M:%S")
                }
                st.session_state.stage = "TRADING"
                st.session_state.analysis_result = None
                st.session_state.memos = [] 
                st.rerun()

# [Step 2] Live Trading
elif st.session_state.stage == "TRADING":
    st.subheader("STEP 2: Live Trading")
    
    data = st.session_state.trade_data
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Entry Time", data["entry_time_str"])
    with col2:
        st.metric("Start Balance", f"${data['start_balance']:,.0f}")
    with col3:
        st.metric("Mood", data["mood"])
    
    st.divider()
    
    st.markdown(f"### 📜 My Strategy: {data['strategy_name']}")
    st.info(data["strategy"])
    
    st.warning("🚨 **NO IMPULSIVE TRADING**: Stick to your plan. Emotional trading is the fastest way to blow up your account.")
    
    st.write("")
    
    # Real-time Memo
    st.markdown("### 📝 Real-time Thoughts & Memos")
    
    with st.form(key="memo_form", clear_on_submit=True):
        memo_text = st.text_input("Record your thoughts...", key="memo_input_field")
        submit_memo = st.form_submit_button("Add Memo")
        
        if submit_memo and memo_text:
            now_str = datetime.now().strftime("%H:%M:%S")
            if "memos" not in st.session_state: st.session_state.memos = [] 
            st.session_state.memos.append({"time": now_str, "text": memo_text})
            st.rerun()

    if st.session_state.memos:
        for memo in reversed(st.session_state.memos):
            st.caption(f"[{memo['time']}] {memo['text']}")
    
    st.write("")
    st.write("")
    
    c_end1, c_end2 = st.columns(2)
    with c_end1:
        if st.button("⬅️ Back to Step 1"):
            st.session_state.stage = "PRE_TRADING"
            st.rerun()
    with c_end2:
        if st.button("🏁 End Trade", type="primary"):
            st.session_state.trade_data["exit_time"] = datetime.now()
            st.session_state.trade_data["exit_time_str"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.trade_data["memos"] = st.session_state.memos
            st.session_state.stage = "POST_TRADING"
            st.rerun()

# [Step 3] Review & Result
elif st.session_state.stage == "POST_TRADING":
    st.subheader("STEP 3: Review & Save")
    
    if st.button("⬅️ Back to Trading"):
        st.session_state.stage = "TRADING"
        st.session_state.trade_data.pop("exit_time", None) 
        st.rerun()
    
    data = st.session_state.trade_data
    
    # Duration Calc
    entry_dt = data["entry_time"]
    exit_dt = data["exit_time"]
    
    if isinstance(entry_dt, str):
        try: entry_dt = datetime.fromisoformat(entry_dt)
        except: entry_dt = datetime.now()
        
    if isinstance(exit_dt, str):
        try: exit_dt = datetime.fromisoformat(exit_dt)
        except: exit_dt = datetime.now()

    duration = exit_dt - entry_dt
    minutes_duration = duration.total_seconds() / 60
    minutes = divmod(duration.seconds, 60)[0]
    hours = divmod(duration.seconds, 3600)[0]
    time_display = f"{minutes}m" if hours == 0 else f"{hours}h {minutes}m"
    
    st.success(f"Trade Ended. (Duration: {time_display})")
    
    if st.session_state.analysis_result is None:
        
        final_balance = st.number_input("Final Balance ($)", min_value=0.0, step=100.0, value=float(data['start_balance']))
        
        temp_profit = final_balance - data['start_balance']
        default_index = 1 # Break-even
        if temp_profit > 0: default_index = 0 # Win
        elif temp_profit < 0: default_index = 2 # Loss
            
        result_status_option = st.radio(
            "Trade Result (Auto)",
            ["Win", "Break-even", "Loss"],
            index=default_index,
            horizontal=True
        )
        result_status = result_status_option
 
        review = st.text_area("Trade Review (What went well/wrong)", height=150, placeholder="Ex: Followed plan well / Emotionally chased prize")
        satisfaction = st.slider("Satisfaction Score", 1, 10, 5)
        
        uploaded_file = st.file_uploader("📷 Upload Chart Screenshot (Optional)", type=['png', 'jpg', 'jpeg', 'webp'])
        if uploaded_file is not None:
            st.image(uploaded_file, caption="Preview", use_container_width=True)
        
        submit_review = st.button("💾 Save", type="primary")

        if submit_review:
            supabase = init_supabase()
            
            # 1. Image Upload
            chart_url = ""
            if uploaded_file is not None:
                if supabase:
                    with st.spinner("Optimizing & Uploading to Supabase..."):
                        try:
                            # Optimize
                            optimized_io = optimize_image_high_quality(uploaded_file)
                            if optimized_io:
                                # Upload
                                start_t = datetime.now()
                                url = upload_image_to_supabase(supabase, optimized_io, bucket_name="trade_images")
                                if url:
                                    chart_url = url
                                    st.success(f"✅ Image Uploaded! (Quality: 100% Lossless WebP)")
                                else:
                                    st.error("Upload failed.")
                            else:
                                st.error("Optimization failed.")
                        except Exception as e:
                            st.error(f"Image Process Error: {e}")
                else:
                    st.error("Supabase not connected.")

            # 2. Data Update
            profit = final_balance - data['start_balance']
            roi = (profit / data['start_balance'] * 100) if data['start_balance'] > 0 else 0
            
            st.session_state.trade_data.update({
                "final_balance": final_balance,
                "profit": profit,
                "roi": roi,
                "result_status": result_status,
                "review": review,
                "satisfaction": satisfaction,
                "memos": st.session_state.memos,
                "chart_url": chart_url,
                "duration_minutes": minutes_duration
            })
            
            # 3. Save to Supabase
            if supabase:
                with st.spinner("Saving to Database..."):
                    success = save_trade_to_supabase(supabase, st.session_state.trade_data, st.session_state.user_id)
                    if success:
                        # Re-fetch
                        with st.spinner("🔄 Syncing latest data..."):
                            full, recent = load_data_from_supabase(supabase, st.session_state.user_id)
                            st.session_state.full_history = full
                            st.session_state.history = recent
                            
                        st.success("✅ Trade saved!")
                        st.session_state.stage = "ANALYTICS" 
                        st.rerun()
            else:
                 st.error("Database connection missing.")

            # 4. Generate AI Feedback (Optional)
            ai_feedback = "API Key not set."
            if openai.api_key:
                try:
                    memo_str = "\n".join([f"- {m['time']} {m['text']}" for m in st.session_state.memos]) if st.session_state.memos else "None"
                    
                    prompt = f"""
                    [Trade Data]
                    Strategy: {data['strategy_name']}
                    Result: {result_status} (${profit:,.0f}, {roi:.2f}%)
                    Review: {review}
                    Memos: {memo_str}
                    
                    Provide 3-line concise feedback in Korean.
                    """
                    
                    with st.spinner("AI Coach Analyzing..."):
                        response = openai.chat.completions.create(
                            model="gpt-4",
                            messages=[{"role": "system", "content": "You are a pro trader coach."}, {"role": "user", "content": prompt}]
                        )
                        ai_feedback = response.choices[0].message.content
                except Exception as e:
                    ai_feedback = f"AI Error: {e}"
            
            st.session_state.analysis_result = ai_feedback
            st.rerun()

    else:
        # Result Summary
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
    
    # [Conditional] Only show Warning if trades >= 15
    if len(st.session_state.full_history) >= 15:
        st.warning("🟢 **Showing analysis for recent 20 trades only.**")
    
    # [Mod] "Tantalizing Data Lock" Implementation
    # 1. Use Full History for Table (with Locks)
    # 2. Use Recent 20 for Analytics (Charts/Metrics)
    
    full_data = st.session_state.full_history if st.session_state.full_history else []
    
    if not full_data:
        st.info("No trade records found yet.")
        if st.button("Go Back"):
            st.session_state.stage = "PRE_TRADING"
            st.rerun()
    else:
        # Prepare Dataframes
        df_all = pd.DataFrame(full_data)
        
        # Preprocessing on df_all
        df_all['datetime_obj'] = pd.to_datetime(df_all['entry_time'], utc=True)
        df_all['date_str'] = df_all['datetime_obj'].dt.strftime('%m/%d')
        
        # Defaults
        if 'strategy_name' not in df_all.columns: df_all['strategy_name'] = "General"
        df_all['strategy_name'] = df_all['strategy_name'].fillna("General")
        
        if 'ticker' not in df_all.columns: df_all['ticker'] = "Unknown"
        df_all['ticker'] = df_all['ticker'].fillna("Unknown").astype(str)
        
        # Defaults
        if "profit" not in df_all.columns: df_all['profit'] = 0.0
        if "roi" not in df_all.columns: df_all['roi'] = 0.0
        
        # Identify Locked Rows (Older than recent 20)
        # Rule: If Premium, NOTHING is locked.
        is_premium = st.session_state.get('is_premium', False)
        
        total_count = len(df_all)
        recent_limit = 20
        df_all['is_locked'] = False
        
        if (not is_premium) and (total_count > recent_limit):
             df_all.loc[:total_count-recent_limit-1, 'is_locked'] = True
        
        # Create Analytics Subset
        # Premium -> All Time capable (Default recent 20? No, let's allow all for now, or just follow filters)
        if is_premium:
             df_analytics = df_all.copy()
        else:
             df_analytics = df_all.iloc[-recent_limit:].copy()
        
        # ---------------------------------------------------------
        # [UI] Grid Layout
        # ---------------------------------------------------------
        
        # --- ROW 1: Top Section (Split 1:1) ---
        top_left, top_right = st.columns([1, 1], gap="medium")
        
        with top_left:
            st.markdown("##### ⚙️ Filters & Metrics (Recent 20)")
            
            # 1. Filters (Applied to Analytics DF primarily)
            # 1. Filters (Applied to Analytics DF primarily)
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
        
            # Apply Filters to Analytics DF
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
            # "All Time" and "Last 30 Trades" just use the available recent 20 (since default is recent 20)

            if df_filtered.empty:
                st.caption("No recent trades match filters.")
                
            # Metrics Calculation (Based on Filtered Recent 20)
            total_profit = df_filtered['profit'].sum()
            
            # [CRITICAL] Real Total Balance from Full History (Always valid)
            real_current_balance = 0.0
            if not df_all.empty:
                real_current_balance = df_all.iloc[-1]['final_balance']

            win_count = len(df_filtered[df_filtered['profit'] > 0])
            total_count_filtered = len(df_filtered)
            win_rate = (win_count / total_count_filtered * 100) if total_count_filtered > 0 else 0
            avg_holding = df_filtered['duration_minutes'].mean() if 'duration_minutes' in df_filtered.columns else 0

            # Metrics Layout
            m_r1_c1, m_r1_c2, m_r1_c3 = st.columns(3)
            with m_r1_c1:
                m_r1_c1.metric("💰 Current Balance", f"${real_current_balance:,.0f}", help="Total Account Balance")
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
                m_r1_c3.metric(f"📈 Win Rate", f"{win_rate:.1f}%")
            
            st.write("")
            
            # Row 2 Metrics
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
            # Use original date string
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
        
        # --- ROW 2: Middle Analysis (Same as before, using df_filtered) ---
        col_mid1, col_mid2, col_mid3 = st.columns(3)
        # (Using df_filtered for these charts ensures consistency with Goldfish logic)
        
        # 1. Time Edge
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

        # 2. Win/Loss Pie
        with col_mid2:
            st.markdown("###### 📊 Win/Loss")
            win_loss_df = df_filtered['result_status'].value_counts().reset_index()
            win_loss_df.columns = ['Result', 'Count']
            fig_pie = px.pie(win_loss_df, values='Count', names='Result', color='Result', hole=0.5,
                             color_discrete_map={'Win':COLOR_WIN, 'Loss':COLOR_LOSS, 'Break-even':COLOR_BE})
            fig_pie.update_layout(showlegend=False, height=300, margin=dict(t=10, b=10, l=10, r=10))
            fig_pie.update_traces(textinfo='percent+label', textposition='inside',textfont_color='white')
            st.plotly_chart(fig_pie, use_container_width=True)

        # 3. R:R Bar
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
        
        # ---------------------------------------------------------
        # [UI] Table with Tantalizing Locks
        # ---------------------------------------------------------
        st.markdown("### 📋 Trade History (Full History)")
        st.caption("Older trades are locked to save space & focus on current performance.")
        
        # Prepare Table Data (Clone Full Data)
        df_table = df_all.copy()
        
        # Sorting (Newest First for Table)
        df_table = df_table.sort_values('entry_time', ascending=False).reset_index(drop=True)
        # Need to re-assess 'is_locked' logic because we sorted it inside the Table View
        # Actually easier to use the original logic:
        # If we sort Descending, Locked rows are indices >= 20. (Since 0..19 are the newest 20)
        
        df_table['is_locked'] = False
        is_premium = st.session_state.get('is_premium', False)
        
        # Only Lock IF (Not Premium) AND (Count > 20)
        if (not is_premium) and (len(df_table) > 20):
            df_table.loc[20:, 'is_locked'] = True # Rows 20 onwards are locked
            
        # Apply MASKING
        # We need a display version separate from logic version to keep 'is_locked' column
        # but masking values
        
        if 'strategy_detail' in df_table.columns: df_table['Detail'] = df_table['strategy_detail']
        elif 'strategy' in df_table.columns: df_table['Detail'] = df_table['strategy']
        else: df_table['Detail'] = ""
        
        # Masking Loop
        # Masking Loop
        for idx in df_table.index:
            if df_table.loc[idx, 'is_locked']:
                df_table.loc[idx, 'ticker'] = "🔒 Locked"
                df_table.loc[idx, 'strategy_name'] = "****"
                df_table.loc[idx, 'result_status'] = "Locked"
                df_table.loc[idx, 'profit'] = 0.0
                df_table.loc[idx, 'roi'] = 0.0
                df_table.loc[idx, 'mood'] = "🔒"
                df_table.loc[idx, 'Detail'] = "Contact us to unlock your full history."
        
        # [Modified] Apply Filters to Table
        # Rule: Locked rows (is_locked=True) should persist even if they don't match the Strategy Filter.
        # (They act as "Footer" to remind users of missing data)

        if strategy_filter:
            # Keep row IF (Strategy matches selection) OR (Row is locked)
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
        
        # Styling
        # Styling function (수정됨)
        def color_result(val):
            # 1. 0이거나 잠긴 데이터는 회색
            if val == 'Locked' or val == 0.0 or val == 0: 
                return 'color: #888'
            
            try:
                # 2. 문자열($ , %) 제거 후 실수형 변환
                # (기존 isdigit은 '-' 부호를 인식 못해서 삭제함)
                text = str(val).replace('$', '').replace(',', '').replace('%', '')
                val_num = float(text)
                
                # 3. 색상 반환
                if val_num > 0:
                    return f'color: {COLOR_WIN}'
                elif val_num < 0:
                    return f'color: {COLOR_LOSS}' # 여기가 파란색 적용됨
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
        
        # Interactive Table
        event = st.dataframe(
            styled_df, 
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        st.divider()
        
        # Selection Logic
        if len(event.selection.rows) > 0:
            selected_row_idx = event.selection.rows[0]
            # Get the record from the SORTED df_table (Descending by date)
            record = df_table.iloc[selected_row_idx]
            
            # Check Lock Status
            if record['is_locked']:
                with st.container():
                     st.warning("🔒 **Archived Trade Locked**")
                     st.info("To unlock your full history and support us via a partner link, please contact us through the button below.")
                     
                     # [Modified] Custom Discord Button (HTML/CSS)
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
                                💬 Join Discord to Unlock
                            </div>
                        </a>
                    """, unsafe_allow_html=True)
            else:
                # Normal Detail View
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