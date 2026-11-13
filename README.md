# Mula Stocks

A single-user educational paper-trading dashboard built with Python and Streamlit.

## Run it
1. Create a Python app in Replit (or another environment that supports Streamlit).
2. Upload `app.py` and `requirements.txt`.
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `streamlit run app.py --server.port 3000 --server.address 0.0.0.0`

The app starts with a simulated $10,000 balance. Trades are stored in a local SQLite database.

## Important limitations
- Paper trading only. No real brokerage connection or real-money orders.
- Quotes come from Yahoo Finance via yfinance and can be delayed, incomplete, or unavailable.
- This starter version is a single-user demo. Do not deploy it as a public multi-user financial app.
- Some hosting platforms use temporary storage; a local SQLite database may reset when the app is redeployed or its environment is replaced. Use managed persistent storage before relying on saved data.
