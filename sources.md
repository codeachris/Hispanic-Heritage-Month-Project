# Sources and indicator reference

**Retrieval date:** shown dynamically in the app.  
**Primary source:** World Bank Open Data / World Development Indicators.  
**API documentation:** https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation  
**API root:** https://api.worldbank.org/v2  
**Country and indicator API responses:** the app displays the exact request URL used for the selected series.

The app requests years from the current calendar year minus 70 through the previous calendar year, inclusive. The actual non-null observations can be fewer than 70 because the API can return missing values or a shorter series. No missing observations are fabricated.

| Indicator label in app | World Bank code | Unit / interpretation |
|---|---|---|
| Life expectancy at birth | `SP.DYN.LE00.IN` | Years; life expectancy under current mortality patterns |
| Unemployment, total (national estimate) | `SL.UEM.TOTL.NE.ZS` | Percent of total labor force; national estimate |
| GDP per capita (current US$) | `NY.GDP.PCAP.CD` | Current US dollars per person; not average wealth or household income |
| Crude birth rate | `SP.DYN.CBRT.IN` | Births per 1,000 people per year; rate, not count |
| Net migration | `SM.POP.NETM` | People, net total; not an emigration count |
| Intentional homicide rate | `VC.IHR.PSRC.P5` | Per 100,000 people |
| Consumer price inflation | `FP.CPI.TOTL.ZG` | Annual percentage change |
| Central government debt | `GC.DOD.TOTL.GD.ZS` | Percent of GDP |
| Total reserves including gold | `FI.RES.TOTL.CD` | Current US dollars |
| External balance on goods and services | `NE.RSB.GNFS.ZS` | Percent of GDP |

Useful links:
- World Bank indicator catalog: https://data.worldbank.org/indicator
- World Bank API documentation: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation
- World Bank country metadata API pattern: `https://api.worldbank.org/v2/country/{ISO3}?format=json`
- World Bank indicator metadata API pattern: `https://api.worldbank.org/v2/indicator/{INDICATOR_CODE}?format=json`

The application uses ISO3 country identifiers for the API: Mexico `MEX`, Brazil `BRA`, Argentina `ARG`, Colombia `COL`, Chile `CHL`, Peru `PER`, Venezuela `VEN`, Ecuador `ECU`, and Uruguay `URY`. The two-letter ISO labels are included in the UI selector names. Brazil is a Latin American comparison country but is Portuguese-speaking, not Spanish-speaking.

Always review the selected indicator's current official metadata and limitations before drawing a substantive conclusion. Coverage, definitions, and historical values may be revised by the World Bank.
