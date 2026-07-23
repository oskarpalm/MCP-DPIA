# DPIA MCP Server

A Model Context Protocol (MCP) server that acts as a document store for AI-guided DPIA (Data Protection Impact Assessment) workflows in Eneo. The Checkpoint assistant uses it to save structured answers from a multi-step group chat conversation, then generates a filled Word document and Excel risk register from a Swedish DPIA template.

---

## Architecture overview

```
User ──► Eneo Group Chat
          ├── Assess Need assistant          (Steg 1)
          ├── Systematic Description assistant (Steg 2)
          ├── Legal Analysis assistant        (Steg 3)
          ├── Risk Analysis assistant         (Steg 4)
          ├── Risk Mitigation assistant       (Steg 5)
          └── Checkpoint assistant  ──► MCP Server (port 80)
                                              ├── current_dpia.json  (state)
                                              ├── fill_docx.py       (Word generation)
                                              ├── fill_excel.py      (Excel generation)
                                              └── output/            (generated files)
```

The Checkpoint assistant is the only assistant with MCP access. It calls save tools after each step discussion is complete, regenerates both output files automatically, and returns download links directly in the chat.

---

## Files

| File | Purpose |
|------|---------|
| `server.py` | MCP server — all tools and download endpoint |
| `fill_docx.py` | Fills all 36 tables in the Word template from saved JSON |
| `fill_excel.py` | Fills the Excel risk register (rows 3–13, columns B–J) |
| `MCP Document.docx` | Swedish DPIA Word template — do not modify |
| `MCP Risks.xlsx` | Swedish DPIA Excel risk register template — do not modify |
| `current_dpia.json` | Active DPIA state (single shared file — see Limitations) |
| `output/` | Generated filled documents — one per DPIA title |
| `.env` | Local configuration (port, public URL) |
| `.env.example` | Template for `.env` |
| `requirements.txt` | Python dependencies |

---

## Setup

```bash
cd dpia_mcp
python -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env
venv/bin/python server.py
```

Before starting, edit `.env`:

**Local development** — defaults work as-is:
```
MCP_PORT=80
MCP_PUBLIC_URL=http://localhost:80
```

**VM / remote host** — set `MCP_PUBLIC_URL` to the VM's IP so download links are reachable:
```
MCP_PORT=80
MCP_PUBLIC_URL=http://your-vm-ip:80
```

Register in Eneo as:
- Local: `http://host.docker.internal:80/mcp`
- VM: `http://your-vm-ip:80/`

---

## Tools

### `start_new_dpia(title)`
Clears all saved state and starts a fresh DPIA.

| Parameter | Description |
|-----------|-------------|
| `title` | Short name for the data processing activity |

> Overwrites `current_dpia.json`. Call once at the very start of a new assessment.

---

### `get_progress()`
Returns the title of the active DPIA and which steps have been saved so far. The Checkpoint should always call this first when a conversation starts.

---

### `save_steg1(...)`
Saves Step 1 — *Bedöm behovet* — into tables T0–T10 in the Word document.

| Parameter | Template table | Description |
|-----------|---------------|-------------|
| `overview` | T0 | Overall description of the planned processing |
| `faktorer` | T1 | Factors already pointing toward needing a DPIA |
| `liknar_35_3` | T2 | "Ja" / "Nej" / "Osäkert – kräver granskning" — resembles Art. 35.3 list? |
| `tva_kriterier` | T4 | "Ja" / "Nej" / "Osäkert – kräver granskning" — 2 or more criteria met? |
| `undantag_trots_ja` | T5 | Line 1: Ja/Nej/Osäkert · Line 2: explanation |
| `genomforas_trots_nej` | T6 | Line 1: Ja/Nej/Osäkert · Line 2: explanation |
| `lik_tidigare` | T7 | Line 1: Ja/Nej/Osäkert · Line 2: explanation |
| `allman_35_10` | T8 | Line 1: Ja/Nej/Osäkert · Line 2: explanation |
| `dso_svar` | T9 | DPO assessment and comments (free text) |
| `behov` | T10 | "Ja" / "Nej" / "Osäkert – kräver granskning" — is a DPIA needed? |

