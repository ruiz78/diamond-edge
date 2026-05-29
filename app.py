"""
Diamond Edge — Flask Web Server
Runs on Render.com (free tier)
Serves the frontend and provides API endpoints for stats + AI predictions
"""

from flask import Flask, jsonify, request, send_from_directory
import requests, os, warnings, json
from datetime import datetime
import pandas as pd

warnings.filterwarnings("ignore")

try:
    from pybaseball import batting_stats_bref, pitching_stats_bref, standings, cache
    cache.enable()
    PYBASEBALL_OK = True
except Exception:
    PYBASEBALL_OK = False

app = Flask(__name__, static_folder="static")

ODDS_API_KEY  = os.environ.get("ODDS_API_KEY", "5a5e898df52b4c54e1535b5ee8db8a4b")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

TEAM_MAP = {
    "Arizona Diamondbacks":  ("ARI","Arizona"),
    "Atlanta Braves":        ("ATL","Atlanta"),
    "Baltimore Orioles":     ("BAL","Baltimore"),
    "Boston Red Sox":        ("BOS","Boston"),
    "Chicago Cubs":          ("CHC","Chi Cubs"),
    "Chicago White Sox":     ("CHW","Chi White Sox"),
    "Cincinnati Reds":       ("CIN","Cincinnati"),
    "Cleveland Guardians":   ("CLE","Cleveland"),
    "Colorado Rockies":      ("COL","Colorado"),
    "Detroit Tigers":        ("DET","Detroit"),
    "Houston Astros":        ("HOU","Houston"),
    "Kansas City Royals":    ("KCR","Kansas City"),
    "Los Angeles Angels":    ("LAA","Los Angeles"),
    "Los Angeles Dodgers":   ("LAD","Los Angeles"),
    "Miami Marlins":         ("MIA","Miami"),
    "Milwaukee Brewers":     ("MIL","Milwaukee"),
    "Minnesota Twins":       ("MIN","Minnesota"),
    "New York Mets":         ("NYM","NY Mets"),
    "New York Yankees":      ("NYY","NY Yankees"),
    "Athletics":             ("ATH","Athletics"),
    "Philadelphia Phillies": ("PHI","Philadelphia"),
    "Pittsburgh Pirates":    ("PIT","Pittsburgh"),
    "San Diego Padres":      ("SDP","San Diego"),
    "San Francisco Giants":  ("SFG","San Francisco"),
    "Seattle Mariners":      ("SEA","Seattle"),
    "St. Louis Cardinals":   ("STL","St. Louis"),
    "Tampa Bay Rays":        ("TBR","Tampa Bay"),
    "Texas Rangers":         ("TEX","Texas"),
    "Toronto Blue Jays":     ("TOR","Toronto"),
    "Washington Nationals":  ("WSN","Washington"),
}

STANDINGS_KW = {
    "ARI":"D-backs","ATL":"Braves","BAL":"Orioles","BOS":"Red Sox",
    "CHC":"Cubs","CHW":"White Sox","CIN":"Reds","CLE":"Guardians",
    "COL":"Rockies","DET":"Tigers","HOU":"Astros","KCR":"Royals",
    "LAA":"Angels","LAD":"Dodgers","MIA":"Marlins","MIL":"Brewers",
    "MIN":"Twins","NYM":"Mets","NYY":"Yankees","ATH":"Athletics",
    "PHI":"Phillies","PIT":"Pirates","SDP":"Padres","SFG":"Giants",
    "SEA":"Mariners","STL":"Cardinals","TBR":"Rays","TEX":"Rangers",
    "TOR":"Blue Jays","WSN":"Nationals",
}

_cache = {}

def get_bref_data(year):
    key = f"bref_{year}"
    if key in _cache:
        return _cache[key]
    try:
        bat = batting_stats_bref(year) if PYBASEBALL_OK else pd.DataFrame()
        pit = pitching_stats_bref(year) if PYBASEBALL_OK else pd.DataFrame()
        _cache[key] = (bat, pit)
        return bat, pit
    except Exception as e:
        print(f"BRef error: {e}")
        return pd.DataFrame(), pd.DataFrame()

def filter_team(df, kw):
    if df is None or df.empty or "Tm" not in df.columns:
        return pd.DataFrame()
    exact = df[df["Tm"] == kw]
    return exact if not exact.empty else df[df["Tm"].str.contains(kw, case=False, na=False)]

def num(s):
    return pd.to_numeric(s, errors="coerce")

def team_batting(kw, bat_df):
    t = filter_team(bat_df, kw)
    if t.empty: return {}
    AB=num(t["AB"]).sum(); H=num(t["H"]).sum()
    BB=num(t["BB"]).sum(); HR=num(t["HR"]).sum()
    R=num(t["R"]).sum();   SO=num(t["SO"]).sum()
    RBI=num(t["RBI"]).sum()
    out = {}
    if AB > 0:
        out["BA"]  = f"{H/AB:.3f}"
        out["OBP"] = f"{(H+BB)/(AB+BB):.3f}" if (AB+BB)>0 else "N/A"
        out["K%"]  = f"{SO/AB*100:.1f}%"
    if not pd.isna(HR):  out["HR"]  = str(int(HR))
    if not pd.isna(R):   out["R"]   = str(int(R))
    if not pd.isna(RBI): out["RBI"] = str(int(RBI))
    return out

