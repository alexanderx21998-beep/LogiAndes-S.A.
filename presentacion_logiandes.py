from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "logiandes.csv"


st.set_page_config(
    page_title="LogiAndes | Presentación logística", 
    page_icon="LA",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1320px;
    }
    div[data-testid="stMetric"] {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 12px 14px;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12);
    }
    div[data-testid="stMetricLabel"] p {
        color: #cbd5e1 !important;
        font-size: 0.85rem;
    }
    div[data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
    div[data-testid="stMetricValue"] div {
        color: #ffffff !important;
    }
    div[data-testid="stMetricDelta"] {
        color: #67e8f9 !important;
    }
    .section-note {
        border-left: 4px solid #0f766e;
        padding: 0.75rem 1rem;
        background: #f8fafc;
        color: #1f2937;
        margin: 0.5rem 0 1rem 0;
    }
    .case-box {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1rem;
        background: #ffffff;
        min-height: 158px;
    }
    .case-title {
        font-weight: 700;
        color: #111827;
        margin-bottom: .35rem;
    }
    .case-detail {
        color: #475569;
        font-size: .94rem;
        line-height: 1.45;
    }
    .audience-card {
        border: 1px solid #dbeafe;
        border-radius: 8px;
        padding: 0.85rem;
        background: #eff6ff;
        min-height: 135px;
    }
    .audience-title {
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: .25rem;
    }
    .kpi-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.85rem;
        background: #ffffff;
        min-height: 210px;
    }
    .kpi-name {
        font-weight: 700;
        color: #0f172a;
        margin-bottom: .35rem;
    }
    .kpi-line {
        color: #475569;
        font-size: .90rem;
        line-height: 1.38;
    }
