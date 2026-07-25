from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from catalog_service import load_catalog
from campaign_service import PLACEMENTS, build_attribution
from finance_service import SMMLV_2026, income_range_for
from lead_service import (
    DB_PATH,
    capture_lead,
    get_campaign_performance,
    get_dashboard_metrics,
    init_db,
    list_events,
    list_leads,
    retry_crm_sync,
    update_funnel_status,
)


st.set_page_config(
    page_title="Colsubsidio | Captura inteligente de leads",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { --col-blue:#0067b1; --col-yellow:#ffd000; --graphite:#575756; }
    .stApp { background: #f4f7fb; color: #253443; }
    [data-testid="stSidebar"] { background: #062b48; }
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
        padding: 1.6rem 1.8rem; border-radius: 20px;
        background: linear-gradient(120deg,#003d6b 0%,#0067b1 65%,#0789df 100%);
        color:white; box-shadow:0 12px 35px rgba(0,73,126,.18); margin-bottom:1rem;
    }
    .hero h1 { margin:0; font-size:2.15rem; color:white; }
    .hero p { opacity:.9; margin:.55rem 0 0; }
    .ad-card {
        background:white; border-radius:22px; overflow:hidden;
        border:1px solid #e4eaf0; box-shadow:0 12px 35px rgba(25,53,76,.10);
        color:#253443;
    }
    .ad-head { padding:1rem 1.2rem; display:flex; gap:.75rem; align-items:center; }
    .ad-logo {
        width:44px;height:44px;border-radius:50%;background:#ffd000;color:#004d85;
        display:grid;place-items:center;font-weight:900;font-size:1.2rem;
    }
    .ad-visual {
        min-height:260px;padding:2.1rem;
        background:linear-gradient(145deg,#0067b1,#00375f);color:white;
        display:flex;flex-direction:column;justify-content:center;
    }
    .ad-visual h2 { color:white;font-size:2rem;line-height:1.05;margin:.5rem 0; }
    .pill { display:inline-block;width:max-content;background:#ffd000;color:#17212b;
        padding:.35rem .7rem;border-radius:99px;font-weight:800;font-size:.8rem; }
    .stage {
        padding:.6rem .8rem;border-radius:12px;background:white;border:1px solid #e2e8ef;
        text-align:center;font-weight:700;color:#506273;
    }
    .stage.active { background:#e7f4ff;border-color:#0067b1;color:#0067b1; }
    .score-card { border-radius:18px;padding:1.1rem 1.25rem;background:white;
        border-left:6px solid #0067b1;box-shadow:0 6px 18px rgba(0,0,0,.06);
        color:#253443; }
    div[data-testid="stMetric"] { background:white;border:1px solid #e6ebf0;
        border-radius:16px;padding:1rem;color:#253443; }
    div[data-testid="stMetric"] * { color:#253443; }
    .small-muted { color:#708090;font-size:.86rem; }
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

if "show_form" not in st.session_state:
    st.session_state.show_form = False
if "last_result" not in st.session_state:
    st.session_state.last_result = None

with st.sidebar:
    st.markdown("## 30X · LeadFlow")
    st.caption("Prototipo de arquitectura financiera")
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
    st.caption("Persistencia local")
    st.code(str(DB_PATH), language=None)

st.markdown(
    """
    <div class="hero">
      <h1>Visionario ViviendAI</h1>
      <p>Convertimos un clic en una conversación sobre tu sueño de vivienda, con perfilamiento humano y trazable.</p>
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
    stages = st.columns(4)
    labels = ["1 · Anuncio", "2 · Formulario", "3 · HANA / SQLite", "4 · Salesforce"]
    active = 1 if st.session_state.show_form else 0
    for index, (column, label) in enumerate(zip(stages, labels)):
        css = "stage active" if index <= active else "stage"
        column.markdown(f'<div class="{css}">{label}</div>', unsafe_allow_html=True)

    left, right = st.columns([1.05, 1], gap="large")
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
        if st.button("Registrarte", type="primary", use_container_width=True):
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
            with st.form("meta_lead_form", clear_on_submit=False):
                full_name = st.text_input("Nombre y apellido *", placeholder="Ej. Laura Martínez")
                id_type = st.selectbox(
                    "Tipo de documento *",
                    ["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte"],
                )
                id_number = st.text_input("Número de documento *", placeholder="Sin puntos ni espacios")
                income_monthly = st.number_input(
                    "¿Cuánto suman los ingresos mensuales de tu hogar? *",
                    min_value=0,
                    max_value=50_000_000,
                    value=2_500_000,
                    step=100_000,
                    format="%d",
                    help=f"SMMLV 2026 usado por la simulación: ${SMMLV_2026:,.0f}.",
                )
                income_range = income_range_for(income_monthly)
                st.caption(f"Rango calculado automáticamente: **{income_range}**")
                affiliation_type = st.selectbox(
                    "¿Cuál es tu tipo de afiliación a Colsubsidio? *",
                    ["Afiliado como trabajador", "Beneficiario", "No afiliado"],
                )
                purchase_horizon = st.selectbox(
                    "¿Cuándo te gustaría comprar vivienda?",
                    [
                        "En los próximos 6 meses",
                        "Entre 6 y 12 meses",
                        "En más de 12 meses",
                        "Estoy explorando",
                    ],
                )
                savings_range = st.selectbox(
                    "¿Con qué ahorro cuentas hoy? (declarado por ti)",
                    [
                        "Prefiero no responder",
                        "Aún no tengo ahorro",
                        "Menos de $3 millones",
                        "Entre $3 y $10 millones",
                        "Más de $10 millones",
                    ],
                    help="No consultamos cuentas bancarias. Esta respuesta es voluntaria y orientativa.",
                )
                preferred_project = campaign_project
                st.info(f"Llegaste por la campaña de **{preferred_project}**; no te lo preguntaremos otra vez.")
                bedrooms = st.slider("¿Cuántas habitaciones necesitas?", 1, 4, 2)
                consent = st.checkbox("Autorizo el tratamiento de mis datos personales.")
                submitted = st.form_submit_button("Enviar solicitud", type="primary", use_container_width=True)

            if submitted:
                if not full_name.strip():
                    st.error("El nombre y apellido son obligatorios.")
                elif len(full_name.strip().split()) < 2:
                    st.error("Ingresa al menos un nombre y un apellido.")
                elif not id_number.strip().isalnum() or len(id_number.strip()) < 5:
                    st.error("Ingresa un número de documento válido.")
                elif not consent:
                    st.error("Debes autorizar el tratamiento de datos para continuar.")
                else:
                    payload = {
                        "full_name": full_name,
                        "id_type": id_type,
                        "id_number": id_number.strip(),
                        "income_monthly": income_monthly,
                        "income_range": income_range,
                        "affiliation_type": affiliation_type,
                        "affiliated": affiliation_type != "No afiliado",
                        "negative_report": False,
                        "purchase_horizon": purchase_horizon,
                        "savings_range": savings_range,
                        "preferred_project": preferred_project,
                        "bedrooms": bedrooms,
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
                      <b>Prioridad comercial: {display_rating}</b> · {result["score"]}/100<br>
                      <span class="small-muted">{result["recommendation"]}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.caption(
                    "CRM: "
                    + ("sincronizado correctamente" if result["crm_status"] == "SYNCED" else "pendiente de reintento")
                )
                st.info(
                    "Esta prioridad orienta la atención comercial. No equivale a aprobación "
                    "de crédito ni asignación de subsidio."
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
        st.subheader("Inventario completo")
        st.dataframe(table, use_container_width=True, hide_index=True)

elif section == "Centro de operaciones":
    metrics = get_dashboard_metrics()
    cols = st.columns(5)
    cols[0].metric("Leads", metrics["total"])
    cols[1].metric("Prioridad alta", metrics["hot"])
    cols[2].metric("% prioridad alta", f"{metrics['conversion_rate']:.1f}%")
    cols[3].metric("Duplicados", metrics["duplicates"])
    cols[4].metric("CRM pendientes", metrics["crm_pending"])

    st.subheader("Bandeja comercial")
    leads = list_leads()
    if leads:
        df = pd.DataFrame(leads)
        display_columns = {
            "lead_code": "Código",
            "meta_lead_id": "ID origen",
            "full_name": "Nombre",
            "income_range": "Ingresos",
            "affiliation_type": "Afiliación",
            "preferred_project": "Proyecto",
            "utm_source": "Fuente",
            "campaign_id": "Campaña",
            "purchase_horizon": "Horizonte",
            "score": "Puntaje",
            "rating": "Prioridad",
            "crm_status": "Salesforce",
            "funnel_status": "Etapa CRM",
            "created_at": "Capturado",
        }
        st.dataframe(
            df[list(display_columns)].rename(columns=display_columns),
            use_container_width=True,
            hide_index=True,
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
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("Aún no hay leads. Completa el formulario en la experiencia del cliente.")

    st.subheader("Trazabilidad técnica")
    events = list_events()
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)

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
