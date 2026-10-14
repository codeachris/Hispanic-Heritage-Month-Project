from __future__ import annotations

import io
import math
from datetime import date, datetime
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from sklearn.metrics import mean_absolute_error, r2_score

APP_TITLE = "Hispanic Heritage Historical Data Explorer"
API_ROOT = "https://api.worldbank.org/v2"
COUNTRIES = {
    "Mexico (MX)": "MEX", "Brazil (BR)": "BRA", "Argentina (AR)": "ARG",
    "Colombia (CO)": "COL", "Chile (CL)": "CHL", "Peru (PE)": "PER",
    "Venezuela (VE)": "VEN", "Ecuador (EC)": "ECU", "Uruguay (UY)": "URY",
}
INDICATORS = {
    "Life expectancy at birth": {
        "code": "SP.DYN.LE00.IN", "unit": "years",
        "definition": "The number of years a newborn would live if patterns of mortality at the time of birth remained the same.",
        "constraint": "positive",
    },
    "Unemployment, total (national estimate)": {
        "code": "SL.UEM.TOTL.NE.ZS", "unit": "% of total labor force",
        "definition": "Unemployment as a share of the labor force, using national estimates.",
        "constraint": "percent",
    },
    "GDP per capita (current US$)": {
        "code": "NY.GDP.PCAP.CD", "unit": "current US dollars per person",
        "definition": "Gross domestic product divided by midyear population, expressed in current US dollars. This is not average wealth or household income.",
        "constraint": "positive",
    },
    "Crude birth rate": {
        "code": "SP.DYN.CBRT.IN", "unit": "births per 1,000 people per year",
        "definition": "The annual number of live births per 1,000 people. This is a rate, not a total birth count.",
        "constraint": "nonnegative",
    },
    "Net migration": {
        "code": "SM.POP.NETM", "unit": "people (net total)",
        "definition": "The net total of migrants during the period: immigrants minus emigrants. It is not an emigration count.",
        "constraint": "any",
    },
    "Intentional homicide rate": {
        "code": "VC.IHR.PSRC.P5", "unit": "per 100,000 people",
        "definition": "Intentional homicides per 100,000 people, based on the World Bank indicator metadata.",
        "constraint": "nonnegative",
    },
    "Consumer price inflation": {
        "code": "FP.CPI.TOTL.ZG", "unit": "% annual change",
        "definition": "Annual percentage change in the consumer price index.",
        "constraint": "any",
    },
    "Central government debt": {
        "code": "GC.DOD.TOTL.GD.ZS", "unit": "% of GDP",
        "definition": "Central government debt expressed as a percentage of GDP; coverage depends on national reporting.",
        "constraint": "nonnegative",
    },
    "Total reserves including gold": {
        "code": "FI.RES.TOTL.CD", "unit": "current US dollars",
        "definition": "Total reserves including gold, valued in current US dollars.",
        "constraint": "nonnegative",
    },
    "External balance on goods and services": {
        "code": "NE.RSB.GNFS.ZS", "unit": "% of GDP",
        "definition": "External balance on goods and services, expressed as a percentage of GDP.",
        "constraint": "any",
    },
}
WB_SOURCE = "https://data.worldbank.org/"
INDICATOR_SOURCE = "https://api.worldbank.org/v2/indicator/{code}?format=json"
COUNTRY_SOURCE = "https://api.worldbank.org/v2/country/{code}?format=json"

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("HISPANIC HERITAGE DATA LAB · Authentic World Bank data, transparent modeling, and student-led interpretation")
st.info("Brazil is included as a Latin American comparison country. Brazil is not a Spanish-speaking country; its official language is Portuguese.")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_world_bank(country_code: str, indicator_code: str, start_year: int, end_year: int) -> tuple[pd.DataFrame, str]:
    """Fetch a single country-indicator series from the official World Bank API."""
    url = f"{API_ROOT}/country/{country_code}/indicator/{indicator_code}"
    params = {"date": f"{start_year}:{end_year}", "format": "json", "per_page": 20000}
    try:
        response = requests.get(url, params=params, timeout=(5, 25))
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise RuntimeError("The World Bank API request timed out. Try again later or check your connection.") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach the World Bank API: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("The API response was not valid JSON.") from exc

    if not isinstance(payload, list) or len(payload) < 2:
        message = payload[0].get("message", [{}])[0].get("value", "Unexpected API response") if isinstance(payload, list) and payload and isinstance(payload[0], dict) else "Unexpected API response"
        raise RuntimeError(f"World Bank API returned no data payload: {message}")
    records = payload[1]
    if records is None:
        records = []
    rows = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        year = rec.get("date")
        value = rec.get("value")
        try:
            year_i = int(year)
        except (TypeError, ValueError):
            continue
        rows.append({"year": year_i, "value": value})
    df = pd.DataFrame(rows, columns=["year", "value"])
    if df.empty:
        return pd.DataFrame(columns=["year", "value"]), response.url
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).sort_values("year").drop_duplicates("year", keep="last").reset_index(drop=True)
    return df, response.url

