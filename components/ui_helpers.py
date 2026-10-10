"""
Componentes visuales y estilos reutilizables para la interfaz de Streamlit.
"""
import streamlit as st

def apply_custom_css():
    """Aplica estilos CSS personalizados a la aplicación."""
    st.markdown(
        """
        <style>
        /* Tipografía y márgenes generales */
        .main .block-container {
            padding-top: 1.8rem;
            padding-bottom: 3rem;
            max-width: 95%;
        }
        
        /* Banner superior */
        .top-banner {
            background: linear-gradient(90deg, #0F2027 0%, #203A43 50%, #2C5364 100%);
            color: #FFFFFF;
            padding: 18px 24px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .top-banner h2 {
            margin: 0;
            color: #FFFFFF !important;
            font-size: 1.6rem;
            font-weight: 700;
        }
        .top-banner p {
            margin: 4px 0 0 0;
            color: #E0E0E0;
            font-size: 0.95rem;
        }
        
        /* Tarjetas de métricas */
        .metric-card {
            background-color: #FFFFFF;
            border-radius: 10px;
            padding: 16px 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.06);
            border-left: 5px solid #2C5364;
            margin-bottom: 12px;
            transition: transform 0.2s ease;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.12);
        }
        .metric-title {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #6c757d;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .metric-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1a252f;
            line-height: 1.1;
        }
        .metric-sub {
            font-size: 0.8rem;
            color: #888888;
            margin-top: 5px;
        }
        
        /* Badges de estado */
        .badge {
            display: inline-block;
            padding: 3px 8px;
            font-size: 0.78rem;
            font-weight: 600;
            border-radius: 12px;
            text-transform: uppercase;
        }
        .badge-success { background-color: #d4edda; color: #155724; }
        .badge-warning { background-color: #fff3cd; color: #856404; }
        .badge-danger  { background-color: #f8d7da; color: #721c24; }
        .badge-info    { background-color: #d1ecf1; color: #0c5460; }
        .badge-primary { background-color: #cce5ff; color: #004085; }
        
        /* Cajas de reglas de negocio */
        .rule-box {
            background-color: #f8f9fa;
            border-left: 4px solid #17a2b8;
            padding: 12px 16px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 16px;
            font-size: 0.9rem;
        }
        
        /* Ajuste de tablas */
        .stDataFrame {
            border-radius: 8px;
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def render_header(title: str, subtitle: str, icon: str = "🚌"):
    """Renderiza el banner superior de cada módulo."""
    st.markdown(
        f"""
        <div class="top-banner">
            <h2>{icon} {title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_metric_card(title: str, value: str, sub: str = "", border_color: str = "#2C5364"):
    """Renderiza una tarjeta métrica enriquecida."""
    st.markdown(
        f"""
        <div class="metric-card" style="border-left-color: {border_color};">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
            {f'<div class="metric-sub">{sub}</div>' if sub else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

def render_rule_badge(rule_code: str, description: str):
    """Muestra una píldora indicando la regla del requerimiento cubierta."""
    st.markdown(
        f"""
        <div class="rule-box">
            <strong>📋 Requerimiento {rule_code}:</strong> {description}
        </div>
        """,
        unsafe_allow_html=True
    )
