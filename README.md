# Hispanic Heritage Historical Data Explorer

A Streamlit classroom app for exploring historical World Bank indicators, editing a clearly labeled working dataset, fitting centered-time polynomial models, calculating estimates, comparing countries, and exporting CSV, Excel, and PDF reports.

## Requirements

Python 3.10–3.12 recommended. Dependencies are version-bounded in `requirements.txt`. The versions are compatible dependency ranges, not a claim that this exact environment was executed or tested. The app authoring environment did not run a full Streamlit/API integration test; use the verification checklist below.

## Run locally

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed in the terminal (usually `http://localhost:8501`). An internet connection is needed for World Bank API requests.

## Data and interpretation

- The app requests calendar years `current year - 70` through `current year - 1`, inclusive. It reports actual non-null coverage and observation count; 70 years of values are not guaranteed.
- The official World Bank API is the data source. Null values are omitted, never filled with invented or random values.
- GDP per capita is not average wealth or household income. Crude birth rate is a rate, not a birth count. Net migration is a net total, not an emigration count.
- Brazil is offered as a Latin American comparison country, but it is Portuguese-speaking rather than Spanish-speaking.
- Polynomial fits are descriptive. In-sample R² and MAE are not independent validation. The optional chronological holdout reserves the latest 20% of valid years when enough training points remain.
- Estimates outside the observed time range are extrapolations and can become implausible. The app does not clip them or label simplified bounds as 95% prediction intervals.
- The editor is a working copy. “Reset to source” restores the retrieved source values. Exports identify whether the current working data is a user-modified scenario.

## Deploy to GitHub and Streamlit Community Cloud

1. Create a GitHub repository and add `app.py`, `requirements.txt`, `README.md`, and `sources.md`.
2. Commit and push the files. Do not commit API keys or credentials; this app uses the public World Bank API and requires no credentials.
3. In Streamlit Community Cloud, create a new app, connect the repository/branch, and set the main file path to `app.py`.
4. Deploy. Check app logs if startup or dependency installation fails.

## Deploy to Render

1. Create a **Python Web Service** linked to the GitHub repository.
2. Build command:

   ```bash
   pip install -r requirements.txt
   ```

3. Start command (single line):

   ```bash
   python -m streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT
   ```

4. Deploy and inspect Render logs. Confirm the service uses a supported Python version and that outbound HTTPS requests are allowed.

## Verification checklist

- **Source accuracy:** compare the displayed indicator code and years with the World Bank indicator page and API request URL in the app. Verify the definition and unit against official metadata.
- **Coverage:** check that reported observation count matches non-null working rows and actual first/last years; gaps are normal.
- **Edit/reset:** change a value or add a row. Confirm “USER-MODIFIED SCENARIO” appears and exports reflect it. Press “Reset to source” and confirm source values return.
- **Validation:** try a decimal year, duplicate year, blank value, negative value for a nonnegative indicator, and an out-of-range unemployment percentage. Confirm warnings appear and invalid rows do not enter the fit.
- **Insufficient data:** remove rows until fewer than degree + 1 distinct valid years remain. Confirm the app stops with a clear message rather than fitting a deficient model.
- **Equation/metrics:** check `t = year - base year`, degree, observation count, in-sample R², MAE, mean, and residuals. Independently evaluate the displayed polynomial for a few years.
- **Single/batch agreement:** calculate a year with “Calculate Value”, include the same year in batch mode, and check the displayed difference is approximately zero.
- **Invalid batch input:** try `2000, nope, 2101, 2001.5`; verify invalid tokens are explained.
- **API failure:** disconnect from the internet or temporarily use an invalid indicator in a development copy. Confirm a useful error appears and no substitute values are fabricated.
- **Controls:** change country, indicator, degree, sample increment, horizon, comparison countries, pathway, and printer mode. Confirm each affects its corresponding output.
- **Exports:** download CSV, open the `.xlsx` workbook and inspect Summary / Working Data / Calculated Years sheets, and open the PDF. Check metadata, equation, metrics, chart, findings/limitations, preview, and calculated results.
- **Deployment:** test the deployed URL in a fresh browser session, verify dependencies install, and inspect logs after an API or startup error.

## Troubleshooting

- `ModuleNotFoundError`: activate the intended virtual environment and rerun `pip install -r requirements.txt`.
- `requests` timeout / API errors: verify internet access and retry; public API availability and rate limits are outside the app's control.
- `No observations`: some country-indicator pairs have sparse coverage. Select another indicator or country; do not replace missing data with zeros.
- Polynomial fitting error: ensure there are at least degree + 1 distinct valid years. Higher-degree fits are more sensitive to sparse data.
- Excel/PDF export issue: confirm `XlsxWriter` and `reportlab` installed successfully, then inspect terminal logs.
- Deployment health/startup issue: verify `app.py` is the main file and that Render's start command binds to `0.0.0.0` and `$PORT`.

## How the code works

- `fetch_world_bank`: cached request to the official API with timeout, HTTP, JSON, and empty-response handling.
- `validate_working_data`: checks editable year/value rows and applies simple indicator-specific bounds.
- `fit_polynomial`: fits a degree-d polynomial using `t = year - base year`, which reduces numerical conditioning problems versus using large calendar years directly.
- `predict`: applies the same centered-time transform once for all single-year, batch, and plot estimates.
- `chronological_holdout`: fits on earlier years and scores the latest segment separately when there are enough training rows.
- Chart/export helpers: create a Matplotlib chart and genuine CSV, `.xlsx`, and ReportLab PDF files from current app state.

## Mathematical assumptions and limitations

A polynomial is a flexible curve, not a causal model or a guarantee of future outcomes. Higher degree can reduce training error while creating unstable oscillations and implausible extrapolation. Missing observations can cause uneven time gaps. R² and MAE here are in-sample summaries; holdout metrics can be unstable for short series. Residuals and MAE provide error context but are not formal prediction intervals. The derivative-based analysis applies to the fitted polynomial and is limited to the displayed historical interval unless explicitly stated otherwise. The app does not infer historical causes from trends.