</style>
"""


@st.cache_data
def cargar_datos(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["fecha_pedido"] = pd.to_datetime(df["fecha_pedido"], errors="coerce")

    reemplazos = {
        "Est�ndar urbano": "Estándar urbano", 
        "Estándar urbano": "Estándar urbano", 
        "Manab�": "Manabí",
        "Manabí": "Manabí", 
    }
    for columna in ["provincia", "region", "canal_entrega", "tipo_cliente", "motivo_reclamo"]:
        df[columna] = df[columna].replace(reemplazos)

    df["motivo_reclamo"] = df["motivo_reclamo"].fillna("Sin reclamo")
    df["fecha"] = df["fecha_pedido"].dt.date
    df["hora"] = df["fecha_pedido"].dt.hour
    df["dia_semana"] = df["fecha_pedido"].dt.day_name()
    df["mes"] = df["fecha_pedido"].dt.to_period("M").astype(str)
    df["ciclo_total_min"] = df["tiempo_atencion_min"] + df["tiempo_individual_entrega_min"]
    df["entrega_horas"] = df["tiempo_individual_entrega_min"] / 60
    df["venta_por_km"] = df["ventas_asociadas_usd"] / df["distancia_km"].replace(0, pd.NA)
    df["tuvo_reclamo"] = df["reclamos_registrados"].gt(0)
    return df


def formato_usd(valor: float) -> str:
    return f"${valor:,.0f}"


def formato_pct(valor: float) -> str:
    return f"{valor:.1%}"


def resumen(df: pd.DataFrame, sla_min: float) -> dict[str, float]:
    pedidos = len(df)
    reclamos = int(df["reclamos_registrados"].sum())
    return {
        "pedidos": pedidos,
        "ventas": float(df["ventas_asociadas_usd"].sum()),
        "entrega_prom": float(df["tiempo_individual_entrega_min"].mean()),
        "entrega_p90": float(df["tiempo_individual_entrega_min"].quantile(0.90)),
        "reclamos": reclamos,
        "tasa_reclamos": reclamos / pedidos if pedidos else 0,
        "fuera_sla": float(df["tiempo_individual_entrega_min"].gt(sla_min).mean()) if pedidos else 0,
        "distancia_prom": float(df["distancia_km"].mean()),
    }


def tabla_resumen(df: pd.DataFrame, columnas: list[str], sla_min: float) -> pd.DataFrame:
    tabla = (
        df.groupby(columnas, dropna=False)
        .agg(
            pedidos=("pedido_id", "count"),
            ventas_usd=("ventas_asociadas_usd", "sum"),
            entrega_prom_min=("tiempo_individual_entrega_min", "mean"),
            entrega_p90_min=("tiempo_individual_entrega_min", lambda s: s.quantile(0.90)),
            reclamos=("reclamos_registrados", "sum"),
            distancia_prom_km=("distancia_km", "mean"),
        )
        .reset_index()
    )
    tabla["tasa_reclamos"] = tabla["reclamos"] / tabla["pedidos"]
    tabla["fuera_sla_estimado"] = (
        df.assign(fuera_sla=df["tiempo_individual_entrega_min"].gt(sla_min))
        .groupby(columnas, dropna=False)["fuera_sla"]
        .mean()
        .to_numpy()
    )
    return tabla.sort_values(["fuera_sla_estimado", "entrega_p90_min"], ascending=False)


def grafico_barras(
    data: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    titulo: str = "",
    formato_y: str | None = None,
) -> alt.Chart:
    y_axis = alt.Y(f"{y}:Q", title=None)
    if formato_y:
        y_axis = alt.Y(f"{y}:Q", title=None, axis=alt.Axis(format=formato_y))
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X(f"{x}:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-25)),
            y=y_axis,
            tooltip=[
                alt.Tooltip(f"{x}:N", title=x.replace("_", " ").title()),
                alt.Tooltip(f"{y}:Q", title=y.replace("_", " ").title(), format=".2f"),
            ],
        )
        .properties(height=330, title=titulo)
    )
    if color:
        chart = chart.encode(color=alt.Color(f"{color}:N", title=None))
    else:
        chart = chart.encode(color=alt.value("#0f766e"))
    return chart


def grafico_linea(data: pd.DataFrame, x: str, y: str, color: str, titulo: str) -> alt.Chart:
    return (
        alt.Chart(data)
        .mark_line(point=True)
        .encode(
            x=alt.X(f"{x}:N", title=None),
            y=alt.Y(f"{y}:Q", title=None),
            color=alt.Color(f"{color}:N", title=None),
            tooltip=[
                alt.Tooltip(f"{x}:N", title=x.replace("_", " ").title()),
                alt.Tooltip(f"{color}:N", title=color.replace("_", " ").title()),
                alt.Tooltip(f"{y}:Q", title=y.replace("_", " ").title(), format=".2f"),
            ],
        )
        .properties(height=330, title=titulo)
    )


def render_metricas(df: pd.DataFrame, sla_min: float) -> None:
    kpis = resumen(df, sla_min)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pedidos", f"{kpis['pedidos']:,}")
    c2.metric("Ventas asociadas", formato_usd(kpis["ventas"]))
    c3.metric("Entrega promedio", f"{kpis['entrega_prom']:.1f} min")
    c4.metric("P90 entrega", f"{kpis['entrega_p90']:.1f} min")
    c5.metric("Fuera de SLA", formato_pct(kpis["fuera_sla"]))


def render_audiencias() -> None:
    st.subheader("Audiencias y decisiones que soporta")
    audiencias = [
        (
            "Gerencia general",
            "Controlar servicio, volumen, riesgo de SLA y focos de mejora por territorio.",
        ),
        (
            "Operaciones",
            "Detectar cuellos de botella por canal, provincia, distancia y pedidos criticos.",
        ),
        (
            "Comercial",
            "Evaluar impacto de promesas de entrega sobre experiencia y ventas asociadas.",
        ),
        (
            "Finanzas",
            "Priorizar zonas donde la friccion logistica afecta pedidos de mayor valor.",
        ),
        (
            "Atencion al cliente",
            "Ubicar reclamos, motivos frecuentes y pedidos que requieren gestion inmediata.",
        ),
    ]
    cols = st.columns(5)
    for col, (titulo, detalle) in zip(cols, audiencias):
        with col:
            st.markdown(
                f'<div class="audience-card"><div class="audience-title">{titulo}</div>'
                f'<div class="case-detail">{detalle}</div></div>',
                unsafe_allow_html=True,
            )


def fichas_kpi(sla_min: float) -> list[dict[str, str]]:
    return [
        {
            "Nombre": "Cumplimiento de SLA",
            "Objetivo": "Medir la proporción de pedidos entregados dentro del tiempo objetivo.",
            "Formula": f"Pedidos con entrega <= {sla_min:.0f} min / total de pedidos",
            "Fuente": "logiandes.csv: tiempo_individual_entrega_min, pedido_id",
            "Frecuencia": "Diaria / semanal",
            "Meta": ">= 85%",
            "Umbral": "< 75% requiere revisión operativa",
            "Interpretacion": "Valores bajos senalan saturación, promesa comercial agresiva o problemas de ruta.", 
        },
        {
            "Nombre": "P90 de tiempo de entrega",
            "Objetivo": "Controlar la experiencia de los pedidos mas lentos.",
            "Formula": "Percentil 90 de tiempo_individual_entrega_min",
            "Fuente": "logiandes.csv: tiempo_individual_entrega_min",
            "Frecuencia": "Diaria / semanal",
            "Meta": "<= 190 min",
            "Umbral": "> 210 min implica foco crítico", 
            "Interpretacion": "Resume la cola de demoras mejor que el promedio cuando hay casos extremos.",
        },
        {
            "Nombre": "Tasa de reclamos",
            "Objetivo": "Medir fricción de servicio percibida por el cliente.", 
            "Formula": "Pedidos con reclamo / total de pedidos",
            "Fuente": "logiandes.csv: reclamos_registrados, motivo_reclamo",
            "Frecuencia": "Semanal",
            "Meta": "<= 3%",
            "Umbral": "> 5% requiere acción correctiva",
            "Interpretacion": "Ayuda a priorizar causas como demora, dirección, producto o atención.",
        },
        {
            "Nombre": "Distancia promedio por pedido",
            "Objetivo": "Entender complejidad física de la red logística.", 
            "Formula": "Promedio de distancia_km",
            "Fuente": "logiandes.csv: distancia_km",
            "Frecuencia": "Semanal / mensual",
            "Meta": "Monitoreo por provincia y canal",
            "Umbral": "Aumentos con mayor tiempo de entrega deben investigarse",
            "Interpretacion": "Permite separar demoras por cobertura geografica de demoras por gestion interna.",
        },
        {
            "Nombre": "Ventas en riesgo logístico",
            "Objetivo": "Cuantificar valor comercial expuesto a demoras o reclamos.",
            "Formula": "Suma de ventas_asociadas_usd en pedidos fuera de SLA o con reclamo",
            "Fuente": "logiandes.csv: ventas_asociadas_usd, reclamos_registrados, tiempo_individual_entrega_min",
            "Frecuencia": "Semanal / mensual",
            "Meta": "Reducir tendencia",
            "Umbral": "Crecimiento sostenido frente al periodo anterior",
            "Interpretacion": "Conecta decisiones logísticas con impacto comercial y financiero.",
        },
    ]


def estado_kpis(df: pd.DataFrame, sla_min: float) -> pd.DataFrame:
    kpis = resumen(df, sla_min)
    ventas_riesgo = df.loc[
        df["tiempo_individual_entrega_min"].gt(sla_min) | df["tuvo_reclamo"],
        "ventas_asociadas_usd",
    ].sum()
    cumplimiento_sla = 1 - kpis["fuera_sla"]
    return pd.DataFrame(
        [
            {
                "KPI": "Cumplimiento de SLA",
                "Valor actual": formato_pct(cumplimiento_sla),
                "Meta": ">= 85%",
                "Estado": "En meta" if cumplimiento_sla >= 0.85 else "Revisar",
                "Lectura": "Mide pedidos entregados dentro del tiempo objetivo.",
            },
            {
                "KPI": "P90 de tiempo de entrega",
                "Valor actual": f"{kpis['entrega_p90']:.1f} min",
                "Meta": "<= 190 min",
                "Estado": "En meta" if kpis["entrega_p90"] <= 190 else "Revisar",
                "Lectura": "Controla la cola de pedidos mas lentos.",
            },
            {
                "KPI": "Tasa de reclamos",
                "Valor actual": formato_pct(kpis["tasa_reclamos"]),
                "Meta": "<= 3%",
                "Estado": "En meta" if kpis["tasa_reclamos"] <= 0.03 else "Revisar",
                "Lectura": "Mide fricción percibida por el cliente.",
            },
            {
                "KPI": "Distancia promedio por pedido",
                "Valor actual": f"{kpis['distancia_prom']:.1f} km",
                "Meta": "Monitoreo",
                "Estado": "Controlar por territorio",
                "Lectura": "Ayuda a entender complejidad fisica de cobertura.",
            },
            {
                "KPI": "Ventas en riesgo logístico", 
                "Valor actual": formato_usd(float(ventas_riesgo)),
                "Meta": "Reducir tendencia",
                "Estado": "Priorizar" if ventas_riesgo > 0 else "Sin riesgo",
                "Lectura": "Cuantifica valor asociado a demoras o reclamos.",
            },
        ]
    )


def pagina_resumen(df: pd.DataFrame, sla_min: float) -> None:
    st.title("Vista ejecutiva")
    st.markdown(
        '<div class="section-note">Problema empresarial: LogiAndes necesita monitorear servicio, reclamos, '
        "territorios y valor comercial expuesto para tomar decisiones logisticas con datos.</div>",
        unsafe_allow_html=True,
    )
    render_metricas(df, sla_min)
    render_audiencias()

    st.subheader("Diagnóstico rapido")
    por_canal = tabla_resumen(df, ["canal_entrega"], sla_min)
    por_provincia = tabla_resumen(df, ["provincia"], sla_min)
    col1, col2 = st.columns(2)
    with col1:
        st.altair_chart(
            grafico_barras(
                por_canal,
                "canal_entrega",
                "entrega_p90_min",
                titulo="P90 de entrega por canal",
            ),
            use_container_width=True,
        )
    with col2:
        st.altair_chart(
            grafico_barras(
                por_provincia.head(6),
                "provincia",
                "fuera_sla_estimado",
                titulo="Porcentaje estimado fuera de SLA por provincia",
                formato_y=".0%",
            ),
            use_container_width=True,
        )

    peor_canal = por_canal.iloc[0]
    peor_provincia = por_provincia.iloc[0]
    st.info(
        f"Foco sugerido: revisar {peor_canal['canal_entrega']} y {peor_provincia['provincia']}, "
        f"porque combinan mayor riesgo de demora con impacto directo en servicio."
    )

    diario = (
        df.groupby(["fecha", "canal_entrega"], dropna=False)
        .agg(entrega_prom_min=("tiempo_individual_entrega_min", "mean"))
        .reset_index()
    )
    diario["fecha"] = diario["fecha"].astype(str)
    st.altair_chart(
        grafico_linea(diario, "fecha", "entrega_prom_min", "canal_entrega", "Evolucion diaria del tiempo medio de entrega"),
        use_container_width=True,
    )


def pagina_territorial(df: pd.DataFrame, sla_min: float) -> None:
    st.title("Análisis territorial")
    st.caption("Comparación por region, provincia y canal para detectar donde se tensiona la red.")

    col1, col2 = st.columns(2)
    por_region_canal = tabla_resumen(df, ["region", "canal_entrega"], sla_min)
    with col1:
        st.altair_chart(
            grafico_barras(
                por_region_canal,
                "canal_entrega",
                "entrega_prom_min",
                "region",
                "Tiempo promedio por canal y región", 
            ),
            use_container_width=True,
        )
    with col2:
        dispersion = (
            df.groupby(["provincia", "canal_entrega"], dropna=False)
            .agg(
                pedidos=("pedido_id", "count"),
                distancia_prom_km=("distancia_km", "mean"),
                entrega_prom_min=("tiempo_individual_entrega_min", "mean"),
                ventas_usd=("ventas_asociadas_usd", "sum"),
            )
            .reset_index()
        )
        chart = (
            alt.Chart(dispersion)
            .mark_circle(opacity=0.78)
            .encode(
                x=alt.X("distancia_prom_km:Q", title="Distancia promedio km"),
                y=alt.Y("entrega_prom_min:Q", title="Entrega promedio min"),
                size=alt.Size("pedidos:Q", title="Pedidos"),
                color=alt.Color("canal_entrega:N", title="Canal"),
                tooltip=[
                    "provincia:N",
                    "canal_entrega:N",
                    alt.Tooltip("pedidos:Q", format=","),
                    alt.Tooltip("distancia_prom_km:Q", format=".1f"),
                    alt.Tooltip("entrega_prom_min:Q", format=".1f"),
                    alt.Tooltip("ventas_usd:Q", format="$,.0f"),
                ],
            )
            .properties(height=330, title="Relacion distancia-tiempo")
        )
        st.altair_chart(chart, use_container_width=True)

    st.subheader("Ranking territorial para priorización")
    por_provincia = tabla_resumen(df, ["region", "provincia"], sla_min)
    st.dataframe(
        por_provincia,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ventas_usd": st.column_config.NumberColumn("ventas_usd", format="$ %.0f"),
            "entrega_prom_min": st.column_config.NumberColumn("entrega_prom_min", format="%.1f"),
            "entrega_p90_min": st.column_config.NumberColumn("entrega_p90_min", format="%.1f"),
            "tasa_reclamos": st.column_config.ProgressColumn("tasa_reclamos", min_value=0, max_value=max(0.1, por_provincia["tasa_reclamos"].max())),
            "fuera_sla_estimado": st.column_config.ProgressColumn("fuera_sla_estimado", min_value=0, max_value=1),
        },
    )

    st.subheader("Segmentos con mayor riesgo operativo")
    riesgo = tabla_resumen(df, ["provincia", "canal_entrega", "tipo_cliente"], sla_min).head(12)
    st.dataframe(
        riesgo,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ventas_usd": st.column_config.NumberColumn("ventas_usd", format="$ %.0f"),
            "entrega_prom_min": st.column_config.NumberColumn("entrega_prom_min", format="%.1f"),
            "entrega_p90_min": st.column_config.NumberColumn("entrega_p90_min", format="%.1f"),
            "tasa_reclamos": st.column_config.ProgressColumn("tasa_reclamos", min_value=0, max_value=max(0.1, riesgo["tasa_reclamos"].max())),
            "fuera_sla_estimado": st.column_config.ProgressColumn("fuera_sla_estimado", min_value=0, max_value=1),
        },
    )


def pagina_reclamos(df: pd.DataFrame, sla_min: float) -> None:
    st.title("Reclamos y perdida de experiencia")
    reclamos = df[df["tuvo_reclamo"]].copy()
    col1, col2, col3 = st.columns(3)
    col1.metric("Pedidos con reclamo", f"{len(reclamos):,}")
    col2.metric("Tasa de reclamos", formato_pct(len(reclamos) / len(df) if len(df) else 0))
    col3.metric("Venta en pedidos reclamados", formato_usd(reclamos["ventas_asociadas_usd"].sum()))

    if reclamos.empty:
        st.success("No hay reclamos en el filtro actual.")
        return

    col1, col2 = st.columns(2)
    motivos = (
        reclamos.groupby("motivo_reclamo", dropna=False)
        .agg(reclamos=("pedido_id", "count"), entrega_prom_min=("tiempo_individual_entrega_min", "mean"))
        .reset_index()
        .sort_values("reclamos", ascending=False)
    )
    with col1:
        st.altair_chart(
            grafico_barras(motivos, "motivo_reclamo", "reclamos", titulo="Motivos mas frecuentes"),
            use_container_width=True,
        )
    with col2:
        por_prov = tabla_resumen(reclamos, ["provincia"], sla_min)
        st.altair_chart(
            grafico_barras(por_prov, "provincia", "entrega_prom_min", titulo="Tiempo medio de pedidos con reclamo"),
            use_container_width=True,
        )

    st.subheader("Lectura para accion")
    st.write(
        "Cuando el reclamo se concentra en demora, el primer frente es capacidad y promesa de entrega. "
        "Cuando aparece producto danado, dirección o atención, conviene revisar calidad de preparación, datos de despacho y traspasos entre equipos."
    )
    st.dataframe(
        reclamos.sort_values(["tiempo_individual_entrega_min", "ventas_asociadas_usd"], ascending=False).head(25),
        use_container_width=True,
        hide_index=True,
    )


def pagina_casos(df: pd.DataFrame, sla_min: float) -> None:
    st.title("Detalle operativo")
    st.caption("Pedidos y combinaciones de negocio que requieren acción operativa.")
    df = df.copy()
    df["fuera_sla"] = df["tiempo_individual_entrega_min"].gt(sla_min)

    casos = []
    demora = df.sort_values("tiempo_individual_entrega_min", ascending=False).iloc[0]
    casos.append(
        (
            "Caso 1: entrega extrema",
            f"Pedido {demora['pedido_id']} en {demora['provincia']} tardo {demora['tiempo_individual_entrega_min']:.1f} min. "
            f"Canal {demora['canal_entrega']}, distancia {demora['distancia_km']:.1f} km. "
            "Revisar ruteo, disponibilidad de flota y promesa al cliente.",
        )
    )
    reclamo_valor = df[df["tuvo_reclamo"]].sort_values("ventas_asociadas_usd", ascending=False)
    if not reclamo_valor.empty:
        pedido = reclamo_valor.iloc[0]
        casos.append(
            (
                "Caso 2: reclamo de alto valor",
                f"Pedido {pedido['pedido_id']} genero reclamo por {pedido['motivo_reclamo']} y tenia "
                f"{formato_usd(pedido['ventas_asociadas_usd'])} asociados. "
                "Priorizar retención y trazabilidad del incidente.",
            )
        )
    provincia_critica = tabla_resumen(df, ["provincia"], sla_min).iloc[0]
    casos.append(
        (
            "Caso 3: provincia con fricción", 
            f"{provincia_critica['provincia']} muestra {formato_pct(provincia_critica['fuera_sla_estimado'])} de pedidos fuera de SLA "
            f"y P90 de {provincia_critica['entrega_p90_min']:.1f} min. "
            "Evaluar microzonas, ventanas horarias y capacidad en picos.",
        )
    )
    canal_critico = tabla_resumen(df, ["canal_entrega"], sla_min).iloc[0]
    casos.append(
        (
            "Caso 4: canal con riesgo de promesa",
            f"{canal_critico['canal_entrega']} concentra {canal_critico['pedidos']:,} pedidos y "
            f"{formato_pct(canal_critico['fuera_sla_estimado'])} fuera de SLA. "
            "Ajustar promesa comercial o reforzar despacho en esa modalidad.",
        )
    )

    c1, c2 = st.columns(2)
    for indice, (titulo, detalle) in enumerate(casos):
        contenedor = c1 if indice % 2 == 0 else c2
        with contenedor:
            st.markdown(
                f'<div class="case-box"><div class="case-title">{titulo}</div>'
                f'<div class="case-detail">{detalle}</div></div>',
                unsafe_allow_html=True,
            )
            st.write("")

    st.subheader("Pedidos priorizados")
    priorizados = df.assign(
        score_riesgo=(
            df["fuera_sla"].astype(int) * 40
            + df["tuvo_reclamo"].astype(int) * 35
            + df["tiempo_individual_entrega_min"].rank(pct=True) * 15
            + df["ventas_asociadas_usd"].rank(pct=True) * 10
        )
    ).sort_values("score_riesgo", ascending=False)
    st.dataframe(
        priorizados[
            [
                "pedido_id",
                "fecha_pedido",
                "provincia",
                "region",
                "canal_entrega",
                "tipo_cliente",
                "tiempo_individual_entrega_min",
                "distancia_km",
                "reclamos_registrados",
                "motivo_reclamo",
                "ventas_asociadas_usd",
                "score_riesgo",
            ]
        ].head(30),
        hide_index=True,
        use_container_width=True,
        column_config={
            "ventas_asociadas_usd": st.column_config.NumberColumn("ventas_asociadas_usd", format="$ %.2f"),
            "score_riesgo": st.column_config.ProgressColumn("score_riesgo", min_value=0, max_value=100),
        },
    )


def pagina_simulador(df: pd.DataFrame, sla_min: float) -> None:
    st.title("Simulador de decisión: impacto de mejorar tiempos")
    st.caption("Explora que pasaria si se reduce el tiempo de entrega en segmentos especificos.")

    col1, col2, col3 = st.columns(3)
    provincia = col1.selectbox("Provincia", ["Todas"] + sorted(df["provincia"].dropna().unique().tolist()))
    canal = col2.selectbox("Canal", ["Todos"] + sorted(df["canal_entrega"].dropna().unique().tolist()))
    mejora = col3.slider("Reduccion estimada de tiempo", 0, 60, 15, 5, format="%d min")

    escenario = df.copy()
    mascara = pd.Series(True, index=escenario.index)
    if provincia != "Todas":
        mascara &= escenario["provincia"].eq(provincia)
    if canal != "Todos":
        mascara &= escenario["canal_entrega"].eq(canal)

    antes_fuera = escenario["tiempo_individual_entrega_min"].gt(sla_min).sum()
    escenario.loc[mascara, "tiempo_individual_entrega_min"] = (
        escenario.loc[mascara, "tiempo_individual_entrega_min"] - mejora
    ).clip(lower=0)
    despues_fuera = escenario["tiempo_individual_entrega_min"].gt(sla_min).sum()
    pedidos_afectados = int(mascara.sum())
    recuperados = int(antes_fuera - despues_fuera)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pedidos impactados", f"{pedidos_afectados:,}")
    m2.metric("Fuera de SLA antes", f"{antes_fuera:,}")
    m3.metric("Fuera de SLA despues", f"{despues_fuera:,}", delta=f"-{recuperados:,}")
    m4.metric("Mejora relativa", formato_pct(recuperados / antes_fuera if antes_fuera else 0))

    comparativo = pd.DataFrame(
        {
            "escenario": ["Actual", "Con mejora"],
            "entrega_prom_min": [
                df["tiempo_individual_entrega_min"].mean(),
                escenario["tiempo_individual_entrega_min"].mean(),
            ],
            "fuera_sla": [
                df["tiempo_individual_entrega_min"].gt(sla_min).mean(),
                escenario["tiempo_individual_entrega_min"].gt(sla_min).mean(),
            ],
        }
    )
    c1, c2 = st.columns(2)
    with c1:
        st.altair_chart(
            grafico_barras(comparativo, "escenario", "entrega_prom_min", titulo="Entrega promedio simulada"),
            use_container_width=True,
        )
    with c2:
        st.altair_chart(
            grafico_barras(comparativo, "escenario", "fuera_sla", titulo="Porcentaje fuera de SLA", formato_y=".0%"),
            use_container_width=True,
        )


def pagina_kpis_gobernanza(df: pd.DataFrame, sla_min: float) -> None:
    st.title("KPIs y Riesgos")
    st.caption("Definicion operativa de indicadores para conectar el analisis Python con el dashboard.")

    st.subheader("Estado actual de los KPIs")
    estado = estado_kpis(df, sla_min)
    st.dataframe(estado, hide_index=True, use_container_width=True)

    estado_conteo = estado["Estado"].value_counts().reset_index()
    estado_conteo.columns = ["Estado", "Cantidad"]
    st.altair_chart(
        grafico_barras(estado_conteo, "Estado", "Cantidad", titulo="Resumen de estado de indicadores"),
        use_container_width=True,
    )

    st.subheader("Ficha tecnica de indicadores")
    fichas = fichas_kpi(sla_min)
    cols = st.columns(2)
    for indice, ficha in enumerate(fichas):
        with cols[indice % 2]:
            st.markdown(
                '<div class="kpi-card">'
                f'<div class="kpi-name">{ficha["Nombre"]}</div>'
                f'<div class="kpi-line"><b>Objetivo:</b> {ficha["Objetivo"]}</div>'
                f'<div class="kpi-line"><b>Formula:</b> {ficha["Formula"]}</div>'
                f'<div class="kpi-line"><b>Fuente:</b> {ficha["Fuente"]}</div>'
                f'<div class="kpi-line"><b>Frecuencia:</b> {ficha["Frecuencia"]}</div>'
                f'<div class="kpi-line"><b>Meta:</b> {ficha["Meta"]}</div>'
                f'<div class="kpi-line"><b>Umbral:</b> {ficha["Umbral"]}</div>'
                f'<div class="kpi-line"><b>Interpretacion:</b> {ficha["Interpretacion"]}</div>'
                "</div>",
                unsafe_allow_html=True,
            )
            st.write("")

    st.subheader("Riesgos de interpretación responsable") 
    riesgos = pd.DataFrame(
        [
            {
                "Riesgo": "Sobreinteractividad",
                "Control": "Mantener filtros de negocio claros y comparar siempre contra KPIs base.",
            },
            {
                "Riesgo": "Sesgo visual",
                "Control": "Usar escalas legibles, ordenar rankings y no ocultar volumen de pedidos.",
            },
            {
                "Riesgo": "Privacidad",
                "Control": "Trabajar con identificadores de pedido y evitar datos personales del cliente.",
            },
            {
                "Riesgo": "Gobernanza",
                "Control": "Documentar fórmula, fuente, frecuencia y umbral de cada KPI.",
            },
            {
                "Riesgo": "Limite interpretativo",
                "Control": "No inferir causalidad; validar demoras con informacion de rutas, flota o capacidad.",
            },
        ]
    )
    st.dataframe(riesgos, hide_index=True, use_container_width=True)


def pagina_datos(df: pd.DataFrame) -> None:
    st.title("Datos utilizados")
    st.caption("Vista filtrada de la base de pedidos LogiAndes.")
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Descargar datos filtrados",
        data=csv,
        file_name="logiandes_filtrado.csv",
        mime="text/csv",
    )


def aplicar_filtros(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    st.sidebar.title("Filtros")
    fecha_min = df["fecha_pedido"].min().date()
    fecha_max = df["fecha_pedido"].max().date()
    rango = st.sidebar.date_input("Rango de fechas", value=(fecha_min, fecha_max), min_value=fecha_min, max_value=fecha_max)
    regiones = st.sidebar.multiselect("Region", sorted(df["region"].dropna().unique()), default=sorted(df["region"].dropna().unique()))
    canales = st.sidebar.multiselect("Canal", sorted(df["canal_entrega"].dropna().unique()), default=sorted(df["canal_entrega"].dropna().unique()))
    provincias = st.sidebar.multiselect("Provincia", sorted(df["provincia"].dropna().unique()), default=sorted(df["provincia"].dropna().unique()))
    clientes = st.sidebar.multiselect("Tipo de cliente", sorted(df["tipo_cliente"].dropna().unique()), default=sorted(df["tipo_cliente"].dropna().unique()))
    sla_min = st.sidebar.slider("SLA objetivo de entrega (min)", 60, 240, 150, 10)

    filtrado = df.copy()
    if len(rango) == 2:
        inicio, fin = rango
        filtrado = filtrado[(filtrado["fecha_pedido"].dt.date >= inicio) & (filtrado["fecha_pedido"].dt.date <= fin)]
    filtrado = filtrado[
        filtrado["region"].isin(regiones)
        & filtrado["canal_entrega"].isin(canales)
        & filtrado["provincia"].isin(provincias)
        & filtrado["tipo_cliente"].isin(clientes)
    ]
    return filtrado, float(sla_min)


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    datos = cargar_datos(DATA_PATH)
    df, sla_min = aplicar_filtros(datos)

    st.sidebar.divider()
    pagina = st.sidebar.radio(
        "Secciones",
        [
            "Vista ejecutiva",
            "Análisis territorial",
            "Detalle operativo",
            "Reclamos",
            "Simulador",
            "KPIs y Riesgos",
            "Datos",
        ],
    )

    if df.empty:
        st.warning("No hay datos para la combinacion de filtros seleccionada.")
        return

    if pagina == "Vista ejecutiva":
        pagina_resumen(df, sla_min)
    elif pagina == "Análisis territorial":
        pagina_territorial(df, sla_min)
    elif pagina == "Detalle operativo":
        pagina_casos(df, sla_min)
    elif pagina == "Reclamos":
        pagina_reclamos(df, sla_min)
    elif pagina == "Simulador":
        pagina_simulador(df, sla_min)
    elif pagina == "KPIs y Riesgos":
        pagina_kpis_gobernanza(df, sla_min)
    else:
        pagina_datos(df)


if __name__ == "__main__":
    main()
