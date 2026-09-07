import csv
from pathlib import Path

import streamlit as st

st.title("Coverage")
st.caption("Availability, gaps, licensing, collection, and source outages remain distinct.")
inventory = Path("research/market_capabilities.csv")
if inventory.exists():
    with inventory.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    available = [row for row in rows if row.get("available") == "True"]
    st.metric("Available source-market capabilities", len(available))
    st.dataframe(available, use_container_width=True, hide_index=True)
else:
    st.info("No dynamic source inventory found yet.")
st.subheader("YouTube methodology boundaries")
st.info(
    "Video category is recorded per snapshot. The viewCount definition boundary is "
    "2025-03-31_SHORTS_STARTS_OR_REPLAYS. Current-state availability does not imply history."
)
