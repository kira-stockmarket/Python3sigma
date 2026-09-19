import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import numpy as np

# --- Page Configuration ---
st.set_page_config(page_title="Nifty 500 3-Sigma Scanner", layout="wide")
st.title("📈 Nifty 500 Breakout Scanner (Mean + 3 SD)")

# --- Step 1: Load Nifty 500 Stocks ---
@st.cache_data
def load_symbols():
    try:
        # Referencing the exact file name provided
        df = pd.read_csv('ind_nifty500list.csv')
        # yfinance requires '.NS' for NSE stocks
        symbols = [f"{symbol}.NS" for symbol in df['Symbol'].tolist()]
        return symbols
    except FileNotFoundError:
        st.error("Please ensure 'ind_nifty500list.csv' is in the same directory.")
        return []

# --- Step 2: Download Data & Run Scanner ---
@st.cache_data(ttl=3600) # Cache data for 1 hour to speed up re-runs
def fetch_and_scan(symbols, days):
    breakout_stocks = []
    all_stock_data = {}
    
    # Progress bar for downloading
    progress_text = "Downloading stock data... Please wait."
    my_bar = st.progress(0, text=progress_text)
    
    for i, symbol in enumerate(symbols):
        try:
            # Fetch 6 months of data to ensure we have enough trading days
            data = yf.download(symbol, period="6mo", progress=False)
            if data.empty:
                continue
                
            # Calculate Daily Returns (%)
            data['Returns'] = data['Close'].pct_change() * 100
            data = data.dropna()
            
            # Slice the data to the selected timeframe (30, 60, or 90 days)
            recent_data = data.tail(days)
            if len(recent_data) < days * 0.8: # Skip if recently listed / lacking data
                continue
                
            # Calculate Statistics
            mean_return = recent_data['Returns'].mean()
            std_return = recent_data['Returns'].std()
            upper_band = mean_return + (3 * std_return)
            lower_band = mean_return - (3 * std_return)
            latest_return = recent_data['Returns'].iloc[-1]
            
            # Save data for plotting
            all_stock_data[symbol] = {
                'data': recent_data,
                'mean': mean_return,
                'upper': upper_band,
                'lower': lower_band
            }
            
            # SCANNER CONDITION: Latest return > Mean + 3 SD
            if latest_return > upper_band:
                breakout_stocks.append({
                    'Symbol': symbol.replace('.NS', ''),
                    'Latest Return (%)': round(latest_return, 2),
                    'Mean Return (%)': round(mean_return, 2),
                    'Upper Band (+3 SD)': round(upper_band, 2)
                })
        except Exception:
            pass
        
        # Update progress bar
        my_bar.progress((i + 1) / len(symbols), text=progress_text)
        
    my_bar.empty()
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
        name='Returns', marker_color='navy'
    ))

    # Mean Line (Green)
    fig.add_trace(go.Scatter(
        x=df.index, y=[mean]*len(df),
        mode='lines', name='Mean returns', line=dict(color='green', width=2)
    ))

    # Mean + 3 SD Line (Orange)
    fig.add_trace(go.Scatter(
        x=df.index, y=[upper]*len(df),
        mode='lines', name='Mean + 3 SD', line=dict(color='orange', width=2)
    ))

    # Mean - 3 SD Line (Red)
    fig.add_trace(go.Scatter(
        x=df.index, y=[lower]*len(df),
        mode='lines', name='Mean - 3 SD', line=dict(color='red', width=2)
    ))

    fig.update_layout(
        title=f"{symbol} {days}-day Stock Performance",
        yaxis_title="%",
        xaxis_title="Dates",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    return fig

# --- App Layout & Interaction ---
symbols = load_symbols()

if symbols:
    # Sidebar controls
    st.sidebar.header("Scanner Settings")
    timeframe = st.sidebar.radio("Select Timeframe:", [30, 60, 90], format_func=lambda x: f"{x} Days")
    
    # Run Scanner limit to first 100 for quick testing, remove `[:100]` for full Nifty 500
    st.write(f"Scanning Nifty 500 stocks over the last {timeframe} days...")
    breakout_df, all_stock_data = fetch_and_scan(symbols, days=timeframe) 
    
    if breakout_df.empty:
        st.info("No stocks broke out above the 3 SD band today.")
    else:
        st.success(f"Found {len(breakout_df)} stocks breaking above 3 SD!")
        st.dataframe(breakout_df, use_container_width=True)
        
        st.subheader("Visualize Scanned Stocks")
        selected_stock = st.selectbox("Select a stock to view its chart:", breakout_df['Symbol'].tolist())
        
        if selected_stock:
            stock_key = f"{selected_stock}.NS"
            fig = plot_stock(selected_stock, all_stock_data[stock_key], timeframe)
            st.plotly_chart(fig, use_container_width=True)
