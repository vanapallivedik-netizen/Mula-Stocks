import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

# Mula Stocks — single-user paper-trading demo.
# All trades are simulated. No brokerage connection or real-money orders.

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "mula_stocks.db"
STARTING_CASH = 10_000.00
DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "TSLA"]


def connect_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cash REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS holdings (
                ticker TEXT PRIMARY KEY,
                shares REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                shares REAL NOT NULL,
                price REAL NOT NULL,
                total REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker TEXT PRIMARY KEY
            )
        """)
        conn.execute(
            "INSERT OR IGNORE INTO account (id, cash) VALUES (1, ?)",
            (STARTING_CASH,),
        )
        count = conn.execute("SELECT COUNT(*) AS n FROM watchlist").fetchone()["n"]
        if count == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)",
                [(t,) for t in DEFAULT_WATCHLIST],
            )


def get_cash():
    with connect_db() as conn:
        row = conn.execute("SELECT cash FROM account WHERE id = 1").fetchone()
        return float(row["cash"])


def get_holdings():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT ticker, shares FROM holdings WHERE shares > 0 ORDER BY ticker"
        ).fetchall()
        return {row["ticker"]: float(row["shares"]) for row in rows}


def get_transactions(limit=100):
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_watchlist():
    with connect_db() as conn:
        rows = conn.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
        return [row["ticker"] for row in rows]


@st.cache_data(ttl=60, show_spinner=False)
def get_stock_data(ticker):
    """Return current-ish quote and recent daily history from Yahoo Finance."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Enter a ticker symbol.")

    stock = yf.Ticker(ticker)
    hist = stock.history(period="1mo", interval="1d", auto_adjust=True)
    if hist.empty or "Close" not in hist:
        raise ValueError(f"No price data found for {ticker}. Check the ticker symbol.")

    closes = hist["Close"].dropna()
    if closes.empty:
        raise ValueError(f"No usable price data found for {ticker}.")

    price = float(closes.iloc[-1])
    previous = float(closes.iloc[-2]) if len(closes) > 1 else price
    change = price - previous
    percent = (change / previous * 100) if previous else 0.0
    return {
        "price": price,
        "previous": previous,
        "change": change,
        "percent": percent,
        "history": hist,
        "as_of": str(hist.index[-1].date()),
    }


def execute_trade(ticker, side, shares, price):
    ticker = ticker.strip().upper()
    shares = float(shares)
    price = float(price)
    total = shares * price

    if not ticker or shares <= 0 or price <= 0:
        raise ValueError("Enter a valid ticker, share amount, and price.")

    with connect_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        account = conn.execute(
            "SELECT cash FROM account WHERE id = 1"
        ).fetchone()
        cash = float(account["cash"])
        holding = conn.execute(
            "SELECT shares FROM holdings WHERE ticker = ?", (ticker,)
        ).fetchone()
        owned = float(holding["shares"]) if holding else 0.0

        if side == "BUY":
            if total > cash + 1e-8:
                raise ValueError(
                    f"Not enough simulated cash. Available: ${cash:,.2f}."
                )
            conn.execute(
                "UPDATE account SET cash = cash - ? WHERE id = 1", (total,)
            )
            new_shares = owned + shares
        elif side == "SELL":
            if shares > owned + 1e-8:
                raise ValueError(
                    f"You only own {owned:.6f} shares of {ticker}."
                )
            conn.execute(
                "UPDATE account SET cash = cash + ? WHERE id = 1", (total,)
            )
            new_shares = owned - shares
        else:
            raise ValueError("Trade side must be BUY or SELL.")

        if new_shares <= 1e-8:
            conn.execute("DELETE FROM holdings WHERE ticker = ?", (ticker,))
        else:
            conn.execute(
                """
                INSERT INTO holdings (ticker, shares) VALUES (?, ?)
                ON CONFLICT(ticker) DO UPDATE SET shares = excluded.shares
                """,
                (ticker, new_shares),
            )

        conn.execute(
            """
            INSERT INTO transactions
            (timestamp, ticker, side, shares, price, total)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ticker, side, shares, price, total,
            ),
        )


def add_to_watchlist(ticker):
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Enter a ticker symbol.")
    # Verify that Yahoo Finance recognizes the symbol before saving it.
    get_stock_data(ticker)
    with connect_db() as conn:
        conn.execute("INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)", (ticker,))


def remove_from_watchlist(ticker):
    with connect_db() as conn:
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))


def money(value):
    return f"${value:,.2f}"


st.set_page_config(
    page_title="Mula Stocks",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()


st.markdown("""
<style>
/* Main background */
.stApp {
    background: #080c14;
    color: #f5f7fa;
}

[data-testid="stAppViewContainer"] {
    background: #080c14;
}

[data-testid="stHeader"] {
    background: #080c14;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #101827;
    border-right: 1px solid #263449;
}

[data-testid="stSidebar"] * {
    color: #e8eef7 !important;
}

/* Main text */
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] p,
.stMarkdown h1, .stMarkdown h2,
.stMarkdown h3 {
    color: #f5f7fa !important;
}