def validate_working_data(df: pd.DataFrame, constraint: str) -> tuple[pd.DataFrame, list[str]]:
    """Normalize and validate the editable year/value table. Never silently replace bad values."""
    errors = []
    if not {"year", "value"}.issubset(df.columns):
        return pd.DataFrame(columns=["year", "value"]), ["Table must contain year and value columns."]
    work = df[["year", "value"]].copy()
    raw_year = pd.to_numeric(work["year"], errors="coerce")
    non_integer = raw_year.notna() & (np.floor(raw_year) != raw_year)
    if non_integer.any():
        errors.append("Years must be integers; rows with non-integer years are excluded from fitting.")
    work["year"] = raw_year
    work["value"] = pd.to_numeric(work["value"], errors="coerce")
    if work["year"].isna().any():
        errors.append("Some years are blank or non-numeric; those rows are excluded.")
    if work["value"].isna().any():
        errors.append("Some values are blank or non-numeric; those rows are excluded.")
    work = work.dropna(subset=["year", "value"])
    work = work.loc[np.floor(work["year"]) == work["year"]].copy()
    work["year"] = work["year"].astype(int)
    if work["year"].duplicated().any():
        errors.append("Duplicate years found. Keep one row per year; duplicate rows are excluded from fitting.")
        work = work.drop_duplicates("year", keep="last")
    if constraint == "positive":
        bad = work["value"] <= 0
    elif constraint == "nonnegative":
        bad = work["value"] < 0
    elif constraint == "percent":
        bad = (work["value"] < 0) | (work["value"] > 100)
    else:
        bad = pd.Series(False, index=work.index)
    if bad.any():
        errors.append(f"{int(bad.sum())} value(s) violate the indicator's basic {constraint} constraint and are excluded.")
        work = work.loc[~bad]
    return work.sort_values("year").reset_index(drop=True), errors

def fit_polynomial(df: pd.DataFrame, degree: int) -> dict[str, Any]:
    data = df.sort_values("year").copy()
    if data["year"].nunique() < degree + 1:
        raise ValueError(f"Degree {degree} requires at least {degree + 1} distinct valid years; only {data['year'].nunique()} are available.")
    base = int(data["year"].min())
    t = data["year"].to_numpy(dtype=float) - base
    y = data["value"].to_numpy(dtype=float)
    coef = np.polynomial.polynomial.polyfit(t, y, degree)
    predicted = np.polynomial.polynomial.polyval(t, coef)
    return {
        "base": base, "degree": degree, "coef": coef, "years": data["year"].to_numpy(dtype=int),
        "actual": y, "fitted": predicted, "r2": float(r2_score(y, predicted)),
        "mae": float(mean_absolute_error(y, predicted)), "n": len(data),
        "min_year": int(data["year"].min()), "max_year": int(data["year"].max()),
        "mean": float(np.mean(y)), "residuals": y - predicted, "data": data,
    }

def predict(model: dict[str, Any], years: Any) -> np.ndarray:
    """Apply exactly the same centered-time transformation used in fitting."""
    return np.polynomial.polynomial.polyval(np.asarray(years, dtype=float) - model["base"], model["coef"])

def equation_text(model: dict[str, Any], unit: str) -> str:
    terms = []
    for power, coefficient in enumerate(model["coef"]):
        if abs(coefficient) < 1e-12:
            continue
        if power == 0:
            terms.append(f"{coefficient:.10g}")
        elif power == 1:
            terms.append(f"{coefficient:.10g}t")
        else:
            terms.append(f"{coefficient:.10g}t^{power}")
    return "y = " + (" + ".join(terms).replace("+ -", "− ") if terms else "0") + f", where t = year − {model['base']} (units: {unit})"

def chronological_holdout(df: pd.DataFrame, degree: int) -> dict[str, Any] | None:
    data = df.sort_values("year").copy()
    # Keep the latest 20% (at least one year) as a chronological test set.
    test_n = max(1, int(math.ceil(len(data) * 0.2)))
    train = data.iloc[:-test_n]
    test = data.iloc[-test_n:]
    if len(train) < degree + 1 or test.empty:
        return None
    base = int(train["year"].min())
    coef = np.polynomial.polynomial.polyfit(train["year"].to_numpy() - base, train["value"].to_numpy(), degree)
    pred = np.polynomial.polynomial.polyval(test["year"].to_numpy() - base, coef)
    return {"n_test": len(test), "start": int(test["year"].min()), "end": int(test["year"].max()),
            "mae": float(mean_absolute_error(test["value"], pred)),
            "r2": float(r2_score(test["value"], pred)) if len(test) > 1 else None}

