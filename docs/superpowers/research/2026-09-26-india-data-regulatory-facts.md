<!-- Generated 2026-09-26 by a research + verification workflow (web research, then a skeptic re-fetched every cited source). Re-verify anything time-sensitive before relying on it. -->

# Facts Sheet: Indian-Equity Portfolio Recommendation Agent

Compiled 2026-09-26 from a verification pass. Legend: **[C]** = claim with verdict `confirmed` (URL cited). **[R]** = claim refuted; the correction is stated. **[A]** = additional finding recorded in the same pass with a primary-source quote but no verdict field; treat as high-confidence but re-check. Everything else is in section 6.

## 1. NSE data via yfinance

**Ticker formats [C]** (`https://help.yahoo.com/kb/SLN2310.html`)
- NSE: `<NSE_SYMBOL>.NS`, e.g. `RELIANCE.NS`, `TCS.NS`, `HDFCBANK.NS` ("Real-time, ICE Data Services").
- BSE: `<SYMBOL>.BO`, e.g. `RELIANCE.BO` (15-min delay). Prefer `.NS`: `RELIANCE.BO` `history(period='5d')` returned 1 row vs 5 for `RELIANCE.NS`; `period='1mo'` returned 1 row vs 24.
- Index symbols [C] (`https://finance.yahoo.com/quote/%5ENSEI/`): `^NSEI` = NIFTY 50, `^CRSLDX` = NIFTY 500 (close 22,603.50 on 2026-09-25 matched NSE `allIndices`), `^CNX100` = NIFTY 100, `^CNX200` = NIFTY 200, `^NSMIDCP` = NIFTY NEXT 50, `^NSEBANK` = NIFTY BANK.

**Library [C]** (`https://pypi.org/pypi/yfinance/json`)
- Current PyPI version `1.7.0` (uploaded 2026-08-26). Docs `https://ranaroussi.github.io/yfinance`, repo `https://github.com/ranaroussi/yfinance`. README: "the Yahoo! finance API is intended for personal use only."

**What works (live, yfinance 1.7.0, 2026-09-26) [C]** (`https://finance.yahoo.com/quote/RELIANCE.NS/`)
- `yf.Ticker('RELIANCE.NS').history(period='5d')` -> 5 daily rows, tz-aware `Asia/Kolkata`; Close 2026-09-25 = 1226.0. `fast_info`: currency `INR`, exchange `NSI`, tz `Asia/Kolkata`.
- `yf.download(['TCS.NS','INFY.NS','HDFCBANK.NS'], period='5d')` -> shape (5, 15); Close 2026-09-25: HDFCBANK 735.60, INFY 1000.20, TCS 2082.0. One `yf.download` of all 50 Nifty tickers returned 50 non-NaN closes.
- `Ticker.info` is populated but gappy: `RELIANCE.NS` trailingPE 22.07, forwardPE 17.17, marketCap 16590810644480, dividendYield 0.49, sector `Energy`, beta 0.152, priceToBook 1.835, debtToEquity 36.65, returnOnEquity `None`. `TCS.NS` ROE 0.477; `HDFCBANK.NS` 0.138; `INFY.NS` 0.32; `SBIN.NS` 0.152.

