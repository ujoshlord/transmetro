"""
Módulo de Estaciones y Accesos.
Requerimientos: R2, R3, R8, R10, R11.
"""
import streamlit as st
import pandas as pd
from db_connection import query_df, execute_stmt, get_connection
from components.ui_helpers import render_header, render_rule_badge
from auth import has_permission

def render():
    render_header(
        title="Estaciones y Accesos",
        subtitle="Pertenencia multi-línea, accesos por estación, relación con municipalidades y seguridad",
        icon="🚪"
    )
    render_rule_badge("R2, R3, R8, R10, R11", "Estaciones en múltiples líneas, accesos exclusivos por estación, consulta de accesos por línea y guardias por acceso.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏢 Directorio de Estaciones (R2, R11)",
        "🔍 Accesos por Línea (R8)",
        "🚪 Accesos y Seguridad por Estación (R3, R10)",
        "➕ Registrar Estación"
    ])

    # --- PESTAÑA 1: DIRECTORIO DE ESTACIONES ---
    with tab1:
        st.subheader("Estaciones de la Red Transmetro")
        df_est = query_df("SELECT * FROM transmetro.vw_estacion_lineas ORDER BY codigo;")
        
        # Filtro de búsqueda
        filtro_txt = st.text_input("Filtrar estación por nombre o código:", placeholder="Ej. Trébol, Centra, E02")
        if filtro_txt:
            df_est = df_est[
                df_est['nombre'].str.contains(filtro_txt, case=False, na=False) |
                df_est['codigo'].str.contains(filtro_txt, case=False, na=False)
            ]
            
        st.dataframe(
            df_est[['codigo', 'nombre', 'municipalidad', 'total_lineas', 'lineas', 'total_accesos', 'total_parqueos']],
            use_container_width=True,
            hide_index=True
        )

        st.caption("ℹ️ Nota R2: Estaciones como **El Trébol (E02)** pertenecen a múltiples líneas (L12 y L13) facilitando el trasbordo.")

    # --- PESTAÑA 2: ACCESOS POR LÍNEA (R8) ---
    with tab2:
        st.subheader("R8: Catálogo Completo de Accesos de Cada Línea")
        
        # Resumen general de accesos por línea
        df_resumen = query_df("SELECT * FROM transmetro.vw_resumen_accesos_linea ORDER BY linea_codigo;")
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        # Filtro por línea específica
        lineas = query_df("SELECT linea_id, codigo, nombre FROM transmetro.linea ORDER BY codigo;")
        linea_sel = st.selectbox("Seleccione Línea para ver el detalle de sus accesos:", lineas['codigo'].tolist())
        
        df_accesos_linea = query_df("""
            SELECT orden_estacion, estacion, acceso_codigo, acceso, tipo, ubicacion,
                   horario_apertura, horario_cierre, activo
              FROM transmetro.vw_accesos_por_linea
             WHERE linea_codigo = %s
             ORDER BY orden_estacion, acceso_codigo;
        """, (linea_sel,))
        
        st.dataframe(df_accesos_linea, use_container_width=True, hide_index=True)

    # --- PESTAÑA 3: ACCESOS Y SEGURIDAD POR ESTACIÓN (R3, R10) ---
    with tab3:
        st.subheader("Accesos por Estación y Asignación de Guardias (R3, R10)")
        
        estaciones_list = query_df("SELECT estacion_id, codigo, nombre FROM transmetro.estacion ORDER BY codigo;")
        est_dict = {f"{r['codigo']} - {r['nombre']}": r['estacion_id'] for _, r in estaciones_list.iterrows()}
        sel_est = st.selectbox("Seleccione Estación:", list(est_dict.keys()), key="est_acc_sel")
        sel_est_id = est_dict[sel_est]

        df_guardias_acc = query_df("""
            SELECT acceso_codigo, acceso, guardias_vigentes, guardias, cumple_regla
              FROM transmetro.vw_guardias_por_acceso
             WHERE estacion_id = %s
             ORDER BY acceso_codigo;
        """, (sel_est_id,))
        
        if not df_guardias_acc.empty:
            st.dataframe(df_guardias_acc, use_container_width=True, hide_index=True)
        else:
            st.warning("Esta estación no tiene accesos registrados.")

        # Formulario para agregar un acceso a esta estación (R3)
        if has_permission("estaciones_accesos", "crear"):
            with st.expander("➕ Agregar Nuevo Acceso a esta Estación (R3)"):
                with st.form("form_nuevo_acceso"):
                    c1, c2 = st.columns(2)
                    with c1:
                        cod_acc = st.text_input("Código del Acceso:", placeholder="Ej. A-E02-4")
                        nom_acc = st.text_input("Nombre / Descripción:", placeholder="Ej. Acceso Calle Roosevelt Poniente")
                        tipo_acc = st.selectbox("Tipo de Acceso:", ["PEATONAL", "RAMPA", "ESCALERA", "ELEVADOR", "PASARELA"])
                    with c2:
                        ubi_acc = st.text_input("Ubicación exacta:", placeholder="Ej. Esquina 6ta avenida")
                        hora_ap = st.time_input("Horario Apertura:", value=pd.to_datetime("04:30").time())
                        hora_ci = st.time_input("Horario Cierre:", value=pd.to_datetime("22:00").time())
                    
                    sub_acc = st.form_submit_button("Guardar Acceso")
                    if sub_acc:
                        if not cod_acc or not nom_acc:
                            st.error("Código y nombre son obligatorios.")
                        else:
                            ok, msg, _ = execute_stmt("""
                                INSERT INTO transmetro.acceso (codigo, estacion_id, nombre, tipo, ubicacion, horario_apertura, horario_cierre)
                                VALUES (%s, %s, %s, %s, %s, %s, %s);
                            """, (cod_acc.strip().upper(), sel_est_id, nom_acc.strip(), tipo_acc, ubi_acc.strip(), hora_ap, hora_ci))
                            if ok:
                                st.success("Acceso creado exitosamente. Recuerde asignarle al menos un guardia (R10).")
                                st.rerun()
                            else:
                                st.error(f"Error al crear acceso: {msg}")

    # --- PESTAÑA 4: REGISTRAR NUEVA ESTACIÓN (R2, R11) ---
    with tab4:
        st.subheader("Registrar Nueva Estación")
        st.info("💡 **Regla R2:** Toda estación debe pertenecer al menos a una línea. Para cumplir la regla, seleccione la línea a la que pertenecerá inicialmente.")
        
        if has_permission("estaciones_accesos", "crear"):
            with st.form("form_nueva_estacion"):
                e_c1, e_c2 = st.columns(2)
                with e_c1:
                    cod_e = st.text_input("Código de Estación:", placeholder="Ej. E07")
                    nom_e = st.text_input("Nombre de Estación:", placeholder="Ej. Estación San Juan")
                    munis = query_df("SELECT municipalidad_id, nombre FROM transmetro.municipalidad ORDER BY nombre;")
                    muni_map = {r['nombre']: r['municipalidad_id'] for _, r in munis.iterrows()}
                    muni_sel = st.selectbox("Municipalidad Perteneciente (R11):", list(muni_map.keys()))
                with e_c2:
                    dir_e = st.text_input("Dirección:", placeholder="Ej. Calzada San Juan 15-40")
                    lat_e = st.number_input("Latitud:", value=14.630000, format="%.6f")
                    lon_e = st.number_input("Longitud:", value=-90.520000, format="%.6f")
                    
                    lineas_disp = query_df("SELECT linea_id, codigo, nombre FROM transmetro.linea ORDER BY codigo;")
                    lin_map = {f"{r['codigo']} - {r['nombre']}": r['linea_id'] for _, r in lineas_disp.iterrows()}
                    lin_sel = st.selectbox("Línea Inicial Obligatoria (R2):", list(lin_map.keys()))
                
                sub_e = st.form_submit_button("Crear Estación y Asignar a Línea")
                if sub_e:
                    if not cod_e or not nom_e:
                        st.error("Código y nombre son obligatorios.")
                    else:
                        # Ejecutar en transacción atómica (inserción de estación + línea_estacion)
                        with get_connection() as conn:
                            try:
                                with conn.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO transmetro.estacion (codigo, nombre, municipalidad_id, direccion, latitud, longitud)
                                        VALUES (%s, %s, %s, %s, %s, %s)
                                        RETURNING estacion_id;
                                    """, (cod_e.strip().upper(), nom_e.strip(), muni_map[muni_sel], dir_e.strip(), lat_e, lon_e))
                                    nueva_est_id = cur.fetchone()[0]
                                    
                                    # Obtener orden siguiente
                                    cur.execute("SELECT COALESCE(MAX(orden), 0) + 1 FROM transmetro.linea_estacion WHERE linea_id = %s;", (lin_map[lin_sel],))
                                    sig_orden = cur.fetchone()[0]
                                    
                                    cur.execute("""
                                        INSERT INTO transmetro.linea_estacion (linea_id, estacion_id, orden)
                                        VALUES (%s, %s, %s);
                                    """, (lin_map[lin_sel], nueva_est_id, sig_orden))
                                    conn.commit()
                                    st.success(f"Estación '{nom_e}' creada y asignada a la línea con orden {sig_orden}.")
                                    st.rerun()
                            except Exception as ex:
                                conn.rollback()
                                st.error(f"Error al registrar estación: {ex}")
        else:
            st.info("No cuenta con permisos para crear estaciones.")
