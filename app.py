import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Page Configuration ---
st.set_page_config(page_title="Nifty 500 3-Sigma Scanner", layout="wide")
st.title("📈 Nifty 500 Scanner: First 3 SD Breakout with Volume Confirmation")

# Initialize session state so results persist across dropdown selections
if "breakout_df" not in st.session_state:
    st.session_state.breakout_df = None
if "all_stock_data" not in st.session_state:
    st.session_state.all_stock_data = {}

# --- Step 1: Load Nifty 500 Stocks ---
@st.cache_data
def load_symbols():
    try:
        df = pd.read_csv('ind_nifty500list.csv')
        symbols = [f"{symbol}.NS" for symbol in df['Symbol'].tolist()]
        return symbols
    except FileNotFoundError:
        st.error("Please ensure 'ind_nifty500list.csv' is in the repository root directory.")
        return []

# --- Step 2: Download Data & Run Scanner with Volume Filter ---
def fetch_and_scan(symbols, days=90, min_vol_multiplier=1.5):
    breakout_stocks = []
    all_stock_data = {}
    
    progress_bar = st.progress(0, text="Starting scan...")
    total = len(symbols)
    
    for i, symbol in enumerate(symbols):
        try:
            # Download 1 year of daily data
            data = yf.download(symbol, period="1y", progress=False)
            if data.empty:
                continue
                
            # Safely extract 'Close' and 'Volume' as 1D Series
            if isinstance(data.columns, pd.MultiIndex):
                close_series = data['Close'].iloc[:, 0]
                volume_series = data['Volume'].iloc[:, 0]
            else:
                close_series = data['Close']
                volume_series = data['Volume']
            
            close_series = pd.to_numeric(close_series, errors='coerce').dropna()
            volume_series = pd.to_numeric(volume_series, errors='coerce').fillna(0)
            
            # Daily returns
            returns_series = close_series.pct_change().dropna() * 100
            
            # Align indices between returns and volume
            common_index = returns_series.index.intersection(volume_series.index)
            returns_series = returns_series.loc[common_index]
            volume_series = volume_series.loc[common_index]
            
            # Filter to required window
            recent_returns = returns_series.tail(days)
            recent_volume = volume_series.tail(days)
            
            if len(recent_returns) < int(days * 0.75):
                continue
                
            # Statistical thresholds
            mean_return = float(recent_returns.mean())
            std_return = float(recent_returns.std())
            upper_band = mean_return + (3 * std_return)
            lower_band = mean_return - (3 * std_return)
            
            prior_returns = recent_returns.iloc[:-1]
            latest_return = float(recent_returns.iloc[-1])
            
            # Volume calculations
            prior_avg_volume = float(recent_volume.iloc[:-1].mean())
            latest_volume = float(recent_volume.iloc[-1])
            vol_multiplier = (latest_volume / prior_avg_volume) if prior_avg_volume > 0 else 0.0
            
            # Scanner Conditions:
            # 1. Crossed +3 SD today
            # 2. ZERO prior crosses in the window (First-time cross)
            # 3. Today's volume >= specified multiplier of average volume
            crossed_today = latest_return > upper_band
            prior_crosses = int((prior_returns > upper_band).sum())
            volume_confirmed = vol_multiplier >= min_vol_multiplier
            
            if crossed_today and (prior_crosses == 0) and volume_confirmed:
                clean_symbol = symbol.replace('.NS', '')
                all_stock_data[clean_symbol] = {
                    'dates': recent_returns.index,
                    'returns': recent_returns.values,
                    'volume': recent_volume.values,
                    'mean': mean_return,
                    'upper': upper_band,
                    'lower': lower_band,
                    'avg_volume': prior_avg_volume
                }
                breakout_stocks.append({
                    'Symbol': clean_symbol,
                    'Today Return (%)': round(latest_return, 2),
                    'Mean Return (%)': round(mean_return, 2),
                    'Upper Band (+3 SD)': round(upper_band, 2),
                    'Volume Multiplier': f"{round(vol_multiplier, 2)}x",
                    'Today Volume': f"{int(latest_volume):,}",
                    'Avg Volume': f"{int(prior_avg_volume):,}"
                })
        except Exception:
            pass
        
        progress_bar.progress((i + 1) / total, text=f"Scanning stocks: {i + 1}/{total}")
        
    progress_bar.empty()
    return pd.DataFrame(breakout_stocks), all_stock_data