def make_chart(data: pd.DataFrame, model: dict[str, Any], increment: int, query_years: list[int] | None = None, query_values: list[float] | None = None):
    fig, ax = plt.subplots(figsize=(10, 5.2))
    years = data["year"].to_numpy(dtype=int)
    vals = data["value"].to_numpy(dtype=float)
    ax.scatter(years, vals, color="#1f77b4", label="Observed source / edited values", zorder=4)
    dense = np.linspace(model["min_year"], model["max_year"] + 0.0001, 500)
    ax.plot(dense, predict(model, dense), color="#e07a24", linewidth=2.2, label="Polynomial fit (historical range)")
    sample_years = np.arange(model["min_year"], model["max_year"] + 1, increment)
    ax.scatter(sample_years, predict(model, sample_years), marker="x", s=24, color="#9467bd", label=f"Model markers every {increment} year(s)")
    if model.get("horizon", 0) > 0:
        future = np.linspace(model["max_year"], model["max_year"] + model["horizon"], 150)
        ax.plot(future, predict(model, future), linestyle="--", color="#d62728", linewidth=2, label="Extrapolation (not validated)")
        ax.axvline(model["max_year"], color="gray", linestyle=":", label="Historical boundary")
    else:
        ax.axvline(model["max_year"], color="gray", linestyle=":", label="Historical boundary")
    if query_years:
        ax.scatter(query_years, query_values, marker="*", s=120, color="#2ca02c", edgecolor="black", label="Calculated estimate", zorder=6)
    ax.set_xlabel("Year")
    ax.set_ylabel(model["unit"])
    ax.set_title(model["title"])
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    return fig

def pdf_bytes(metadata: dict[str, Any], chart_png: bytes, preview: pd.DataFrame, results: pd.DataFrame, findings: list[str]) -> bytes:
    buff = io.BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    story = [Paragraph(metadata["title"], styles["Title"]), Spacer(1, 8)]
    for line in metadata["lines"]:
        story.append(Paragraph(line, styles["BodyText"]))
    story += [Spacer(1, 8), Paragraph("Model equation and in-sample metrics", styles["Heading2"]),
              Paragraph(metadata["equation"], styles["BodyText"]),
              Paragraph(metadata["metrics"], styles["BodyText"]), Spacer(1, 8)]
    story.append(RLImage(io.BytesIO(chart_png), width=650, height=335))
    story.append(Paragraph("Findings and limitations", styles["Heading2"]))
    for item in findings:
        story.append(Paragraph("• " + item, styles["BodyText"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Data preview (first 15 rows)", styles["Heading2"]))
    def table_for(frame):
        if frame is None or frame.empty:
            return Table([["No rows"]])
        rows = [list(frame.columns)] + frame.head(15).astype(str).values.tolist()
        tbl = Table(rows, repeatRows=1)
        tbl.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0),colors.HexColor("#d9e6f2")),
                                 ("GRID",(0,0),(-1,-1),0.3,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),
                                 ("VALIGN",(0,0),(-1,-1),"TOP")]))
        return tbl
    story.append(table_for(preview))
    if results is not None and not results.empty:
        story += [Spacer(1, 8), Paragraph("Calculated-year results", styles["Heading2"]), table_for(results)]
    doc.build(story)
    return buff.getvalue()

# Sidebar controls
now_year = date.today().year
start_default, end_default = now_year - 70, now_year - 1
with st.sidebar:
    st.header("Explore")
    country_label = st.selectbox("Country", list(COUNTRIES), index=0)
    indicator_label = st.selectbox("Indicator", list(INDICATORS), index=0)
    degree = st.slider("Polynomial degree", min_value=3, max_value=8, value=3)
    sample_increment = st.slider("Graph sample increment (years)", min_value=1, max_value=10, value=5)
    horizon = st.slider("Forward display horizon (years)", min_value=0, max_value=50, value=10)
    comparison_labels = st.multiselect("Compare countries (same indicator)", [x for x in COUNTRIES if x != country_label], default=[])
    printer_mode = st.checkbox("Printer-friendly report view", value=False)
    st.caption(f"Requested API window: {start_default}–{end_default} ({end_default-start_default+1} calendar years)")

country_code = COUNTRIES[country_label]
indicator = INDICATORS[indicator_label]
with st.spinner("Retrieving official World Bank observations…"):
    try:
        source_df, request_url = fetch_world_bank(country_code, indicator["code"], start_default, end_default)
        fetch_error = None
    except RuntimeError as exc:
        source_df, request_url, fetch_error = pd.DataFrame(columns=["year", "value"]), "", str(exc)

