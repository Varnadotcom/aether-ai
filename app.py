from datetime import datetime, timezone
import requests
import streamlit as st

# Streamlit Page Config
st.set_page_config(
    page_title="Aether AI - Bot-Free YouTube Search", page_icon="🛡️", layout="wide"
)

st.title("🛡️ Aether AI: High-Trust YouTube Search Engine")
st.markdown(
    "Filter out bot-inflated, stagnant, and clickbait content using engagement velocity heuristics."
)

# Sidebar Configuration
st.sidebar.header("Configuration & Filters")
api_key = st.sidebar.text_input(
    "Enter Google Data API Key", type="password", help="Requires YouTube Data API v3"
)
search_query = st.sidebar.text_input("Search Query", "CachyOS setup guide")
max_results = st.sidebar.slider("Results to Analyze", 5, 30, 15)
min_trust_score = st.sidebar.slider(
    "Minimum Human Trust Score", 0.0, 10.0, 6.5, 0.5
)

st.sidebar.markdown("---")
st.sidebar.info(
    "**Heuristics Active:**\n"
    "- Engagement-to-View Ratio Checks\n"
    "- Velocity vs. Subscriber Spikes\n"
    "- Comment Suppression Detection"
)


def search_youtube(query, api_key, max_results=15):
  search_url = "https://www.googleapis.com/youtube/v3/search"
  params = {
      "part": "snippet",
      "q": query,
      "type": "video",
      "maxResults": max_results,
      "key": api_key,
  }
  response = requests.get(search_url, params=params)
  if response.status_code != 200:
    st.error(f"YouTube API Error: {response.json().get('error', {}).get('message', 'Unknown error')}")
    return []
  return response.json().get("items", [])


def get_video_and_channel_details(video_ids, channel_ids, api_key):
  # Fetch Video Stats
  videos_url = "https://www.googleapis.com/youtube/v3/videos"
  v_params = {
      "part": "statistics,snippet",
      "id": ",".join(video_ids),
      "key": api_key,
  }
  v_response = requests.get(videos_url, params=v_params)
  videos_data = (
      v_response.json().get("items", []) if v_response.status_code == 200 else []
  )

  # Fetch Channel Stats
  channels_url = "https://www.googleapis.com/youtube/v3/channels"
  c_params = {
      "part": "statistics",
      "id": ",".join(list(set(channel_ids))),
      "key": api_key,
  }
  c_response = requests.get(channels_url, params=c_params)
  channels_data = (
      c_response.json().get("items", []) if c_response.status_code == 200 else []
  )

  channels_map = {c["id"]: c["statistics"] for c in channels_data}
  return videos_data, channels_map


def calculate_metrics(item, channel_stats):
  stats = item.get("statistics", {})
  views = int(stats.get("viewCount", 0))
  likes = int(stats.get("likeCount", 0))
  comments = int(stats.get("commentCount", 0))

  subscriber_count = int(channel_stats.get("subscriberCount", 1))

  # Calculate content age in days
  published_at = datetime.fromisoformat(
      item["snippet"]["publishedAt"].replace("Z", "+00:00")
  )
  age_days = max((datetime.now(timezone.utc) - published_at).days, 1)

  # 1. Engagement Velocity (Interactions / Days)
  total_interactions = likes + comments
  velocity = round(total_interactions / age_days, 2)

  # 2. Heuristic Bot & Trust Checks
  trust_score = 10.0
  flags = []

  # Check 1: Abnormally low engagement-to-view ratio
  engagement_rate = (total_interactions / views) if views > 0 else 0
  if views > 200 and engagement_rate < 0.003:
    trust_score -= 3.0
    flags.append("Low Engagement Ratio (Stagnant or Inflated)")

  # Check 2: Unrealistic velocity-to-subscriber ratio (Bot spikes)
  if velocity > 500 and subscriber_count < 100:
    trust_score -= 4.0
    flags.append("Suspicious Velocity vs Sub Count")

  # Check 3: Comment suppression (Comments disabled often hides bot activity)
  if "commentCount" not in stats:
    trust_score -= 2.0
    flags.append("Comments Disabled")

  trust_score = max(0.0, min(10.0, trust_score))

  return {
      "trust_score": trust_score,
      "flags": flags,
      "velocity": velocity,
      "views": views,
      "likes": likes,
      "comments": comments,
      "age_days": age_days,
  }


# Main execution flow
if st.sidebar.button("Run Aether Search", type="primary"):
  if not api_key:
    st.warning("Please enter a valid Google Data API Key in the sidebar.")
  else:
    with st.spinner("Analyzing human trust metrics and engagement velocity..."):
      raw_items = search_youtube(search_query, api_key, max_results)

      if raw_items:
        video_ids = [item["id"]["videoId"] for item in raw_items if "videoId" in item["id"]]
        channel_ids = [item["snippet"]["channelId"] for item in raw_items]

        videos_data, channels_map = get_video_and_channel_details(
            video_ids, channel_ids, api_key
        )

        analyzed_results = []
        for v in videos_data:
          c_id = v["snippet"]["channelId"]
          c_stats = channels_map.get(c_id, {})
          metrics = calculate_metrics(v, c_stats)

          if metrics["trust_score"] >= min_trust_score:
            analyzed_results.append({"video": v, "metrics": metrics})

        # Sort results by Trust Score then Velocity
        analyzed_results.sort(
            key=lambda x: (x["metrics"]["trust_score"], x["metrics"]["velocity"]),
            reverse=True,
        )

        st.success(
            f"Found {len(analyzed_results)} high-trust results meeting your threshold!"
        )

        for res in analyzed_results:
          v = res["video"]
          m = res["metrics"]
          snippet = v["snippet"]

          with st.container():
            col1, col2 = st.columns([1, 3])
            with col1:
              st.image(
                  snippet["thumbnails"]["medium"]["url"],
                  use_container_width=True,
              )
            with col2:
              st.subheader(snippet["title"])
              st.markdown(
                  f"**Channel:** {snippet['channelTitle']} | "
                  f"**Published:** {snippet['publishedAt'][:10]}"
              )
              st.markdown(
                  f"🟢 **Trust Score:** `{m['trust_score']:.1f}/10` | "
                  f"⚡ **Engagement Velocity:** `{m['velocity']} interactions/day` | "
                  f"👁️ **Views:** `{m['views']:,}`"
              )

              if m["flags"]:
                st.warning("Warnings: " + ", ".join(m["flags"]))
              else:
                st.caption("✅ Clean organic engagement profile.")

              st.markdown(
                  f"[Watch on YouTube](https://www.youtube.com/watch?v={v['id']})"
              )
            st.markdown("---")
      else:
        st.info("No videos found matching your query.")
else:
  st.info(
      "Configure your API key and search parameters in the sidebar, then click"
      " **Run Aether Search**."
  )
