#  MPDTE College Predictor & Analyzer

> A desktop tool to predict MPDTE engineering college admission chances based on JEE rank and category — built for Madhya Pradesh students navigating MPDTE counselling.

---

## ⚠️ Important Notes Before Anything Else

**This tool only works for MPDTE (Madhya Pradesh Directorate of Technical Education) counselling.** It is not designed for JoSAA, MHT-CET, or any other state counselling. If you are not an MP engineering aspirant, this is not for you.

**This project was not built to scale or become a product.** I made it for myself to understand my own MPDTE counselling options. I'm sharing it publicly on the off-chance that even one student finds it useful. That's enough for me.

**This was built with AI assistance (Claude Sonnet by Anthropic).**I am a student and this project was built primarily for personal use. The code was generated with AI help, guided by what I needed. I'm being upfront about this because I think honesty matters more than credit.

---

## What It Does

You import official MPDTE counselling PDFs, enter your JEE rank and category, and the tool tells you:

- Which colleges and branches you have a realistic chance at
- Probability percentage for each option (based on historical closing ranks)
- A suggested counselling preference order
- Which colleges you narrowly missed
- What happens if your rank were slightly different

Everything is stored locally in a SQLite database on your machine. No internet connection needed after setup.

---

## Probability Scale

| Probability | Label |
|---|---|
| 95%+ | Almost Guaranteed |
| 80–95% | Very Safe |
| 60–80% | Safe |
| 40–60% | Possible |
| 20–40% | Difficult |
| < 20% | Very Unlikely |

---

## Features

- **College Predictor** — Enter rank, category, domicile, fee waiver, and get ranked results across all imported data
- **Counselling Strategy** — Optimal preference order weighted by probability and college type (Govt > Aided > SFI > Private)
- **Rank Simulator** — See how your options shift at ±5000 ranks
- **Missed Opportunities** — Colleges just beyond your closing rank
- **Global Search** — Search by college name, branch, city, type
- **Analytics Dashboard** — Category distribution, branch distribution, college type breakdown
- **Export** — CSV, color-coded Excel, and printable PDF report

---

## Installation

### Requirements
- Python 3.10 or higher
- Works on Windows, Linux, and macOS

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/mpdte-predictor.git
cd mpdte-predictor

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### Windows (easier)
```
Double-click run_windows.bat
```

### Linux / Mac
```bash
chmod +x run_linux_mac.sh
./run_linux_mac.sh
```

---

## How to Use

1. **Import PDFs** — Get official MPDTE counselling result PDFs from the MPDTE website and import them through the app. It auto-extracts all data.
2. **Enter your profile** — JEE rank, category (General/OBC/SC/ST/EWS), MP domicile (Yes/No), fee waiver eligibility
3. **Get predictions** — The app scans all imported data and calculates admission probability for every matching college + branch combination
4. **Export** — Save results as CSV, Excel, or PDF report

---

## Project Structure

```
mpdte_predictor/
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
│
├── core/
│   ├── database.py            # SQLite storage layer
│   ├── pdf_extractor.py       # Parses MPDTE counselling PDFs
│   ├── prediction_engine.py   # Probability calculation logic
│   └── export_manager.py      # CSV / Excel / PDF export
│
└── gui/
    └── main_window.py         # Desktop UI (CustomTkinter)
```

**Database location:** `~/mpdte_predictor.db` (your home directory)  
**Exports location:** `~/mpdte_exports/`

---

## Supported PDF Format

The extractor is built for the standard MPDTE counselling allotment PDF table format:

| Column | Description |
|---|---|
| S.No | Serial number |
| Institute Name | Full name with city |
| Institute Type | GOVT / AIDED / S.F.I. / private |
| FW | Y = Fee Waiver row |
| Branch | Branch code (CSE, EC, MECH, etc.) |
| National Player | AI = All India seat |
| Opening Rank | Opening JEE rank |
| Closing Rank | Closing JEE rank |
| Allotted Category | UR/X/OP, OBC/X/OP, SC/X/OP, EWS, etc. |
| Domicile | Y = MP Domicile |
| Total Allotted | Seats filled |

PDFs from different rounds (Round 1, Round 2, etc.) can all be imported — duplicates are detected and skipped automatically.

---

## Dependencies

```
customtkinter   — Desktop GUI
pdfplumber      — PDF table extraction
pandas          — Data handling
reportlab       — PDF report generation
openpyxl        — Excel export
Pillow          — Image support
```

---

## Limitations

- Only works with MPDTE counselling data (MP state engineering admissions)
- Predictions are based on historical closing ranks — actual cutoffs change every year
- PDF extraction may not work perfectly if MPDTE changes their PDF format
- Not tested with all possible edge cases in counselling PDFs

---

## Build as Executable (Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "MPDTE_Predictor" main.py
# Output: dist/MPDTE_Predictor.exe
```

---

## Disclaimer

This tool uses historical MPDTE counselling data for prediction. Actual admission cutoffs vary every year based on the applicant pool, seat availability, and MPDTE policy changes. Always verify with official MPDTE sources at [dte.mponline.gov.in](https://dte.mponline.gov.in).

---

## Why I Built This

I got tired of manually searching through large MPDTE cutoff PDFs during counselling.

I wanted a way to import the PDFs, search all colleges instantly, and estimate my chances based on rank and category.

After building it for myself, I decided to share it publicly in case it helps other MP engineering aspirants.

---

## Honesty Section

I want to be clear about what this is and isn't:

- This is a **personal project** shared publicly in case it helps someone
- The **code was written with AI assistance** (Claude Sonnet by Anthropic) — I directed what to build and what I needed, the AI wrote most of the code
- I am **not a developer** and this is not a polished product
- There are likely bugs and edge cases I haven't handled
- I will not be actively maintaining this — if something breaks, feel free to fork and fix it

If you're an MP engineering student and this helps you make sense of your counselling options, that's all I hoped for.

---

## License

MIT License