**Gotchas**
- [C] `dividendYield` is in percent units (0.49 == "0.49%"). Sector/industry names are Yahoo's, not NSE's.
- [C] `returnOnEquity` is `None` for `RELIANCE.NS`, `ITC.NS`, `TMPV.NS`; `trailingPE` is `None` for `TMPV.NS`; `debtToEquity` is `None` for banks (`HDFCBANK.NS`, `SBIN.NS`). A screener needs fallbacks.
- [A] ROE fallback from statements: `yf.Ticker('RELIANCE.NS').financials.loc['Net Income']` (FY to 2026-03-31) = 807,750,000,000 and `.balance_sheet.loc['Stockholders Equity']` = 9,040,300,000,000 -> ROE 8.93%. Row labels available: `Net Income`, `Net Income Common Stockholders`, `Stockholders Equity`, `Total Equity Gross Minority Interest`.
- [C] Defaults from main-branch source (`https://raw.githubusercontent.com/ranaroussi/yfinance/main/yfinance/multi.py`): `history(..., interval="1d", auto_adjust=True, actions=True, ...)`; `download(tickers, ..., actions=False, threads=True, ignore_tz=None, group_by='column', auto_adjust=True, ..., multi_level_index=True)`. `Close` is adjusted by default; `auto_adjust=False` gives columns `['Adj Close','Close','High','Low','Open','Volume']`.
- [A] Timezone: `download()` sets `ignore_tz = interval[-1] not in ('m','h')` when `None`, so daily downloads get a tz-naive index while `Ticker.history()` is always tz-aware. Pass `ignore_tz=False` to get `Asia/Kolkata` (verified live).
- [C] Rate limiting (`https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=5d&interval=1d`): bare curl with a Chrome UA got HTTP 429 immediately; yfinance 1.7.0 (curl_cffi impersonation + cookie/crumb) succeeded in the same minute. Use yfinance, add caching/back-off. No documented safe request rate exists (see section 6).
- [C] Session timings, IST (`https://www.nseindia.com/static/products-services/closing-auction-session`): Normal market 09:15-15:30; pre-open 09:00-09:08 (per NSE timings table; the "09:12-09:15 buffer" detail was not on the fetched page); CAS 15:15-15:35, transition 15:35-15:50, post-close 15:50-16:00; Closing session 15:40-16:00; equity derivatives 09:15-15:40; trade-modification cut-off 16:15. yfinance `history_metadata.currentTradingPeriod.regular` = 09:15-15:30+05:30.
- [A] Trading holidays: `https://www.nseindia.com/api/holiday-master?type=trading` returns HTTP 200 JSON with a Chrome UA and no cookies; use key `CM` for equities (20 entries for 2026, dates as `DD-Mon-YYYY`, e.g. `02-Oct-2026`, `20-Oct-2026`, `08-Nov-2026` "Diwali Laxmi Pujan*" = muhurat session, `10-Nov-2026`, `24-Nov-2026`, `25-Dec-2026`).

## 2. Nifty 50 constituents

**Source [C]** (`https://archives.nseindia.com/content/indices/ind_nifty50list.csv`)
- Serves plain curl: HTTP 200, `text/csv`, 3352 bytes, 50 data rows, header `Company Name,Industry,Symbol,Series,ISIN Code`, Last-Modified `Sat, 26 Sep 2026 03:30:24 GMT` (consistent with a daily ~03:30 GMT refresh, single-day sample).
- Correction to the original claim: `https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv` and `https://www.niftyindices.com/...` drop plain curl / `python-requests` UA (HTTP 000) and only return 200 with a Chrome User-Agent (+ Referer for niftyindices). Fallback order: `archives.nseindia.com` (no headers) -> `nsearchives.nseindia.com` or `niftyindices.com` (browser UA).
- Yahoo mapping: `Symbol` column + `.NS`. Non-obvious symbols that work: `M&M.NS` (3035.0), `BAJAJ-AUTO.NS` (11281.0), `TMPV.NS` (290.45), `ETERNAL.NS` (335.0), `JIOFIN.NS` (227.0), `INDIGO.NS` (4940.0), `MAXHEALTH.NS` (1014.0) (closes 2026-09-25).

**Static list: [R] do not hard-code** (`https://www.niftyindices.com/Press_Release/ind_prs10082026.pdf`)
- The original "stable static list" claim was refuted. The 50 symbols in today's CSV and their closes were re-verified, but: (1) per the NSE Indices press release of Aug 10, 2026, `WIPRO` is excluded and BSE Ltd. (NSE symbol `BSE`, Yahoo `BSE.NS`) is included in Nifty 50 "effective from September 30, 2026 (close of September 29, 2026)". Today's CSV still shows `WIPRO`, so a hard-coded list goes stale in 4 days. (2) The 28 Mar 2025 removals were `BPCL` and `BRITANNIA` (official release), not LTIMindtree. (3) The Feb 23, 2026 review: "No changes are being made in Nifty 50". Fetch the CSV daily instead. The full 50-symbol list is intentionally not reproduced here.
- [A] Nifty 500: `https://archives.nseindia.com/content/indices/ind_nifty500list.csv` (plain curl 200, 32,840 bytes, Last-Modified `Sat, 26 Sep 2026 03:30:22 GMT`) has 501 data rows: 500 in series `EQ` plus `HFCL` in series `BE`. Filter `Series == 'EQ'`.

