"""
Módulo de Gestión de Flota de Buses.
Requerimientos: R4, R5, R6, R7, R14.
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, execute_sp, execute_stmt
from components.ui_helpers import render_header, render_rule_badge
from components.charts import chart_regla_buses_linea
from auth import has_permission

def render():
    render_header(
        title="Gestión de Flota de Buses",
        subtitle="Asignación a líneas (0..1), regla de flota [N, 2N], capacidades y parqueo obligatorio",
        icon="🚌"
    )
    render_rule_badge("R4, R5, R6, R14", "Un bus sólo puede estar en una línea o en ninguna; cada línea tiene entre N y 2N buses; todo bus tiene asignado un parqueo.")

    tab_flota, tab_asignacion, tab_nuevo = st.tabs([
        "📋 Catálogo de Buses",
        "🔄 Asignación de Línea (R4, R5)",
        "➕ Registrar Nuevo Bus"
    ])

    # --- PESTAÑA 1: CATÁLOGO DE BUSES ---
    with tab_flota:
        st.subheader("Flota de Buses Transmetro")
        df_buses = query_df("""
            SELECT b.bus_id, b.numero_unidad, b.placa, b.marca, b.modelo, b.anio,
                   b.capacidad_maxima, b.estado,
                   COALESCE(l.codigo, 'SIN LÍNEA (Disponible)') AS linea,
                   p.codigo AS parqueo_codigo, p.nombre AS parqueo_nombre,
                   ep.nombre AS estacion_parqueo
              FROM transmetro.bus b
              LEFT JOIN transmetro.linea l ON l.linea_id = b.linea_id
              JOIN transmetro.parqueo p ON p.parqueo_id = b.parqueo_id
              JOIN transmetro.estacion ep ON ep.estacion_id = p.estacion_id
             ORDER BY b.numero_unidad;
        """)

        # Filtros
        fc1, fc2 = st.columns(2)
        with fc1:
            filtro_linea = st.selectbox("Filtrar por Línea:", ["TODAS"] + sorted(df_buses['linea'].unique().tolist()))
        with fc2:
            filtro_estado = st.selectbox("Filtrar por Estado:", ["TODOS", "ACTIVO", "MANTENIMIENTO", "BAJA"])

        df_filtrado = df_buses.copy()
        if filtro_linea != "TODAS":
            df_filtrado = df_filtrado[df_filtrado['linea'] == filtro_linea]
        if filtro_estado != "TODOS":
            df_filtrado = df_filtrado[df_filtrado['estado'] == filtro_estado]

        st.dataframe(
            df_filtrado[['numero_unidad', 'placa', 'marca', 'modelo', 'capacidad_maxima', 'linea', 'parqueo_nombre', 'estacion_parqueo', 'estado']],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")
        st.subheader("Verificación Visual de Flota vs Estaciones (R5)")
        df_buses_linea = query_df("SELECT * FROM transmetro.vw_buses_linea;")
        chart_regla_buses_linea(df_buses_linea)

    # --- PESTAÑA 2: ASIGNACIÓN DE LÍNEA (R4, R5) ---
    with tab_asignacion:
        st.subheader("R4: Asignar o Desasignar Bus de Línea")
        st.info("ℹ️ Un bus solo puede pertenecer a **una línea a la vez**, pero puede no estar asignado a ninguna (reserva / mantenimiento).")

        col_as1, col_as2 = st.columns(2)
        with col_as1:
            with st.container(border=True):
                st.write("🚍 **Reasignar Bus a Línea**")
                buses_activos = query_df("""
                    SELECT b.bus_id, b.numero_unidad, b.capacidad_maxima,
                           COALESCE(l.codigo, 'Sin Línea') AS linea_actual
                      FROM transmetro.bus b
                      LEFT JOIN transmetro.linea l ON l.linea_id = b.linea_id
                     WHERE b.estado <> 'BAJA'
                     ORDER BY b.numero_unidad;
                """)
                bus_dict = {f"{r['numero_unidad']} (Cap: {r['capacidad_maxima']}) - Actualmente: {r['linea_actual']}": r['bus_id'] for _, r in buses_activos.iterrows()}
                sel_bus = st.selectbox("Seleccione Unidad:", list(bus_dict.keys()), key="sel_bus_linea")

                lineas_db = query_df("SELECT linea_id, codigo, nombre FROM transmetro.linea ORDER BY codigo;")
                lin_target = {f"{r['codigo']} - {r['nombre']}": r['linea_id'] for _, r in lineas_db.iterrows()}
                sel_lin_target = st.selectbox("Asignar a la Línea:", list(lin_target.keys()))

                if st.button("Guardar Asignación", type="primary", disabled=not has_permission("flota_buses", "editar")):
                    ok, msg, _ = execute_sp("sp_asignar_bus_linea", (bus_dict[sel_bus], lin_target[sel_lin_target]))
                    if ok:
                        st.success(f"Bus asignado a la línea {sel_lin_target}.")
                        st.rerun()
                    else:
                        st.error(f"Error al asignar: {msg}")

        with col_as2:
            with st.container(border=True):
                st.write("🔓 **Desasignar Bus (Dejar en Reserva)**")
                buses_con_linea = query_df("""
                    SELECT b.bus_id, b.numero_unidad, l.codigo AS linea_actual
                      FROM transmetro.bus b
                      JOIN transmetro.linea l ON l.linea_id = b.linea_id
                     WHERE b.estado <> 'BAJA'
                     ORDER BY b.numero_unidad;
                """)
                if not buses_con_linea.empty:
                    bus_cl_dict = {f"{r['numero_unidad']} (Línea: {r['linea_actual']})": r['bus_id'] for _, r in buses_con_linea.iterrows()}
                    sel_bus_desasig = st.selectbox("Bus a desasignar:", list(bus_cl_dict.keys()), key="desasig_bus_sel")
                    
                    if st.button("Liberar de Línea", disabled=not has_permission("flota_buses", "editar")):
                        ok, msg, _ = execute_sp("sp_desasignar_bus", (bus_cl_dict[sel_bus_desasig],))
                        if ok:
                            st.success("Bus liberado de la línea.")
                            st.rerun()
                        else:
                            st.error(f"Error: {msg}")
                else:
                    st.info("No hay buses asignados a líneas actualmente.")

    # --- PESTAÑA 3: REGISTRAR NUEVO BUS (R6, R14) ---
    with tab_nuevo:
        st.subheader("Registrar Nueva Unidad en la Flota")
        st.info("💡 **Regla R6:** Todo bus debe contar obligatoriamente con un parqueo asignado.")

        if has_permission("flota_buses", "crear"):
            with st.form("form_nuevo_bus"):
                bc1, bc2 = st.columns(2)
                with bc1:
                    num_uni = st.text_input("Número de Unidad (Ej. TM-106):")
                    placa_b = st.text_input("Placa de Circulación:", placeholder="Ej. U106TMG")
                    marca_b = st.text_input("Marca del Bus:", placeholder="Ej. Volvo, Mercedes-Benz, Scania")
                    modelo_b = st.text_input("Modelo del Bus:", placeholder="Ej. B340M Articulado")
                with bc2:
                    anio_b = st.number_input("Año de Fabricación:", min_value=1995, max_value=2030, value=2024)
                    cap_b = st.number_input("Capacidad Máxima de Pasajeros (R14):", min_value=30, max_value=250, value=160, step=10)
                    
                    # Parqueos disponibles (R6)
                    parqueos = query_df("SELECT parqueo_id, codigo, nombre, capacidad_buses FROM transmetro.parqueo ORDER BY nombre;")
                    parq_map = {f"{r['codigo']} - {r['nombre']} (Capacidad: {r['capacidad_buses']})": r['parqueo_id'] for _, r in parqueos.iterrows()}
                    sel_parq = st.selectbox("Parqueo Asignado Obligatorio (R6):", list(parq_map.keys()))
                    
                    # Línea opcional (R4)
                    lineas_opt = query_df("SELECT linea_id, codigo, nombre FROM transmetro.linea ORDER BY codigo;")
                    lin_opt_map = {"(Ninguna - Sin línea)": None}
                    for _, r in lineas_opt.iterrows():
                        lin_opt_map[f"{r['codigo']} - {r['nombre']}"] = r['linea_id']
                    sel_lin_opt = st.selectbox("Línea Asignada Inicial (Opcional - R4):", list(lin_opt_map.keys()))

                sub_b = st.form_submit_button("Registrar Bus")
                if sub_b:
                    if not num_uni or not placa_b:
                        st.error("Número de unidad y placa son requeridos.")
                    else:
                        ok, msg, _ = execute_stmt("""
                            INSERT INTO transmetro.bus (numero_unidad, placa, marca, modelo, anio, capacidad_maxima, linea_id, parqueo_id, estado)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVO');
                        """, (num_uni.strip().upper(), placa_b.strip().upper(), marca_b.strip(), modelo_b.strip(),
                              int(anio_b), int(cap_b), lin_opt_map[sel_lin_opt], parq_map[sel_parq]))
                        if ok:
                            st.success(f"Bus {num_uni} registrado correctamente con parqueo asignado.")
                            st.rerun()
                        else:
                            st.error(f"Error al registrar bus: {msg}")
        else:
            st.info("No cuenta con permisos para registrar nuevos buses.")