if fetch_error:
    st.error(fetch_error)
    st.warning("No substitute or random values are generated. You can retry by rerunning the app.")
if source_df.empty and not fetch_error:
    st.warning("The API returned no non-null observations for this country, indicator, and requested window.")

# Each selection combination gets its own original/working state.
state_key = f"working::{country_code}::{indicator['code']}"
source_key = f"source::{country_code}::{indicator['code']}"
if source_key not in st.session_state or st.session_state.get(source_key + "::request_url") != request_url:
    st.session_state[source_key] = source_df.copy()
    st.session_state[source_key + "::request_url"] = request_url
    st.session_state[state_key] = source_df.copy()
    st.session_state[state_key + "::edited"] = False
if state_key not in st.session_state:
    st.session_state[state_key] = source_df.copy()
    st.session_state[state_key + "::edited"] = False

top1, top2, top3 = st.columns(3)
top1.metric("Non-null source observations", f"{len(source_df)}")
top2.metric("Actual source coverage", f"{int(source_df.year.min())}–{int(source_df.year.max())}" if not source_df.empty else "No observations")
top3.metric("Retrieval date", date.today().isoformat())
st.caption(f"Source: World Bank API · Indicator {indicator['code']} · [Indicator page]({INDICATOR_SOURCE.format(code=indicator['code'])}) · [Country metadata]({COUNTRY_SOURCE.format(code=country_code)})")
st.write("**Definition:** " + indicator["definition"])
st.write("**Unit:** " + indicator["unit"])
st.write(f"**API request:** `{request_url or 'Not available'}`")

st.subheader("Working data table")
st.write("The original API values are kept separately from this editable working table. Editing creates a user-modified scenario; it does not alter the source.")
if st.button("Reset to source", key="reset_source"):
    st.session_state[state_key] = st.session_state[source_key].copy()
    st.session_state[state_key + "::edited"] = False
    st.session_state.pop("calc_single_result", None)
    st.session_state.pop("calc_batch_result", None)
    st.rerun()
working_df = st.session_state[state_key].copy()
edited_df = st.data_editor(working_df, num_rows="dynamic", use_container_width=True, key=f"editor::{country_code}::{indicator['code']}")
if not edited_df.equals(working_df):
    st.session_state[state_key] = edited_df.copy()
    st.session_state[state_key + "::edited"] = True
    st.session_state.pop("calc_single_result", None)
    st.session_state.pop("calc_batch_result", None)
    st.rerun()
edited_status = bool(st.session_state.get(state_key + "::edited", False))
st.caption("Data status: " + ("USER-MODIFIED SCENARIO" if edited_status else "World Bank source values (working copy unchanged)"))

valid_df, validation_messages = validate_working_data(st.session_state[state_key], indicator["constraint"])
for message in validation_messages:
    st.warning(message)
if valid_df.empty:
    st.error("There are no valid rows available for modeling. Restore source data or correct the working table.")
    st.stop()
if len(valid_df) < degree + 1:
    st.error(f"Not enough distinct valid years for degree {degree}. Need at least {degree + 1}; have {valid_df.year.nunique()}.")
    st.stop()
try:
    model = fit_polynomial(valid_df, degree)
except (ValueError, np.linalg.LinAlgError) as exc:
    st.error(f"Model could not be fit: {exc}")
    st.stop()
model["horizon"] = horizon
model["unit"] = indicator["unit"]
model["title"] = f"{country_label}: {indicator_label}"
model["edited"] = edited_status
model["indicator_code"] = indicator["code"]
model["country_code"] = country_code

# Model fingerprint ensures stored calculation results are invalidated when inputs change.
fingerprint = (country_code, indicator["code"], degree, tuple(valid_df["year"]), tuple(np.round(valid_df["value"], 12)))
for key in ("calc_single_result", "calc_batch_result"):
    stored = st.session_state.get(key)
    if stored and stored.get("fingerprint") != fingerprint:
        st.session_state.pop(key, None)

st.subheader("Polynomial model")
st.code(equation_text(model, indicator["unit"]))
m1, m2, m3, m4 = st.columns(4)
m1.metric("Degree", degree)
m2.metric("In-sample R²", f"{model['r2']:.5f}")
m3.metric("In-sample MAE", f"{model['mae']:.5g} {indicator['unit']}")
m4.metric("Observations", model["n"])
st.caption(f"Centered time: t = year − {model['base']}. Historical range: {model['min_year']}–{model['max_year']}; observed-value mean: {model['mean']:.6g} {indicator['unit']}. Fit statistics are in-sample, not independent validation.")
holdout = chronological_holdout(valid_df, degree)
if holdout:
    st.write(f"**Chronological holdout (separate score):** trained through {holdout['start']-1 if holdout['start'] > model['min_year'] else 'training boundary'}; test years {holdout['start']}–{holdout['end']} (n={holdout['n_test']}), MAE = {holdout['mae']:.6g}; R² = {holdout['r2']:.5f}" if holdout["r2"] is not None else f"**Chronological holdout (separate score):** test year {holdout['start']}, MAE = {holdout['mae']:.6g}; R² is not defined for one test point.")