**NSE website API [C]** (`https://www.nseindia.com/api/equity-stock-indices?index=NIFTY%2050`)
- Works with only a Chrome User-Agent, no cookies: `https://www.nseindia.com/api/allIndices` (139 indices; NIFTY 50 pe 19.56, pb 2.8, dy 1.22; NIFTY 500 pe 21.9, pb 3.13, dy 0.99) and the hyphenated `/api/equity-stock-indices?index=NIFTY%2050` (51 rows: index + 50 constituents with `symbol, lastPrice, previousClose, change, pChange, open, dayHigh, dayLow, totalTradedVolume, totalTradedValue, ffmc, nearWKH, nearWKL, perChange30d, perChange365d, lastUpdateTime, marketStatus`).
- Correction: the camel-case `/api/equity-stockIndices?index=NIFTY%2050` returns 404 "Resource not found" (endpoint renamed). Homepage returns 403 to curl (Akamai); `/api/quote-equity?symbol=RELIANCE` returns 403 to bare curl but works through jugaad-data's warmed-up session. `python-requests` UA is dropped (HTTP 000).

## 3. Alternative India data packages

- [C] `jugaad-data` `0.35.9`, uploaded 2026-09-23, `requires_python >=3.9`, repo `https://github.com/jugaad-py/jugaad-data`, docs `https://marketsetup.in/documentation/jugaad-data/` (`https://pypi.org/pypi/jugaad-data/json`). Only NSE-specific package with a release in the last 12 months. Built-in caching "to play nice with NSE". API: `stock_df(symbol=..., from_date=..., to_date=..., series="EQ")`, `bhavcopy_save(date, dir)`.
- [A] Live 2026-09-26: `stock_df(symbol='SBIN', from_date=date(2026,9,15), to_date=date(2026,9,25), series='EQ')` -> 9 rows, columns `DATE, SERIES, OPEN, HIGH, LOW, PREV. CLOSE, LTP, CLOSE, VWAP, VOLUME, VALUE, NO OF TRADES, DELIVERY QTY, DELIVERY %, SYMBOL`. `NSELive().live_index('NIFTY 50')`, `.stock_quote('RELIANCE')`, `.holiday_list()` all returned JSON. It warms up via GET `https://www.nseindia.com/get-quotes/equity?symbol=LT` with Chrome/134 headers. Gotcha: `DATE` comes back UTC-naive (`2026-09-24 18:30:00` means 2026-09-25 IST); add 5h30m before joining with yfinance dates.
- [C] Others, none released in the last 12 months (`https://pypi.org/pypi/nsetools/json`): `nsepython` 2.97 (2025-05-26; repo pushed 2026-03-07, no release since); `nsetools` 2.0.1 (2025-03-18, 907 stars, not archived); `bsedata` 0.6.0 (2024-03-14; README: "Please do not use this application for production usage"). `nsepython`/`nsetools` were not tested live.

## 4. SEBI regulatory notes + recommended disclaimer

**Investment Advisers Regulations, 2013 (amended to 25-Nov-2025) [C]** (`https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1785912187595.pdf`)
- Reg 2(1)(l): "investment advice" = advice on investing in/purchasing/selling securities and on "investment portfolio containing securities ... for the benefit of the client", including financial planning. Proviso: advice through media "widely available to the public" is not investment advice under these Regs. Second proviso (w.e.f. 16-12-2024): "trading calls shall not be considered as investment advice" (they fall under the RA Regs instead).
- Reg 2(1)(m): "investment adviser" = any person who "for consideration" is in the business of providing investment advice, including a part-time adviser or anyone who "holds out himself as an investment adviser". Reg 3(1): registration required. Reg 4(a): exemption only for general comments that "do not specify any particular securities". No personal-use or educational-software carve-out exists in the text.

