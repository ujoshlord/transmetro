"""
Módulo de Cálculo y Consulta de Distancias en la Red Transmetro.
Requerimientos: R12, R13.
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, query_one, execute_stmt
from components.ui_helpers import render_header, render_rule_badge
from components.charts import chart_distancia_acumulada_linea
from auth import has_permission

def render():
    render_header(
        title="Cálculo de Distancias y Trazado de Rutas",
        subtitle="Longitud total de líneas y calculadora de distancias entre cualquier par de estaciones",
        icon="📏"
    )
    render_rule_badge("R12, R13", "Saber la distancia entre cualquier par de estaciones y la distancia total de cada línea.")

    tab_calc, tab_lineas, tab_tramos = st.tabs([
        "🧭 Calculadora de Distancia entre Estaciones (R12)",
        "🛤️ Longitud Total de Líneas (R13)",
        "🛣️ Tramos Consecutivos Registrados"
    ])

    # --- PESTAÑA 1: CALCULADORA DE DISTANCIA (R12) ---
    with tab_calc:
        st.subheader("Calculadora de Distancia entre Dos Estaciones")
        st.caption("Permite calcular la distancia dentro de una línea en específico o la ruta más corta a través de toda la red integrada.")

        estaciones = query_df("SELECT estacion_id, codigo, nombre FROM transmetro.estacion ORDER BY nombre;")
        est_dict = {f"{r['codigo']} - {r['nombre']}": r['estacion_id'] for _, r in estaciones.iterrows()}

        col_orig, col_dest = st.columns(2)
        with col_orig:
            orig_sel = st.selectbox("Estación Origen:", list(est_dict.keys()), index=0)
            orig_id = est_dict[orig_sel]
        with col_dest:
            dest_sel = st.selectbox("Estación Destino:", list(est_dict.keys()), index=min(1, len(est_dict)-1))
            dest_id = est_dict[dest_sel]

        # Filtro opcional por línea
        lineas_disp = query_df("SELECT linea_id, codigo, nombre FROM transmetro.linea ORDER BY codigo;")
        lin_dict = {"(Cualquier Ruta en la Red - Ruta más corta)": None}
        for _, r in lineas_disp.iterrows():
            lin_dict[f"{r['codigo']} - {r['nombre']}"] = r['linea_id']
        lin_sel = st.selectbox("Restringir a una línea específica (opcional):", list(lin_dict.keys()))
        lin_id = lin_dict[lin_sel]

        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            btn_calcular = st.button("Calcular Distancia 🚀", type="primary", use_container_width=True)
        with col_btn2:
            if st.session_state.get("calc_distancia_resultado") and st.button("Limpiar Cálculo 🗑️", type="secondary"):
                del st.session_state["calc_distancia_resultado"]
                st.rerun()

        if btn_calcular:
            if orig_id == dest_id:
                st.info("La estación de origen y destino son la misma (Distancia: 0.00 km). No se puede registrar un tramo con la misma estación.")
                if "calc_distancia_resultado" in st.session_state:
                    del st.session_state["calc_distancia_resultado"]
            else:
                try:
                    es_geodesica = False
                    if lin_id is not None:
                        sql = "SELECT transmetro.fn_distancia_entre_estaciones(%s, %s, %s) AS dist_km;"
                        res = query_one(sql, (orig_id, dest_id, lin_id))
                    else:
                        sql = "SELECT transmetro.fn_distancia_entre_estaciones(%s, %s) AS dist_km;"
                        res = query_one(sql, (orig_id, dest_id))
                    
                    dist_km = res['dist_km'] if res else None

                    # Si no hay ruta calculada previa, estimar distancia geodésica mediante coordenadas (Haversine)
                    if dist_km is None:
                        sql_geo = """
                            SELECT transmetro.fn_haversine_km(ea.latitud, ea.longitud, eb.latitud, eb.longitud) AS dist_km
                              FROM transmetro.estacion ea, transmetro.estacion eb
                             WHERE ea.estacion_id = %s AND eb.estacion_id = %s;
                        """
                        res_geo = query_one(sql_geo, (orig_id, dest_id))
                        dist_km = res_geo['dist_km'] if res_geo else None
                        es_geodesica = True
                    
                    if dist_km is not None:
                        dist_km = float(dist_km)
                        tiempo_min = round(dist_km / 25.0 * 60.0, 1)
                        if tiempo_min <= 0:
                            tiempo_min = 1.0

                        st.session_state["calc_distancia_resultado"] = {
                            "orig_id": orig_id,
                            "dest_id": dest_id,
                            "orig_nombre": orig_sel,
                            "dest_nombre": dest_sel,
                            "dist_km": dist_km,
                            "tiempo_min": tiempo_min,
                            "es_geodesica": es_geodesica
                        }
                    else:
                        st.warning("No se encontró una ruta continua ni coordenadas registradas para calcular la distancia.")
                        if "calc_distancia_resultado" in st.session_state:
                            del st.session_state["calc_distancia_resultado"]
                except Exception as e:
                    st.error(f"Error al calcular distancia: {e}")
                    if "calc_distancia_resultado" in st.session_state:
                        del st.session_state["calc_distancia_resultado"]

        # Mostrar resultado y opción de añadir a la tabla 'tramo'
        if st.session_state.get("calc_distancia_resultado"):
            calc = st.session_state["calc_distancia_resultado"]
            
            st.markdown("---")
            rc1, rc2 = st.columns(2)
            with rc1:
                st.metric("Distancia Calculada (R12)", f"{calc['dist_km']:.3f} km")
            with rc2:
                st.metric("Tiempo Estimado de Viaje", f"~{calc['tiempo_min']} minutos", "A velocidad promedio 25 km/h")
            
            if calc.get("es_geodesica"):
                st.info("ℹ️ Distancia estimada por geolocalización de coordenadas (Haversine en línea recta).")
            else:
                st.success(f"Trayecto calculado desde **{calc['orig_nombre']}** hasta **{calc['dest_nombre']}** exitosamente.")

            # --- OPCIÓN DE AÑADIR A LA TABLA TRAMO ---
            with st.container(border=True):
                st.subheader("💾 Registro en la Tabla de Tramos (`transmetro.tramo`)")
                st.caption("Usted decide si desea registrar este trayecto en la base de datos para que forme parte de las conexiones oficiales de la red.")

                # Consultar si ya existe un tramo registrado entre estas estaciones
                tramo_existente = query_one("""
                    SELECT tramo_id, distancia_km, tiempo_estimado_min, estacion_origen_id, estacion_destino_id
                      FROM transmetro.tramo
                     WHERE (estacion_origen_id = %s AND estacion_destino_id = %s)
                        OR (estacion_origen_id = %s AND estacion_destino_id = %s)
                     LIMIT 1;
                """, (calc['orig_id'], calc['dest_id'], calc['dest_id'], calc['orig_id']))

                if tramo_existente:
                    st.warning(
                        f"⚠️ **Tramo ya existente en BD:** Actualmente ya existe un tramo registrado entre estas dos estaciones "
                        f"con distancia de **{tramo_existente['distancia_km']} km** y tiempo estimado de **{tramo_existente['tiempo_estimado_min']} min**."
                    )
                else:
                    st.info(f"✨ **Nuevo Tramo:** No existe aún un tramo registrado en la base de datos entre **{calc['orig_nombre']}** y **{calc['dest_nombre']}**.")

                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    dist_guardar = st.number_input(
                        "Distancia a guardar (km):",
                        min_value=0.001,
                        max_value=200.0,
                        value=float(calc['dist_km']),
                        format="%.3f",
                        key="dist_guardar_input"
                    )
                with col_f2:
                    tiempo_guardar = st.number_input(
                        "Tiempo estimado a guardar (minutos):",
                        min_value=0.1,
                        max_value=300.0,
                        value=float(calc['tiempo_min']),
                        format="%.2f",
                        key="tiempo_guardar_input"
                    )

                puede_guardar = has_permission("distancias", "crear") or has_permission("distancias", "editar")

                col_act1, col_act2 = st.columns([1.5, 3])
                with col_act1:
                    btn_texto = "🔄 Actualizar Tramo en BD" if tramo_existente else "💾 Añadir a Tabla Tramo"
                    if st.button(btn_texto, type="primary", use_container_width=True, disabled=not puede_guardar):
                        # Inserción con UPSERT en caso de conflicto por el par de estaciones
                        sql_insert_tramo = """
                            INSERT INTO transmetro.tramo (estacion_origen_id, estacion_destino_id, distancia_km, tiempo_estimado_min)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (LEAST(estacion_origen_id, estacion_destino_id), GREATEST(estacion_origen_id, estacion_destino_id))
                            DO UPDATE SET distancia_km = EXCLUDED.distancia_km,
                                          tiempo_estimado_min = EXCLUDED.tiempo_estimado_min;
                        """
                        ok, msg, _ = execute_stmt(
                            sql_insert_tramo,
                            (calc['orig_id'], calc['dest_id'], dist_guardar, tiempo_guardar)
                        )
                        if ok:
                            st.success(f"✅ ¡Tramo entre **{calc['orig_nombre']}** y **{calc['dest_nombre']}** guardado exitosamente con {dist_guardar:.3f} km y {tiempo_guardar:.1f} min!")
                            del st.session_state["calc_distancia_resultado"]
                            st.rerun()
                        else:
                            st.error(f"Error al guardar tramo: {msg}")
                with col_act2:
                    if not puede_guardar:
                        st.caption("🔒 Su usuario actual no cuenta con permisos para crear o modificar tramos en la red.")

        st.markdown("---")
        st.subheader("Matriz de Distancias entre Estaciones de una Línea")
        linea_matriz = st.selectbox("Seleccione Línea para ver su matriz:", lineas_disp['codigo'].tolist(), key="mat_lin_sel")
        
        df_mat = query_df("""
            SELECT estacion_origen, estacion_destino, tramos, distancia_km
              FROM transmetro.vw_distancia_entre_estaciones
             WHERE linea_codigo = %s
             ORDER BY tramos, distancia_km;
        """, (linea_matriz,))
        
        st.dataframe(df_mat, use_container_width=True, hide_index=True)

    # --- PESTAÑA 2: LONGITUD TOTAL DE LÍNEAS (R13) ---
    with tab_lineas:
        st.subheader("R13: Longitud Total de Cada Línea del Sistema")
        df_dist_linea = query_df("SELECT * FROM transmetro.vw_distancia_linea ORDER BY codigo;")
        
        st.dataframe(
            df_dist_linea[['codigo', 'nombre', 'municipalidad', 'estado', 'total_estaciones', 'distancia_total_km']],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")
        # Gráfica de perfil por línea
        sel_l_graf = st.selectbox("Ver perfil de ruta de:", df_dist_linea['codigo'].tolist(), key="graf_dist_sel")
        l_id = df_dist_linea[df_dist_linea['codigo'] == sel_l_graf]['linea_id'].iloc[0]
        
        df_ruta_graf = query_df("SELECT * FROM transmetro.vw_ruta_linea WHERE linea_id = %s ORDER BY orden;", (int(l_id),))
        chart_distancia_acumulada_linea(df_ruta_graf, sel_l_graf)

    # --- PESTAÑA 3: TRAMOS REGISTRADOS ---
    with tab_tramos:
        st.subheader("Registro de Tramos Directos entre Estaciones")
        df_tramos = query_df("""
            SELECT ea.nombre AS origen, eb.nombre AS destino,
                   t.distancia_km, t.tiempo_estimado_min
              FROM transmetro.tramo t
              JOIN transmetro.estacion ea ON ea.estacion_id = t.estacion_origen_id
              JOIN transmetro.estacion eb ON eb.estacion_id = t.estacion_destino_id
             ORDER BY ea.nombre, eb.nombre;
        """)
        st.dataframe(df_tramos, use_container_width=True, hide_index=True)
