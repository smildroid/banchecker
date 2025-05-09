import streamlit as st
import requests
import time
from datetime import datetime
from threading import Thread
from streamlit.components.v1 import html

# Custom CSS for styling
def inject_custom_css():
    st.markdown("""
    <style>
        .main {
            background-color: #0E1117;
        }
        .sidebar .sidebar-content {
            background-color: #1a1a1a;
        }
        h1 {
            color: #ff4b4b;
            border-bottom: 2px solid #ff4b4b;
        }
        .stExpander {
            background: #1a1a1a;
            border-radius: 8px;
            border: 1px solid #333;
        }
        .stAlert {
            border-radius: 8px;
        }
        .banned-badge {
            color: white;
            background: #ff4b4b;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
        }
        .clean-badge {
            color: white;
            background: #00cc66;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
        }
        .avatar-img {
            border-radius: 8px;
            border: 2px solid #333;
        }
    </style>
    """, unsafe_allow_html=True)

def check_bans(api_key, webhook, steam_ids, ban_history):
    results = []
    for sid in steam_ids:
        try:
            # Get ban info
            ban_response = requests.get(
                "https://api.steampowered.com/ISteamUser/GetPlayerBans/v1/",
                params={"key": api_key, "steamids": sid},
                timeout=10
            ).json()
            
            # Get profile info
            profile_response = requests.get(
                "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                params={"key": api_key, "steamids": sid},
                timeout=10
            ).json()
            
            # Process responses
            profile_data = profile_response.get("response", {}).get("players", [{}])[0]
            ban_data = ban_response.get("players", [{}])[0]
            
            result = {
                "steamid": sid,
                "username": profile_data.get("personaname", "Unknown"),
                "avatar": profile_data.get("avatarfull", "https://steamuserimages-a.akamaihd.net/ugc/885384897182110030/1D7D1D7D1D7D1D7D1D7D1D7D1D7D1D7D/"),
                "profile_url": profile_data.get("profileurl", f"https://steamcommunity.com/profiles/{sid}"),
                "vac": ban_data.get("VACBanned", False),
                "game_bans": ban_data.get("NumberOfGameBans", 0),
                "community": ban_data.get("CommunityBanned", False),
                "last_ban_days": ban_data.get("DaysSinceLastBan", 0),
                "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "new_ban": False
            }
            
            # Check ban history
            prev_status = ban_history.get(sid, {})
            if any([result["vac"], result["game_bans"] > 0, result["community"]]):
                if not prev_status or (prev_status.get("vac") != result["vac"] or 
                                    prev_status.get("game_bans") != result["game_bans"] or 
                                    prev_status.get("community") != result["community"]):
                    result["new_ban"] = True
                    send_discord_alert(webhook, result)
            
            ban_history[sid] = result
            results.append(result)
            
        except Exception as e:
            st.error(f"Error checking {sid}: {str(e)}")
    
    return results

def send_discord_alert(webhook, result):
    if not webhook:
        return
    
    ban_types = []
    if result["vac"]: ban_types.append("VAC")
    if result["community"]: ban_types.append("Community")
    if result["game_bans"] > 0: ban_types.append(f"Game ({result['game_bans']})")
    
    embed = {
        "title": "🚨 Steam Ban Detected",
        "color": 16711680,
        "thumbnail": {"url": result["avatar"]},
        "fields": [
            {"name": "Account", "value": f"[{result['username']}]({result['profile_url']})", "inline": True},
            {"name": "SteamID", "value": result["steamid"], "inline": True},
            {"name": "Ban Types", "value": " | ".join(ban_types) if ban_types else "None", "inline": False},
            {"name": "Last Ban", "value": f"{result['last_ban_days']} days ago", "inline": True},
            {"name": "Checked At", "value": result["last_checked"], "inline": True}
        ],
        "footer": {"text": "Steam Ban Checker • Real-time Monitoring"}
    }
    
    try:
        requests.post(webhook, json={"embeds": [embed]})
    except Exception as e:
        st.error(f"Failed to send Discord notification: {e}")