**Research Analysts Regulations, 2014 [C]** (`https://www.sebi.gov.in/sebi_data/attachdocs/feb-2025/1740726945457.pdf`)
- Reg 2(1)(u): "research analyst" = person who "for consideration" provides research services, incl. part-time. Reg 2(1)(w): "research report" = "any written or electronic communication that includes research analysis or research recommendation or an opinion concerning securities ... providing a basis for investment decision", excluding general market trends, broad-based index discussion, economic/political commentary, and "statistical summaries of financial data of the companies". Reg 2(1)(zc): "trading calls" = intraday/ultra-short, non-delivery or non-personalised recommendations. Reg 3(1): registration required. Reg 21(2): anyone recommending through public media must disclose "name, registration status and details of financial interest".
- [A] Reg 24(7) (`https://www.sebi.gov.in/sebi_data/attachdocs/aug-2025/1755176387160.pdf`): an RA "who uses Artificial Intelligence tools, irrespective of the scale and scenario of adoption ... shall be solely responsible" for data security and for "research services based on output of Artificial Intelligence tools"; Reg 19(vii) requires disclosing the extent of AI use. SEBI circular `SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2025/004` (Jan 8, 2025), Annexure-A: "A model portfolio shall mean a basket of securities for which a research report is issued by a RA recommending the relevant weightages." A weighted stock basket published to others is a model portfolio.

**Related circulars and rules [C]**
- `SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2024/143` (22-Oct-2024; `https://www.sebi.gov.in/sebi_data/attachdocs/oct-2024/1729594417893.pdf`): SEBI-regulated persons and their agents may not associate with anyone who "provides advice or any recommendation ... related to a security" unless registered, or who claims returns; investor-education carve-out; "specified digital platform" exception. Brokers/AMCs cannot partner with an unregistered recommendation app.
- `SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2025/11` (29-Jan-2025, updated 8-May-2026 by Circular `HO/47/17/12(11)2025-MRD-POD3/I/11107/2026`; `https://www.sebi.gov.in/sebi_data/attachdocs/jul-2026/1784884437684.pdf`): a person "engaged solely in education" must not use "market price data of the preceding thirty days" (was three months) to name/display any security "indicating the future price, advice or recommendation". A live-price tool naming stocks does not fit the education carve-out.
- Intermediaries (Amendment) Regulations, 2025, Reg 16C (notified 6-Feb-2025, Gazette 10-Feb-2025; `https://www.sebi.gov.in/sebi_data/attachdocs/feb-2025/1739276753544.pdf`): a SEBI-regulated person using AI/ML "irrespective of the scale" is "solely responsible" for data privacy, "the output arising from the usage of such tools", and legal compliance. Applies only to persons regulated by the Board.
- Consultation paper on "Guidelines for Responsible Usage of AI/ML in Indian Securities Markets" (20-Jun-2025; `https://www.sebi.gov.in/sebi_data/attachdocs/jun-2025/1750415065695.pdf`) proposes disclosure, testing, fairness and a "regulatory lite" tier. No final circular was found as of 2026-09-26; the only 2026 SEBI AI circular found is the 5-May-2026 cybersecurity advisory.
- EoDI circular `HO/(79)2026-MIRSD-PODMMC` (26-Feb-2026; `https://www.sebi.gov.in/sebi_data/attachdocs/feb-2026/1772103201432.pdf`): from 1-May-2026 regulated entities/agents must show registered name and registration number on social-media home pages and at the start of securities-related content.
- PR 112/2016 (`https://www.sebi.gov.in/sebi_data/docfiles/34058_t.html`): public cautioned to deal only with SEBI-registered IAs/RAs and to verify registration on the SEBI website.

**Practical reading (interpretation, not a SEBI statement):** an app that outputs specific stock picks or a weighted basket to other people is RA-regulated activity (research report / model portfolio) and, if personalised and paid, IA-regulated; Reg 4(a) only exempts output that names no particular security. A tool used solely by its own author is not explicitly addressed anywhere in the texts fetched. A disclaimer does not change the regulatory characterisation. Get a legal opinion before exposing the agent to anyone else.

**Recommended disclaimer text (draft, modelled on wording seen on unregistered-creator sites; not legal advice):**

> This output is generated automatically by an AI model (Claude, via Amazon Bedrock) for educational and informational purposes only. The operator of this tool is not registered with SEBI as an Investment Adviser or Research Analyst. Nothing here is investment advice, a research report, a model portfolio, a trading call, or a recommendation to buy, sell or hold any security. Price and fundamental data are sourced from third parties (Yahoo Finance via yfinance, NSE) and may be delayed, incomplete or incorrect. Investments in securities markets are subject to market risks; past performance is not indicative of future returns. Consult a SEBI-registered Investment Adviser or Research Analyst before making any investment decision, and verify registration at `https://www.sebi.gov.in`.

## 5. AWS region availability