def team_pitching(kw, pit_df):
    t = filter_team(pit_df, kw)
    if t.empty: return {}
    ip=num(t["IP"]).fillna(0); era=num(t["ERA"]).fillna(0)
    whip=num(t["WHIP"]).fillna(0); so=num(t["SO"]).fillna(0)
    bb=num(t["BB"]).fillna(0);  hr=num(t["HR"]).fillna(0)
    tip = ip.sum()
    if tip == 0: return {}
    return {
        "ERA":  f"{(era*ip).sum()/tip:.2f}",
        "WHIP": f"{(whip*ip).sum()/tip:.3f}",
        "K/9":  f"{so.sum()/tip*9:.1f}",
        "BB/9": f"{bb.sum()/tip*9:.1f}",
        "HR/9": f"{hr.sum()/tip*9:.2f}",
    }

def pitcher_stats(name, pit_df):
    if not name or pit_df.empty: return {}
    mask = pit_df["Name"].astype(str).str.lower().str.contains(name.lower(), na=False)
    hits = pit_df[mask]
    if hits.empty: return {}
    r = hits.sort_values("IP", ascending=False).iloc[0]
    out = {"Name": str(r["Name"])}
    for col, fmt in [("ERA",":.2f"),("WHIP",":.3f"),("SO",":.0f"),("BB",":.0f"),("IP",":.1f"),("HR",":.0f")]:
        try: out[col] = format(float(r[col]), fmt[1:])
        except: pass
    return out

def get_record(abbr, year):
    kw = STANDINGS_KW.get(abbr, abbr)
    try:
        for div in standings(year):
            col = div.columns[0]
            m = div[div[col].astype(str).str.contains(kw, case=False, na=False)]
            if not m.empty:
                r = m.iloc[0]
                s = f"{r.get('W','?')}-{r.get('L','?')}"
                try: s += f" ({float(r['W-L%']):.3f})"
                except: pass
                return s
    except: pass
    return "N/A"

def get_odds(home, away):
    try:
        r = requests.get("https://api.the-odds-api.com/v4/sports/baseball_mlb/odds", params={
            "apiKey": ODDS_API_KEY, "regions": "us",
            "markets": "h2h,spreads,totals", "oddsFormat": "american"
        }, timeout=10)
        if r.status_code != 200: return {}
        games = r.json()
        def match(n, team):
            return team.split()[-1].lower() in n.lower() or team.lower() in n.lower()
        game = next((g for g in games if
            (match(g.get("home_team",""), home) and match(g.get("away_team",""), away)) or
            (match(g.get("away_team",""), home) and match(g.get("home_team",""), away))), None)
        if not game: return {}
        books = game.get("bookmakers", [])
        book = next((b for p in ["draftkings","fanduel","betmgm"] for b in books if p in b["key"]), books[0] if books else None)
        if not book: return {}
        result = {"bookmaker": book["title"]}
        for mkt in book.get("markets", []):
            for o in mkt.get("outcomes", []):
                k = mkt["key"]
                n = o["name"]
                if k == "h2h":
                    if match(n, home): result["home_ml"] = o["price"]
                    elif match(n, away): result["away_ml"] = o["price"]
                elif k == "spreads":
                    if match(n, home): result["home_spread"] = f"{o['point']:+.1f} ({o['price']:+d})"
                    elif match(n, away): result["away_spread"] = f"{o['point']:+.1f} ({o['price']:+d})"
                elif k == "totals":
                    if n == "Over":  result["over"]  = f"O{o['point']} ({o['price']:+d})"
                    elif n == "Under": result["under"] = f"U{o['point']} ({o['price']:+d})"
        return result
    except Exception as e:
        print(f"Odds error: {e}")
        return {}

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/games")
def api_games():
    try:
        r = requests.get("https://api.the-odds-api.com/v4/sports/baseball_mlb/odds", params={
            "apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h", "oddsFormat": "american"
        }, timeout=10)
        if r.status_code != 200: return jsonify([])
        games = []
        for g in r.json():
            ct = g.get("commence_time","")
            games.append({
                "id": g["id"],
                "home": g["home_team"],
                "away": g["away_team"],
                "time": ct[11:16] + " UTC" if ct else "TBD",
            })
        return jsonify(games)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stats")
