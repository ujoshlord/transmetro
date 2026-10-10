"""
Módulo de Gestión de Líneas, Rutas Ordenadas y Regla de Flota.
Requerimientos: R1, R2, R5, R11, R13.
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, query_one, execute_sp, execute_stmt
from components.ui_helpers import render_header, render_rule_badge
from components.charts import chart_distancia_acumulada_linea
from auth import has_permission

def render():
    render_header(
        title="Gestión de Líneas y Rutas",
        subtitle="Administración de líneas, orden de estaciones, perfil de distancia y validación de flota",
        icon="🛤️"
    )
    render_rule_badge("R1, R5, R11, R13", "Orden estricto de estaciones, pertenencia municipal, distancias y regla de flota N <= buses <= 2N.")

    # 1. Obtener listado de líneas
    df_lineas = query_df("""
        SELECT l.linea_id, l.codigo, l.nombre, l.color, l.estado,
               m.nombre AS municipalidad,
               COUNT(le.estacion_id) AS total_estaciones,
               COALESCE((SELECT COUNT(*) FROM transmetro.bus b WHERE b.linea_id = l.linea_id), 0) AS buses_asignados,
               COALESCE((SELECT dl.distancia_total_km FROM transmetro.vw_distancia_linea dl WHERE dl.linea_id = l.linea_id), 0) AS distancia_total_km
          FROM transmetro.linea l
          JOIN transmetro.municipalidad m ON m.municipalidad_id = l.municipalidad_id
          LEFT JOIN transmetro.linea_estacion le ON le.linea_id = l.linea_id
         GROUP BY l.linea_id, l.codigo, l.nombre, l.color, l.estado, m.nombre
         ORDER BY l.codigo;
    """)

    if df_lineas.empty:
        st.info("No hay líneas registradas en el sistema.")
        return

    # Selector de línea
    linea_opciones = {f"{r['codigo']} - {r['nombre']} ({r['estado']})": r['linea_id'] for _, r in df_lineas.iterrows()}
    sel_nombre = st.selectbox("Seleccione una Línea para inspeccionar:", list(linea_opciones.keys()))
    sel_linea_id = linea_opciones[sel_nombre]
    
    linea_info = df_lineas[df_lineas['linea_id'] == sel_linea_id].iloc[0]

    # Resumen en tarjetas métricas
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Código / Estado", f"{linea_info['codigo']}", linea_info['estado'])
    with m2:
        st.metric("Municipalidad (R11)", linea_info['municipalidad'])
    with m3:
        st.metric("Estaciones (N)", str(linea_info['total_estaciones']))
    with m4:
        st.metric("Distancia Total (R13)", f"{linea_info['distancia_total_km']:.2f} km")
    with m5:
        n = int(linea_info['total_estaciones'])
        b = int(linea_info['buses_asignados'])
        cumple = (n <= b <= 2 * n) if n > 0 else False
        st.metric("Buses (Rango [N, 2N])", f"{b} buses", f"Rango: [{n}, {2*n}] - {'OK' if cumple else 'Fuera de rango'}")

    # Pestañas del módulo
    tab_ruta, tab_validacion, tab_nueva = st.tabs(["📍 Estaciones y Ruta Ordenada (R1)", "⚖️ Reglas y Estado de Línea (R5)", "➕ Nueva Línea"])

    # --- PESTAÑA 1: RUTA Y ORDEN DE ESTACIONES ---
    with tab_ruta:
        st.subheader(f"Orden de Estaciones de la Línea {linea_info['codigo']}")
        
        df_ruta = query_df("""
            SELECT orden, estacion_codigo, estacion_nombre, municipalidad_estacion,
                   distancia_desde_anterior_km, distancia_acumulada_km, estacion_id
              FROM transmetro.vw_ruta_linea
             WHERE linea_id = %s
             ORDER BY orden;
        """, (sel_linea_id,))

        if not df_ruta.empty:
            col_t1, col_t2 = st.columns([1.2, 1.8])
            with col_t1:
                st.dataframe(
                    df_ruta[['orden', 'estacion_codigo', 'estacion_nombre', 'distancia_desde_anterior_km', 'distancia_acumulada_km']],
                    use_container_width=True,
                    hide_index=True
                )
            with col_t2:
                chart_distancia_acumulada_linea(df_ruta, linea_info['codigo'])
        else:
            st.warning("Esta línea aún no tiene estaciones asignadas en su recorrido.")

        # Acciones de gestión de ruta
        if has_permission("lineas_rutas", "editar"):
            st.markdown("#### Modificar Recorrido")
            col_add, col_del = st.columns(2)
            
            with col_add:
                with st.container(border=True):
                    st.write("➕ **Agregar Estación a la Ruta**")
                    # Estaciones disponibles que aún no están en la línea
                    estaciones_disp = query_df("""
                        SELECT e.estacion_id, e.codigo, e.nombre
                          FROM transmetro.estacion e
                         WHERE e.estacion_id NOT IN (
                             SELECT estacion_id FROM transmetro.linea_estacion WHERE linea_id = %s
                         )
                         ORDER BY e.nombre;
                    """, (sel_linea_id,))
                    
                    if not estaciones_disp.empty:
                        est_dict = {f"{r['codigo']} - {r['nombre']}": r['estacion_id'] for _, r in estaciones_disp.iterrows()}
                        sel_est = st.selectbox("Seleccione estación:", list(est_dict.keys()), key="add_est_sel")
                        orden_sug = int(df_ruta['orden'].max() + 1) if not df_ruta.empty else 1
                        pos_orden = st.number_input("Posición de orden:", min_value=1, value=orden_sug, step=1)
                        
                        if st.button("Asignar Estación a Línea", type="primary"):
                            ok, msg, _ = execute_sp("sp_agregar_estacion_linea", (sel_linea_id, est_dict[sel_est], int(pos_orden)))
                            if ok:
                                st.success("Estación agregada exitosamente a la ruta.")
                                st.rerun()
                            else:
                                st.error(f"Error al agregar estación: {msg}")
                    else:
                        st.info("Todas las estaciones ya están asignadas a esta línea.")
            
            with col_del:
                with st.container(border=True):
                    st.write("🗑️ **Quitar Estación de la Ruta**")
                    if not df_ruta.empty:
                        est_en_ruta = {f"#{r['orden']} - {r['estacion_nombre']}": r['estacion_id'] for _, r in df_ruta.iterrows()}
                        sel_quitar = st.selectbox("Estación a remover:", list(est_en_ruta.keys()), key="del_est_sel")
                        if st.button("Remover Estación", type="secondary"):
                            ok, msg, _ = execute_sp("sp_quitar_estacion_linea", (sel_linea_id, est_en_ruta[sel_quitar]))
                            if ok:
                                st.success("Estación removida y ruta reordenada.")
                                st.rerun()
                            else:
                                st.error(f"Error: {msg}")
                    else:
                        st.info("No hay estaciones asignadas para remover.")

    # --- PESTAÑA 2: VALIDACIÓN DE REGLAS Y ESTADO OPERATIVO ---
    with tab_validacion:
        st.subheader("Auditoría de Requisitos para Operatividad (R5, R3, R10, R12)")
        
        # Ejecutar fn_validar_linea
        df_val = query_df("SELECT * FROM transmetro.fn_validar_linea(%s);", (sel_linea_id,))
        
        for _, row in df_val.iterrows():
            icono = "✅" if row['cumple'] else "❌"
            color = "green" if row['cumple'] else "red"
            st.markdown(f"**{icono} {row['regla']}**")
            st.markdown(f"<span style='color:{color}; margin-left: 28px;'>{row['detalle']}</span>", unsafe_allow_html=True)
            st.write("")

        todas_cumplen = bool(df_val['cumple'].all()) if not df_val.empty else False

        st.markdown("---")
        st.subheader("Cambio de Estado de la Línea")
        col_es1, col_es2 = st.columns([2, 1])
        with col_es1:
            nuevo_estado = st.selectbox(
                "Estado Operativo:",
                ["EN_DISENO", "OPERATIVA", "SUSPENDIDA"],
                index=["EN_DISENO", "OPERATIVA", "SUSPENDIDA"].index(linea_info['estado'])
            )
        with col_es2:
            st.write("")
            st.write("")
            if st.button("Actualizar Estado", type="primary", disabled=not has_permission("lineas_rutas", "editar")):
                ok, msg, _ = execute_sp("sp_cambiar_estado_linea", (sel_linea_id, nuevo_estado))
                if ok:
                    st.success(f"Estado de la línea {linea_info['codigo']} cambiado a {nuevo_estado}.")
                    st.rerun()
                else:
                    st.error(f"No se pudo cambiar el estado: {msg}")

    # --- PESTAÑA 3: CREAR NUEVA LÍNEA ---
    with tab_nueva:
        st.subheader("Registrar Nueva Línea")
        if has_permission("lineas_rutas", "crear"):
            with st.form("form_nueva_linea"):
                fc1, fc2 = st.columns(2)
                with fc1:
                    cod_lin = st.text_input("Código de Línea (Ej. L7, L18):")
                    nom_lin = st.text_input("Nombre de la Línea:", placeholder="Ej. Línea 7 - Calzada San Juan")
                with fc2:
                    color_lin = st.color_picker("Selecciona un color", "#00f900")
                    munis = query_df("SELECT municipalidad_id, nombre FROM transmetro.municipalidad ORDER BY nombre;")
                    muni_dict = {r['nombre']: r['municipalidad_id'] for _, r in munis.iterrows()}
                    sel_muni = st.selectbox("Municipalidad Perteneciente (R11):", list(muni_dict.keys()))
                
                submit_lin = st.form_submit_button("Crear Línea (inicia en EN_DISENO)")
                if submit_lin:
                    if not cod_lin or not nom_lin:
                        st.error("Código y nombre son obligatorios.")
                    else:
                        ok, msg, _ = execute_stmt("""
                            INSERT INTO transmetro.linea (codigo, nombre, color, municipalidad_id, estado)
                            VALUES (%s, %s, %s, %s, 'EN_DISENO');
                        """, (cod_lin.strip().upper(), nom_lin.strip(), color_lin.strip(), muni_dict[sel_muni]))
                        if ok:
                            st.success("Línea creada exitosamente. Ahora puede agregar estaciones y asignar buses.")
                            st.rerun()
                        else:
                            st.error(f"Error al crear línea: {msg}")
        else:
            st.info("No cuenta con permisos para crear líneas.")