else:
    st.caption("Chronological holdout unavailable: too few training observations remain after reserving the latest 20% for testing.")
resid_table = pd.DataFrame({"year": model["years"], "actual": model["actual"], "fitted": model["fitted"], "residual (actual − fitted)": model["residuals"]})
with st.expander("Residuals and in-sample fitted values"):
    st.dataframe(resid_table, use_container_width=True)

# Mathematics pathway explanations
pathway = st.radio("Assigned mathematics pathway", ["Honors Algebra 2", "Precalculus", "Calculus"], horizontal=True)
st.subheader(f"Mathematics interpretation · {pathway}")
if pathway == "Honors Algebra 2":
    st.write(f"- **Domain shown:** {model['min_year']} through {model['max_year'] + horizon}; predictions outside {model['min_year']}–{model['max_year']} are extrapolations.")
    st.write(f"- **Observed range:** {valid_df.value.min():.6g} to {valid_df.value.max():.6g} {indicator['unit']}. This is the range of the observed data, not a guaranteed range for the polynomial.")
    st.write("- **End behavior:** determined by the highest nonzero coefficient and whether the degree is even or odd; this mathematical behavior may be unrealistic for real-world indicators far beyond the data.")
    avg_rates = np.diff(model["actual"]) / np.diff(model["years"]) if len(model["years"]) > 1 else np.array([])
    if len(avg_rates):
        st.write(f"- **Average rate between adjacent observations:** from {np.min(avg_rates):.6g} to {np.max(avg_rates):.6g} {indicator['unit']} per year.")
    st.write("- **Graphical trend:** use the observed points and fitted curve; the polynomial summarizes shape but does not establish why values changed.")
elif pathway == "Precalculus":
    st.write(f"- **Domain shown:** {model['min_year']} through {model['max_year'] + horizon}; the observed data range is {model['min_year']}–{model['max_year']}.")
    st.write("- **Degree and coefficients:** higher degree allows more curvature and turning points, but can overfit and become unstable near the edges.")
    deriv = np.polynomial.polynomial.polyder(model["coef"])
    crit_t = np.polynomial.polynomial.polyroots(deriv) if len(deriv) > 1 else np.array([])
    crit_years = sorted(float(model["base"] + z.real) for z in crit_t if abs(z.imag) < 1e-7 and model["min_year"] <= model["base"] + z.real <= model["max_year"])
    st.write(f"- **Candidate turning points inside the observed range:** {', '.join(f'{y:.2f}' for y in crit_years) if crit_years else 'none found'}.")
    slopes = np.diff(model["actual"]) / np.diff(model["years"]) if len(model["years"]) > 1 else np.array([])
    st.write(f"- **Changing average rates:** adjacent-observation rates span {np.min(slopes):.6g} to {np.max(slopes):.6g} {indicator['unit']} per year." if len(slopes) else "- Need at least two points to compute average rates.")
    st.write("- **Concavity:** infer from how slopes change; polynomial concavity describes the fitted curve, not a causal explanation.")