# --- Plotting Function (Returns + Volume Subplot) ---
def plot_stock(symbol, stock_info, days):
    dates = stock_info['dates']
    returns = stock_info['returns']
    volume = stock_info['volume']
    mean = stock_info['mean']
    upper = stock_info['upper']
    lower = stock_info['lower']
    avg_vol = stock_info['avg_volume']
    
    # 2 Subplots: Top for Returns, Bottom for Volume
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{symbol} Daily Returns vs 3 SD Bands", "Daily Volume Breakdown")
    )

    # --- TOP PANEL: Returns ---
    fig.add_trace(
        go.Bar(x=dates, y=returns, name='Returns', marker_color='#1E22AA'),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=dates, y=[mean] * len(dates), mode='lines', name='Mean returns', line=dict(color='#5CB85C', width=2)),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=dates, y=[upper] * len(dates), mode='lines', name='Mean + 3 SD', line=dict(color='#FF9900', width=2)),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=dates, y=[lower] * len(dates), mode='lines', name='Mean - 3 SD', line=dict(color='#D9534F', width=2)),
        row=1, col=1
    )

    # --- BOTTOM PANEL: Volume ---
    fig.add_trace(
        go.Bar(x=dates, y=volume, name='Daily Volume', marker_color='#607D8B'),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=dates, y=[avg_vol] * len(dates), mode='lines', name='Avg Volume', line=dict(color='#FF5722', width=2, dash='dot')),
        row=2, col=1
    )

    fig.update_layout(
        height=650,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    fig.update_yaxes(title_text="Return (%)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    
    return fig

# --- Main App Interface ---
symbols = load_symbols()

st.sidebar.header("Scanner Settings")
timeframe = st.sidebar.selectbox("Select Window:", [90, 60, 30], index=0, format_func=lambda x: f"{x} Days")
min_volume = st.sidebar.slider("Minimum Volume vs Avg:", min_value=1.0, max_value=5.0, value=2.0, step=0.5, format="%.1fx")

if st.sidebar.button("Run Scanner", type="primary"):
    if symbols:
        st.write(f"Scanning Nifty 500 for first-time +3 SD breakouts with **≥ {min_volume}x volume** over **{timeframe} days**...")
        breakout_df, all_stock_data = fetch_and_scan(symbols, days=timeframe, min_vol_multiplier=min_volume)
        st.session_state.breakout_df = breakout_df
        st.session_state.all_stock_data = all_stock_data
        st.session_state.timeframe = timeframe

# Display Results from Session State
if st.session_state.breakout_df is not None:
    df_results = st.session_state.breakout_df
    stored_data = st.session_state.all_stock_data
    selected_timeframe = st.session_state.get('timeframe', timeframe)
    
    if df_results.empty:
        st.warning(f"No stocks found meeting both the 3 SD condition and the {min_volume}x volume filter.")
    else:
        st.success(f"Found {len(df_results)} confirmed breakout stock(s)!")
        st.dataframe(df_results, use_container_width=True)
        
        st.markdown("### Stock Visualization")
        stock_list = df_results['Symbol'].tolist()
        selected_stock = st.selectbox("Select a stock to view chart:", stock_list)
        
        if selected_stock and selected_stock in stored_data:
            chart = plot_stock(selected_stock, stored_data[selected_stock], selected_timeframe)
            st.plotly_chart(chart, use_container_width=True)
            
            # Display recent news headlines
            st.markdown("### 📰 Recent Headlines & Filings")
            try:
                ticker_obj = yf.Ticker(f"{selected_stock}.NS")
                news_items = ticker_obj.news
                if news_items:
                    for item in news_items[:5]:
                        title = item.get('title', 'No Title')
                        publisher = item.get('publisher', 'Source')
                        link = item.get('link', '#')
                        st.markdown(f"- **[{title}]({link})** — *{publisher}*")
                else:
                    st.info("No recent news articles found via Yahoo Finance.")
            except Exception:
                st.info("Unable to retrieve news feeds at this time.")
