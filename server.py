"""
DPIA MCP Server

Run:      venv/bin/python server.py
Register: http://host.docker.internal:80/mcp
"""

import json
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from fill_docx import fill_from_data
from fill_excel import fill_risks
from starlette.applications import Starlette
from starlette.responses import FileResponse, PlainTextResponse
from starlette.routing import Route, Mount

load_dotenv()

MCP_PORT = int(os.environ.get("MCP_PORT", "80"))
MCP_PUBLIC_URL = os.environ.get("MCP_PUBLIC_URL", f"http://localhost:{MCP_PORT}")
VM_IP = os.environ.get("VM_IP")

mcp = FastMCP(
    "DPIA Document Store",
    transport_security=TransportSecuritySettings(
      enable_dns_rebinding_protection=False,
    ),
)
mcp_app = mcp.streamable_http_app()
STORAGE_FILE = os.path.join(os.path.dirname(__file__), "current_dpia.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

async def download(request):
    filename = request.path_params["filename"]
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.isfile(path):
        return PlainTextResponse("Not found", status_code=404)
    return FileResponse(path, filename=filename)

app = Starlette(
    routes=[
        Route("/download/{filename}", download),
        Mount("/", app=mcp_app),
    ],
    lifespan=mcp_app.router.lifespan_context,
)

def _load() -> dict:
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE) as f:
            return json.load(f)
    return {}


def _save(data: dict):
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _autogenerate(data: dict) -> str:
    try:
        path = fill_from_data(data)
        return f"{MCP_PUBLIC_URL}/download/{os.path.basename(path)}"
    except Exception as e:
        return f"(DOCX-fel: {e})"


def _autogenerate_excel(data: dict) -> str:
    try:
        path = fill_risks(data)
        return f"{MCP_PUBLIC_URL}/download/{os.path.basename(path)}"
    except Exception as e:
        return f"(Excel-fel: {e})"


def _parse_criterion(value: str) -> dict:
    for sep in [" - ", ": "]:
        if sep in value:
            svar, motivering = value.split(sep, 1)
            return {"svar": svar.strip(), "motivering": motivering.strip()}
    return {"svar": value.strip(), "motivering": ""}


@mcp.tool()
def start_new_dpia(title: str) -> str:
    """
    Start a new DPIA. Call this once at the very beginning of a new assessment.

    Args:
        title: Short name for this data processing activity.
    """
    _save({"title": title})
    return f"Startad ny DPIA: '{title}'"


@mcp.tool()
def get_progress() -> str:
    """
    Show what has already been saved. ALWAYS call this at the start of every
    conversation to check current state before saving anything.
    """
    data = _load()
    if not data:
        return "Ingen aktiv DPIA hittades."
    saved = []
    if data.get("steg1"):   saved.append("steg1")
    if data.get("criteria"): saved.append("kriterier")
    if data.get("steg2"):   saved.append("steg2")
    if data.get("steg3"):   saved.append("steg3")
    if data.get("steg4"):   saved.append("steg4")
    if data.get("steg5"):   saved.append("steg5")
    return (
        f"DPIA: {data.get('title', '(ingen titel)')}\n"
        f"Sparat: {', '.join(saved) if saved else 'ingenting än'}"
    )


# ── Steg 1: Bedöm behovet (T0–T10) ───────────────────────────────────────────