else:
    coef = model["coef"]
    d1 = np.polynomial.polynomial.polyder(coef)
    d2 = np.polynomial.polynomial.polyder(d1)
    st.write(f"- Let t = year − {model['base']}. First derivative dy/dt coefficients (low to high power): `{np.array2string(d1, precision=7)}`.")
    st.write(f"- Second derivative d²y/dt² coefficients (low to high power): `{np.array2string(d2, precision=7)}`.")
    st.write("- Derivatives are rates/curvature of the fitted polynomial per year; they do not prove causes.")
    roots1 = np.polynomial.polynomial.polyroots(d1) if len(d1) > 1 else np.array([])
    critical = sorted(float(model["base"] + r.real) for r in roots1 if abs(r.imag) < 1e-7 and model["min_year"] <= model["base"] + r.real <= model["max_year"])
    st.write(f"- **Critical points in historical range:** {', '.join(f'{y:.3f}' for y in critical) if critical else 'none found'}. Classification uses the second derivative; flat/higher-order cases may require further analysis.")
    candidates = [float(model["min_year"]), float(model["max_year"])] + critical
    cand_vals = predict(model, candidates)
    st.write(f"- **Interval extrema including endpoints:** minimum ≈ {min(cand_vals):.6g} at year {candidates[int(np.argmin(cand_vals))]:.3f}; maximum ≈ {max(cand_vals):.6g} at year {candidates[int(np.argmax(cand_vals))]:.3f} (historical interval only).")
    roots2 = np.polynomial.polynomial.polyroots(d2) if len(d2) > 1 else np.array([])
    inflections = []
    for r in roots2:
        if abs(r.imag) < 1e-7:
            year = model["base"] + r.real
            if model["min_year"] <= year <= model["max_year"]:
                eps = 1e-3
                left, right = np.polynomial.polynomial.polyval(r.real-eps, d2), np.polynomial.polynomial.polyval(r.real+eps, d2)
                if left * right < 0:
                    inflections.append(float(year))
    st.write(f"- **Verified inflection points in historical range:** {', '.join(f'{y:.3f}' for y in inflections) if inflections else 'none verified by a concavity sign change'}.")
    if critical:
        st.write("Critical-point classification: " + "; ".join(
            f"{y:.3f} ({'local minimum' if np.polynomial.polynomial.polyval(y-model['base'], d2)>0 else 'local maximum' if np.polynomial.polynomial.polyval(y-model['base'], d2)<0 else 'inconclusive'} by second derivative)"
            for y in critical))

st.subheader("Calculate a single year")
single_year = st.number_input("Year (1950–2100)", min_value=1950, max_value=2100, value=max(1950, min(2100, model["max_year"] + 1)), step=1, key="single_year_input")
if st.button("Calculate Value", key="calculate_single"):
    st.session_state["calc_single_result"] = {"fingerprint": fingerprint, "year": int(single_year), "value": float(predict(model, [single_year])[0])}
single = st.session_state.get("calc_single_result")
if single and single.get("fingerprint") == fingerprint:
    within = model["min_year"] <= single["year"] <= model["max_year"]
    st.write(f"**Year:** {single['year']} · **Estimate:** {single['value']:.10g} {indicator['unit']} · **Classification:** {'within fitted historical range' if within else 'outside fitted historical range (extrapolation)'}")
    if within and single["year"] in set(model["years"]):
        st.caption("This is the polynomial's fitted value at an observed year, not the actual observation. Compare the actual value in the residual table.")
    if not within:
        st.warning("Polynomial extrapolation can be implausible. The estimate is not clipped; interpret it cautiously.")
    st.caption(f"Residuals and in-sample MAE ({model['mae']:.6g} {indicator['unit']}) give a rough sense of fit error, not a validated prediction interval. No 95% prediction interval is claimed.")

st.subheader("Batch year calculations")
batch_mode = st.radio("Batch input type", ["Year range", "Custom comma-separated years"], horizontal=True)
batch_years: list[int] = []
batch_error = None
if batch_mode == "Year range":
    c1, c2, c3 = st.columns(3)
    with c1:
        range_start = st.number_input("Start year", min_value=1950, max_value=2100, value=max(1950, min(2100, model["min_year"])), step=1)
    with c2:
        range_end = st.number_input("End year", min_value=1950, max_value=2100, value=max(1950, min(2100, model["max_year"])), step=1)
    with c3:
        range_step = st.number_input("Range step (1–10)", min_value=1, max_value=10, value=1, step=1)
    if range_end < range_start:
        batch_error = "End year must be greater than or equal to start year."
    else:
        batch_years = list(range(int(range_start), int(range_end) + 1, int(range_step)))
else:
    custom_text = st.text_input("Custom years (comma-separated, 1950–2100)", value=f"{model['min_year']},{model['max_year']}")
    invalid_tokens = []
    for token in custom_text.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = float(token)
            if not value.is_integer() or value < 1950 or value > 2100:
                invalid_tokens.append(token)
            else:
                batch_years.append(int(value))
        except ValueError:
            invalid_tokens.append(token)
    if invalid_tokens:
        batch_error = "Invalid year(s): " + ", ".join(invalid_tokens) + ". Use integer years from 1950 through 2100."
if batch_error:
    st.error(batch_error)
elif batch_years:
    st.write("Valid requested years: " + ", ".join(map(str, batch_years)))
    if st.button("Calculate batch values", key="calculate_batch"):
        batch_df = pd.DataFrame({"year": batch_years, "estimate": predict(model, batch_years)})
        batch_df["unit"] = indicator["unit"]
        batch_df["classification"] = np.where(batch_df["year"].between(model["min_year"], model["max_year"]), "within fitted historical range", "outside fitted historical range (extrapolation)")
        st.session_state["calc_batch_result"] = {"fingerprint": fingerprint, "data": batch_df}
    batch_stored = st.session_state.get("calc_batch_result")
    if batch_stored and batch_stored.get("fingerprint") == fingerprint:
        batch_results = batch_stored["data"]
        st.dataframe(batch_results, use_container_width=True)
        if single and single.get("fingerprint") == fingerprint and single["year"] in batch_results["year"].values:
            batch_match = float(batch_results.loc[batch_results["year"] == single["year"], "estimate"].iloc[0])
            st.caption(f"Consistency check for single year {single['year']}: single estimate − batch estimate = {single['value'] - batch_match:.12g} (should be approximately 0).")