For multi-line fields (T5–T8), separate the answer from the explanation with `\n`.

---

### `save_criteria(k1, k2, ..., k9)`
Saves the 9 IMY criteria into table T3. Always call this alongside `save_steg1`.

Format for each parameter: `"Ja - short motivation"`, `"Nej - short motivation"` or `"Osäkert - short motivation"`

| Parameter | Criterion |
|-----------|-----------|
| `k1` | Evaluation or scoring of persons |
| `k2` | Automated decision-making with legal/significant effect |
| `k3` | Systematic monitoring |
| `k4` | Sensitive data (Art. 9/10) |
| `k5` | Large-scale processing |
| `k6` | Matching or combining datasets |
| `k7` | Vulnerable data subjects (children, patients, etc.) |
| `k8` | Innovative technology or new application |
| `k9` | Prevents subjects from exercising a right/service/contract |

---

### `save_steg2(...)`
Saves Step 2 — *Systematisk beskrivning* — into tables T11–T21.

| Parameter | Table | Description |
|-----------|-------|-------------|
| `objekt` | T11 | Scope and description of the assessment object |
| `individer` | T14 | Estimated number of individuals and volume of data |
| `lander` | T15 | Countries/regions involved |
| `sammanhang` | T16 | Context — internal and external factors |
| `anledning` | T17 | Reason for the processing and expected benefits |
| `resurser` | T18 | Resources and information assets involved |
| `beskrivning` | T19 | Detailed description of how processing takes place |
| `ansvariga` | T20 | Controllers and their roles |
| `kategorier_json` | T12 | JSON list of personal data categories (max 6) |
| `registrerade_json` | T13 | JSON list of data subject categories (max 6) |
| `mottagare_json` | T21 | JSON list of recipients/processors (max 6) |

**`kategorier_json` format** (what data — e.g. name, health data):
```json
[
  {"kategori": "Namn och e-post", "sarskild": "Nej"},
  {"kategori": "Hälsouppgifter", "sarskild": "Ja"}
]
```

**`registrerade_json` format** (who — e.g. employees, children):
```json
[
  {"kategori": "Anställda", "sarskild": "Nej"},
  {"kategori": "Barn under 18", "sarskild": "Ja"}
]
```
`sarskild` = `"Ja"` if the group is vulnerable (children, patients, etc.).

**`mottagare_json` format:**
```json
[
  {"biträde": "AWS", "kategorier": "Alla kategorier", "ändamål": "Molnlagring"}
]
```

---

### `save_steg3(...)`
Saves Step 3 — *Rättslig analys* — into tables T22–T34.

| Parameter | Table | Description |
|-----------|-------|-------------|
| `regelverk` | T22 | Applicable regulations beyond GDPR |
| `andamal` | T23 | How purpose limitation (Art. 5.1 b) is ensured |
| `uppgiftsminimering` | T26 | How data minimisation (Art. 5.1 c) is ensured |
| `nodvandighet_personuppgift` | T27 col 0 | A data element that is necessary (e.g. "E-mail") |
| `nodvandighet_for` | T27 col 1 | What it is necessary for |
| `nodvandighet_text` | T28 | Extended necessity justification |
| `lagringsminimering` | T29 | Retention periods and deletion routines |
| `sakerhet` | T30 | Technical and organisational security measures |
| `ansvarsskyldighet` | T31 | How accountability (Art. 5.2) is demonstrated |
| `rutiner` | T32 | Procedures for data subjects' rights (Art. 12–22) |
| `tredjeland` | T33 | Third-country transfers and safeguards |
| `samlad_bedomning` | T34 | Overall legal assessment |
| `rattslig_grund_json` | T24 | JSON list of legal bases (max 10) |
| `sarskild_grund_json` | T25 | JSON list of Art. 9/10 exemptions (max 10), or `"[]"` |

