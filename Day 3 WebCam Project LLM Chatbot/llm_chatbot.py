import os, json
import pandas as pd, numpy as np
import google.generativeai as genai

#---------------------------------
# Configuration / Constants
#---------------------------------
CSV_CLEAN = "smartcity_env_log_cleaned.csv" # input CSV with cleaned IoT data
TEMP_COL, HUM=COL = "temp_c", "hum"         # raw metric column names
TEMP_NORM, HUM_NORM = "temp_c_norm", "hum_norm" # optional normalized columns (0..1)
MODEL_NAME = "gemini-1.5-flash"             # Gemini model to use
SYSTEM_STYLE = (
    "You are an IoT data assistant."
    "Answer strictly from the JSON results I give you."
    "Be concise, with units and ranges."
)

def _get_gemini_key():
    """
    Resolve GEMINI_API_KEY in this order:
        1) Environment variable
        2) Google Colab secrets (userdata)
        3) Secure prompt via getpass
    Returns the key string or None if unavailable.
    """
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    
    # Try Google Colab secrets, if available
    try:
        from google.colab import userdata # type: ignore
        key = userdata.get("GEMINI_API_KEY")
        if key:
            os.environ["GEMINI_API_KEY"] = key
            return key
    except Exception:
        pass

    # Last resort: Prompt (Works in Colab & Local)
    try:
        from getpass import getpass
        entered = getpass("Enter your GEMINI_API_KEY (leave blank to skip): ")
        if entered.strip():
            os.environ["GEMINI_API_KEY"] = entered.strip()
            return entered.strip()
    except Exception:
        pass

    return None

def load_df():
    """
    Load the cleaned IoT data CSV and ensure numeric columns.
    Returns a pandas DataFrame with numeric temp/humidity (and normalized columns if present).
    """
    if not os.path.exists(CSV_CLEAN):
        raise SystemExit(f"Missing {CSV_CLEAN}")
    
    df = pd.read_csv(CSV_CLEAN)

    # Ensure numeric types for the columns we will compute on
    df[TEMP_COL] = pd.to_numeric(df[TEMP_COL], errors='coerce')
    df[HUM_COL] = pd.to_numeric(df[HUM_COL], errors='coerce')
    if TEMP_NORM in df.columns:
        df[TEMP_NORM] = pd.to_numeric(df[TEMP_NORM], errors='coerce')
    if HUM_NORM in df.columns:
        df[HUM_NORM] = pd.to_numeric(df[HUM_NORM], errors='coerce')

    # No timestamp here; we operate on the whole dataset (row order as-is)
    return df.reset_index(drop=True)

def latest_reading(df):
    """
    Return the latest row's readings as a small JSON-like dict.
    Includes normalized values if those columns exist.
    """

    r = df.iloc[-1] # last row (assumes DataFrame is non-empty)
    return {
        "temp_c": None if pd.isna(r[TEMP_COL]) else float(r[TEMP_COL]),
        "hum": None if pd.isna(r[HUM_COL]) else float(r[HUM_COL]),
        "temp_c_norm": None if TEMP_NORM not in df.columns or pd.isna(r[TEMP_NORM]) else float(r[TEMP_NORM]),
        "hum_norm": None if HUM_NORM not in df.columns or pd.isna(r[HUM_NORM]) else float(r[HUM_NORM]),
    }

def stats_over_all(df, metric="both"):
    """
    Compute min/max/avg over the entire dataset.
    Metrics can be "temp", "hum", or "both".
    Includes normalized stats if those columns exist.
    """
    sub = df.copy()                    # work on a copy for safety
    out = {"count": int(sub.shape[0])} # number of rows considered
    if sub.empty:
        return out
    
    # Temperature stats
    if metric in ("temp", "both"):
        temp = sub[TEMP_COL]
        out["temp_c"] = {
            "min": float(np.nanmin(sub[TEMP_COL])),
            "max": float(np.nanmax(sub[TEMP_COL])),
            "avg": float(np.nanmean(sub[TEMP_COL])),
        }
        if TEMP_NORM in sub.columns:
            out["temp_c_norm"] = {
                "min": float(np.nanmin(sub[TEMP_NORM])),
                "max": float(np.nanmax(sub[TEMP_NORM])),
                "avg": float(np.nanmean(sub[TEMP_NORM])),
            }

    # Humidity stats
    if metric in ("hum", "both"):
        out["hum"] = {
            "min": float(np.nanmin(sub[HUM_COL])),
            "max": float(np.nanmax(sub[HUM_COL])),
            "avg": float(np.nanmean(sub[HUM_COL])),
        }
        if HUM_NORM in sub.columns:
            out["hum_norm"] = {
                "min": float(np.nanmin(sub[HUM_NORM])),
                "max": float(np.nanmax(sub[HUM_NORM])),
                "avg": float(np.nanmean(sub[HUM_NORM])),
            }
    return out

def route(df, q: str):
    """
    Ultra-simple intent router for the CLI:
    - If the user asks for "latest|current|now" -> return latest_reading
    - If they ask for "average|avg|mean|min|max|stats|summary" -> return stats_over_all
      and choose metric ("temp", "hum", or "both") based on keywords
    - Otherwise, fallback to latest_reading
    Returns a dict that also includes _intent (and _metric for stats).
    """
    ql = (q or "").lower()

    # Latest reading intent
    if any(k in ql for k in ("latest", "current", "now")):
        out = latest_reading(df)
        out["_intent"] = "latest"
        return out
    
    # Stats intent (over the whole dataset)
    if any(k in ql for k in ("average", "avg", "mean", "min", "max", "stats", "summary")):
        metric = "both"  # default to both metrics
        if "temp" in ql:
            metric = "temp"
        elif "hum" in ql or "humidity" in ql:
            metric = "hum"
        
        out = stats_over_all(df, metric)
        out["_intent"] = "stats"
        out["_metric"] = metric
        return out
    
def main():
    """
    CLI entry point:
    - Resolve and configure Gemini API key (env -> Colab secrets -> prompt).
    - Load the CSV once.
    - REPL loop: read question, route to a pandas tool, optionally ask Gemini to phrase an answer.
    """
    API_KEY = _get_gemini_key()
    if not API_KEY:
        print("Warning: GEMINI_API_KEY not set. I will just print computed JSON.\n")
        model = None
    else:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_STYLE)

    # Load the dataset
    df = load_df()
    print("SmartCity IoT - Gemini CLI. Type your question (e.g., 'average temp'). Ctrl+C to exit.\n")

    # Simple REPL loop
    while True:
        try:
            q = input("You> ").strip()
            if not q:
                continue  # skip empty input

            # 1) Compute authoritiative results via pandas "tools"
            results = route(df, q)

            # 2) If Gemini is not available, just print the JSON
            if not model:
                print("Computed results:\n", json.dumps(results, indent=2), "\n")
                continue

            # 3) Ask Gemini to phrase a short, direct natural-language answer
            prompt = (
                f"User question:\n{q}\n\n"
                f"Context JSON (authoritative):\n{json.dumps(results, indent=2)}\n\n"
                "Write a short, direct answer with numbers and ranges."
            )
            try: 
                resp = model.generate_content(prompt)
                ans = (resp.text or "").strip() if resp else "No response."
                print("Bot>", ans, "\n")
            except Exception as e:
                # If LLM call fails, fall back to the raw JSON
                print("[Gemini error]", e)
                print("Computed results:\n", json.dumps(results, indent=2), "\n")

        except (KeyboardInterrupt, EOFError):
                # Graceful exit on Ctrl+C/Ctrl+D
                print("\nBye!")
                break