@mcp.tool()
def save_steg1(
    overview: str,
    faktorer: str,
    liknar_35_3: str,
    tva_kriterier: str,
    undantag_trots_ja: str,
    genomforas_trots_nej: str,
    lik_tidigare: str,
    allman_35_10: str,
    dso_svar: str,
    behov: str,
) -> str:
    """
    Save all answers for Steg 1 (Bedöm behovet). Each argument fills one table.

    For undantag_trots_ja / genomforas_trots_nej / lik_tidigare / allman_35_10:
    First line = "Ja", "Nej" or "Osäkert – kräver granskning", then newline + explanation.
    Example: "Nej\\nInget av undantagen i IMY:s förteckning är tillämpligt."

    Args:
        overview:             T0  — Övergripande beskrivning av den planerade behandlingen
        faktorer:             T1  — Faktorer som redan talar för att en DPIA behövs
        liknar_35_3:          T2  — "Ja", "Nej" eller "Osäkert – kräver granskning" — Liknar eller motsvarar artikel 35.3?
        tva_kriterier:        T4  — "Ja", "Nej" eller "Osäkert – kräver granskning" — Är 2 eller fler kriterier uppfyllda?
        undantag_trots_ja:    T5  — Ja/Nej/Osäkert + motivering — Undantag trots uppfyllda kriterier?
        genomforas_trots_nej: T6  — Ja/Nej/Osäkert + motivering — Genomförs ändå trots ej uppfyllda kriterier?
        lik_tidigare:         T7  — Ja/Nej/Osäkert + motivering — Liknar en tidigare genomförd DPIA?
        allman_35_10:         T8  — Ja/Nej/Osäkert + motivering — Allmän konsekvensbedömning art. 35.10?
        dso_svar:             T9  — Dataskyddsombudets bedömning och synpunkter (fritext)
        behov:                T10 — "Ja", "Nej" eller "Osäkert – kräver granskning" — Behövs en DPIA?
    """
    data = _load()
    if not data:
        return "Ingen aktiv DPIA. Anropa start_new_dpia() först."
    data["steg1"] = {
        "overview": overview, "faktorer": faktorer,
        "liknar_35_3": liknar_35_3, "tva_kriterier": tva_kriterier,
        "undantag_trots_ja": undantag_trots_ja,
        "genomforas_trots_nej": genomforas_trots_nej,
        "lik_tidigare": lik_tidigare, "allman_35_10": allman_35_10,
        "dso_svar": dso_svar, "behov": behov,
    }
    _save(data)
    return f"Steg 1 sparat. Dokument: {_autogenerate(data)}"


@mcp.tool()
def save_criteria(k1: str, k2: str, k3: str, k4: str, k5: str,
                  k6: str, k7: str, k8: str, k9: str) -> str:
    """
    Save the 9 IMY criteria answers for Steg 1 (T3). Call this alongside save_steg1.
    Format: "Ja - kort motivering", "Nej - kort motivering" or "Osäkert - kort motivering"
    Example: k1="Ja - Systemet profilerar användare baserat på tittarhistorik"

    Args:
        k1: Utvärdering eller poängsättning
        k2: Automatiserat beslutsfattande med rättslig/liknande effekt
        k3: Systematisk övervakning
        k4: Känsliga personuppgifter (art. 9/10)
        k5: Storskalig behandling
        k6: Samkörning eller kombination av register
        k7: Sårbara registrerade (barn, patienter m.fl.)
        k8: Innovativ teknik eller ny tillämpning
        k9: Förhindrar registrerade att utöva rättighet/tjänst/avtal
    """
    data = _load()
    if not data:
        return "Ingen aktiv DPIA. Anropa start_new_dpia() först."
    data["criteria"] = {
        str(i): _parse_criterion(v)
        for i, v in enumerate([k1, k2, k3, k4, k5, k6, k7, k8, k9], 1)
    }
    _save(data)
    summary = ", ".join(f"K{i}: {v['svar']}" for i, v in data["criteria"].items())
    return f"Kriterier sparade: {summary}. Dokument: {_autogenerate(data)}"


# ── Steg 2: Systematisk beskrivning (T11–T21) ─────────────────────────────────

