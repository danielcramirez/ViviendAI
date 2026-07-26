from __future__ import annotations

import json
import html
import importlib
import os
import re
import time
from pathlib import Path

import pandas as pd
import streamlit as st
import lead_service as _lead_service

# Streamlit puede conservar módulos locales entre reruns. Se recarga para evitar
# importaciones obsoletas después de una actualización del servicio.
importlib.reload(_lead_service)

from catalog_service import load_catalog
from campaign_service import PLACEMENTS, build_attribution
from finance_service import SMMLV_2026, income_range_for
from instagram_simulator import empty_profile, process_message, start_conversation
from make_service import load_local_env, request_vivi_reply
from lead_service import (
    DB_PATH,
    capture_lead,
    get_campaign_performance,
    get_dashboard_metrics,
    get_storage_status,
    init_db,
    list_events,
    list_leads,
    retry_crm_sync,
    save_conversation_profile,
    update_funnel_status,
)
from profiling_service import build_diagnosis, calculate_propensity
from agents.analista_perfilamiento import EXTRACTABLE_FIELDS, analyze_profile
from vivi_agent_service import request_agent_reply

APP_DIR = Path(__file__).resolve().parent
VIVI_AVATAR = APP_DIR / "assets" / "vivi-avatar.svg"
LOGO_V2 = APP_DIR / "Logov2.png"