else:
    st.info("Enter at least one valid year to calculate batch results.")

# Same-indicator comparison
comparison_frames = []
if comparison_labels:
    st.subheader("Country comparison · same indicator")
    for label in comparison_labels:
        code = COUNTRIES[label]
        try:
            comp_df, _ = fetch_world_bank(code, indicator["code"], start_default, end_default)
            if not comp_df.empty:
                comp_df = comp_df.rename(columns={"value": label})
                comparison_frames.append(comp_df)
            else:
                st.warning(f"No non-null data returned for {label}; omitted from comparison.")
        except RuntimeError as exc:
            st.warning(f"{label} comparison unavailable: {exc}")
    fig_comp, ax_comp = plt.subplots(figsize=(10, 4.5))
    if not source_df.empty:
        ax_comp.plot(source_df.year, source_df.value, marker="o", markersize=3, label=country_label)
    for comp in comparison_frames:
        label = [c for c in comparison_labels if c in comp.columns][0]
        ax_comp.plot(comp.year, comp[label], marker=".", markersize=3, label=label)
    ax_comp.set_xlabel("Year")
    ax_comp.set_ylabel(indicator["unit"])
    ax_comp.set_title(f"{indicator_label}: country comparison")
    ax_comp.legend(fontsize=8)
    ax_comp.grid(alpha=0.25)
    st.pyplot(fig_comp, use_container_width=True)
    coverage = [f"{country_label}: {int(source_df.year.min())}–{int(source_df.year.max())} (n={len(source_df)})" if not source_df.empty else f"{country_label}: no observations"]
    for comp in comparison_frames:
        label = [c for c in comparison_labels if c in comp.columns][0]
        coverage.append(f"{label}: {int(comp.year.min())}–{int(comp.year.max())} (n={len(comp)})")
    st.caption("Coverage: " + " · ".join(coverage) + ". Lines may have gaps because countries report different years or values are missing; do not interpret missing values as zero.")

# Main visualization and report
batch_for_chart = None
if st.session_state.get("calc_batch_result", {}).get("fingerprint") == fingerprint:
    bdata = st.session_state["calc_batch_result"]["data"]
    batch_for_chart = (bdata["year"].tolist(), bdata["estimate"].tolist())
single_for_chart = ([single["year"]], [single["value"]]) if single and single.get("fingerprint") == fingerprint else (None, None)
fig = make_chart(valid_df, model, sample_increment, *(batch_for_chart if batch_for_chart else single_for_chart))
if printer_mode:
    st.subheader("Printer-friendly report")
    st.write(f"**{country_label} · {indicator_label}** | {indicator['code']} | {indicator['unit']}")
    st.write(f"Coverage: {model['min_year']}–{model['max_year']} (n={model['n']}); degree {degree}; R² {model['r2']:.5f}; MAE {model['mae']:.6g}.")
    st.write(equation_text(model, indicator["unit"]))
    st.write("Limitations: polynomial fits are descriptive; extrapolations can be implausible; missing source observations are not filled; fit metrics are in-sample.")
else:
    st.subheader("Historical data and polynomial fit")
st.pyplot(fig, use_container_width=True)

