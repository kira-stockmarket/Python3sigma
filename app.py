import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(page_title="Nifty 500 3-Sigma First-Time Breakout", layout="wide")
st.title("📈 Nifty 500 Scanner: First 3 SD Breakout in 90 Days")

# --- Step 1: Load Nifty 500 Stocks ---
@st.cache_data
def load_symbols():
    try:
        df = pd.read_csv('ind_nifty500list.csv')
        symbols = [f"{symbol}.NS" for symbol in df['Symbol'].tolist()]
        return symbols
    except FileNotFoundError:
        st.error("Please ensure 'ind_nifty500list.csv' is in the repository.")
        return []

# --- Step 2: Download Data & Run Scanner ---
@st.cache_data(ttl=3600)
def fetch_and_scan(symbols, days=90):
    breakout_stocks = []
    all_stock_data = {}
    
    progress_bar = st.progress(0, text="Scanning Nifty 500 stocks...")
    
    for i, symbol in enumerate(symbols):
        try:
            # Download sufficient history for calculations
            data = yf.download(symbol, period="1y", progress=False)
            if data.empty:
                continue
                
            # Flatten multi-level columns if returned by newer yfinance versions
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Daily return percentage
            data['Returns'] = data['Close'].pct_change() * 100
            data = data.dropna()
            
            # Slice the selected timeframe (default 90 trading days)
            recent_data = data.tail(days)
            if len(recent_data) < days * 0.8:
                continue
                
            # Calculate baseline statistics for the window
            mean_return = recent_data['Returns'].mean()
            std_return = recent_data['Returns'].std()
            upper_band = mean_return + (3 * std_return)
            lower_band = mean_return - (3 * std_return)
            
            # Separate historical days from today
            prior_returns = recent_data['Returns'].iloc[:-1]
            latest_return = recent_data['Returns'].iloc[-1]
            
            # CONDITION:
            # 1. Today breaks above 3 SD
            # 2. NONE of the prior days in the window crossed 3 SD (First time)
            crossed_today = latest_return > upper_band
            prior_crosses = (prior_returns > upper_band).sum()
            
            if crossed_today and (prior_crosses == 0):
                all_stock_data[symbol] = {
                    'data': recent_data,
                    'mean': mean_return,
                    'upper': upper_band,
                    'lower': lower_band
                }
                breakout_stocks.append({
                    'Symbol': symbol.replace('.NS', ''),
                    'Today Return (%)': round(latest_return, 2),
                    'Mean Return (%)': round(mean_return, 2),
                    'Upper Band (+3 SD)': round(upper_band, 2),
                    'Prior 3SD Crosses': prior_crosses
                })
        except Exception:
            pass
        
        progress_bar.progress((i + 1) / len(symbols), text=f"Scanned {i+1}/{len(symbols)} stocks...")
        
    progress_bar.empty()
    return pd.DataFrame(breakout_stocks), all_stock_data

# --- Plotting Function ---
def plot_stock(symbol, stock_info, days):
    df = stock_info['data']
    mean = stock_info['mean']
    upper = stock_info['upper']
    lower = stock_info['lower']
    
    fig = go.Figure()

    # Returns Bar Chart
    fig.add_trace(go.Bar(
        x=df.index, y=df['Returns'],
        name='Returns', marker_color='#1E22AA'
    ))

    # Mean Line (Green)
    fig.add_trace(go.Scatter(
        x=df.index, y=[mean] * len(df),
        mode='lines', name='Mean returns', line=dict(color='#5CB85C', width=2)
    ))

    # Mean + 3 SD Line (Orange)
    fig.add_trace(go.Scatter(
        x=df.index, y=[upper] * len(df),
        mode='lines', name='Mean + 3 SD', line=dict(color='#FF9900', width=2)
    ))

    # Mean - 3 SD Line (Red)
    fig.add_trace(go.Scatter(
        x=df.index, y=[lower] * len(df),
        mode='lines', name='Mean - 3 SD', line=dict(color='#D9534F', width=2)
    ))

    fig.update_layout(
        title=f"{symbol}'s {days}-day Stock Performance (First-Time 3 SD Cross)",
        yaxis_title="%",
        xaxis_title="Dates",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    return fig

# --- Main Dashboard Execution ---
symbols = load_symbols()

if symbols:
    st.sidebar.header("Scanner Settings")
    timeframe = st.sidebar.selectbox("Select Window:", [90, 60, 30], index=0, format_func=lambda x: f"{x} Days")
    
    if st.sidebar.button("Run Scanner", type="primary"):
        st.write(f"Scanning for stocks crossing +3 SD **for the first time** in the last {timeframe} days...")
        breakout_df, all_stock_data = fetch_and_scan(symbols, days=timeframe)
        
        if breakout_df.empty:
            st.warning("No stocks found crossing +3 SD for the first time in this period.")
        else:
            st.success(f"Found {len(breakout_df)} fresh breakout stock(s)!")
            st.dataframe(breakout_df, use_container_width=True)
            
            selected_stock = st.selectbox("Select a stock to view chart:", breakout_df['Symbol'].tolist())
            if selected_stock:
                stock_key = f"{selected_stock}.NS"
                fig = plot_stock(selected_stock, all_stock_data[stock_key], timeframe)
                st.plotly_chart(fig, use_container_width=True)
