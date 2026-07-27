import streamlit as st


st.set_page_config(
    page_title="MacroPulse",
    page_icon="📈",
    layout="wide",
)

pages = {
    "MacroPulse": [
        st.Page("ui/home.py", title="Home", icon="🏠", default=True),
        st.Page("ui/nowcast.py", title="US GDP Nowcast", icon="📈"),
        st.Page("ui/data_explorer.py", title="Data Explorer", icon="🗃️"),
        st.Page("ui/model_history.py", title="Model History", icon="🧪"),
    ]
}

navigation = st.navigation(pages)
navigation.run()