**AgentCore [C]** (`https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html`)
- `ap-south-1` (Mumbai) and `ap-southeast-1` (Singapore) both support: AgentCore harness, Runtime microVMs, Runtime Instances, Memory, Gateway, Identity, Built-in Tools, Observability, Policy, Evaluations, optimization. AgentCore payments: Mumbai No, Singapore Yes. AWS Agent Registry and Web Search Tool: No in both.
- Expansions: 1-Jul-2026 Bangkok, Malaysia, Milan, Spain; 27-Aug-2026 N. California and Hyderabad (`ap-south-2`).
- [A] Endpoints (`https://docs.aws.amazon.com/general/latest/gr/bedrock_agentcore.html`, note underscore): control plane `bedrock-agentcore-control.ap-south-1.amazonaws.com` / `bedrock-agentcore-control.ap-southeast-1.amazonaws.com`; data plane `bedrock-agentcore.ap-south-1.amazonaws.com` / `bedrock-agentcore.ap-southeast-1.amazonaws.com`; Gateway `{{gatewayId}}.gateway.bedrock-agentcore.ap-south-1.amazonaws.com` / `{{gatewayId}}.gateway.bedrock-agentcore.ap-southeast-1.amazonaws.com`. That page's control/data-plane tables list only 9 regions (lagging the 22-region devguide table).

**Claude on Bedrock from Mumbai/Singapore [C]** (`https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-5.html`)
- All six current model cards show `ap-south-1 (Mumbai) | not-supported | not-supported | supported` and the same for `ap-southeast-1 (Singapore)`: i.e. In-Region no, Geo no, **Global profile only**. The Sonnet 5 and Haiku 4.5 cards state the bare model ID "isn't supported for on-demand throughput" on `bedrock-runtime`. `bedrock-mantle` (single-region) is not offered in either region for any current Claude model. Anthropic's regions table lists both as "Global" only.

**Global inference profile IDs [C]** (`https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-opus-5-5.html`)