@mcp.tool()
def save_steg2(
    objekt: str,
    individer: str,
    lander: str,
    sammanhang: str,
    anledning: str,
    resurser: str,
    beskrivning: str,
    ansvariga: str,
    kategorier_json: str,
    registrerade_json: str,
    mottagare_json: str,
) -> str:
    """
    Save all answers for Steg 2 (Systematisk beskrivning). Each argument fills one table.

    Args:
        objekt:            T11 — Avgränsa och beskriv objektet för konsekvensbedömningen
        individer:         T14 — Antal individer och mängd personuppgifter som behandlas
        lander:            T15 — Länder och regioner som berörs av behandlingen
        sammanhang:        T16 — Sammanhang; interna och externa faktorer av betydelse
        anledning:         T17 — Anledningen till behandlingen och förväntade fördelar
        resurser:          T18 — Resurser och informationstillgångar som berörs
        beskrivning:       T19 — Detaljerad beskrivning av hur behandlingen går till
        ansvariga:         T20 — Personuppgiftsansvariga och deras roller
        kategorier_json:   T12 — JSON-lista med kategorier av PERSONUPPGIFTER (vad för data). Format:
                           [{"kategori": "Namn och e-post", "sarskild": "Nej"},
                            {"kategori": "Hälsouppgifter", "sarskild": "Ja"}]
                           Max 6. "sarskild" = "Ja" om känslig kategori (art. 9).
        registrerade_json: T13 — JSON-lista med kategorier av REGISTRERADE (vilka personer). Format:
                           [{"kategori": "Anställda", "sarskild": "Nej"},
                            {"kategori": "Barn under 18", "sarskild": "Ja"}]
                           Max 6. "sarskild" = "Ja" om sårbar grupp (barn, patienter m.fl.).
        mottagare_json:    T21 — JSON-lista med mottagare/personuppgiftsbiträden. Format:
                           [{"biträde": "AWS", "kategorier": "Alla kategorier", "ändamål": "Molnlagring"}]
                           Max 6.
    """
    data = _load()
    if not data:
        return "Ingen aktiv DPIA. Anropa start_new_dpia() först."
    try:
        kategorier = json.loads(kategorier_json) if kategorier_json.strip() != "[]" else []
    except Exception:
        kategorier = []
    try:
        registrerade = json.loads(registrerade_json) if registrerade_json.strip() != "[]" else []
    except Exception:
        registrerade = []
    try:
        mottagare = json.loads(mottagare_json) if mottagare_json.strip() != "[]" else []
    except Exception:
        mottagare = []
    data["steg2"] = {
        "objekt": objekt, "individer": individer, "lander": lander,
        "sammanhang": sammanhang, "anledning": anledning, "resurser": resurser,
        "beskrivning": beskrivning, "ansvariga": ansvariga,
        "kategorier": kategorier, "registrerade": registrerade, "mottagare": mottagare,
    }
    _save(data)
    return f"Steg 2 sparat ({len(kategorier)} personuppgiftskategorier, {len(registrerade)} registreradekategorier, {len(mottagare)} mottagare). Dokument: {_autogenerate(data)}"


# ── Steg 3: Rättslig analys (T22–T34) ─────────────────────────────────────────

@mcp.tool()
def save_steg3(
    regelverk: str,
    andamal: str,
    uppgiftsminimering: str,
    nodvandighet_personuppgift: str,
    nodvandighet_for: str,
    nodvandighet_text: str,
    lagringsminimering: str,
    sakerhet: str,
    ansvarsskyldighet: str,
    rutiner: str,
    tredjeland: str,
    samlad_bedomning: str,
    rattslig_grund_json: str,
    sarskild_grund_json: str,
) -> str:
    """
    Save all answers for Steg 3 (Rättslig analys). Each argument fills one table.

    Args:
        regelverk:                T22 — Tillämpligt regelverk utöver GDPR
        andamal:                  T23 — Hur principen om ändamålsbegränsning (art. 5.1 b) säkerställs
        uppgiftsminimering:       T26 — Hur principen om uppgiftsminimering (art. 5.1 c) säkerställs
        nodvandighet_personuppgift: T27 C0 — Personuppgift som är nödvändig (t.ex. "E-postadress")
        nodvandighet_for:         T27 C1 — Vad den är nödvändig för (t.ex. "Skicka bekräftelse till sökande")
        nodvandighet_text:        T28 — Utförligare motivering av nödvändigheten
        lagringsminimering:       T29 — Lagringsminimering och gallringsrutiner (art. 5.1 e)
        sakerhet:                 T30 — Tekniska och organisatoriska säkerhetsåtgärder (art. 5.1 f)
        ansvarsskyldighet:        T31 — Hur ansvarsskyldighet (art. 5.2) visas i praktiken
        rutiner:                  T32 — Rutiner för att tillvarata de registrerades rättigheter (art. 12–22)
        tredjeland:               T33 — Tredjelandsöverföringar och tillämpliga skyddsåtgärder
        samlad_bedomning:         T34 — Samlad bedömning av rättsliga förutsättningar
        rattslig_grund_json:      T24 — JSON-lista med rättsliga grunder. Format:
                                  [{"beskrivning": "Rekryteringsprocess", "personuppgifter": "Namn, CV",
                                    "grund": "Art. 6.1 b — nödvändigt för avtal", "kommentar": ""}]
                                  Max 10 rader.
        sarskild_grund_json:      T25 — JSON-lista med undantag för särskilda kategorier (art. 9/10).
                                  Samma format som rattslig_grund_json. Lämna "[]" om ej tillämpligt.
    """
    data = _load()
    if not data:
        return "Ingen aktiv DPIA. Anropa start_new_dpia() först."
    try:
        rattslig_grund = json.loads(rattslig_grund_json) if rattslig_grund_json.strip() != "[]" else []
    except Exception:
        rattslig_grund = []
    try:
        sarskild_grund = json.loads(sarskild_grund_json) if sarskild_grund_json.strip() != "[]" else []
    except Exception:
        sarskild_grund = []
    data["steg3"] = {
        "regelverk": regelverk, "andamal": andamal,
        "uppgiftsminimering": uppgiftsminimering,
        "nodvandighet_personuppgift": nodvandighet_personuppgift,
        "nodvandighet_for": nodvandighet_for,
        "nodvandighet_text": nodvandighet_text,
        "lagringsminimering": lagringsminimering,
        "sakerhet": sakerhet, "ansvarsskyldighet": ansvarsskyldighet,
        "rutiner": rutiner, "tredjeland": tredjeland,
        "samlad_bedomning": samlad_bedomning,
        "rattslig_grund": rattslig_grund,
        "sarskild_grund": sarskild_grund,
    }
    _save(data)
    return f"Steg 3 sparat ({len(rattslig_grund)} rättsliga grunder). Dokument: {_autogenerate(data)}"


