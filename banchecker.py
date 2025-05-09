import streamlit as st
import requests
import time
from datetime import datetime
from threading import Thread

def check_bans(api_key, webhook, steam_ids, ban_history):
    results = []
    for sid in steam_ids:
        try:
            # Get ban info
            ban_response = requests.get(
                "https://api.steampowered.com/ISteamUser/GetPlayerBans/v1/",
                params={"key": api_key, "steamids": sid}
            ).json()
            
            # Get profile info
            profile_response = requests.get(
                "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                params={"key": api_key, "steamids": sid}
            ).json()
            
            # Extract profile data
            profile_data = profile_response.get("response", {}).get("players", [{}])[0]
            ban_data = ban_response.get("players", [{}])[0]
            
            # Process bans
            vac_banned = ban_data.get("VACBanned", False)
            game_bans = ban_data.get("NumberOfGameBans", 0)
            community_banned = ban_data.get("CommunityBanned", False)
            days_since_last_ban = ban_data.get("DaysSinceLastBan", 0)
            
            result = {
                "steamid": sid,
                "username": profile_data.get("personaname", "Unknown"),
                "avatar": profile_data.get("avatarfull", ""),
                "profile_url": profile_data.get("profileurl", f"https://steamcommunity.com/profiles/{sid}"),
                "vac": vac_banned,
                "game_bans": game_bans,
                "community": community_banned,
                "last_ban_days": days_since_last_ban,
                "new_ban": False
            }
            
            # Check for new bans
            prev_status = ban_history.get(sid, {})
            current_ban_status = (vac_banned, game_bans, community_banned)
            
            if any(current_ban_status):
                if not prev_status or (prev_status.get("vac") != vac_banned or 
                                     prev_status.get("game_bans") != game_bans or 
                                     prev_status.get("community") != community_banned):
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
    if result["vac"]:
        ban_types.append("VAC")
    if result["community"]:
        ban_types.append("Community")
    if result["game_bans"] > 0:
        ban_types.append(f"Game ({result['game_bans']})")
    
    embed = {
        "title": "🚨 NEW BAN DETECTED 🚨",
        "color": 16711680,
        "thumbnail": {"url": result["avatar"]},
        "fields": [
            {"name": "Account", "value": f"[{result['username']}]({result['profile_url']})", "inline": True},
            {"name": "SteamID", "value": result["steamid"], "inline": True},
            {"name": "Ban Types", "value": ", ".join(ban_types) if ban_types else "None", "inline": False},
            {"name": "Days Since Last Ban", "value": str(result["last_ban_days"]), "inline": True}
        ],
        "footer": {"text": f"Detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
    }
    
    try:
        requests.post(webhook, json={"embeds": [embed]})
    except Exception as e:
        st.error(f"Failed to send Discord notification: {e}")

def automatic_checker(api_key, webhook, steam_ids, interval, ban_history):
    while st.session_state.automatic_running:
        st.experimental_rerun()
        time.sleep(interval * 60)

def main():
    st.set_page_config(page_title="Steam Ban Checker", page_icon="🔍", layout="wide")
    st.title("Steam Ban Checker 🔍")
    
    # Initialize session state
    if 'ban_history' not in st.session_state:
        st.session_state.ban_history = {}
    if 'automatic_running' not in st.session_state:
        st.session_state.automatic_running = False
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        api_key = st.text_input("Steam API Key:", type="password")
        st.markdown("[Get API Key](https://steamcommunity.com/dev/apikey)")
        
        webhook = st.text_input("Discord Webhook URL:")
        st.markdown("[Webhook Guide](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)")
        
        # Automatic checking controls
        auto_check = st.checkbox("Enable Automatic Checking")
        if auto_check:
            check_interval = st.number_input("Check Interval (minutes):", min_value=1, value=60)
            if st.button("Start Automatic Checks" if not st.session_state.automatic_running else "Stop Automatic Checks"):
                st.session_state.automatic_running = not st.session_state.automatic_running
                if st.session_state.automatic_running:
                    Thread(target=automatic_checker, args=(api_key, webhook, 
                                                          st.session_state.get('tracked_ids', []), 
                                                          check_interval, 
                                                          st.session_state.ban_history)).start()
    
    # Main interface
    steam_ids_input = st.text_area("Steam64 IDs (separate by commas or new lines):", 
                                  placeholder="76561197960287930, 76561197960287931\n76561197960287932")
    
    steam_ids = [sid.strip() for sid in steam_ids_input.replace('\n', ',').split(',') if sid.strip().isdigit()]
    st.session_state.tracked_ids = steam_ids
    
    if st.button("Check Bans"):
        if not api_key:
            st.error("API Key required!")
            return
            
        results = check_bans(api_key, webhook, steam_ids, st.session_state.ban_history)
        
        # Display results
        for res in results:
            with st.expander(f"{res['username']} ({res['steamid']})", expanded=res['new_ban']):
                col1, col2 = st.columns([1, 4])
                with col1:
                    if res["avatar"]:
                        st.image(res["avatar"], width=100)
                with col2:
                    st.markdown(f"""
                    **Account Status:**
                    - VAC Banned: `{"Yes" if res["vac"] else "No"}`
                    - Game Bans: `{res["game_bans"]}`
                    - Community Banned: `{"Yes" if res["community"] else "No"}`
                    - Days Since Last Ban: `{res["last_ban_days"]}`
                    """)
                    st.markdown(f"[Steam Profile]({res['profile_url']})")
                
                if res["new_ban"]:
                    st.error("NEW BAN DETECTED!")
                else:
                    st.success("No new bans detected")

if __name__ == "__main__":
    main()
