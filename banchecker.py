import streamlit as st
import requests

def check_bans(api_key, webhook, steam_ids):
    results = []
    for sid in steam_ids:
        try:
            # Get ban info
            ban_response = requests.get(
                f"https://api.steampowered.com/ISteamUser/GetPlayerBans/v1/",
                params={"key": api_key, "steamids": sid}
            ).json()
            
            # Get profile info
            profile_response = requests.get(
                f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                params={"key": api_key, "steamids": sid}
            ).json()
            
            # Combine data
            result = {
                "steamid": sid,
                "bans": ban_response.get("players", [{}])[0],
                "profile": profile_response.get("response", {}).get("players", [{}])[0]
            }
            results.append(result)
            
            # Send Discord notification if banned
            if any([result["bans"].get("VACBanned"), result["bans"].get("NumberOfGameBans") > 0]):
                if webhook:
                    requests.post(webhook, json={
                        "content": f"Ban detected for {sid}",
                        "embeds": [{
                            "title": "Steam Ban Alert",
                            "fields": [
                                {"name": "SteamID", "value": sid},
                                {"name": "Profile", "value": result["profile"].get("profileurl")}
                            ]
                        }]
                    })
        except Exception as e:
            st.error(f"Error checking {sid}: {str(e)}")
    return results

def main():
    st.title("Steam Ban Checker 🔍")
    
    # API Key Input
    api_key = st.text_input("Your Steam API Key:", type="password")
    st.markdown("[Get API Key](https://steamcommunity.com/dev/apikey)")
    
    # Webhook Input
    webhook = st.text_input("Discord Webhook URL (optional):")
    st.markdown("[Webhook Guide](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)")

    # Move this inside the function
    steam_ids_input = st.text_area("Steam64 IDs (separate by commas or new lines):", 
                                   placeholder="76561197960287930, 76561197960287931\n76561197960287932")

    steam_ids = [sid.strip() for sid in steam_ids_input.replace('\n', ',').split(',') if sid.strip().isdigit()]
    
    if st.button("Check Bans"):
        if not api_key:
            st.error("API Key required!")
            return
            
        results = check_bans(api_key, webhook, steam_ids)
        
        for res in results:
            with st.expander(f"Account: {res['profile'].get('personaname', 'Unknown')}"):
                st.json(res)

if __name__ == "__main__":
    main()
