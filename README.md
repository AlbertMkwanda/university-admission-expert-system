# University Admission Expert System

**Student:** Albert Mkwanda  
**Serial no.:** 1 · **Registration no.:** 23311351001  
**Assigned title:** University Admission Expert System (`COMPREHENSION-2_022354.pdf`)

## What it does

A rule-based Malawi university matcher compares applicant profiles with published minimum entry requirements where those rules are verified, and suggests source-attributed undergraduate and postgraduate degrees after the user selects a discipline or faculty. Suggestions show the offering institution and official course source; the full catalogue is not presented as an unrestricted browse list. It reports an explanation and official source for each assessed programme. It has a responsive browser interface, a JSON API, a health endpoint, and a production-oriented Waitress server.

The eligibility checker currently has verified rules for these 10 programmes in `config/admission_policy.json`:

| Level | Institution | Programme |
|---|---|---|
| Undergraduate | KUHeS | Bachelor of Medicine Bachelor of Surgery (MBBS) |
| Undergraduate | MUST | BSc Medical Microbiology; BSc Business Information Technology; BEng Biomedical Engineering (Honours) |
| Undergraduate | MUBAS | BSc Information Technology; BCom Banking and Finance |
| Master's | KUHeS | Master of Public Health |
| Master's | MUBAS | MBA; MPhil Information Technology; MSc Electrical and Electronics Engineering |

`config/program_catalog.json` adds 392 degree listings from official catalogues at UNIMA, MUBAS, LUANAR, KUHeS, UNILIA, CUNIMA, and MAU. Users choose a discipline and optionally a degree level to see relevant suggestions. For catalogue listings without verified admission rules, the interface labels them as unverified and does not invent an eligibility result. DMI St. John the Baptist University is linked in the interface, but its supplied official domain could not be resolved during verification; no DMI course claims have been added. The combined 402 listings are not a complete inventory of every NCHE-registered or accredited institution in Malawi. Check each institution and programme's current accreditation, availability, intake, and requirements with NCHE and the institution.

Undergraduate MSCE grades are entered from 1 to 9, with 1 best. Grades 1–6 count as credits; programme-specific science limits are applied only where the official programme page states them. Incomplete results return “More information is needed.” Master's applicants enter GPA on a 0–5 scale, degree type/classification, recognition and relevance, and applicable experience/project details. The GPA is reported but is not converted or used as a gate because the cited programme pages do not publish a shared GPA conversion or threshold.

The policy cites official programme and admissions pages. The latest located intake varies by institution: MUBAS undergraduate 2026/27; its March 2027 postgraduate call includes the MBA and MPhil in IT but not the listed MSc in Electrical and Electronics Engineering; KUHeS postgraduate 2026/27 and the latest located MBBS call 2025/26; some MUST programme pages do not state an intake year. These are minimum-requirement comparisons, not predictions of competitive selection or guarantees of admission. Always confirm the active call, eligibility, qualification equivalence, and document requirements with the institution before applying.

The browser form evaluates locally using the policy embedded when the page loads; it makes no API request and stores no candidate data. The page uses Bootstrap 5.3.3 CSS from jsDelivr; its own styles preserve the layout if the CDN is unavailable, but Bootstrap styling requires a network connection. The JSON API is available for integrations and neither persists nor logs candidate results. Do not enter personal information into a public demo.

## Run locally

Python 3.10 or newer:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.server
```

Open `http://127.0.0.1:8000/`. The JSON endpoint is `POST /api/admissions/evaluate`; an undergraduate request is `{"level":"undergraduate","results_complete":true,"msce_results":{"English":6,"Mathematics":5,"Biology":5,"Physical Science":5,"Geography":6,"History":6}}`. Add an optional canonical `discipline` value to limit the returned programmes to that faculty; requests without it retain the previous all-programme behavior. A postgraduate request includes `level`, `gpa_5`, `degree_type`, `degree_classification`, `degree_relevance_by_program`, `degree_recognized`, `relevant_work_years_by_program`, `post_qualification_work_years`, `capstone_completed`, and `professional_qualification_accepted`. Degree relevance and relevant experience are supplied separately for each programme that requires them. Use `null` for unknown yes/no or experience values. `GET /health` checks service readiness. The server binds to localhost by default; expose it only behind appropriate network controls.

## Tests

Run the unit, API integration, and live-server system tests from this directory:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Portfolio and submission

The three-page portfolio is in `docs/` (`index.html`, `methodology.html`, `results.html`). The workflow in `.github/workflows/pages.yml` publishes those static pages to GitHub Pages. The portfolio links to `https://github.com/AlbertMkwanda/university-admission-expert-system`. Add `stanslausphillimon@gmail.com` as a collaborator, push to `main`, and enable Pages using GitHub Actions. Record the Pages URL for submission; these account actions require the owner's GitHub access.

The portfolio is static; run the local application above for the interactive demo. GitHub Pages cannot host the Python API.