**`rattslig_grund_json` / `sarskild_grund_json` format:**
```json
[
  {
    "beskrivning": "Lönehantering",
    "personuppgifter": "Namn, personnummer, lön",
    "grund": "Art. 6.1 b — nödvändigt för avtal",
    "kommentar": ""
  }
]
```

> Note: T27 only has one data row in the template. Only one necessity pair can be documented in the Word document. Multiple necessity entries should be described in `nodvandighet_text`.

---

### `save_steg4(risks_json, sammanfattning)`
Saves Step 4 — *Riskanalys* — into T35 in the Word document **and** fills the Excel risk register.

| Parameter | Description |
|-----------|-------------|
| `risks_json` | JSON list of risks with full pre- and post-mitigation data (max 11) |
| `sammanfattning` | Narrative summary written to T35 in the Word document |

**`risks_json` format:**
```json
[
  {
    "risk": "Obehörig åtkomst",
    "beskrivning": "Intern aktör får tillgång till data utanför sin behörighet.",
    "sannolikhet": "Medel",
    "konsekvensniva": "Allvarlig",
    "riskbedomning": "Hög",
    "atgard": "Rollbaserad åtkomstkontroll och kvartalsvis behörighetsöversyn.",
    "sannolikhet_efter": "Låg",
    "konsekvensniva_efter": "Allvarlig",
    "riskbedomning_efter": "Medel"
  }
]
```

Valid values for `sannolikhet` / `sannolikhet_efter`: `Låg`, `Medel`, `Hög`, `Mycket hög`

Valid values for `konsekvensniva` / `konsekvensniva_efter`: `Begränsad`, `Relativt allvarlig`, `Allvarlig`, `Mycket allvarlig`

Valid values for `riskbedomning` / `riskbedomning_efter`: `Låg`, `Medel`, `Hög`, `Mycket hög`

Returns download links for both the Word document and the Excel file.

---

### `save_steg5(sammanfattning)`
Saves Step 5 — *Riskhantering* — summary text, appended to T35 in the Word document below the Step 4 summary.

| Parameter | Description |
|-----------|-------------|
| `sammanfattning` | Summary of mitigation measures, residual risk, DPO sign-off, and final conclusion |

---

### `generate_docx()`
Regenerates both output files from the current saved state and returns download links. Only sections that have been saved are filled — unsaved steps leave the template cells blank.

Returns the Excel link only if Step 4 has been saved.

---

## Download links

Every save tool and `generate_docx()` returns one or two download URLs:

```
Word:  <MCP_PUBLIC_URL>/download/<title>_filled.docx
Excel: <MCP_PUBLIC_URL>/download/<title>_risks.xlsx
```

The base URL comes from `MCP_PUBLIC_URL` in `.env`. Links are clickable in Eneo's chat interface. The Excel link is only included once Step 4 has been saved.

---

## Word template mapping (all 36 tables)

| Table | Step | Content |
|-------|------|---------|
| T0 | Steg 1 | Overview of planned processing |
| T1 | Steg 1 | Existing factors pointing toward DPIA need |
| T2 | Steg 1 | Resembles Art. 35.3 list? |
| T3 | Steg 1 | 9 IMY criteria (Ja/Nej + motivation) |
| T4 | Steg 1 | 2 or more criteria met? |
| T5 | Steg 1 | Exception despite criteria being met? |
| T6 | Steg 1 | Proceeding despite criteria not met? |
| T7 | Steg 1 | Similar to a previous DPIA? |
| T8 | Steg 1 | Covered by a general Art. 35.10 assessment? |
| T9 | Steg 1 | DPO assessment |
| T10 | Steg 1 | Final need conclusion (Ja/Nej) |
| T11 | Steg 2 | Assessment object description |
| T12 | Steg 2 | Categories of personal data (up to 6) |
| T13 | Steg 2 | Categories of data subjects / registrerade (up to 6) |
| T14 | Steg 2 | Number of individuals and data volume |
| T15 | Steg 2 | Countries and regions |
| T16 | Steg 2 | Context |
| T17 | Steg 2 | Reason and expected benefits |
| T18 | Steg 2 | Resources and information assets |
| T19 | Steg 2 | Detailed processing description |
| T20 | Steg 2 | Controllers and roles |
| T21 | Steg 2 | Recipients/processors (up to 6) |
| T22 | Steg 3 | Applicable regulations |
| T23 | Steg 3 | Purpose limitation |
| T24 | Steg 3 | Legal bases (up to 10 rows) |
| T25 | Steg 3 | Art. 9/10 exemptions (up to 10 rows) |
| T26 | Steg 3 | Data minimisation |
| T27 | Steg 3 | Necessity table (1 row) |
| T28 | Steg 3 | Extended necessity justification |
| T29 | Steg 3 | Storage minimisation |
| T30 | Steg 3 | Security measures |
| T31 | Steg 3 | Accountability |
| T32 | Steg 3 | Data subject rights procedures |
| T33 | Steg 3 | Third-country transfers |
| T34 | Steg 3 | Overall legal assessment |
| T35 | Steg 4+5 | Risk analysis + mitigation summary (narrative) |

