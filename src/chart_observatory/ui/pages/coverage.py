import csv
from pathlib import Path

import streamlit as st

from chart_observatory.ui.source_inventory import load_capabilities

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
st.subheader("Global source coverage")
global_coverage = Path("research/global_market_coverage.csv")
if global_coverage.exists():
    with global_coverage.open(encoding="utf-8", newline="") as handle:
        st.dataframe(list(csv.DictReader(handle)), use_container_width=True, hide_index=True)
else:
    st.info("No global coverage report found yet.")
st.subheader("Capability status by source")
capabilities = load_capabilities(Path("research/market_capabilities.csv"))
if capabilities:
    st.dataframe(capabilities, use_container_width=True, hide_index=True)
st.subheader("YouTube methodology boundaries")
st.info(
    "Video category is recorded per snapshot. The viewCount definition boundary is "
    "2025-03-31_SHORTS_STARTS_OR_REPLAYS. Current-state availability does not imply history."
)