def api_stats():
    home = request.args.get("home","")
    away = request.args.get("away","")
    hpit = request.args.get("hpit","")
    apit = request.args.get("apit","")
    year = datetime.today().year

    home_abbr, home_kw = TEAM_MAP.get(home, ("",""))
    away_abbr, away_kw = TEAM_MAP.get(away, ("",""))

    bat_df, pit_df = get_bref_data(year)

    data = {
        "home": {
            "name": home, "abbr": home_abbr,
            "record": get_record(home_abbr, year),
            "batting": team_batting(home_kw, bat_df),
            "pitching": team_pitching(home_kw, pit_df),
            "sp": pitcher_stats(hpit, pit_df),
        },
        "away": {
            "name": away, "abbr": away_abbr,
            "record": get_record(away_abbr, year),
            "batting": team_batting(away_kw, bat_df),
            "pitching": team_pitching(away_kw, pit_df),
            "sp": pitcher_stats(apit, pit_df),
        },
        "odds": get_odds(home, away),
    }
    return jsonify(data)

@app.route("/api/predict", methods=["POST"])
def api_predict():
    body = request.json or {}
    home    = body.get("home","")
    away    = body.get("away","")
    bet     = body.get("betType","Moneyline (Winner)")
    date    = body.get("date", str(datetime.today().date()))
    hpit    = body.get("homePitcher","")
    apit    = body.get("awayPitcher","")
    stats   = body.get("stats", {})
    odds    = body.get("odds", {})

    def fmt_stats(s, name):
        lines = [f"{name}:"]
        lines.append(f"  Record: {s.get('record','N/A')}")
        if s.get('batting'): lines += [f"  {k}: {v}" for k,v in s['batting'].items()]
        if s.get('pitching'): lines += [f"  Staff {k}: {v}" for k,v in s['pitching'].items()]
        if s.get('sp'): lines += [f"  SP ({s['sp'].get('Name','')}): ERA {s['sp'].get('ERA','?')}, WHIP {s['sp'].get('WHIP','?')}, K/9 {s['sp'].get('SO9',s['sp'].get('SO','?'))}"]
        return "\n".join(lines)

    odds_str = ""
    if odds:
        bk = odds.get('bookmaker','Sportsbook')
        hml = odds.get('home_ml'); aml = odds.get('away_ml')
        if hml: odds_str = f"LIVE ODDS ({bk}): Home ML {hml:+d} | Away ML {aml:+d} | Spread: {odds.get('home_spread','N/A')} / {odds.get('away_spread','N/A')} | Total: {odds.get('over','N/A')} / {odds.get('under','N/A')}"

    prompt = f"""You are a sharp MLB betting analyst. Analyze this matchup and return ONLY valid JSON.

BET TYPE: {bet}
HOME: {home} (SP: {hpit or 'Unknown'})
AWAY: {away} (SP: {apit or 'Unknown'})
DATE: {date}
{odds_str}

{fmt_stats(stats.get('home',{{}}), 'HOME STATS')}

{fmt_stats(stats.get('away',{{}}), 'AWAY STATS')}

Return ONLY this JSON, no markdown:
{{"pick":"<team or OVER/UNDER X.X>","betLabel":"<e.g. MONEYLINE PICK>","winProbability":<51-85>,"confidence":"<HIGH|MEDIUM|LOW>","pickSub":"<one short line>","analysis":"<4-5 sharp sentences referencing specific stats and odds>","homeStats":[{{"label":"Record","value":"<>","better":false}},{{"label":"Team ERA","value":"<>","better":false}},{{"label":"Team BA","value":"<>","better":false}},{{"label":"Runs","value":"<>","better":false}},{{"label":"SP ERA","value":"<>","better":false}},{{"label":"SP WHIP","value":"<>","better":false}}],"awayStats":[{{"label":"Record","value":"<>","better":false}},{{"label":"Team ERA","value":"<>","better":false}},{{"label":"Team BA","value":"<>","better":false}},{{"label":"Runs","value":"<>","better":false}},{{"label":"SP ERA","value":"<>","better":false}},{{"label":"SP WHIP","value":"<>","better":false}}],"leans":{{"ml":{{"pick":"<ABBR or PASS>","class":"<go|pass|fade>","note":"<short>"}},"rl":{{"pick":"<e.g. ATL -1.5 or PASS>","class":"<go|pass|fade>","note":"<short>"}},"ou":{{"pick":"<OVER|UNDER|PASS>","class":"<go|pass|fade>","note":"<short>"}}}},"valueAngles":[{{"tag":"<EDGE|PASS|FADE>","text":"<specific angle with price targets>"}},{{"tag":"<EDGE|PASS|FADE>","text":"<second angle>"}},{{"tag":"<EDGE|PASS|FADE>","text":"<third angle>"}}]}}

Set "better":true on whichever team has the better value per stat (lower ERA = better, higher BA/runs = better)."""

    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"Content-Type":"application/json","x-api-key": ANTHROPIC_KEY,"anthropic-version":"2023-06-01"},
            json={"model":"claude-sonnet-4-20250514","max_tokens":1500,"messages":[{"role":"user","content":prompt}]},
            timeout=30)
        if r.status_code != 200:
            return jsonify({"error": f"Anthropic API error {r.status_code}"}), 500
        text = "".join(c.get("text","") for c in r.json().get("content",[]))
        m = __import__("re").search(r"\{[\s\S]*\}", text)
        if not m: return jsonify({"error":"No JSON in response"}), 500
        return jsonify(json.loads(m.group()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