def automatic_checker(api_key, webhook, steam_ids, interval, ban_history):
    while st.session_state.automatic_running:
        check_bans(api_key, webhook, steam_ids, ban_history)
        time.sleep(interval * 60)

def main():
    inject_custom_css()
    
    st.set_page_config(
        page_title="Steam Ban Monitor",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    if 'ban_history' not in st.session_state:
        st.session_state.ban_history = {}
    if 'automatic_running' not in st.session_state:
        st.session_state.automatic_running = False
    
    # Sidebar Configuration
    with st.sidebar:
        st.title("⚙️ Configuration")
        api_key = st.text_input("Steam API Key:", type="password", help="Get from https://steamcommunity.com/dev")
        webhook = st.text_input("Discord Webhook URL:", help="Optional for ban notifications")
        
        st.divider()
        
        st.header("🔄 Automatic Checking")
        auto_check = st.checkbox("Enable Scheduled Checks")
        if auto_check:
            check_interval = st.slider("Check Interval (minutes):", 1, 360, 60)
            
            if st.button("▶️ Start Monitoring" if not st.session_state.automatic_running else "⏹️ Stop Monitoring"):
                st.session_state.automatic_running = not st.session_state.automatic_running
                if st.session_state.automatic_running:
                    Thread(target=automatic_checker, args=(
                        api_key, webhook, 
                        st.session_state.get('tracked_ids', []), 
                        check_interval, 
                        st.session_state.ban_history
                    )).start()
    
    # Main Interface
    st.title("🛡️ Steam Account Monitor")
    st.caption("Track VAC, Game, and Community bans in real-time")
    
    # Input Section
    with st.container():
        steam_ids_input = st.text_area(
            "📥 Enter Steam64 IDs (separate by commas or new lines):",
            height=150,
            placeholder="76561197960287930, 76561197960287931\n76561197960287932",
            help="Paste Steam64 IDs separated by commas or new lines"
        )
        
        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("🔍 Check Now", use_container_width=True):
                st.session_state.tracked_ids = process_ids(steam_ids_input)
        with col2:
            if st.session_state.get('tracked_ids'):
                st.success(f"Tracking {len(st.session_state.tracked_ids)} accounts")
    
    # Results Display
    if st.session_state.get('tracked_ids') and api_key:
        results = check_bans(api_key, webhook, st.session_state.tracked_ids, st.session_state.ban_history)
        
        for res in results:
            with st.expander(f"{res['username']} ({res['steamid']})", expanded=res['new_ban']):
                col1, col2 = st.columns([1, 4])
                
                with col1:
                    st.image(res["avatar"], use_column_width=True, output_format="PNG", 
                            caption=f"Last checked: {res['last_checked']}")
                
                with col2:
                    st.markdown(f"""
                    **Account Status**
                    - **VAC Banned:** `{"🔴 Yes" if res["vac"] else "🟢 No"}`
                    - **Game Bans:** `{"⚠️" * res["game_bans"]} ({res['game_bans']})`
                    - **Community Banned:** `{"🔴 Yes" if res["community"] else "🟢 No"}`
                    - **Days Since Last Ban:** `{res['last_ban_days'] or 'Never'}`
                    """)
                    
                    st.markdown(f"🔗 [Steam Profile]({res['profile_url']})")
                    
                    if res["new_ban"]:
                        st.error("🚨 NEW BAN DETECTED!")
                    elif any([res["vac"], res["community"], res["game_bans"] > 0]):
                        st.warning("Account has existing bans")
                    else:
                        st.success("No bans detected")

def process_ids(input_text):
    return [sid.strip() for sid in input_text.replace('\n', ',').split(',') if sid.strip().isdigit()]

if __name__ == "__main__":
    main()