# Export datasets and report based on current selection and scenario.
summary = pd.DataFrame([
    ["Project", APP_TITLE], ["Country", country_label], ["Country ISO3", country_code],
    ["Indicator", indicator_label], ["Indicator code", indicator["code"]], ["Definition", indicator["definition"]],
    ["Unit", indicator["unit"]], ["Source", WB_SOURCE], ["Retrieval date", date.today().isoformat()],
    ["API request URL", request_url], ["Requested window", f"{start_default}–{end_default}"],
    ["Actual source coverage", f"{int(source_df.year.min())}–{int(source_df.year.max())}" if not source_df.empty else "No observations"],
    ["Valid working coverage", f"{model['min_year']}–{model['max_year']}"], ["Working rows", model["n"]],
    ["Data status", "USER-MODIFIED SCENARIO" if edited_status else "World Bank source values"],
    ["Polynomial degree", degree], ["Base year", model["base"]], ["Equation", equation_text(model, indicator["unit"])],
    ["In-sample R-squared", model["r2"]], ["In-sample MAE", model["mae"]], ["Observed-value mean", model["mean"]],
], columns=["field", "value"])
batch_results_export = st.session_state.get("calc_batch_result", {}).get("data", pd.DataFrame(columns=["year", "estimate", "unit", "classification"]))
single_export = pd.DataFrame([{"year": single["year"], "estimate": single["value"], "unit": indicator["unit"], "classification": "within fitted historical range" if model["min_year"] <= single["year"] <= model["max_year"] else "outside fitted historical range (extrapolation)"}]) if single and single.get("fingerprint") == fingerprint else pd.DataFrame(columns=["year", "estimate", "unit", "classification"])
results_export = pd.concat([single_export.assign(result_type="single"), batch_results_export.assign(result_type="batch")], ignore_index=True)
working_export = st.session_state[state_key].copy()
working_export["data_status"] = "USER-MODIFIED SCENARIO" if edited_status else "World Bank source values"
csv_bytes = working_export.to_csv(index=False).encode("utf-8")
excel_buffer = io.BytesIO()
with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
    summary.to_excel(writer, sheet_name="Summary", index=False)
    working_export.to_excel(writer, sheet_name="Working Data", index=False)
    results_export.to_excel(writer, sheet_name="Calculated Years", index=False)
    for sheet, frame in [("Summary", summary), ("Working Data", working_export), ("Calculated Years", results_export)]:
        worksheet = writer.sheets[sheet]
        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, max(0, len(frame)), max(0, len(frame.columns)-1))
        for idx, col in enumerate(frame.columns):
            values = [str(x) for x in frame[col].head(100).tolist()]
            width = min(60, max([len(str(col))] + [len(x) for x in values]) + 2)
            worksheet.set_column(idx, idx, width)
chart_buffer = io.BytesIO()
fig.savefig(chart_buffer, format="png", dpi=150, bbox_inches="tight")
chart_png = chart_buffer.getvalue()
findings = [
    f"The model uses {model['n']} valid year-value observations from {model['min_year']} through {model['max_year']}.",
    f"In-sample R² is {model['r2']:.5f}; in-sample MAE is {model['mae']:.6g} {indicator['unit']}. These are not guarantees of future accuracy.",
    "Polynomial extrapolation is especially uncertain outside the observed time range. Estimates are not clipped and no 95% prediction interval is claimed.",
    "No causal explanation is inferred from the curve. Coverage differences and missing observations can affect comparisons.",
    "Data status: " + ("user-modified scenario." if edited_status else "working copy unchanged from retrieved source."),
]
metadata = {
    "title": APP_TITLE,
    "lines": [f"Country: {country_label} ({country_code}) · Indicator: {indicator_label} ({indicator['code']})",
              f"Definition: {indicator['definition']}", f"Unit: {indicator['unit']}",
              f"Retrieved: {date.today().isoformat()} · Source: {WB_SOURCE}",
              f"Requested years: {start_default}–{end_default} · Data status: {'USER-MODIFIED SCENARIO' if edited_status else 'World Bank source values'}"],
    "equation": equation_text(model, indicator["unit"]),
    "metrics": f"Degree {degree}; base year {model['base']}; n={model['n']}; actual fitted range {model['min_year']}–{model['max_year']}; in-sample R²={model['r2']:.8f}; in-sample MAE={model['mae']:.8g}; mean={model['mean']:.8g}.",
}
pdf_data = pdf_bytes(metadata, chart_png, working_export, results_export, findings)
st.subheader("Export current selection")
st.caption("Exports reflect the current country, indicator, model, edited-data status, and any calculated-year results.")
ex1, ex2, ex3 = st.columns(3)
ex1.download_button("Download working data CSV", data=csv_bytes, file_name="working_data.csv", mime="text/csv")
ex2.download_button("Download Excel workbook", data=excel_buffer.getvalue(), file_name="hispanic_heritage_explorer.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
ex3.download_button("Download PDF report", data=pdf_data, file_name="hispanic_heritage_report.pdf", mime="application/pdf")

with st.expander("Residual plot"):
    fig_r, ax_r = plt.subplots(figsize=(9, 3))
    ax_r.axhline(0, color="gray", linestyle="--")
    ax_r.scatter(model["years"], model["residuals"])
    ax_r.set_xlabel("Year")
    ax_r.set_ylabel(f"Residual ({indicator['unit']})")
    ax_r.set_title("In-sample residuals")
    ax_r.grid(alpha=0.25)
    st.pyplot(fig_r, use_container_width=True)

st.caption("Educational tool, not an official forecast. Indicator definitions and coverage may change as the World Bank revises its database. Always inspect the source metadata before making a substantive claim.")