# ── Steg 4: Riskanalys (T35) ──────────────────────────────────────────────────

@mcp.tool()
def save_steg4(risks_json: str, sammanfattning: str) -> str:
    """
    Save the risk analysis for Steg 4. Fills both the Excel risk register and T35 in the Word doc.

    Args:
        risks_json: JSON list of identified risks (max 11). Each object must have these keys:
                    {
                      "risk": "Short risk name (e.g. Obehörig åtkomst)",
                      "beskrivning": "Detailed description of the risk",
                      "sannolikhet": "Låg | Medel | Hög | Mycket hög",
                      "konsekvensniva": "Begränsad | Relativt allvarlig | Allvarlig | Mycket allvarlig",
                      "riskbedomning": "Låg | Medel | Hög | Mycket hög",
                      "atgard": "Planned or implemented mitigation measure",
                      "sannolikhet_efter": "Låg | Medel | Hög | Mycket hög",
                      "konsekvensniva_efter": "Begränsad | Relativt allvarlig | Allvarlig | Mycket allvarlig",
                      "riskbedomning_efter": "Låg | Medel | Hög | Mycket hög"
                    }
        sammanfattning: Narrative summary of the risk analysis → written to T35 in the Word doc.
    """
    data = _load()
    if not data:
        return "Ingen aktiv DPIA. Anropa start_new_dpia() först."
    try:
        risks = json.loads(risks_json) if risks_json.strip() not in ("[]", "") else []
    except Exception:
        risks = []
    data["steg4"] = {"risks": risks, "sammanfattning": sammanfattning}
    _save(data)
    docx = _autogenerate(data)
    excel = _autogenerate_excel(data)
    return f"Steg 4 sparat ({len(risks)} risker). Dokument: {docx} | Excel: {excel}"


# ── Steg 5: Riskhantering ──────────────────────────────────────────────────────

@mcp.tool()
def save_steg5(sammanfattning: str) -> str:
    """
    Save the risk mitigation summary for Steg 5.
    Covers: technical and organisational safeguards, residual risk assessment,
    DPO sign-off, and overall conclusion on whether processing can proceed.

    Args:
        sammanfattning: Full summary of mitigation measures, residual risk conclusion,
                        DPO recommendation, and final DPIA outcome.
    """
    data = _load()
    if not data:
        return "Ingen aktiv DPIA. Anropa start_new_dpia() först."
    data["steg5"] = sammanfattning
    _save(data)
    docx = _autogenerate(data)
    result = f"Steg 5 sparat. Dokument: {docx}"
    if data.get("steg4"):
        result += f" | Excel: {_autogenerate_excel(data)}"
    return result


# ── Generate ───────────────────────────────────────────────────────────────────

@mcp.tool()
def generate_docx() -> str:
    """
    Regenerate and export the filled DOCX. Only saved sections are filled.
    Call this when the user explicitly asks for the document.
    """
    data = _load()
    if not data:
        return "Ingen aktiv DPIA."
    docx = _autogenerate(data)
    result = f"Dokument genererat: {docx}"
    if data.get("steg4"):
        result += f" | Excel: {_autogenerate_excel(data)}"
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=VM_IP, port=MCP_PORT)