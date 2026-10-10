"""
Aplicación Principal Streamlit - Sistema Integral de Gestión Transmetro GT.
Controla el flujo de autenticación, autorización por módulos y navegación principal.
"""
import streamlit as st
from config import DEFAULT_PAGE_TITLE, DEFAULT_PAGE_ICON
from components.ui_helpers import apply_custom_css
from auth import init_auth_state, is_authenticated, render_login_page, logout, get_current_user, has_permission

# Importación de módulos funcionales
from modules import (
    dashboard,
    lineas_rutas,
    estaciones_accesos,
    flota_buses,
    parqueos,
    pilotos,
    seguridad_guardias,
    distancias,
    alertas_afluencia,
    recorridos_visitas,
    admin_usuarios
)

# 1. Configuración de página de Streamlit
st.set_page_config(
    page_title=DEFAULT_PAGE_TITLE,
    page_icon=DEFAULT_PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Aplicar estilos globales
apply_custom_css()
init_auth_state()

# 3. Flujo de Autenticación
if not is_authenticated():
    render_login_page()
    st.stop()

# 4. Usuario Autenticado - Renderizado de la Navegación y Sidebar
user = get_current_user()

with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; padding: 10px 0; border-bottom: 2px solid #e9ecef; margin-bottom: 15px;">
            <h2 style="margin: 0; color: #2C5364; font-size: 1.5rem;">🚌 TRANSMETRO</h2>
            <p style="margin: 2px 0 0 0; font-size: 0.85rem; color: #6c757d;">Sistema de Gestión de Tráfico</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Tarjeta de perfil del usuario logueado
    st.markdown(
        f"""
        <div style="background: #f8f9fa; border-radius: 8px; padding: 12px; margin-bottom: 18px; border: 1px solid #e2e8f0;">
            <div style="font-size: 0.78rem; text-transform: uppercase; color: #718096; font-weight: 600;">Usuario Activo</div>
            <div style="font-size: 1.05rem; font-weight: 700; color: #1a202c;">{user['nombre_completo']}</div>
            <div style="margin-top: 4px;">
                <span class="badge badge-primary">{user['rol_nombre']}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Catálogo de módulos disponibles según permisos del usuario
    modulos_disponibles = []
    
    lista_modulos = [
        ("dashboard",          "📊 Panel de Control",        dashboard.render),
        ("lineas_rutas",       "🛤️ Líneas y Rutas",          lineas_rutas.render),
        ("estaciones_accesos", "🚪 Estaciones y Accesos",    estaciones_accesos.render),
        ("flota_buses",        "🚌 Flota de Buses",          flota_buses.render),
        ("parqueos",           "🅿️ Gestión de Parqueos",     parqueos.render),
        ("pilotos",            "👨‍✈️ Pilotos y Fichas",       pilotos.render),
        ("seguridad_guardias", "👮 Seguridad y Guardias",    seguridad_guardias.render),
        ("distancias",         "📏 Cálculo de Distancias",   distancias.render),
        ("alertas_afluencia",  "🚨 Afluencia y Alertas",     alertas_afluencia.render),
        ("recorridos_visitas", "⏱️ Recorridos y Operación",  recorridos_visitas.render),
        ("admin_usuarios",     "⚙️ Usuarios y Permisos",     admin_usuarios.render)
    ]
    
    for mod_id, mod_label, mod_func in lista_modulos:
        if has_permission(mod_id, "ver"):
            modulos_disponibles.append((mod_id, mod_label, mod_func))

    modulo_labels = [m[1] for m in modulos_disponibles]
    
    st.markdown("**Navegación de Módulos:**")
    selected_label = st.radio(
        label="Seleccione Módulo:",
        options=modulo_labels,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
        logout()

# 5. Enrutamiento y Ejecución del Módulo Seleccionado
for mod_id, mod_label, mod_func in modulos_disponibles:
    if mod_label == selected_label:
        mod_func()
        break
