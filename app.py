import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(page_title="Nifty 500 3-Sigma Scanner", layout="wide")
st.title("📈 Nifty 500 Scanner: First 3 SD Breakout in 90 Days")

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

# --- Step 2: Download Data & Run Scanner ---
def fetch_and_scan(symbols, days=90):
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
                
            # Safely extract 'Close' as a 1D Series regardless of yfinance formatting
            if isinstance(data.columns, pd.MultiIndex):
                close_series = data['Close'].iloc[:, 0]
            else:
                close_series = data['Close']
            
            close_series = pd.to_numeric(close_series, errors='coerce').dropna()
            
            # Calculate daily percentage returns
            returns_series = close_series.pct_change().dropna() * 100
            
            # Filter to required window
            recent_returns = returns_series.tail(days)
            if len(recent_returns) < int(days * 0.75):
                continue
                
            # Calculate statistics
            mean_return = float(recent_returns.mean())
            std_return = float(recent_returns.std())
            upper_band = mean_return + (3 * std_return)
            lower_band = mean_return - (3 * std_return)
            
            prior_returns = recent_returns.iloc[:-1]
            latest_return = float(recent_returns.iloc[-1])
            
            # Scan condition: Crossed +3 SD today AND 0 prior crossings in the window
            crossed_today = latest_return > upper_band
            prior_crosses = int((prior_returns > upper_band).sum())
            
            if crossed_today and (prior_crosses == 0):
                clean_symbol = symbol.replace('.NS', '')
                all_stock_data[clean_symbol] = {
                    'dates': recent_returns.index,
                    'returns': recent_returns.values,
                    'mean': mean_return,
                    'upper': upper_band,
                    'lower': lower_band
                }
                breakout_stocks.append({
                    'Symbol': clean_symbol,
                    'Today Return (%)': round(latest_return, 2),
                    'Mean Return (%)': round(mean_return, 2),
                    'Upper Band (+3 SD)': round(upper_band, 2),
                    'Prior Crosses': prior_crosses
                })
        except Exception:
            pass
        
        progress_bar.progress((i + 1) / total, text=f"Scanning stocks: {i + 1}/{total}")
        
    progress_bar.empty()
    return pd.DataFrame(breakout_stocks), all_stock_data

# --- Plotting Function ---
def plot_stock(symbol, stock_info, days):
    dates = stock_info['dates']
    returns = stock_info['returns']
    mean = stock_info['mean']
    upper = stock_info['upper']
    lower = stock_info['lower']
    
    fig = go.Figure()

    # Returns Bar Chart
    fig.add_trace(go.Bar(
        x=dates, 
        y=returns,
        name='Returns', 
        marker_color='#1E22AA'
    ))

    # Mean Line (Green)
    fig.add_trace(go.Scatter(
        x=dates, 
        y=[mean] * len(dates),
        mode='lines', 
        name='Mean returns', 
        line=dict(color='#5CB85C', width=2)
    ))

    # Upper +3 SD Line (Orange)
    fig.add_trace(go.Scatter(
        x=dates, 
        y=[upper] * len(dates),
        mode='lines', 
        name='Mean + 3 SD', 
        line=dict(color='#FF9900', width=2)
    ))

    # Lower -3 SD Line (Red)
    fig.add_trace(go.Scatter(
        x=dates, 
        y=[lower] * len(dates),
        mode='lines', 
        name='Mean - 3 SD', 
        line=dict(color='#D9534F', width=2)
    ))

    fig.update_layout(
        title=f"{symbol}'s {days}-day Stock Performance (First-Time 3 SD Cross)",
        yaxis_title="Daily Return (%)",
        xaxis_title="Date",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    return fig

# --- Main App Interface ---
symbols = load_symbols()

st.sidebar.header("Scanner Settings")
timeframe = st.sidebar.selectbox("Select Window:", [90, 60, 30], index=0, format_func=lambda x: f"{x} Days")

if st.sidebar.button("Run Scanner", type="primary"):
    if symbols:
        st.write(f"Scanning Nifty 500 for first-time +3 SD breakouts over the last **{timeframe} trading days**...")
        breakout_df, all_stock_data = fetch_and_scan(symbols, days=timeframe)
        st.session_state.breakout_df = breakout_df
        st.session_state.all_stock_data = all_stock_data
        st.session_state.timeframe = timeframe

# Display Results from Session State (Survives Dropdown Clicks)
if st.session_state.breakout_df is not None:
    df_results = st.session_state.breakout_df
    stored_data = st.session_state.all_stock_data
    selected_timeframe = st.session_state.get('timeframe', timeframe)
    
    if df_results.empty:
        st.warning(f"No stocks found crossing +3 SD for the first time in the last {selected_timeframe} days.")
    else:
        st.success(f"Found {len(df_results)} stock(s) matching the criteria!")
        st.dataframe(df_results, use_container_width=True)
        
        st.markdown("### Stock Visualization")
        stock_list = df_results['Symbol'].tolist()
        selected_stock = st.selectbox("Select a stock to view chart:", stock_list)
        
        if selected_stock and selected_stock in stored_data:
            chart = plot_stock(selected_stock, stored_data[selected_stock], selected_timeframe)
            st.plotly_chart(chart, use_container_width=True)
