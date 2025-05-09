import streamlit as st
import requests
from datetime import datetime
from PIL import Image
from io import BytesIO
import re

st.set_page_config(
    page_title="Steam Ban Monitor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
            margin-bottom: 0.5em;
        }
        .avatar-img {
            border-radius: 8px;
            border: 2px solid #333;
        }
        .stAlert {
            border-radius: 8px;
        }
        /* Help links: inline, immediately below input fields */
        .help-link {
            display: block;
            margin: 0;
            font-size: 0.8em;
        }
        /* Compact text styling */
        .compact-text {
            font-size: 0.9em;
            line-height: 1.2;
        }
    </style>
    """, unsafe_allow_html=True)

def check_bans(api_key, webhook, steam_ids):
    results = []
    for sid in steam_ids:
        try:
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

            results.append(result)
        except Exception as e:
            st.error(f"Error checking {sid}: {str(e)}")
    return results

# Using a regex to extract any sequence of 15 or more digits supports all provided formats.
def process_ids(input_text):
    ids = re.findall(r'\d{15,}', input_text)
    return ids

def main():
    inject_custom_css()

    with st.sidebar:
        st.title("⚙️ Configuration")
        # Steam API key input with inline help link immediately below
        api_key = st.text_input("Steam API Key:", type="password", key="api_key_input")
        st.markdown("<small class='help-link'><a href='https://steamcommunity.com/dev' target='_blank'>How to get it?</a></small>", unsafe_allow_html=True)

        # Discord webhook input with inline help link immediately below
        webhook = st.text_input("Discord Webhook URL (optional):", key="webhook_input")
        st.markdown("<small class='help-link'><a href='https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks' target='_blank'>Guide</a></small>", unsafe_allow_html=True)

        st.markdown("<small style='color: #AAA;'>This tool doesn't store any API keys or user data. All inputs are session-only.</small>", unsafe_allow_html=True)
        # Add the image below the credential reminder; using use_container_width instead of the deprecated use_column_width.
        st.image("https://i.imgur.com/jZsExFB.jpeg", use_container_width=True)

    st.title("🛡️ Steam Account Monitor")
    placeholder_text = (
        "Example:\n"
        "76561197960287930\n"
        "76561197960287931, 76561197960287932\n"
        "https://steamcommunity.com/profiles/76561197960287930"
    )
    steam_ids_input = st.text_area("📥 Enter Steam64 IDs:", height=150, key="steam_ids_input", placeholder=placeholder_text)

    if st.button("🔍 Check Now", key="check_now_button"):
        steam_ids = process_ids(steam_ids_input)
        results = []
        if steam_ids and api_key:
            results = check_bans(api_key, webhook, steam_ids)

        total_loaded = len(results)
        total_banned = sum(1 for r in results if r["vac"] or r["game_bans"] > 0 or r["community"])
        st.markdown(f"**Accounts Loaded:** {total_loaded} | **Accounts Banned:** {total_banned}")

        for res in results:
            with st.expander(f"{res['username']} ({res['steamid']})"):
                col1, col2 = st.columns([1, 5])
                with col1:
                    try:
                        response = requests.get(res["avatar"])
                        img = Image.open(BytesIO(response.content))
                        img_small = img.resize((80, 80))
                    except Exception as e:
                        st.error(f"Error processing avatar image: {e}")
                        img_small = None
                    if img_small:
                        st.image(img_small, width=80, output_format="PNG")
                with col2:
                    vac_status = "🔴 Yes" if res["vac"] else "🟢 No"
                    game_status = "🔴 Yes" if res["game_bans"] > 0 else "🟢 No"
                    community_status = "🔴 Yes" if res["community"] else "🟢 No"
                    summary = (
                        f"**Status:** VAC: {vac_status} | Game: {game_status} ({res['game_bans']}) | "
                        f"Community: {community_status} | Last Ban: {res['last_ban_days'] if res['last_ban_days'] else 'Never'} days | "
                        f"Reg: {res['registration_date']}  \n"
                        f"🔗 [Profile]({res['profile_url']}) • Last checked: {res['last_checked']}"
                    )
                    st.markdown(summary, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
