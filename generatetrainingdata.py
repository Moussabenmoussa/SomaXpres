# generate_training_data.py
import csv
import random
import time

FIELDNAMES = [
    "timestamp","symbol","volume_24h","buys","sells",
    "avg_trade","buy_ratio","whale_score","imbalance","label"
]

LABELS = ["BUY","SELL","NEUTRAL"]

def synth_row(symbol):
    volume = random.uniform(1e3, 5e6)
    buys = random.randint(0, 2000)
    sells = random.randint(0, 2000)
    total = max(1, buys + sells)
    buy_ratio = (buys / total) * 100
    avg_trade = volume / total
    whale_score = min(100, int((avg_trade / 1000) * 100))
    imbalance = buys - sells

    # قواعد توليد التسمية (محاكاة لما نريد أن يتعلمه النموذج)
    if avg_trade > 2000 and buy_ratio > 55:
        label = "BUY"
    elif buy_ratio < 40:
        label = "SELL"
    elif avg_trade < 100 and buy_ratio > 60:
        label = "BUY"
    else:
        label = random.choices(LABELS, weights=[0.2,0.2,0.6])[0]

    return {
        "timestamp": int(time.time()),
        "symbol": symbol,
        "volume_24h": int(volume),
        "buys": buys,
        "sells": sells,
        "avg_trade": round(avg_trade,2),
        "buy_ratio": round(buy_ratio,2),
        "whale_score": whale_score,
        "imbalance": imbalance,
        "label": label
    }

def generate_csv(path="training_data.csv", rows=20000, symbols=None):
    symbols = symbols or ["BTCX","ETHX","MIMEX","ALT1","ALT2","TEST"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for _ in range(rows):
            row = synth_row(random.choice(symbols))
            writer.writerow(row)
    print(f"Generated {rows} rows to {path}")

if __name__ == "__main__":
    generate_csv()
