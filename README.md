# Bot de alerte Fomo → Telegram

Botul urmărește portofelele traderilor de top de pe Fomo și îți trimite pe Telegram
un mesaj când cumpără sau vând un token (nume, sumă, market cap, lichiditate, vechime,
link spre grafic). Dacă mai mulți traderi urmăriți cumpără același token în ultimele
6 ore, mesajul o spune (🔥). **Nu tranzacționează și nu cere nicio cheie privată.**

Rulează gratuit pe GitHub, la fiecare ~5 minute (uneori GitHub întârzie câteva minute).

---

## Pasul 1 — Botul de Telegram (5 min)

1. În Telegram, caută **@BotFather** → scrie `/newbot` → alege un nume.
2. Primești un **token** (arată așa: `123456789:AAH...`). Păstrează-l.
3. Deschide botul tău nou și apasă **Start** (scrie-i orice mesaj).
4. În browser deschide (pui tokenul tău în loc de TOKEN):
   `https://api.telegram.org/botTOKEN/getUpdates`
5. Caută `"chat":{"id":` — numărul de după e **chat ID-ul** tău.

## Pasul 2 — Cheia Helius (3 min)

1. Fă cont gratuit pe **dashboard.helius.dev**.
2. Copiază **API key**-ul din dashboard.

## Pasul 3 — Pune botul pe GitHub (10 min)

1. Fă cont pe **github.com** → butonul **New** → nume `fomo-bot` → bifează **Private** → **Create**.
2. Apasă **uploading an existing file** și trage înăuntru TOATE fișierele din arhivă,
   inclusiv folderul `.github` (de pe calculator, nu de pe telefon). **Commit changes**.
3. **Settings → Secrets and variables → Actions → New repository secret**, adaugă 3:
   - `HELIUS_API_KEY` = cheia de la Helius
   - `TELEGRAM_TOKEN` = tokenul de la BotFather
   - `TELEGRAM_CHAT_ID` = numărul de la pasul 1.5
4. **Settings → Actions → General → Workflow permissions** → alege
   **Read and write permissions** → **Save**.

## Pasul 4 — Alege traderii

1. În Fomo, deschide leaderboard-ul și profilul traderilor care îți plac.
2. Copiază **adresa portofelului Solana** din profil.
3. Pe GitHub, deschide `wallets.txt` → creionul ✏️ → pune câte o linie:
   `ADRESA  NumeTrader` → **Commit changes**.

Începe cu 5–10 traderi. Contul gratuit Helius are o limită de credite pe lună, așa că
verifică din când în când consumul în dashboard-ul Helius.

## Pasul 5 — Pornește

Tab-ul **Actions** → **Alerte Fomo** → **Run workflow**. Primești pe Telegram
„✅ Botul a pornit”. De acum rulează singur.

---

## Setări (în `bot.py`, sus)

| Setare | Ce face | Implicit |
|---|---|---|
| `MIN_LICHIDITATE_USD` | ignoră tokenurile cu lichiditate mai mică | 10.000 $ |
| `MIN_SUMA_USD` | ignoră tranzacțiile mai mici | 50 $ |
| `ALERTE_VANZARI` | `False` = doar cumpărări | `True` |
| `ORE_GRUP` | fereastra pentru „🔥 au mai cumpărat” | 6 ore |

## Probleme

- **Nu vine nimic pe Telegram:** în **Actions** apasă pe ultima rulare și vezi mesajul
  de eroare. „Lipsesc setarile secrete” = un secret e scris greșit.
- **Eroare la „Salveaza ce a vazut botul”:** nu ai făcut pasul 3.4.
- **Oprire:** Actions → Alerte Fomo → **⋯ → Disable workflow**.

> Alertele sunt informații, nu recomandări. Când vezi alerta, traderul a intrat deja,
> iar meme coin-urile pot pierde mult în câteva minute. Testează o vreme doar
> urmărind, fără bani.