/* Hero banner */
.hero {
    padding: 32px;
    border-radius: 20px;
    background: linear-gradient(120deg, #142b31, #17243b);
    border: 1px solid #29434a;
    margin-bottom: 25px;
}

.hero h1 {
    color: white !important;
    font-size: 42px;
}

.hero p {
    color: #aab9c9 !important;
}

/* Portfolio metric cards */
[data-testid="stMetric"] {
    background: #131e2e;
    border: 1px solid #29394e;
    padding: 22px;
    border-radius: 16px;
}

[data-testid="stMetricLabel"] {
    color: #aab9c9 !important;
}

[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-weight: 700;
}

/* Buttons */
.stButton button,
.stFormSubmitButton button {
    background: #00c878;
    color: #07140f !important;
    border: none;
    border-radius: 12px;
    font-weight: 700;
    padding: 10px 20px;
    transition: 0.2s;
}

.stButton button:hover,
.stFormSubmitButton button:hover {
    background: #00e58a;
    border: none;
}

/* Input fields */
.stTextInput input,
.stNumberInput input {
    background: #172337;
    color: white !important;
    border: 1px solid #34465e;
    border-radius: 10px;
}

/* Data tables */
[data-testid="stDataFrame"] {
    border: 1px solid #29394e;
    border-radius: 12px;
}

/* Alerts */
[data-testid="stAlert"] {
    border-radius: 12px;
}

/* Dividers */
hr {
    border-color: #263449;
}
</style>
""", unsafe_allow_html=True)


st.markdown("""
<div class="hero">
  <h1>📈 Mula Stocks</h1>
  <p>Your personal stock-market practice dashboard.</p>
</div>
<div class="notice">
  PAPER TRADING ONLY — Trades use simulated money. Prices are informational and may be delayed.
  This app does not place real orders or provide investment advice.
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("Mula Stocks")
    page = st.radio(
        "Navigate",
        ["Overview", "Trade", "Watchlist", "Activity"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Practice account")
    st.metric("Available cash", money(get_cash()))
    st.caption("Starting balance: $10,000")

cash = get_cash()
holdings = get_holdings()

# Get quotes needed to calculate the portfolio. A missing quote won't crash the app.
quotes = {}
quote_errors = {}
tickers_needed = sorted(set(holdings) | set(get_watchlist()))
for symbol in tickers_needed:
    try:
        quotes[symbol] = get_stock_data(symbol)
    except Exception as exc:
        quote_errors[symbol] = str(exc)

holdings_value = sum(
    shares * quotes[ticker]["price"]
    for ticker, shares in holdings.items()
    if ticker in quotes
)
account_value = cash + holdings_value
total_gain = account_value - STARTING_CASH
total_return = (total_gain / STARTING_CASH * 100) if STARTING_CASH else 0

if page == "Overview":
    st.subheader("Your portfolio")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total account value", money(account_value))
    c2.metric("Available cash", money(cash))
    c3.metric("Invested value", money(holdings_value))
    c4.metric("Total simulated return", f"{money(total_gain)} ({total_return:+.2f}%)")

    st.subheader("Your holdings")
    if holdings:
        rows = []
        for ticker, shares in holdings.items():
            if ticker not in quotes:
                rows.append({
                    "Ticker": ticker, "Shares": shares,
                    "Price": "Unavailable", "Market value": "Unavailable",
                })
            else:
                q = quotes[ticker]
                rows.append({
                    "Ticker": ticker,
                    "Shares": round(shares, 6),
                    "Price": money(q["price"]),
                    "Market value": money(shares * q["price"]),
                    "Daily change": f"{q['percent']:+.2f}%",
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("You don't own any stocks yet. Visit Trade to make a simulated purchase.")

    st.subheader("Portfolio allocation")
    if holdings_value > 0:
        allocation = pd.DataFrame([
            {"Asset": ticker, "Value": shares * quotes[ticker]["price"]}
            for ticker, shares in holdings.items() if ticker in quotes
        ])
        allocation.loc[len(allocation)] = ["Cash", cash]
        st.bar_chart(allocation.set_index("Asset"))
    else:
        st.caption("Your allocation chart will appear after your first simulated purchase.")

    st.subheader("Market snapshot")
    watch = get_watchlist()
    market_rows = []
    for ticker in watch:
        if ticker in quotes:
            q = quotes[ticker]
            market_rows.append({
                "Ticker": ticker,
                "Latest available price": money(q["price"]),
                "Daily change": f"{q['change']:+.2f}",
                "Daily change %": f"{q['percent']:+.2f}%",
                "Data date": q["as_of"],
            })
    if market_rows:
        st.dataframe(pd.DataFrame(market_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Market quotes are temporarily unavailable.")

elif page == "Trade":
    st.subheader("Trade stocks")
    st.write("Buy or sell using your simulated account balance.")
    left, right = st.columns([1, 1])

    with left:
        with st.form("trade_form"):
            ticker_input = st.text_input("Ticker symbol", value="AAPL").strip().upper()
            side = st.radio("Action", ["BUY", "SELL"], horizontal=True)
            shares_input = st.number_input(
                "Shares (fractional shares allowed)",
                min_value=0.000001,
                value=1.0,
                step=0.25,
                format="%.6f",
            )
            submitted = st.form_submit_button(
                "Preview and submit simulated trade",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            try:
                quote = get_stock_data(ticker_input)
                estimated_total = shares_input * quote["price"]
                st.write(f"Estimated price: **{money(quote['price'])}** per share")
                st.write(f"Estimated total: **{money(estimated_total)}**")
                if side == "BUY":
                    st.write(f"Cash after trade: **{money(cash - estimated_total)}**")
                else:
                    st.write(f"Cash after trade: **{money(cash + estimated_total)}**")
                execute_trade(ticker_input, side, shares_input, quote["price"])
                get_stock_data.clear()
                st.success(
                    f"Simulated {side.lower()} completed: "
                    f"{shares_input:.6f} shares of {ticker_input}."
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with right:
        st.markdown("#### Quote lookup")
        lookup = st.text_input("Look up a ticker", value="MSFT", key="quote_lookup")
        if st.button("Get quote", use_container_width=True):
            try:
                q = get_stock_data(lookup)
                st.metric(
                    f"{lookup.upper()} latest available price",
                    money(q["price"]),
                    f"{q['change']:+.2f} ({q['percent']:+.2f}%)",
                )
                st.caption(f"Latest daily data date: {q['as_of']}")
                st.line_chart(q["history"]["Close"])
            except Exception as exc:
                st.error(str(exc))

    st.caption("Quotes are fetched from Yahoo Finance through yfinance. They may be delayed, incomplete, or unavailable.")

elif page == "Watchlist":
    st.subheader("Your watchlist")
    with st.form("watchlist_form"):
        new_ticker = st.text_input("Add a ticker symbol (for example, META)")
        add_clicked = st.form_submit_button("Add to watchlist")
    if add_clicked:
        try:
            add_to_watchlist(new_ticker)
            st.success(f"{new_ticker.upper()} added.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    watch = get_watchlist()
    if watch:
        for ticker in watch:
            col1, col2, col3 = st.columns([2, 2, 1])
            col1.write(f"**{ticker}**")
            if ticker in quotes:
                q = quotes[ticker]
                col2.write(f"{money(q['price'])}  ({q['percent']:+.2f}%)")
            else:
                try:
                    q = get_stock_data(ticker)
                    col2.write(f"{money(q['price'])}  ({q['percent']:+.2f}%)")
                except Exception:
                    col2.write("Quote unavailable")
            if col3.button("Remove", key=f"remove_{ticker}"):
                remove_from_watchlist(ticker)
                st.rerun()
    else:
        st.info("Your watchlist is empty.")

elif page == "Activity":
    st.subheader("Transaction activity")
    transactions = get_transactions()
    if transactions:
        df = pd.DataFrame(transactions)
        df = df.rename(columns={
            "timestamp": "Date and time",
            "ticker": "Ticker",
            "side": "Action",
            "shares": "Shares",
            "price": "Price per share",
            "total": "Total",
        })
        df = df[[
            "Date and time", "Ticker", "Action",
            "Shares", "Price per share", "Total",
        ]]
        df["Price per share"] = df["Price per share"].map(money)
        df["Total"] = df["Total"].map(money)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Your trades will appear here.")

st.divider()
st.caption(
    "Mula Stocks is an educational paper-trading project. "
    "It is not affiliated with Robinhood. Market data is provided by Yahoo Finance "
    "and may be delayed or subject to availability."
)