st.set_page_config(
    page_title="Colsubsidio | Captura inteligente de leads",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --col-blue:#0067b1; --col-yellow:#ffd000; --graphite:#575756;
        --soft-gray:#f0f2f6; --white:#ffffff;
        --space-1:8px; --space-2:16px; --space-3:24px; --space-4:32px;
        --shadow-soft:0 10px 30px rgba(0,72,126,.10);
    }
    html, body, [class*="st-"], [class*="stApp"] {
        font-family:Inter,Roboto,"Segoe UI",Arial,sans-serif;
    }
    .block-container {
        max-width:none;
        padding:var(--space-3) var(--space-3) var(--space-4);
    }
    .stApp { background:var(--white); color:var(--graphite); }
    .stApp p { color:var(--graphite);font-size:20px;line-height:1.55; }
    .stApp label, .stApp label p {
        color:rgba(87,87,86,.80);font-size:14px;line-height:1.4;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    .small-muted {
        color:rgba(87,87,86,.80) !important;font-size:14px !important;
        line-height:1.45 !important;
    }
    [data-testid="InputInstructions"] { display:none; }
    [data-testid="stSidebar"] {
        background:#080808;border-right:1px solid rgba(255,255,255,.12);
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #f7fbff;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label p {
        color: #f7fbff;
    }
    .hero {
        position:relative;overflow:hidden;min-height:330px;
        padding:clamp(32px,5vw,72px);border-radius:32px;
        background:#050505;color:white;
        box-shadow:0 20px 55px rgba(0,0,0,.18);margin-bottom:var(--space-3);
        display:flex;flex-direction:column;justify-content:center;
    }
    .hero::before {
        content:"";position:absolute;width:340px;height:340px;right:-70px;top:-90px;
        border-radius:50%;background:var(--col-yellow);
        box-shadow:-100px 190px 0 -90px var(--col-blue);
    }
    .hero::after {
        content:"VIVI";position:absolute;right:42px;bottom:18px;color:#000;
        font-size:92px;font-weight:900;letter-spacing:-8px;
        transform:rotate(-7deg);opacity:.92;
    }
    .hero-kicker {
        position:relative;z-index:1;width:max-content;margin-bottom:var(--space-2);
        color:var(--col-yellow);font-size:14px;font-weight:900;
        letter-spacing:.12em;text-transform:uppercase;
    }
    .hero h1 {
        position:relative;z-index:1;margin:0;max-width:790px;
        font-size:clamp(48px,6vw,82px) !important;line-height:.98 !important;
        color:white;letter-spacing:-.055em;
    }
    .hero p {
        position:relative;z-index:1;margin:var(--space-3) 0 0;
        font-size:20px;max-width:690px;color:white;
    }
    .hero-accent { color:var(--col-yellow); }
    .impact-grid {
        display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
        gap:var(--space-2);margin-bottom:var(--space-4);
    }
    .impact-card {
        min-height:150px;padding:var(--space-3);border-radius:22px;
        background:var(--white);border:1px solid #e2e7eb;
        box-shadow:var(--shadow-soft);position:relative;overflow:hidden;
    }
    .impact-card::after {
        content:"";position:absolute;width:72px;height:8px;left:24px;bottom:0;
        background:var(--col-yellow);border-radius:8px 8px 0 0;
    }
    .impact-number {
        color:#000;font-size:clamp(38px,4vw,58px);font-weight:900;
        line-height:1;letter-spacing:-.05em;
    }
    .impact-label {
        margin-top:12px;color:var(--graphite);font-size:15px;
        line-height:1.4;font-weight:700;
    }
    h1, h2 {
        color:var(--graphite);font-size:48px !important;font-weight:600 !important;
        line-height:1.2 !important;letter-spacing:-.035em;
    }
    [data-testid="stChatMessageContent"] p { font-size:20px;line-height:1.55; }
    [data-testid="stChatMessage"] {
        border:1px solid #e3e9ee;border-radius:18px;padding:var(--space-2);
        margin-bottom:var(--space-2);box-shadow:var(--shadow-soft);
        background:var(--white);
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background:var(--col-blue);border-color:var(--col-blue);
        margin-left:clamp(16px,8vw,96px);
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {
        color:var(--white) !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        margin-right:clamp(16px,8vw,96px);
    }
    [data-testid="stChatInput"] {
        border:2px solid rgba(0,103,177,.28);border-radius:18px;
        box-shadow:0 8px 24px rgba(0,103,177,.10);
    }
    div[data-testid="stSelectbox"] {
        background:#ffffff;
        border:1px solid #dce4eb;
        border-radius:18px;
        padding:.75rem .85rem .9rem;
        box-shadow:0 8px 22px rgba(0,103,177,.09);
    }
    div[data-testid="stSelectbox"] > label {
        margin-bottom:.45rem;
    }
    div[data-testid="stSelectbox"] > label p {
        color:#0067b1 !important;
        font-size:18px !important;
        font-weight:800 !important;
        line-height:1.25;
        margin-bottom:.25rem;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        min-height:58px;
        background:#ffffff !important;
        border:2px solid var(--col-blue) !important;
        border-radius:14px !important;
        box-shadow:inset 7px 0 0 var(--col-yellow), 0 4px 12px rgba(0,103,177,.12);
        overflow:hidden;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        min-height:56px;
        background:#ffffff !important;
        border:0 !important;
        padding-left:.55rem;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"]:hover,
    div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
        border-color:var(--col-yellow) !important;
        box-shadow:inset 7px 0 0 var(--col-yellow), 0 0 0 3px rgba(255,208,0,.24);
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] input,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] div {
        color:#111111 !important;
        font-size:18px !important;
        font-weight:700 !important;
    }
    div[data-testid="stTextInput"],
    div[data-testid="stNumberInput"] {
        padding:var(--space-1) 0;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        min-height:52px;background:var(--white);color:var(--graphite);
        border:1.5px solid #cbd8e2;border-radius:14px;
        font-size:18px;padding:0 var(--space-2);
    }
    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stNumberInput"] input:focus {
        border-color:var(--col-blue);box-shadow:0 0 0 3px rgba(0,103,177,.12);
    }
    div[data-testid="stCheckbox"] {
        background:#f8fbfd;border:1px solid #dce6ed;border-radius:14px;
        padding:var(--space-2);
    }
    div[data-testid="stAlert"] {
        border-radius:16px;border-left-width:6px;padding:var(--space-2);
    }
    [data-testid="stExpander"] {
        margin:var(--space-2) 0;border:1px solid #dfe6eb;
        border-radius:16px;overflow:hidden;background:var(--white);
    }
    [data-testid="stExpander"] details > summary {
        min-height:56px;padding:12px 16px !important;
        display:flex;align-items:center;gap:12px;
        background:#f8f9fa;border-bottom:0;
    }
    [data-testid="stExpander"] details[open] > summary {
        border-bottom:1px solid #dfe6eb;
        box-shadow:inset 0 -3px 0 var(--col-yellow);
    }
    [data-testid="stExpander"] details > summary p,
    [data-testid="stExpander"] details > summary span {
        margin:0 !important;padding:0 !important;
        color:var(--graphite) !important;font-size:16px !important;
        font-weight:700 !important;line-height:1.25 !important;
    }
    [data-testid="stExpander"] details > summary svg {
        flex:0 0 20px;width:20px;height:20px;
        color:var(--col-blue);
    }
    [data-testid="stExpanderDetails"] {
        padding:var(--space-2) !important;
    }
    [data-testid="stExpanderDetails"] p,
    [data-testid="stExpanderDetails"] pre,
    [data-testid="stExpanderDetails"] code {
        font-size:14px !important;line-height:1.5 !important;
    }
    [data-testid="stForm"] {
        background:var(--white);border:1px solid #dfe6eb;border-radius:24px;
        padding:var(--space-4);box-shadow:0 18px 48px rgba(0,72,126,.09);
    }
    .ad-card {
        background:white; border-radius:22px; overflow:hidden;
        border:1px solid #e4eaf0; box-shadow:0 12px 35px rgba(25,53,76,.10);
        color:var(--graphite);
    }
    .ad-head { padding:1rem 1.2rem; display:flex; gap:.75rem; align-items:center; }
    .ad-head b { color:var(--graphite);font-size:18px; }
    .ad-logo {
        width:44px;height:44px;border-radius:50%;background:#ffd000;color:#0067b1;
        display:grid;place-items:center;font-weight:900;font-size:1.2rem;
    }
    .ad-visual {
        min-height:260px;padding:2.1rem;
        background:linear-gradient(145deg,#0067b1,#00375f);color:white;
        display:flex;flex-direction:column;justify-content:center;
    }
    .ad-visual h2 { color:white;font-size:2rem;line-height:1.05;margin:.5rem 0; }
    .ad-visual p {
        color:#000000;font-weight:400;
        background:rgba(255,255,255,.84);
        border:1px solid rgba(255,255,255,.92);
        border-radius:14px;
        padding:.85rem 1rem;
        margin:.65rem 0 0;
        box-shadow:0 6px 18px rgba(0,0,0,.12);
        backdrop-filter:blur(5px);
    }
    .pill { display:inline-block;width:max-content;background:#ffd000;color:#17212b;
        padding:.35rem .7rem;border-radius:99px;font-weight:800;font-size:.8rem; }
    .stage {
        min-height:54px;padding:var(--space-2);border-radius:16px;
        background:white;border:1px solid #dce4ea;
        text-align:center;font-weight:800;color:var(--graphite);
        box-shadow:0 5px 16px rgba(0,0,0,.04);
    }
    .stage.active {
        background:#000;border-color:#000;color:#fff;
        box-shadow:inset 0 -6px 0 var(--col-yellow);
    }
    .feature-strip {
        display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
        gap:var(--space-2);margin:var(--space-2) 0 var(--space-3);
    }
    .feature-item {
        display:flex;align-items:center;gap:12px;background:#f8fbfd;
        border:1px solid #dce7ef;border-radius:16px;padding:var(--space-2);
        color:var(--graphite);font-size:16px;font-weight:700;
    }
    .feature-icon {
        width:40px;height:40px;flex:0 0 40px;border-radius:12px;
        display:grid;place-items:center;background:rgba(255,208,0,.24);
        color:var(--col-blue);font-size:21px;
    }
    .income-explainer {
        border-left:5px solid var(--col-yellow);background:#fffbed;
        border-radius:12px;padding:12px 16px;margin:0 0 var(--space-2);
        color:var(--graphite);font-size:14px;line-height:1.45;
    }
    .flow-intro {
        display:flex;align-items:center;gap:var(--space-2);
        margin:var(--space-2) 0 var(--space-3);padding:var(--space-2);
        border-radius:16px;background:#000;color:#fff;
    }
    .flow-intro strong { color:var(--col-yellow); }
    .flow-intro span { color:#fff;font-size:16px;line-height:1.45; }
    .score-card { border-radius:18px;padding:1.1rem 1.25rem;background:white;
        border-left:6px solid #0067b1;box-shadow:var(--shadow-soft);
        color:var(--graphite); }
    div[data-testid="stMetric"] { background:white;border:1px solid #e6ebf0;
        border-radius:16px;padding:1rem;color:#253443; }
    div[data-testid="stMetric"] * { color:#253443; }
    .small-muted { color:#708090;font-size:.86rem; }
    div.stButton > button[kind="primary"], .btn-primary {
        min-height:50px;background:var(--col-yellow);border:0;border-radius:25px;
        color:var(--graphite);font-weight:800;padding:0 var(--space-3);
        box-shadow:0 8px 20px rgba(255,208,0,.24);
    }
    div.stButton > button[kind="primary"]:hover, .btn-primary:hover {
        background:#eabd00;border-color:#eabd00;color:var(--graphite);
        transform:translateY(-1px);
    }
    div.stButton > button[kind="secondary"], .btn-secondary {
        min-height:50px;background:var(--col-blue);border:0;border-radius:25px;
        color:var(--white);font-weight:800;padding:0 var(--space-3);
    }
    div.stButton > button[kind="secondary"]:hover, .btn-secondary:hover {
        background:#00558f;color:var(--white);transform:translateY(-1px);
    }
    div[data-testid="stFormSubmitButton"] button {
        min-height:54px;background:var(--col-yellow);border:0;border-radius:27px;
        color:var(--graphite);font-weight:900;padding:0 var(--space-3);
        box-shadow:0 8px 20px rgba(255,208,0,.24);
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background:#eabd00;border-color:#eabd00;color:var(--graphite);
        transform:translateY(-1px);
    }
    [data-testid="stLinkButton"] a {
        min-height:50px;background:var(--col-yellow) !important;
        border:0 !important;border-radius:25px !important;
        color:var(--graphite) !important;font-weight:800 !important;
        box-shadow:0 8px 20px rgba(255,208,0,.24);
    }
    [data-testid="stDataFrame"] {
        border:1px solid #dfe6eb;border-radius:18px;overflow:hidden;
        box-shadow:0 10px 28px rgba(0,72,126,.08);
    }
    a { color:var(--col-blue); }
    .dream-card, .ficha-sueno {
        background:rgba(255,208,0,.20);border:1px solid var(--col-blue);
        border-radius:16px;padding:var(--space-3);margin:var(--space-2) 0 var(--space-3);
        color:var(--graphite);
        box-shadow:0 12px 28px rgba(0,103,177,.08);
    }
    .dream-card h3, .ficha-sueno h3 {
        color:var(--col-blue);margin:0 0 var(--space-1);font-size:24px;
    }
    .dream-card p, .ficha-sueno p { margin:0;font-size:20px;line-height:1.6; }
    .score-shell {
        background:var(--soft-gray);border-radius:999px;height:22px;
        overflow:hidden;border:1px solid #d7dce1;margin:.5rem 0 .75rem;
    }
    .score-fill {
        height:100%;border-radius:999px;
        background:linear-gradient(90deg,var(--graphite) 0%,#b39b31 55%,var(--col-yellow) 100%);
        transition:width .45s ease;
    }
    .score-labels {
        display:flex;justify-content:space-between;color:var(--graphite);
        font-size:.78rem;font-weight:700;margin-bottom:1rem;
    }
    .brand-note {
        background:white;border-radius:16px;padding:.75rem;color:var(--graphite);
        border:1px solid rgba(255,255,255,.35);
    }
    .agent2-divider {
        height:1px;background:linear-gradient(90deg,transparent,var(--col-blue),transparent);
        margin:var(--space-2) 0;border:0;
    }
    .agent2-card {
        background:var(--white);border:2px solid var(--col-blue);
        border-radius:18px;overflow:hidden;margin:var(--space-2) 0 var(--space-3);
        box-shadow:0 8px 24px rgba(0,103,177,.10);
    }
    .agent2-header {
        display:flex;align-items:center;gap:10px;
        padding:14px 18px;background:#f0f6fe;
        border-bottom:1px solid #d0ddea;
    }
    .agent2-icon {
        width:32px;height:32px;flex:0 0 32px;border-radius:50%;
        background:var(--col-blue);color:#fff;
        display:grid;place-items:center;font-size:16px;font-weight:900;
    }
    .agent2-title {
        font-weight:800;font-size:15px;color:var(--graphite);
    }
    .agent2-body {
        padding:var(--space-2) var(--space-2) var(--space-3);
    }
    .agent2-metrics {
        display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
        gap:var(--space-2);
    }
    .agent2-metric {
        text-align:center;padding:var(--space-1) var(--space-2);
    }
    .agent2-metric-value {
        display:block;font-size:20px;font-weight:900;color:#000;
        line-height:1.2;
    }
    .agent2-metric-label {
        display:block;font-size:11px;color:var(--graphite);
        font-weight:700;text-transform:uppercase;letter-spacing:.04em;
        margin-top:2px;
    }
    .agent2-recommended {
        margin-top:var(--space-2);padding:var(--space-1) var(--space-2);
        background:#eef6ff;border-radius:12px;
        border-left:4px solid var(--col-blue);
        font-size:15px;line-height:1.5;color:var(--graphite);
    }
    .agent2-missing {
        margin:var(--space-1) var(--space-2) var(--space-2);
        font-size:14px;line-height:1.8;color:var(--graphite);
    }
    .agent2-pill {
        display:inline-block;padding:2px 10px;margin:2px 4px 2px 0;
        background:#fef3cd;color:#856404;border-radius:99px;
        font-size:12px;font-weight:700;white-space:nowrap;
    }
    .agent2-diagnosis {
        margin-top:var(--space-2);padding:var(--space-1) var(--space-2);
        background:rgba(255,208,0,.15);border-radius:12px;
        border-left:4px solid var(--col-yellow);
        font-size:15px;line-height:1.5;color:var(--graphite);
    }
    .agent2-persistence {
        display:flex;align-items:center;gap:8px;
        margin:var(--space-1) var(--space-2) var(--space-2);
        font-size:13px;line-height:1.5;color:var(--graphite);
    }
    .persistence-badge {
        display:inline-block;padding:1px 10px;border-radius:99px;
        font-size:11px;font-weight:800;letter-spacing:.02em;
    }
    .persistence-ok {
        background:#d4edda;color:#155724;
    }
    .persistence-local {
        background:#fff3cd;color:#856404;
    }
    .persistence-error {
        background:#f8d7da;color:#721c24;
    }
    .agent2-missing strong, .agent2-recommended strong, .agent2-diagnosis strong,
    .agent2-persistence strong {
        color:var(--graphite);
    }
    @media (max-width:768px) {
        .agent2-metrics { grid-template-columns:repeat(2,1fr); }
    }
    button:focus-visible, input:focus-visible, textarea:focus-visible,
    [data-baseweb="select"]:focus-within {
        outline:3px solid rgba(255,208,0,.70) !important;
        outline-offset:2px;
    }
    @media (max-width:768px) {
        .block-container { padding:var(--space-2); }
        h1, h2, .hero h1 { font-size:clamp(32px,9vw,42px) !important; }
        .hero { padding:var(--space-3);border-radius:18px; }
        .stApp p, [data-testid="stChatMessageContent"] p { font-size:18px; }
        [data-testid="stChatMessage"] { margin-left:0 !important;margin-right:0 !important; }
        .feature-strip { grid-template-columns:1fr; }
        .impact-grid { grid-template-columns:1fr; }
        .hero { min-height:420px;padding:var(--space-3); }
        .hero::before { width:230px;height:230px;right:-75px;top:-55px; }
        .hero::after { right:20px;bottom:10px;font-size:58px; }
        [data-testid="stForm"] { padding:var(--space-2); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def bootstrap_database() -> str:
    init_db()
    return str(DB_PATH)


@st.cache_data
def get_catalog() -> list[dict]:
    return load_catalog()


bootstrap_database()
load_local_env()
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "ViviendAI_bot").lstrip("@")

if "show_form" not in st.session_state:
    st.session_state.show_form = False
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "instagram_messages" not in st.session_state:
    st.session_state.instagram_messages = []
if "instagram_profile" not in st.session_state:
    st.session_state.instagram_profile = None
if "instagram_lead_code" not in st.session_state:
    st.session_state.instagram_lead_code = None
if "instagram_agent2_result" not in st.session_state:
    st.session_state.instagram_agent2_result = None
if "instagram_last_agent2_turn" not in st.session_state:
    st.session_state.instagram_last_agent2_turn = 0


def _count_new_profile_fields(old: dict, new: dict) -> int:
    """Count how many Agent-2-extractable fields changed from empty to filled."""
    count = 0
    for key in EXTRACTABLE_FIELDS:
        old_val = old.get(key) if isinstance(old, dict) else None
        new_val = new.get(key) if isinstance(new, dict) else None
        if old_val in (None, "", [], {}) and new_val not in (None, "", [], {}):
            count += 1
    return count


with st.sidebar:
    st.image(str(LOGO_V2), width="stretch")
    st.markdown("### VIVI · ViviendAI")
    st.caption("Perfilamiento inteligente de vivienda")
    section = st.radio(
        "Navegación",
        [
            "Experiencia del cliente",
            "Catálogo de proyectos",
            "Centro de operaciones",
            "Arquitectura y API",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("VIVI 1.0 · Perfilamiento inteligente")
    st.markdown(
        '<div class="brand-note">Datos trazables · IA responsable · Scoring auditable</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">Perfilamiento inteligente de leads</div>
      <h1>Un clic. Una conversación. <span class="hero-accent">Un hogar posible.</span></h1>
      <p>VIVI transforma leads pagos en conversaciones humanas, perfiles trazables y oportunidades listas para el asesor.</p>
    </div>
    <div class="impact-grid" aria-label="Indicadores del reto">
      <div class="impact-card">
        <div class="impact-number">0,2%</div>
        <div class="impact-label">Conversión actual de leads pagos que queremos transformar.</div>
      </div>
      <div class="impact-card">
        <div class="impact-number">2%</div>
        <div class="impact-label">Referencia de conversión de los leads orgánicos.</div>
      </div>
      <div class="impact-card">
        <div class="impact-number">0–100</div>
        <div class="impact-label">Score VIVI auditable antes de llegar a Salesforce.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


if section == "Experiencia del cliente":
    campaign_controls = st.columns([2, 1])
    campaign_project = campaign_controls[0].selectbox(
        "Campaña de proyecto que originó la visita",
        [project["name"] for project in get_catalog()],
        help="Cada proyecto conserva una campaña independiente hasta Salesforce.",
    )
    campaign_placement = campaign_controls[1].selectbox(
        "Origen",
        list(PLACEMENTS),
    )
    attribution = build_attribution(campaign_project, campaign_placement)
    st.caption(
        f"Campaña `{attribution['campaign_id']}` · Anuncio `{attribution['ad_id']}` · "
        f"UTM `{attribution['utm_campaign']}`"
    )
    stages = st.columns(5)
    labels = [
        "1 · Anuncio",
        "2 · Formulario",
        "3 · HANA / SQLite",
        "4 · VIVI",
        "5 · Salesforce",
    ]
    active = 1 if st.session_state.show_form else 0
    if st.session_state.last_result:
        active = 2
    if st.session_state.instagram_messages:
        active = 3
    if st.session_state.last_result and st.session_state.last_result.get("crm_status") == "SYNCED":
        active = 4
    for index, (column, label) in enumerate(zip(stages, labels)):
        css = "stage active" if index <= active else "stage"
        column.markdown(f'<div class="{css}">{label}</div>', unsafe_allow_html=True)

    # El anuncio y el formulario se apilan verticalmente para aprovechar todo
    # el ancho. El formulario no debe quedar comprimido en una columna lateral.
    left = st.container()
    right = st.container()
    with left:
        st.markdown(
            f"""
            <div class="ad-card">
              <div class="ad-head">
                <div class="ad-logo">C</div>
                <div><b>Colsubsidio</b><br><span class="small-muted">Publicidad · Patrocinado</span></div>
              </div>
              <div class="ad-visual">
                <span class="pill">CAMPAÑA PERSONALIZADA · {campaign_placement.upper()}</span>
                <h2>Tu nueva historia puede comenzar en {campaign_project.title()}.</h2>
                <p>Senderos, naturaleza y un hogar para crecer. Cuéntanos qué sueñas y descubre opciones para acercarte a tu vivienda.</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Registrarte", type="primary", width="stretch"):
            st.session_state.show_form = True
            st.rerun()

    with right:
        if not st.session_state.show_form:
            st.info("Selecciona **Registrarte** para abrir el formulario instantáneo de Meta.")
            st.markdown("#### ¿Qué demuestra esta pantalla?")
            st.markdown(
                "- Experiencia móvil sin redirecciones.\n"
                "- Captura de cinco variables mínimas.\n"
                "- Consentimiento y propósito visibles."
            )
        else:
            st.subheader("Formulario instantáneo")
            st.caption("Queremos entender tu sueño, no hacerte repetir información innecesaria.")
            st.markdown(
                """
                <div class="flow-intro">
                  <strong>PASO 1 · 60 SEGUNDOS</strong>
                  <span>Confirma los datos mínimos de Meta. Después, VIVI continuará
                  el perfilamiento como una conversación, con una sola pregunta por turno.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                """
                <div class="feature-strip" aria-label="Características del perfil de vivienda">
                  <div class="feature-item">
                    <span class="feature-icon" aria-hidden="true">⌖</span>
                    <span>Proyecto y ubicación</span>
                  </div>
                  <div class="feature-item">
                    <span class="feature-icon" aria-hidden="true">▣</span>
                    <span>Alcobas y espacio</span>
                  </div>
                  <div class="feature-item">
                    <span class="feature-icon" aria-hidden="true">◇</span>
                    <span>Capacidad orientativa</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.form("meta_lead_form", clear_on_submit=False):
                identity_columns = st.columns(2, gap="large")
                with identity_columns[0]:
                    full_name = st.text_input(
                        "👤 Nombre y apellido *",
                        placeholder="Ej. Laura Martínez",
                    )
                    id_number = st.text_input(
                        "▤ Número de documento *",
                        placeholder="Sin puntos ni espacios",
                    )
                with identity_columns[1]:
                    id_type = st.selectbox(
                        "◫ Tipo de documento *",
                        ["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte"],
                    )
                    telegram_username = st.text_input(
                        "✈ Usuario de Telegram (opcional)",
                        placeholder="@usuario",
                        help=(
                            "El bot no puede escribirte solamente con este usuario. "
                            "Después de enviar la solicitud deberás pulsar Continuar en Telegram."
                        ),
                    )

                financial_columns = st.columns(2, gap="large")
                with financial_columns[0]:
                    income_monthly = st.number_input(
                        "＄ ¿Cuánto suman los ingresos mensuales de tu hogar? *",
                        min_value=0,
                        max_value=50_000_000,
                        value=2_500_000,
                        step=100_000,
                        format="%d",
                        help=f"SMMLV 2026 usado por la simulación: ${SMMLV_2026:,.0f}.",
                    )
                    income_range = income_range_for(income_monthly)
                    formatted_income = f"${income_monthly:,.0f}".replace(",", ".")
                    st.markdown(
                        f"""
                        <div class="income-explainer">
                          <strong>{formatted_income} · {html.escape(income_range)}</strong><br>
                          SMMLV significa salario mínimo mensual legal vigente.
                          Para esta simulación usamos el valor 2026 de
                          ${SMMLV_2026:,.0f}.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    purchase_horizon = st.selectbox(
                        "◷ ¿Cuándo te gustaría comprar vivienda?",
                        [
                            "En los próximos 6 meses",
                            "Entre 6 y 12 meses",
                            "En más de 12 meses",
                            "Estoy explorando",
                        ],
                    )
                with financial_columns[1]:
                    affiliation_type = st.selectbox(
                        "◇ ¿Cuál es tu tipo de afiliación a Colsubsidio? *",
                        ["Afiliado como trabajador", "Beneficiario", "No afiliado"],
                    )
                    savings_range = st.selectbox(
                        "▱ ¿Con qué ahorro cuentas hoy? (declarado por ti)",
                        [
                            "Prefiero no responder",
                            "Aún no tengo ahorro",
                            "Menos de $3 millones",
                            "Entre $3 y $10 millones",
                            "Más de $10 millones",
                        ],
                        help=(
                            "No consultamos cuentas bancarias. "
                            "Esta respuesta es voluntaria y orientativa."
                        ),
                    )
                preferred_project = campaign_project
                st.info(f"Llegaste por la campaña de **{preferred_project}**; no te lo preguntaremos otra vez.")
                bedrooms = st.slider("▣ ¿Cuántas habitaciones necesitas?", 1, 4, 2)
                consent = st.checkbox(
                    "🔒 Autorizo el tratamiento de mis datos personales para esta simulación.",
                    help="Puedes retirar la autorización. El prototipo no consulta información bancaria.",
                )
                st.markdown(
                    "[Consultar la política oficial de tratamiento de datos de Colsubsidio]"
                    "(https://www.colsubsidio.com/transparencia-acceso-informacion/"
                    "tratamiento-datos-personales)"
                )
                submitted = st.form_submit_button("Enviar solicitud", type="primary", width="stretch")

            if submitted:
                if not full_name.strip():
                    st.error("El nombre y apellido son obligatorios.")
                elif len(full_name.strip().split()) < 2:
                    st.error("Ingresa al menos un nombre y un apellido.")
                elif not id_number.strip().isalnum() or len(id_number.strip()) < 5:
                    st.error("Ingresa un número de documento válido.")
                elif telegram_username.strip() and not re.fullmatch(
                    r"@?[A-Za-z0-9_]{5,32}", telegram_username.strip()
                ):
                    st.error("Ingresa un usuario de Telegram válido, por ejemplo @laura_2026.")
                elif not consent:
                    st.error("Debes autorizar el tratamiento de datos para continuar.")
                else:
                    normalized_full_name = " ".join(
                        part.capitalize() for part in full_name.strip().split()
                    )
                    payload = {
                        "full_name": normalized_full_name,
                        "id_type": id_type,
                        "id_number": id_number.strip(),
                        "telegram_username": telegram_username.strip().lstrip("@"),
                        "income_monthly": income_monthly,
                        "income_range": income_range,
                        "affiliation_type": affiliation_type,
                        "affiliated": affiliation_type != "No afiliado",
                        "negative_report": False,
                        "purchase_horizon": purchase_horizon,
                        "savings_range": savings_range,
                        "preferred_project": preferred_project,
                        "bedrooms": bedrooms,
                        "consent": consent,
                        "source": attribution["utm_source"].upper(),
                        "campaign": attribution["campaign_name"],
                        **attribution,
                    }
                    with st.status("Procesando webhook de Meta…", expanded=True) as status:
                        st.write("POST recibido · validando integridad")
                        time.sleep(0.5)
                        st.write("Normalizando datos y calificando lead")
                        time.sleep(0.5)
                        result = capture_lead(payload, simulate_latency=0.5)
                        st.write("Registro persistido · sincronizando con CRM")
                        status.update(label="Flujo completado", state="complete", expanded=False)
                    st.session_state.last_result = result
                    if st.session_state.instagram_lead_code != result["lead_code"]:
                        st.session_state.instagram_messages = start_conversation(
                            normalized_full_name, preferred_project
                        )
                        st.session_state.instagram_profile = empty_profile(
                            preferred_project,
                            attribution["campaign_id"],
                            result["lead_code"],
                            {
                                **payload,
                                "max_monthly_payment": result["financial_profile"][
                                    "max_monthly_payment"
                                ],
                                "consent": consent,
                            },
                        )
                        st.session_state.instagram_lead_code = result["lead_code"]
                        profile_seed = st.session_state.instagram_profile
                        try:
                            request_vivi_reply(
                                {
                                    "lead_id": result["lead_code"],
                                    "channel": "captura_meta_simulada",
                                    "customer_name": normalized_full_name,
                                    "project_origin": preferred_project,
                                    "campaign_id": attribution["campaign_id"],
                                    "message": (
                                        "INICIALIZAR PERFIL PARA TELEGRAM. "
                                        "No es un mensaje escrito por el cliente."
                                    ),
                                    "history": "",
                                    "turn_count": 0,
                                    "profile_json": json.dumps(
                                        profile_seed, ensure_ascii=False
                                    ),
                                    "last_score": 0,
                                }
                            )
                            profile_seed["make_profile_seeded"] = True
                        except RuntimeError as error:
                            profile_seed["make_profile_seeded"] = False
                            profile_seed["make_seed_warning"] = str(error)

            result = st.session_state.last_result
            if result:
                if result["duplicate"]:
                    st.warning(
                        f"Posible duplicado detectado. Se conservó la trazabilidad en el lead "
                        f"**{result['lead_code']}**."
                    )
                else:
                    source_lead_id = result.get("meta_lead_id", "sesión anterior")
                    st.success(
                        f"Solicitud recibida con código **{result['lead_code']}** "
                        f"e identificador de origen **{source_lead_id}**."
                    )
                legacy_ratings = {
                    "CALIENTE": "ALTA",
                    "TIBIO": "MEDIA",
                    "FRÍO": "NUTRICIÓN",
                }
                display_rating = legacy_ratings.get(result["rating"], result["rating"])
                color = {
                    "ALTA": "#16803a",
                    "MEDIA": "#b45309",
                    "NUTRICIÓN": "#526273",
                }.get(display_rating, "#0067b1")
                st.markdown(
                    f"""
                    <div class="score-card" style="border-left-color:{color}">
                      <b>Precalificación técnica inicial: {result["score"]}/100</b><br>
                      <span class="small-muted">
                        Evalúa datos declarados del formulario. La prioridad comercial
                        se determina únicamente después del diagnóstico de VIVI.
                      </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                initial_score = max(0, min(100, int(result["score"])))
                st.markdown(
                    f"""
                    <div class="score-shell" role="progressbar"
                         aria-label="Precalificación técnica inicial"
                         aria-valuenow="{initial_score}" aria-valuemin="0" aria-valuemax="100">
                      <div class="score-fill" style="width:{initial_score}%"></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.caption(
                    "CRM: "
                    + (
                        "sincronizado correctamente"
                        if result["crm_status"] == "SYNCED"
                        else "en espera del diagnóstico de VIVI"
                    )
                )
                st.info(
                    "Esta prioridad orienta la atención comercial. No equivale a aprobación "
                    "de crédito ni asignación de subsidio."
                )
                telegram_start_url = (
                    f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={result['lead_code']}"
                )
                st.link_button(
                    "Continuar conversación en Telegram",
                    telegram_start_url,
                    type="primary",
                    width="stretch",
                )
                st.caption(
                    "Telegram abrirá el bot con el código del lead. Por seguridad, "
                    "el cliente debe pulsar Iniciar para autorizar la conversación."
                )
                financial = result.get("financial_profile")
                if financial:
                    finance_cols = st.columns(3)
                    finance_cols[0].metric(
                        "Subsidio Colsubsidio estimado",
                        f"${financial['colsubsidio_subsidy']:,.0f}".replace(",", "."),
                    )
                    finance_cols[1].metric(
                        "Concurrente potencial",
                        f"${financial['concurrent_potential']:,.0f}".replace(",", "."),
                    )
                    finance_cols[2].metric(
                        "Cuota máxima orientativa",
                        f"${financial['max_monthly_payment']:,.0f}".replace(",", "."),
                    )
                    st.caption(financial["disclaimer"])

                st.divider()
                st.subheader("Instagram Direct · Simulación")
                st.caption(
                    f"Conversación originada por `{result.get('campaign_id', attribution['campaign_id'])}`. "
                    "No se envían mensajes reales."
                )
                for chat_message in st.session_state.instagram_messages:
                    avatar = str(VIVI_AVATAR) if chat_message["role"] == "assistant" else None
                    with st.chat_message(chat_message["role"], avatar=avatar):
                        st.write(chat_message["content"])

                customer_message = st.chat_input(
                    "Responde como cliente…",
                    key="instagram_simulated_input",
                )
                if customer_message:
                    st.session_state.instagram_messages.append(
                        {"role": "user", "content": customer_message}
                    )
                    profile = dict(st.session_state.instagram_profile)
                    history = "\n".join(
                        f"{'VIVI' if item['role'] == 'assistant' else 'USUARIO'}: "
                        f"{item['content']}"
                        for item in st.session_state.instagram_messages[:-1]
                    )
                    try:
                        agent_result = request_agent_reply(
                            {
                                "lead_id": result["lead_code"],
                                "channel": "instagram_simulado",
                                "customer_name": full_name,
                                "project_origin": profile["project_origin"],
                                "campaign_id": profile["campaign_id"],
                                "message": customer_message,
                                "history": history,
                                "turn_count": max(
                                    len(st.session_state.instagram_messages) // 2,
                                    0,
                                ),
                                "profile_json": json.dumps(profile, ensure_ascii=False),
                                "last_score": calculate_propensity(profile)[
                                    "propensity_score"
                                ],
                            }
                        )
                        response = agent_result["reply"]
                        profile = agent_result["profile"]
                    except RuntimeError as error:
                        response, profile = process_message(
                            customer_message,
                            st.session_state.instagram_profile,
                        )
                        profile["agent_source"] = "SIMULADOR_LOCAL"
                        profile["integration_warning"] = str(error)
                    scoring = calculate_propensity(profile)
                    diagnosis = build_diagnosis(profile, scoring)

                    # --- Agent 2: análisis de perfilamiento activado por nuevos campos o turnos ---
                    profile_before = dict(st.session_state.instagram_profile or {})
                    new_fields = _count_new_profile_fields(profile_before, profile)
                    current_turn = max(len(st.session_state.instagram_messages) // 2, 0)
                    turns_since_last = current_turn - st.session_state.instagram_last_agent2_turn
                    should_analyze = new_fields >= 2 or (current_turn >= 5 and turns_since_last >= 5)
                    agent2_result = st.session_state.instagram_agent2_result
                    if should_analyze:
                        full_history = "\n".join(
                            f"{'VIVI' if item['role'] == 'assistant' else 'USUARIO'}: "
                            f"{item['content']}"
                            for item in st.session_state.instagram_messages
                        )
                        try:
                            agent2_result = analyze_profile(
                                lead_id=result["lead_code"],
                                channel="instagram_simulado",
                                customer_name=profile.get("customer_name", ""),
                                project_origin=profile.get("project_origin", ""),
                                campaign_id=profile.get("campaign_id", ""),
                                history=full_history,
                                profile=profile,
                                force=True,
                            )
                            st.session_state.instagram_agent2_result = agent2_result
                            st.session_state.instagram_last_agent2_turn = current_turn
                        except RuntimeError as exc:
                            agent2_result = {
                                "ok": False,
                                "reply_warning": str(exc),
                                "gemini_source": None,
                            }
                            st.session_state.instagram_agent2_result = agent2_result
                    # --- fin Agente 2 ---

                    profile["scoring"] = scoring
                    profile["diagnosis"] = diagnosis
                    # Si Agent 2 ya persistió, evitamos duplicar la escritura
                    if should_analyze and agent2_result and agent2_result.get("ok"):
                        profile["crm_status"] = agent2_result.get("crm_status", "SYNCED")
                    else:
                        profile["crm_status"] = save_conversation_profile(
                            result["lead_code"],
                            profile,
                            scoring,
                            diagnosis,
                        )
                    result["crm_status"] = profile["crm_status"]
                    st.session_state.last_result = result
                    st.session_state.instagram_profile = profile
                    st.session_state.instagram_messages.append(
                        {"role": "assistant", "content": response}
                    )
                    st.rerun()

                profile = st.session_state.instagram_profile
                if profile:
                    if profile.get("integration_warning"):
                        st.warning(
                            "Make/Gemini no respondió; VIVI utilizó temporalmente el "
                            "simulador local. Revisa que el escenario esté activo."
                        )
                    scoring = profile.get("scoring") or calculate_propensity(profile)
                    diagnosis = profile.get("diagnosis") or build_diagnosis(profile, scoring)
                    profile_columns = st.columns(3)
                    profile_columns[0].metric(
                        "Propensión de compra",
                        f"{scoring['propensity_score']}/100",
                    )
                    profile_columns[1].metric(
                        "Prioridad",
                        scoring["priority"],
                    )
                    profile_columns[2].metric(
                        "Ruta",
                        scoring["route"],
                    )
                    score_value = scoring["propensity_score"]
                    st.markdown(
                        f"""
                        <div class="score-shell" role="progressbar"
                             aria-valuenow="{score_value}" aria-valuemin="0" aria-valuemax="100">
                          <div class="score-fill" style="width:{score_value}%"></div>
                        </div>
                        <div class="score-labels">
                          <span>TEMPRANO</span><span>NUTRICIÓN</span>
                          <span>MEDIA</span><span>ALTA</span>
                        </div>
                        <div class="ficha-sueno dream-card">
                          <h3>✦ Ficha del Sueño</h3>
                          <p>{html.escape(diagnosis)}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.caption(scoring["disclaimer"])
                    with st.expander("Desglose auditable del score"):
                        st.json(scoring)
                    with st.expander("Datos estructurados obtenidos por VIVI"):
                        st.json(profile)

                    # --- Agente 2: resultados del análisis de perfilamiento ---
                    # Botón explícito de actualización
                    if st.button(
                        "🔄 Actualizar análisis de perfilamiento",
                        key="agent2_refresh",
                        type="secondary",
                    ):
                        full_history = "\n".join(
                            f"{'VIVI' if item['role'] == 'assistant' else 'USUARIO'}: "
                            f"{item['content']}"
                            for item in st.session_state.instagram_messages
                        )
                        with st.spinner("Ejecutando análisis del Agente 2…"):
                            try:
                                fresh = analyze_profile(
                                    lead_id=st.session_state.last_result["lead_code"],
                                    channel="instagram_simulado",
                                    customer_name=profile.get("customer_name", ""),
                                    project_origin=profile.get("project_origin", ""),
                                    campaign_id=profile.get("campaign_id", ""),
                                    history=full_history,
                                    profile=profile,
                                    force=True,
                                )
                                st.session_state.instagram_agent2_result = fresh
                                current_turn = max(
                                    len(st.session_state.instagram_messages) // 2, 0
                                )
                                st.session_state.instagram_last_agent2_turn = current_turn
                                st.rerun()
                            except RuntimeError as exc:
                                st.error(f"Agente 2 falló: {exc}")

                    agent2 = st.session_state.instagram_agent2_result
                    if agent2 and agent2.get("ok"):
                        a2_scoring = agent2.get("scoring", {})
                        a2_profile = agent2.get("profile", {})
                        a2_missing = a2_scoring.get("missing_fields", [])
                        a2_action = a2_scoring.get("recommended_action", "")
                        filled_count = sum(
                            1 for k in EXTRACTABLE_FIELDS
                            if a2_profile.get(k) not in (None, "", [], {})
                        )
                        st.markdown("<div class='agent2-divider'></div>", unsafe_allow_html=True)
                        st.markdown(
                            f"""
                            <div class="agent2-card">
                              <div class="agent2-header">
                                <span class="agent2-icon">◇</span>
                                <span class="agent2-title">Agente 2 · Analista de Perfilamiento</span>
                              </div>
                              <div class="agent2-body">
                                <div class="agent2-metrics">
                                  <div class="agent2-metric">
                                    <span class="agent2-metric-value">{a2_scoring.get("propensity_score", "—")}/100</span>
                                    <span class="agent2-metric-label">Score VIVI</span>
                                  </div>
                                  <div class="agent2-metric">
                                    <span class="agent2-metric-value">{a2_scoring.get("priority", "—")}</span>
                                    <span class="agent2-metric-label">Prioridad</span>
                                  </div>
                                  <div class="agent2-metric">
                                    <span class="agent2-metric-value">{filled_count}/16</span>
                                    <span class="agent2-metric-label">Campos extraídos</span>
                                  </div>
                                  <div class="agent2-metric">
                                    <span class="agent2-metric-value">{agent2.get("gemini_source", "—")}</span>
                                    <span class="agent2-metric-label">Fuente</span>
                                  </div>
                                  <div class="agent2-metric">
                                    <span class="agent2-metric-value">{html.escape(a2_scoring.get("route", "—"))}</span>
                                    <span class="agent2-metric-label">Ruta</span>
                                  </div>
                                  <div class="agent2-metric">
                                    <span class="agent2-metric-value">{html.escape(str(agent2.get("crm_status", "—")))}</span>
                                    <span class="agent2-metric-label">CRM</span>
                                  </div>
                                </div>
                                <div class="agent2-recommended">
                                  <strong>Acción recomendada:</strong> {html.escape(a2_action)}
                                </div>
                                <div class="agent2-diagnosis">
                                  <strong>Ficha del Sueño:</strong> {html.escape(agent2.get("diagnosis", ""))}
                                </div>
                              </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if a2_missing:
                            pills = " ".join(
                                f'<span class="agent2-pill">{html.escape(m)}</span>'
                                for m in a2_missing
                            )
                            st.markdown(
                                f'<div class="agent2-missing"><strong>Campos faltantes:</strong> {pills}</div>',
                                unsafe_allow_html=True,
                            )
                        # Estado de persistencia (independiente del CRM)
                        _storage = get_storage_status()
                        if _storage.get("cloud_enabled"):
                            _persist_text = "SUPABASE + SQLITE"
                            _persist_class = "persistence-ok"
                        else:
                            _persist_text = "SOLO SQLITE"
                            _persist_class = "persistence-local"
                        _last = st.session_state.last_result
                        if _last and _last.get("storage_warning"):
                            _persist_text = "ERROR DE SINCRONIZACIÓN"
                            _persist_class = "persistence-error"
                        st.markdown(
                            f"""
                            <div class="agent2-persistence">
                              <strong>Persistencia:</strong>
                              <span class="persistence-badge {_persist_class}">{html.escape(_persist_text)}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        if agent2.get("schema_errors"):
                            st.warning(f"Errores de validación del schema: {'; '.join(agent2['schema_errors'])}")
                        with st.expander("Ver desglose auditable del score"):
                            st.json(a2_scoring)
                        with st.expander("Perfil completo extraído por Agente 2"):
                            st.json(a2_profile)
                    elif agent2 and agent2.get("ok") is False:
                        st.info("Agente 2 no disponible en este momento (Gemini no respondió).")


elif section == "Catálogo de proyectos":
    catalog = get_catalog()
    st.subheader("Portafolio identificado en la base anonimizada")
    st.caption(
        f"{len(catalog)} proyectos encontrados en 4.142 registros. "
        "Los indicadores de esta vista describen compradores históricos; no sustituyen "
        "los precios ni la disponibilidad comercial vigente."
    )
    if not catalog:
        st.warning("No se encontró el archivo tableConvert.com_x950qq.json.")
    else:
        selected_name = st.selectbox(
            "Selecciona un proyecto",
            [project["name"] for project in catalog],
        )
        project = next(item for item in catalog if item["name"] == selected_name)

        metrics = st.columns(5)
        metrics[0].metric("Registros", f"{project['records']:,}".replace(",", "."))
        metrics[1].metric("Etapas", len(project["stages"]))
        metrics[2].metric(
            "Valor mediano estimado",
            (
                f"${project['estimated_price_median']:,.0f}".replace(",", ".")
                if project["estimated_price_median"]
                else "Sin dato"
            ),
        )
        metrics[3].metric("Desistimientos", project["desistments"])
        metrics[4].metric("Tasa desistimiento", f"{project['desistment_rate']:.1f}%")

        st.info(
            "El valor monetario es una inferencia analítica: el campo exportado contiene "
            "cuatro ceros adicionales y fue dividido por 10.000. Debe confirmarse contra "
            "el brochure vigente antes de mostrarse como precio comercial."
        )

        left, right = st.columns(2, gap="large")
        with left:
            st.markdown("#### Cobertura del dataset")
            st.write(f"**Etapas:** {', '.join(project['stages']) or 'Sin dato'}")
            st.write(
                f"**Opciones registradas:** {project['first_option'] or 'Sin dato'} "
                f"a {project['last_option'] or 'Sin dato'}"
            )
            st.write(
                "**Rango estimado de valores:** "
                + (
                    (
                        f"${project['estimated_price_min']:,.0f} – "
                        f"${project['estimated_price_max']:,.0f}"
                    ).replace(",", ".")
                    if project["estimated_price_min"]
                    else "Sin dato"
                )
            )
        with right:
            st.markdown("#### Perfil agregado")
            st.write(
                "**Edades predominantes:** "
                + ", ".join(
                    f"{item['label']} ({item['count']})" for item in project["age_ranges"]
                )
            )
            st.write(
                "**Canales principales:** "
                + ", ".join(
                    f"{item['label']} ({item['count']})" for item in project["channels"]
                )
            )
            st.write(
                "**Entidades financieras:** "
                + ", ".join(
                    f"{item['label']} ({item['count']})"
                    for item in project["financial_entities"]
                )
            )

        table = pd.DataFrame(
            [
                {
                    "Proyecto": item["name"],
                    "Registros": item["records"],
                    "Etapas": len(item["stages"]),
                    "Primera opción": item["first_option"],
                    "Última opción": item["last_option"],
                    "Desistimiento %": item["desistment_rate"],
                }
                for item in catalog
            ]
        )
        table = table.fillna("—").replace({"": "—", "None": "—"})
        st.subheader("Inventario completo")
        st.dataframe(
            table,
            width="stretch",
            hide_index=True,
            column_config={
                "Registros": st.column_config.NumberColumn(format="localized"),
                "Desistimiento %": st.column_config.ProgressColumn(
                    "Desistimiento", min_value=0, max_value=100, format="%.1f%%"
                ),
            },
        )

elif section == "Centro de operaciones":
    metrics = get_dashboard_metrics()
    cols = st.columns(5)
    cols[0].metric("Leads", metrics["total"])
    cols[1].metric("Prioridad alta", metrics["hot"])
    cols[2].metric("% prioridad alta", f"{metrics['conversion_rate']:.1f}%")
    cols[3].metric("Duplicados", metrics["duplicates"])
    cols[4].metric("CRM pendientes", metrics["crm_pending"])

    # Estado de persistencia global
    _op_storage = get_storage_status()
    if _op_storage.get("cloud_enabled"):
        _op_persist_text = "SUPABASE + SQLITE"
        _op_persist_class = "persistence-ok"
    else:
        _op_persist_text = "SOLO SQLITE"
        _op_persist_class = "persistence-local"
    st.markdown(
        f"""
        <div class="agent2-persistence">
          <strong>Persistencia:</strong>
          <span class="persistence-badge {_op_persist_class}">{html.escape(_op_persist_text)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Bandeja comercial")
    leads = list_leads()
    if leads:
        df = pd.DataFrame(leads)
        # Derivar ruta comercial desde propensity_score (determinístico, misma lógica que profiling_service)
        def _derive_route(ps: float | None) -> str:
            if ps is None or ps < 30:
                return "NUTRICIÓN_DIGITAL"
            if ps < 55:
                return "PERTENECER"
            if ps < 80:
                return "COMPLETAR_PERFIL"
            return "ASESOR_COMERCIAL"

        df["propensity_route"] = df["propensity_score"].apply(
            lambda v: _derive_route(v) if pd.notna(v) else "—"
        )
        # Score VIVI: usar propensity_score si existe, si no el score inicial
        df["vivi_score"] = df["propensity_score"].fillna(df["score"]).astype(int)
        df["vivi_priority"] = df["propensity_priority"].fillna(df["rating"])

        display_columns = {
            "lead_code": "Código",
            "full_name": "Nombre",
            "income_range": "Ingresos",
            "preferred_project": "Proyecto",
            "vivi_score": "Score VIVI",
            "vivi_priority": "Prioridad VIVI",
            "propensity_route": "Ruta",
            "crm_status": "CRM",
            "utm_source": "Fuente",
            "purchase_horizon": "Horizonte",
            "created_at": "Capturado",
        }
        commercial_df = (
            df[list(display_columns)]
            .rename(columns=display_columns)
            .fillna("—")
            .replace({"": "—", "None": "—"})
        )
        st.dataframe(
            commercial_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Score VIVI": st.column_config.ProgressColumn(
                    "Score VIVI", min_value=0, max_value=100, format="%d/100"
                ),
                "Código": st.column_config.TextColumn(width="small"),
                "Nombre": st.column_config.TextColumn(width="medium"),
                "Proyecto": st.column_config.TextColumn(width="medium"),
                "Ruta": st.column_config.TextColumn(width="medium"),
            },
        )
        pending = [lead for lead in leads if lead["crm_status"] != "SYNCED"]
        if pending and st.button("Reintentar sincronizaciones pendientes"):
            synced = retry_crm_sync()
            st.success(f"{synced} registro(s) sincronizado(s).")
            st.rerun()

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar leads en CSV", csv, "meta_leads_capture.csv", "text/csv")

        st.subheader("Seguimiento simulado en Salesforce")
        stage_columns = st.columns(2)
        selected_lead = stage_columns[0].selectbox(
            "Lead",
            [lead["lead_code"] for lead in leads],
        )
        selected_stage = stage_columns[1].selectbox(
            "Nueva etapa",
            [
                "NUEVO",
                "CONTACTADO",
                "PERFILADO",
                "CITA_AGENDADA",
                "SEPARADO",
                "NUTRICIÓN",
                "DESCARTADO",
            ],
        )
        if st.button("Actualizar etapa comercial"):
            update_funnel_status(selected_lead, selected_stage)
            st.success(f"{selected_lead} actualizado a {selected_stage}.")
            st.rerun()

        st.subheader("Efectividad por campaña y fuente")
        performance = pd.DataFrame(get_campaign_performance())
        if not performance.empty:
            performance = performance.fillna("—").replace({"": "—", "None": "—"})
            st.dataframe(
                performance.rename(
                    columns={
                        "campaign_id": "Campaña",
                        "project": "Proyecto",
                        "source": "Fuente",
                        "records": "Registros",
                        "unique_people": "Personas únicas",
                        "duplicates": "Duplicados",
                        "high_priority": "Prioridad alta",
                        "separated": "Separaciones",
                        "conversion_rate": "Conversión %",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Conversión %": st.column_config.ProgressColumn(
                        "Conversión", min_value=0, max_value=100, format="%.1f%%"
                    )
                },
            )
    else:
        st.info("Aún no hay leads. Completa el formulario en la experiencia del cliente.")

    st.subheader("Trazabilidad técnica")
    events = list_events()
    if events:
        events_df = pd.DataFrame(events).fillna("—").replace({"": "—", "None": "—"})
        with st.expander("Ver eventos técnicos de integración"):
            st.dataframe(events_df, width="stretch", hide_index=True)

else:
    st.subheader("Arquitectura funcional")
    st.code(
        """
META ADS / INSTAGRAM · Proyecto de vivienda
        │ CTA
        ▼
META LEAD FORM
        │ POST JSON · 1.5 s
        ▼
VALIDACIÓN + NORMALIZACIÓN + PERFILAMIENTO EXPLICABLE
        │ INSERT INTO
        ▼
SQLite: META_LEADS_CAPTURE  ⇄  SAP HANA Cloud (gemelo digital)
        │ payload mapeado
        ▼
Salesforce Lead API / AppExchange / Make / Zapier
        """.strip(),
        language=None,
    )
    st.subheader("Ejemplo de webhook")
    sample = {
        "full_name": "Laura Martínez",
        "id_type": "Cédula de ciudadanía",
        "id_number": "1012345678",
        "income_range": "Entre 2 y 4 SMMLV",
        "affiliation_type": "Afiliado como trabajador",
        "affiliated": True,
        "negative_report": False,
        "purchase_horizon": "En los próximos 6 meses",
        "savings_range": "Entre $3 y $10 millones",
        "preferred_project": "Samán · VIS · Ricaurte",
        "bedrooms": 2,
        "source": "META_ADS",
        "campaign": "VIVIENDA_SAMAN_VIS",
    }
    st.code(json.dumps(sample, ensure_ascii=False, indent=2), language="json")
    st.caption(
        "El reto simula las integraciones: no consulta DataCrédito, cuentas bancarias ni aprueba "
        "créditos. En producción se requerirían OAuth 2.0, cifrado de secretos, consentimiento "
        "versionado, reintentos y monitoreo centralizado."
    )
