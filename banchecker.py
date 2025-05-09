import streamlit as st
import requests
from datetime import datetime
from PIL import Image
from io import BytesIO
import re
import threading
import time

st.set_page_config(
    page_title="🔪️ am I cooked?",
    page_icon="👩‍🍳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------
# Initialize session state variables
# ---------------------------
if "log" not in st.session_state:
    st.session_state.log = []
if "show_log" not in st.session_state:
    st.session_state.show_log = False
if "auto_monitor_thread_started" not in st.session_state:
    st.session_state.auto_monitor_thread_started = False
if "auto_monitor" not in st.session_state:
    st.session_state.auto_monitor = False
if "monitor_interval" not in st.session_state:
    st.session_state.monitor_interval = 30  # default to 30 minutes
if "sent_notifications" not in st.session_state:
    st.session_state.sent_notifications = {}  # to prevent duplicate alerts
if "last_auto_monitor_status" not in st.session_state:
    st.session_state.last_auto_monitor_status = st.session_state.auto_monitor

# ---------------------------
# Helper function: add log messages
# ---------------------------
def add_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.log.append(f"{timestamp} - {message}")

# ---------------------------
# Custom CSS for styling
# ---------------------------
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
                margin-bottom: 0.5em;
            }
            .avatar-img {
                border-radius: 8px;
                border: 2px solid #333;
            }
            .stAlert {
                border-radius: 8px;
            }
            /* Help links: on the same row as the input label */
            .help-link {
                font-size: 12px;
                margin: 0;
                padding-top: 8px;
            }
            /* Compact text styling */
            .compact-text {
                font-size: 0.9em;
                line-height: 1.2;
            }
            /* Small jobs link styling */
            .jobs-link {
                font-size: 8px;
                text-align: center;
                color: #aaa;
            }
        </style>
    """, unsafe_allow_html=True)

# ---------------------------
# Discord webhook alert function
# ---------------------------
def send_discord_alert(webhook, result):
    if not webhook:
        return
    ban_types = []
    if result["vac"]:
        ban_types.append("VAC")
    if result["community"]:
        ban_types.append("Community")
    if result["game_bans"] > 0:
        ban_types.append(f"Game ({result['game_bans']})")
    
    embed = {
        "title": "🚨 Steam Ban Detected",
        "color": 16711680,
        "thumbnail": {"url": result["avatar"]},
        "fields": [
            {"name": "Account", "value": f"[{result['username']}]({result['profile_url']})", "inline": True},
            {"name": "SteamID", "value": result["steamid"], "inline": True},
            {"name": "Ban Types", "value": " | ".join(ban_types) if ban_types else "None", "inline": False},
            {"name": "Last Ban", "value": (f"{result['last_ban_days']} days ago" if result["last_ban_days"] > 0 else "Never"), "inline": True},
            {"name": "Checked At", "value": result["last_checked"], "inline": True}
        ],
        "footer": {"text": "Steam Ban Checker • Real-time Monitoring"}
    }
    try:
        requests.post(webhook, json={"embeds": [embed]})
        add_log(f"Discord alert sent for {result['username']} ({result['steamid']}).")
    except Exception as e:
        st.error(f"Failed to send Discord notification: {e}")
        add_log(f"Failed to send Discord alert for {result['username']} ({result['steamid']}): {e}")

# ---------------------------
# Function to check bans for each Steam64 ID
# ---------------------------
def check_bans(api_key, webhook, steam_ids):
    results = []
    for sid in steam_ids:
        try:
            add_log(f"Checking bans for {sid}.")
            ban_response = requests.get(
                "https://api.steampowered.com/ISteamUser/GetPlayerBans/v1/",
                params={"key": api_key, "steamids": sid},
                timeout=10
            ).json()
            profile_response = requests.get(
                "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                params={"key": api_key, "steamids": sid},
                timeout=10
            ).json()
            profile_data = profile_response.get("response", {}).get("players", [{}])[0]
            ban_data = ban_response.get("players", [{}])[0]
            registration_date = "Unknown"
            if "timecreated" in profile_data and profile_data["timecreated"]:
                registration_date = datetime.fromtimestamp(profile_data["timecreated"]).strftime("%Y-%m-%d")
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
                "registration_date": registration_date
            }
            current_state = (result["vac"], result["game_bans"], result["community"])
            previous_state = st.session_state.sent_notifications.get(sid)
            if webhook and (result["vac"] or result["game_bans"] > 0 or result["community"]):
                if previous_state is None or previous_state != current_state:
                    send_discord_alert(webhook, result)
                    st.session_state.sent_notifications[sid] = current_state
                else:
                    add_log(f"Notification already sent for {sid}, skipping duplicate.")
            add_log(f"Finished checking {sid}.")
            results.append(result)
        except Exception as e:
            err = f"Error checking {sid}: {e}"
            st.error(err)
            add_log(err)
    return results

# ---------------------------
# Process Steam64 IDs input (regex: sequences of 15+ digits)
# ---------------------------
def process_ids(input_text):
    ids = re.findall(r'\d{15,}', input_text)
    return ids

# ---------------------------
# Automatic monitoring function (runs in a background thread)
# ---------------------------
def auto_monitor():
    while st.session_state.get("auto_monitor", False):
        api_key_local = st.session_state.get("api_key_input")
        webhook_local = st.session_state.get("webhook_input")
        interval = st.session_state.get("monitor_interval", 30)
        steam_ids_text = st.session_state.get("steam_ids_input", "")
        steam_ids = process_ids(steam_ids_text)
        if steam_ids and api_key_local:
            add_log(f"Auto-monitor: Monitoring {len(steam_ids)} entered IDs.")
            add_log("Auto-monitor: Starting cycle.")
            results = check_bans(api_key_local, webhook_local, steam_ids)
            add_log(f"Auto-monitor: Cycle complete. Checked {len(results)} accounts.")
        else:
            add_log("Auto-monitor: Missing API key or Steam IDs; skipping cycle.")
        time.sleep(interval * 60)

# ---------------------------
# Main application
# ---------------------------
def main():
    inject_custom_css()
    
    with st.sidebar:
        st.title("⚙️ Configuration")
        # Steam API key and help link on one row
        col_api, col_api_help = st.columns([4, 1])
        with col_api:
            api_key = st.text_input("Steam API Key:", type="password", key="api_key_input")
        with col_api_help:
            st.markdown("[Fetch](https://steamcommunity.com/dev)", unsafe_allow_html=True)
        
        # Discord webhook and help link on one row
        col_webhook, col_webhook_help = st.columns([4, 1])
        with col_webhook:
            webhook = st.text_input("Discord Webhook URL (optional):", key="webhook_input")
        with col_webhook_help:
            st.markdown("[Guide](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)", unsafe_allow_html=True)
        
        st.markdown("<small style='color: #AAA;'>This tool doesn't store any API keys or user data. All inputs are session-only.</small>", unsafe_allow_html=True)
        st.image("https://i.imgur.com/jZsExFB.jpeg", use_container_width=True)
        # Insert the new hyperlink directly under the image with no extra space
        st.markdown("<div class='jobs-link' style='margin: 0; padding: 0; text-align: center;'><a href='https://jobs.mchire.com/' target='_blank'>put the fries in the bag</a></div>", unsafe_allow_html=True)
        
        st.checkbox("Enable Automatic Monitoring", key="auto_monitor")
        # Check if auto-monitor checkbox state has changed; log a message if so.
        if st.session_state.get("auto_monitor") != st.session_state.get("last_auto_monitor_status"):
            if st.session_state.get("auto_monitor"):
                add_log("Auto-monitor enabled.")
            else:
                add_log("Auto-monitor disabled.")
            st.session_state.last_auto_monitor_status = st.session_state.get("auto_monitor")
            
        if st.session_state.get("auto_monitor", False):
            st.slider("Monitoring Interval (minutes):", 5, 360, 30, key="monitor_interval")
            if not st.session_state.get("auto_monitor_thread_started", False):
                thread = threading.Thread(target=auto_monitor, daemon=True)
                thread.start()
                st.session_state.auto_monitor_thread_started = True

    st.title("🛡️ Steam Account Monitor")
    placeholder_text = ("Example:\n76561197960287930\n76561197960287931, 76561197960287932\nhttps://steamcommunity.com/profiles/76561197960287930")
    steam_ids_input = st.text_area("📥 Enter Steam64 IDs:", height=150, key="steam_ids_input", placeholder=placeholder_text)
    
    col1, col2 = st.columns([1, 1])
    if col1.button("🔍 Check Now", key="check_now_button"):
        add_log("Manual check triggered.")
        steam_ids = process_ids(steam_ids_input)
        results = []
        if steam_ids and st.session_state.get("api_key_input"):
            results = check_bans(st.session_state.get("api_key_input"), st.session_state.get("webhook_input"), steam_ids)
        total_loaded = len(results)
        total_banned = sum(1 for r in results if r["vac"] or r["game_bans"] > 0 or r["community"])
        st.markdown(f"**Accounts Loaded:** {total_loaded} | **Accounts Banned:** {total_banned}")
        for res in results:
            with st.expander(f"{res['username']} ({res['steamid']})"):
                col_img, col_info = st.columns([1, 5])
                with col_img:
                    try:
                        response = requests.get(res["avatar"])
                        img = Image.open(BytesIO(response.content))
                        img_small = img.resize((80, 80))
                    except Exception as e:
                        st.error(f"Error processing avatar image: {e}")
                        img_small = None
                    if img_small:
                        st.image(img_small, width=80, output_format="PNG")
                with col_info:
                    vac_status = "🔴 Yes" if res["vac"] else "🟢 No"
                    game_status = "🔴 Yes" if res["game_bans"] > 0 else "🟢 No"
                    community_status = "🔴 Yes" if res["community"] else "🟢 No"
                    last_ban_str = f"{res['last_ban_days']} days ago" if res["last_ban_days"] > 0 else "Never"
                    summary = (f"**Status:** VAC: {vac_status} | Game: {game_status} ({res['game_bans']}) | "
                               f"Community: {community_status} | Last Ban: {last_ban_str} | "
                               f"Reg: {res['registration_date']}  \n🔗 [Profile]({res['profile_url']}) • Last checked: {res['last_checked']}")
                    st.markdown(summary, unsafe_allow_html=True)
    if col2.button("Logs", key="toggle_log_button"):
        st.session_state.show_log = not st.session_state.show_log

    if st.session_state.show_log:
        st.text_area("Log Details", value="\n".join(st.session_state.log), height=300)

if __name__ == "__main__":
    main()
