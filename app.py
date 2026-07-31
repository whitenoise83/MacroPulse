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
        st.Page("ui/inflation_nowcast.py", title="US Inflation Nowcast", icon="🌡️"),
        st.Page("ui/inflation_news.py", title="Inflation News", icon="🧾"),
        st.Page("ui/labour_nowcast.py", title="US Labour Nowcast", icon="👷"),
        st.Page("ui/news_decomposition.py", title="GDP News Decomposition", icon="📰"),
        st.Page("ui/data_explorer.py", title="Data Explorer", icon="🗃️"),
        st.Page("ui/model_comparison.py", title="Model Comparison", icon="⚖️"),
        st.Page("ui/model_history.py", title="Model History", icon="🧪"),
        st.Page("ui/backtesting.py", title="GDP Backtesting", icon="🎯"),
        st.Page("ui/inflation_backtesting.py", title="Inflation Backtesting", icon="🧭"),
        st.Page("ui/labour_backtesting.py", title="Labour Backtesting", icon="🧰"),
        st.Page("ui/validation.py", title="Validation & Governance", icon="🛡️"),
    ]
}

navigation = st.navigation(pages)
navigation.run()