| Model | Global profile ID | Launch | Context | Geo prefixes |
|---|---|---|---|---|
| Claude Opus 5.5 | `global.anthropic.claude-opus-5-5` | 22-Sep-2026 | 1M; adaptive thinking always on | `us.`, `eu.`, `au.`, `jp.` |
| Claude Sonnet 5 | `global.anthropic.claude-sonnet-5` | 30-Jun-2026 | 1M | `us.`, `eu.`, `au.` |
| Claude Fable 5.1 | `global.anthropic.claude-fable-5-1` | 1-Sep-2026 | - | `us.` only; requires `aws_review` data-retention opt-in; "Refusal rates on this model are materially higher" |
| Claude Haiku 4.5 | `global.anthropic.claude-haiku-4-5-20251001-v1:0` | 16-Oct-2025 | 200K; EOL no sooner than 16-Oct-2026 | `us.`, `eu.`, `au.`, `jp.` |
| Claude Sonnet 4.5 | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` | - | - | `us.`, `eu.`, `au.`, `jp.` |
| Claude Opus 4.6 | `global.anthropic.claude-opus-4-6-v1` | - | - | `us.`, `eu.`, `au.` |

- No `apac.` profile appears on any of these six cards. Correction to the "apac" question: the only AWS-documented `apac.` profile is legacy `apac.anthropic.claude-sonnet-4-20250514-v1:0` (`https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4.html`), whose source regions include `ap-south-1` and `ap-southeast-1` and whose destinations are `ap-northeast-1/2/3`, `ap-south-1/2`, `ap-southeast-1/2/4`. Sonnet 4 is "Legacy" with "Model EOL date: October 14, 2026" and 200K context, so it is not a viable APAC-residency path.

**Cross-region inference mechanics [C]** (`https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html`)
- Global routes to any supported commercial region worldwide at "Approximately 10% savings" vs geo profiles; "There's no additional routing cost"; price is based on the source region. Global "can route requests to AWS Regions that are not manually enabled in your AWS account"; data stays on the AWS network, encrypted in transit. Geo profiles keep data "in the AWS Regions where it originally resides", but for abuse detection "your input prompts and output results will be stored in the destination region". CloudTrail logs in the source region with `additionalEventData.inferenceRegion`. SCPs must allow `"aws:RequestedRegion": "unspecified"` for Global (deny pattern uses `ArnLike bedrock:InferenceProfileArn arn:aws:bedrock:*:*:inference-profile/global.*`).
- Global destination list on the Haiku 4.5 / Sonnet 4.5 / Opus 4.6 cards includes 13 APAC regions (`ap-east-2`, `ap-northeast-1`, `ap-northeast-2`, `ap-northeast-3`, `ap-south-1`, `ap-south-2`, `ap-southeast-1`, `ap-southeast-2`, `ap-southeast-3`, `ap-southeast-4`, `ap-southeast-5`, `ap-southeast-6`, `ap-southeast-7`) plus 8 Americas and 12 EMEA regions.
- Application inference profiles can be created in `ap-south-1` and `ap-southeast-1` (`https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html`). Geo-tied destination lists never change; Global lists can grow. That page still carries stale text saying Global is "only supported on Anthropic Claude Sonnet 4"; ignore it.

## 6. Open questions - Unverified, check before relying on

- Yahoo's safe request rate is undocumented. Empirically, one `yf.download` of all 50 Nifty tickers (`threads=True`) plus ~15 `Ticker.info`/`history` calls in a few minutes did not trigger 429; bare curl was 429'd immediately. The old `requests_cache`/ratelimiter recipe has been removed from the README; docs' caching page covers only the tz/cookie cache (`yf.set_tz_cache_location`).
- Whether Yahoo carries `BSE.NS` with full history was not tested; test before the Sep 30, 2026 Nifty 50 switchover.
- `https://finance.yahoo.com/quote/%5ECRSLDX/` returned HTTP 503; `^CRSLDX` = NIFTY 500 is confirmed only via yfinance metadata (`shortName == 'NIFTY 500'`) and the exact close match with NSE.
- Unauthenticated daily access to `archives.nseindia.com` CSVs is a single-day observation; no NSE document guaranteeing it was found.
- The yfinance 1.5.2 "fixed breakage with curl_cffi>=0.16" changelog note was not seen during verification.
- ROE was not recomputed for `ITC.NS`/`TMPV.NS`; textbook ROE needs average equity of the last two years.
- Whether SEBI issued the final "Responsible Usage of AI/ML" circular between 19-Aug-2026 (chairman quoted in press: "We will shortly be issuing guidelines", with kill-switch and human-in-the-loop controls; secondary source `https://newsarenaindia.com/economy/sebi-to-soon-issue-ai-ml-guidelines-for-capital-markets/84856`) and today. Check `https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0` for Sep-2026 entries.
- Legal interpretation not answered by any SEBI text: (a) whether a free, personal-use tool naming specific stocks is outside IA/RA registration; (b) whether the 30-day price-data rule for education-only persons applies to a private live-price tool; (c) DPDP Act 2023 implications of Global-CRIS routing of prompts containing a user's portfolio. Needs a legal opinion.
- The SEBI IA FAQ PDF (`1424862077270.pdf`) carries no visible date and quotes pre-Dec-2024 wording; treat as partly stale.
- Opus 4.6 `apac.` conflict: Anthropic's legacy table (`https://platform.claude.com/docs/en/build-with-claude/claude-on-amazon-bedrock-legacy`) says apac = Yes for Opus 4.6; the AWS card lists only `us.`/`eu.`/`au.`/global. Definitive check: `aws bedrock list-inference-profiles --region ap-south-1 --type-equals SYSTEM_DEFINED` and look for `apac.anthropic.*`.
- Fable 5.1 single-region availability conflicts: AWS card says `bedrock-mantle` In-Region only in `us-gov-west-1`; Anthropic says regional endpoints "available in `us-east-1` only". Neither offers anything in APAC.
- The Sonnet 5, Opus 5.5 and Fable 5.1 cards do not render a "Global inference details" destination table, so the 13-region APAC destination list is proven only for Haiku 4.5, Sonnet 4.5 and Opus 4.6 and assumed for the 5.x models.
- Haiku 4.5 card is internally inconsistent on EOL ("no sooner than: Oct 16, 2026" vs "No sooner than 10/1/2026").
- AgentCore control/data-plane hostnames for Hyderabad, Malaysia, Thailand, Milan, Spain and N. California are not in the General Reference tables (Gateway table does list 21 regions incl. `ap-south-2`).
- `nsepython` and `nsetools` were not exercised live against nseindia.com.