---

## Current limitations

### Single shared state file
`current_dpia.json` is one file on disk with no user isolation. If two users are running a DPIA simultaneously they will overwrite each other. See *Production requirements* below.

### No authentication on download links
The `/download/<file>` endpoint is accessible to anyone who can reach the server's port. Files in `output/` are not protected by any auth.

### One necessity row (T27)
The Word template only has a single data row in the necessity table (T27). Only one `personuppgift`/`nödvändig för att` pair can be filled. Additional necessity entries should be included in `nodvandighet_text` (T28).

### Max category and recipient counts are template-fixed
- Personal data categories: max 6 (T12)
- Data subject categories: max 6 (T13)
- Recipients: max 6 (T21)
- Legal bases: max 10 (T24)
- Art. 9/10 exemptions: max 10 (T25)
- Risks in Excel: max 11 (rows 3–13 in the template)

Entries beyond these limits are silently dropped.

### No history or versioning
Each call to `start_new_dpia()` wipes the previous state. There is no way to retrieve a previous DPIA once overwritten. Output files in `output/` persist until manually deleted.

### Download link reachability depends on MCP_PUBLIC_URL
Links embedded in chat use whatever `MCP_PUBLIC_URL` is set to. With the default `http://localhost:80` they only work on the same machine. Set `MCP_PUBLIC_URL` to the VM's IP to make links reachable from outside.

### Tool schema is cached in Eneo
When tool signatures change (e.g. `save_steg4` adding `risks_json`), the Eneo UI caches the old schema. A manual tool refresh in the Eneo MCP settings is required after any server-side signature change.

---

## Production requirements

To support multiple concurrent users in a production deployment the following changes would be needed:

### 1. Per-user state storage (PostgreSQL)
Replace `current_dpia.json` with a `dpias` table in the existing Eneo PostgreSQL database:

```sql
CREATE TABLE dpias (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id),
    title       TEXT,
    data        JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

Each tool call reads/writes to the row matching the calling user's `user_id` instead of a shared file.

### 2. User identity extraction
The MCP server currently has no way to identify who is calling it. In production, Eneo passes a `Bearer` JWT in the `Authorization` header when proxying tool calls. The server middleware should decode this token and extract `user_id`, then pass it to every tool call transparently — without requiring the LLM to supply it as a parameter.


### 3. Multiple active DPIAs per user
Currently `start_new_dpia()` replaces whatever was in progress. In production, users should be able to have multiple DPIAs in progress simultaneously (e.g. one per processing activity). This requires a `dpia_id` returned by `start_new_dpia()` and passed to all subsequent save calls, or a selection mechanism in `get_progress()`.

### 4. File storage
Generated files are written to a local `output/` directory. In a multi-instance or containerised deployment this directory is not shared. Files should be stored in object storage (e.g. Azure Blob Storage) and download links should be pre-signed blob URLs with a configurable expiry.
