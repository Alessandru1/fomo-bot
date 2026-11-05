"""
Bot de alerte Fomo -> Telegram
Urmareste portofelele (Solana) ale traderilor din wallets.txt si trimite
pe Telegram cand cumpara sau vand un token.

Nu tranzactioneaza si nu are nevoie de nicio cheie privata.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

# ================== SETARI (le poti schimba) ==================
MIN_LICHIDITATE_USD = 10_000     # ignora tokenurile cu lichiditate mai mica
MIN_SUMA_USD = 50                # ignora cumparari/vanzari mai mici de atat
ALERTE_VANZARI = True            # True = anunta si cand vand
ORE_GRUP = 6                     # cate ore inapoi cauta "mai multi traderi pe acelasi token"
# ==============================================================

HELIUS_KEY = os.environ.get("HELIUS_API_KEY", "").strip()
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

STATE_FILE = "state.json"
WALLETS_FILE = "wallets.txt"

SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
BAZA = {SOL, USDC, USDT}  # monede "de plata", nu primesti alerte pentru ele


# ---------------------------------------------------------------- utilitare
def citeste_portofele(cale=WALLETS_FILE):
    """wallets.txt: o linie per trader -> ADRESA  nume (numele e optional)."""
    rezultat = []
    with open(cale, encoding="utf-8") as f:
        for linie in f:
            linie = linie.split("#")[0].strip()
            if not linie:
                continue
            parti = linie.split(maxsplit=1)
            adresa = parti[0]
            nume = parti[1].strip() if len(parti) > 1 else adresa[:4] + "…" + adresa[-4:]
            rezultat.append((adresa, nume))
    return rezultat


def incarca_stare():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"ultima_tx": {}, "cumparari": {}}


def salveaza_stare(stare):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(stare, f, indent=1)


def get_json(url, **kw):
    for incercare in range(3):
        try:
            r = requests.get(url, timeout=20, **kw)
            if r.status_code == 429:          # prea multe cereri, asteptam
                time.sleep(2 * (incercare + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"  eroare retea ({e}), reincerc…")
            time.sleep(2)
    return None


# ---------------------------------------------------------------- surse de date
def tranzactii_noi(adresa, ultima_semnatura):
    """Tranzactiile portofelului mai noi decat ultima vazuta (cele mai noi primele)."""
    url = f"https://api-mainnet.helius-rpc.com/v0/addresses/{adresa}/transactions"
    date = get_json(url, params={"api-key": HELIUS_KEY, "limit": 25})
    if not isinstance(date, list):
        return [], ultima_semnatura
    noi = []
    for tx in date:
        if tx.get("signature") == ultima_semnatura:
            break
        noi.append(tx)
    cea_mai_noua = date[0]["signature"] if date else ultima_semnatura
    return noi, cea_mai_noua


def info_token(mint):
    """Nume, pret, lichiditate etc. de pe DexScreener (perechea cu cea mai mare lichiditate)."""
    date = get_json(f"https://api.dexscreener.com/latest/dex/tokens/{mint}")
    perechi = (date or {}).get("pairs") or []
    perechi = [p for p in perechi
               if p.get("chainId") == "solana" and (p.get("baseToken") or {}).get("address") == mint]
    if not perechi:
        return None
    p = max(perechi, key=lambda x: (x.get("liquidity") or {}).get("usd") or 0)
    return {
        "nume": p["baseToken"].get("name", "?"),
        "simbol": p["baseToken"].get("symbol", "?"),
        "pret": float(p.get("priceUsd") or 0),
        "lichiditate": (p.get("liquidity") or {}).get("usd") or 0,
        "mcap": p.get("marketCap") or p.get("fdv") or 0,
        "creat": p.get("pairCreatedAt"),
        "url": p.get("url") or f"https://dexscreener.com/solana/{mint}",
    }


# ---------------------------------------------------------------- logica
def analizeaza(tx, adresa):
    """Returneaza lista de (tip, mint, cantitate) pentru o tranzactie. tip = BUY / SELL."""
    primit, trimis = {}, {}
    for t in tx.get("tokenTransfers") or []:
        cant = float(t.get("tokenAmount") or 0)
        if cant <= 0:
            continue
        if t.get("toUserAccount") == adresa:
            primit[t["mint"]] = primit.get(t["mint"], 0) + cant
        if t.get("fromUserAccount") == adresa:
            trimis[t["mint"]] = trimis.get(t["mint"], 0) + cant

    nativ = tx.get("nativeTransfers") or []
    sol_iesit = sum(n.get("amount", 0) for n in nativ if n.get("fromUserAccount") == adresa) / 1e9
    sol_intrat = sum(n.get("amount", 0) for n in nativ if n.get("toUserAccount") == adresa) / 1e9

    a_platit = sol_iesit > 0.001 or any(m in BAZA for m in trimis)
    a_incasat = sol_intrat > 0.001 or any(m in BAZA for m in primit)

    rezultat = []
    for mint, cant in primit.items():
        if mint not in BAZA and a_platit and mint not in trimis:
            rezultat.append(("BUY", mint, cant))
    for mint, cant in trimis.items():
        if mint not in BAZA and a_incasat and mint not in primit:
            rezultat.append(("SELL", mint, cant))
    return rezultat


def format_bani(x):
    if x >= 1_000_000:
        return f"${x / 1_000_000:.2f}M"
    if x >= 1_000:
        return f"${x / 1_000:.1f}K"
    return f"${x:,.0f}"


def varsta(ms):
    if not ms:
        return "necunoscută"
    ore = (time.time() - ms / 1000) / 3600
    if ore < 1:
        return f"{max(int(ore * 60), 1)} min"
    if ore < 48:
        return f"{ore:.0f} ore"
    return f"{ore / 24:.0f} zile"


def trimite_telegram(text):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=20,
        )
        if not r.ok:
            print("  Telegram a refuzat mesajul:", r.text)
    except requests.RequestException as e:
        print("  Nu am putut trimite pe Telegram:", e)


def mesaj(tip, nume_trader, adresa, mint, info, suma_usd, alti_traderi):
    titlu = "🟢 CUMPĂRARE" if tip == "BUY" else "🔴 VÂNZARE"
    linii = [
        f"<b>{titlu}</b> — {nume_trader}",
        f"<b>${info['simbol']}</b> ({info['nume']})",
        f"Sumă: ~{format_bani(suma_usd)}",
        f"Market cap: {format_bani(info['mcap'])} · Lichiditate: {format_bani(info['lichiditate'])}",
        f"Vechime: {varsta(info['creat'])}",
    ]
    if alti_traderi:
        linii.append(f"🔥 Au mai cumpărat recent: {', '.join(alti_traderi)}")
    linii += [
        f"<code>{mint}</code>",
        f"<a href=\"{info['url']}\">Grafic</a> · <a href=\"https://solscan.io/account/{adresa}\">Portofel</a>",
    ]
    return "\n".join(linii)


def main():
    lipsa = [n for n, v in [("HELIUS_API_KEY", HELIUS_KEY), ("TELEGRAM_TOKEN", TG_TOKEN),
                            ("TELEGRAM_CHAT_ID", TG_CHAT)] if not v]
    if lipsa:
        sys.exit("Lipsesc setarile secrete: " + ", ".join(lipsa))

    portofele = citeste_portofele()
    if not portofele:
        sys.exit("wallets.txt e gol. Adauga cel putin o adresa de portofel.")
    stare = incarca_stare()
    acum = time.time()

    # curata cumpararile mai vechi de ORE_GRUP
    for mint in list(stare["cumparari"]):
        stare["cumparari"][mint] = [c for c in stare["cumparari"][mint]
                                    if acum - c["t"] < ORE_GRUP * 3600]
        if not stare["cumparari"][mint]:
            del stare["cumparari"][mint]

    if not stare["ultima_tx"]:
        trimite_telegram("✅ Botul de alerte Fomo a pornit. Urmăresc "
                         f"{len(portofele)} traderi și te anunț la următoarele lor tranzacții.")

    trimise = 0
    for adresa, nume in portofele:
        ultima = stare["ultima_tx"].get(adresa)
        noi, cea_mai_noua = tranzactii_noi(adresa, ultima)
        stare["ultima_tx"][adresa] = cea_mai_noua
        if ultima is None:      # trader nou adaugat: doar memoram, fara alerte vechi
            continue

        for tx in reversed(noi):  # de la cea mai veche la cea mai noua
            for tip, mint, cant in analizeaza(tx, adresa):
                if tip == "SELL" and not ALERTE_VANZARI:
                    continue
                info = info_token(mint)
                if not info:
                    continue
                suma = cant * info["pret"]
                if info["lichiditate"] < MIN_LICHIDITATE_USD or suma < MIN_SUMA_USD:
                    continue

                alti = []
                if tip == "BUY":
                    lista = stare["cumparari"].setdefault(mint, [])
                    alti = sorted({c["nume"] for c in lista if c["adresa"] != adresa})
                    lista.append({"adresa": adresa, "nume": nume, "t": tx.get("timestamp") or acum})

                trimite_telegram(mesaj(tip, nume, adresa, mint, info, suma, alti))
                trimise += 1
                time.sleep(0.5)
        time.sleep(0.2)

    salveaza_stare(stare)
    print(f"Gata: {len(portofele)} portofele verificate, {trimise} alerte trimise "
          f"({datetime.now(timezone.utc):%H:%M} UTC).")


if __name__ == "__main__":
    main()
