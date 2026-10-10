"""
Módulo de Gestión de Parqueos e Historial de Reasignaciones.
Requerimientos: R6, R7.
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, execute_sp, execute_stmt
from components.ui_helpers import render_header, render_rule_badge
from components.charts import chart_ocupacion_parqueos
from auth import has_permission

def render():
    render_header(
        title="Gestión de Parqueos y Reasignación de Flota",
        subtitle="Control de predios por estación, asignación obligatoria e historial auditado de cambios",
        icon="🅿️"
    )
    render_rule_badge("R6, R7", "Parqueos pertenecen a estaciones; cada bus tiene parqueo asignado; un bus puede cambiar de parqueo pero nunca quedar sin él.")

    tab_parq, tab_cambio, tab_historial, tab_nuevo = st.tabs([
        "🅿️ Estado y Ocupación",
        "🔄 Cambiar Parqueo de Bus (R7)",
        "📜 Historial de Cambios de Parqueo",
        "➕ Nuevo Parqueo"
    ])

    # --- PESTAÑA 1: ESTADO Y OCUPACIÓN ---
    with tab_parq:
        st.subheader("Ocupación de Parqueos de la Red")
        df_parq = query_df("SELECT * FROM transmetro.vw_parqueo_ocupacion ORDER BY codigo;")
        
        col1, col2 = st.columns([1.2, 1.8])
        with col1:
            st.dataframe(
                df_parq[['codigo', 'nombre', 'estacion', 'capacidad_buses', 'buses_asignados', 'espacios_disponibles']],
                use_container_width=True,
                hide_index=True
            )
        with col2:
            chart_ocupacion_parqueos(df_parq)

        st.markdown("---")
        st.subheader("Buses Asignados por Cada Parqueo")
        parq_select = st.selectbox("Seleccione un parqueo para ver sus unidades:", df_parq['nombre'].tolist())
        sel_parq_id = df_parq[df_parq['nombre'] == parq_select]['parqueo_id'].iloc[0]
        
        df_buses_parq = query_df("""
            SELECT b.numero_unidad, b.placa, b.marca, b.modelo, b.capacidad_maxima,
                   COALESCE(l.codigo, 'Sin Línea') AS linea, b.estado
              FROM transmetro.bus b
              LEFT JOIN transmetro.linea l ON l.linea_id = b.linea_id
             WHERE b.parqueo_id = %s
             ORDER BY b.numero_unidad;
        """, (int(sel_parq_id),))
        
        st.dataframe(df_buses_parq, use_container_width=True, hide_index=True)

    # --- PESTAÑA 2: CAMBIAR PARQUEO DE BUS (R7) ---
    with tab_cambio:
        st.subheader("R7: Reasignación de Parqueo de un Bus")
        st.info("💡 **Regla R7:** El bus puede ser reasignado a otro parqueo con capacidad disponible, pero **la base de datos rechaza cualquier intento de dejarlo sin parqueo**.")

        if has_permission("parqueos", "editar"):
            with st.container(border=True):
                buses_list = query_df("""
                    SELECT b.bus_id, b.numero_unidad, b.parqueo_id,
                           p.nombre AS parqueo_actual, p.codigo AS parqueo_codigo
                      FROM transmetro.bus b
                      JOIN transmetro.parqueo p ON p.parqueo_id = b.parqueo_id
                     WHERE b.estado <> 'BAJA'
                     ORDER BY b.numero_unidad;
                """)
                bus_map = {f"{r['numero_unidad']} (Actualmente en: {r['parqueo_codigo']} - {r['parqueo_actual']})": r['bus_id'] for _, r in buses_list.iterrows()}
                bus_sel = st.selectbox("Seleccione el Bus:", list(bus_map.keys()))
                
                parqueos_disp = query_df("""
                    SELECT p.parqueo_id, p.codigo, p.nombre, p.capacidad_buses,
                           (p.capacidad_buses - (SELECT COUNT(*) FROM transmetro.bus b WHERE b.parqueo_id = p.parqueo_id)) AS disponibles
                      FROM transmetro.parqueo p
                     ORDER BY p.nombre;
                """)
                parq_map = {f"{r['codigo']} - {r['nombre']} (Espacios libres: {r['disponibles']}/{r['capacidad_buses']})": r['parqueo_id'] for _, r in parqueos_disp.iterrows()}
                parq_sel = st.selectbox("Nuevo Parqueo Destino:", list(parq_map.keys()))
                
                motivo = st.text_input("Motivo de la reasignación:", placeholder="Ej. Reubicación operativa por cambio de turno")
                
                if st.button("Ejecutar Reasignación de Parqueo", type="primary"):
                    target_bus_id = bus_map[bus_sel]
                    target_parq_id = parq_map[parq_sel]
                    
                    ok, msg, _ = execute_sp("sp_cambiar_parqueo_bus", (target_bus_id, target_parq_id, motivo))
                    if ok:
                        st.success(f"Parqueo actualizado correctamente con auditoría.")
                        st.rerun()
                    else:
                        st.error(f"No se pudo cambiar el parqueo: {msg}")
        else:
            st.info("No cuenta con permisos para reasignar parqueos.")

    # --- PESTAÑA 3: HISTORIAL AUDITADO DE CAMBIOS ---
    with tab_historial:
        st.subheader("Historial Cronológico de Cambios de Parqueo (R7)")
        df_hist = query_df("""
            SELECT h.historial_id, b.numero_unidad, b.placa,
                   COALESCE(pa.codigo || ' - ' || pa.nombre, '(Asignación Inicial)') AS parqueo_anterior,
                   pn.codigo || ' - ' || pn.nombre AS parqueo_nuevo,
                   h.fecha_cambio, h.motivo
              FROM transmetro.historial_parqueo_bus h
              JOIN transmetro.bus b ON b.bus_id = h.bus_id
              LEFT JOIN transmetro.parqueo pa ON pa.parqueo_id = h.parqueo_anterior_id
              JOIN transmetro.parqueo pn ON pn.parqueo_id = h.parqueo_nuevo_id
             ORDER BY h.fecha_cambio DESC;
        """)
        
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

    # --- PESTAÑA 4: REGISTRAR NUEVO PARQUEO (R6) ---
    with tab_nuevo:
        st.subheader("Registrar Nuevo Parqueo en una Estación (R6)")
        st.info("💡 **Regla R6:** Algunas estaciones tienen parqueos asignados para el resguardo de la flota.")

        if has_permission("parqueos", "crear"):
            with st.form("form_nuevo_parqueo"):
                pc1, pc2 = st.columns(2)
                with pc1:
                    cod_p = st.text_input("Código de Parqueo (Ej. P03):")
                    nom_p = st.text_input("Nombre del Predio/Parqueo:", placeholder="Ej. Predio Trébol Norte")
                    cap_p = st.number_input("Capacidad Máxima de Buses:", min_value=1, max_value=50, value=10)
                with pc2:
                    estaciones = query_df("SELECT estacion_id, codigo, nombre FROM transmetro.estacion ORDER BY nombre;")
                    est_dict = {f"{r['codigo']} - {r['nombre']}": r['estacion_id'] for _, r in estaciones.iterrows()}
                    est_parq_sel = st.selectbox("Estación a la que se Asigna (R6):", list(est_dict.keys()))
                    dir_p = st.text_input("Dirección del predio:", placeholder="Ej. Calzada Roosevelt y 6ta avenida")

                sub_p = st.form_submit_button("Crear Parqueo")
                if sub_p:
                    if not cod_p or not nom_p:
                        st.error("Código y nombre son obligatorios.")
                    else:
                        ok, msg, _ = execute_stmt("""
                            INSERT INTO transmetro.parqueo (codigo, nombre, estacion_id, capacidad_buses, direccion)
                            VALUES (%s, %s, %s, %s, %s);
                        """, (cod_p.strip().upper(), nom_p.strip(), est_dict[est_parq_sel], int(cap_p), dir_p.strip()))
                        if ok:
                            st.success("Parqueo registrado exitosamente.")
                            st.rerun()
                        else:
                            st.error(f"Error al registrar parqueo: {msg}")
        else:
            st.info("No cuenta con permisos para crear nuevos parqueos.")
