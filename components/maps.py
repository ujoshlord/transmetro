"""
Visualización geográfica interactiva para Transmetro con PyDeck y Streamlit.
Dibuja las líneas de ruta, estaciones, conexiones y parqueos.
"""
import pydeck as pdk
import pandas as pd
import streamlit as st
from configfile import DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_ZOOM
from db_connection import query_df

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    return [r, g, b, 220]

def get_map_data(selected_linea_id: int = None):
    """Obtiene los datos geoespaciales de estaciones y rutas ordenadas."""
    # Estaciones con coordenadas y líneas
    sql_estaciones = """
        SELECT e.estacion_id, e.codigo, e.nombre, e.latitud, e.longitud,
               m.nombre AS municipalidad,
               string_agg(DISTINCT l.codigo, ', ' ORDER BY l.codigo) AS lineas,
               COUNT(DISTINCT a.acceso_id) AS total_accesos,
               COUNT(DISTINCT p.parqueo_id) AS total_parqueos
          FROM transmetro.estacion e
          JOIN transmetro.municipalidad m ON m.municipalidad_id = e.municipalidad_id
          LEFT JOIN transmetro.linea_estacion le ON le.estacion_id = e.estacion_id
          LEFT JOIN transmetro.linea l ON l.linea_id = le.linea_id
          LEFT JOIN transmetro.acceso a ON a.estacion_id = e.estacion_id AND a.activo
          LEFT JOIN transmetro.parqueo p ON p.estacion_id = e.estacion_id
         WHERE e.latitud IS NOT NULL AND e.longitud IS NOT NULL
         GROUP BY e.estacion_id, e.codigo, e.nombre, e.latitud, e.longitud, m.nombre;
    """
    df_estaciones = query_df(sql_estaciones)
    
    # Rutas ordenadas por línea para trazar los caminos
    sql_rutas = """
        SELECT l.linea_id, l.codigo AS linea_codigo, l.nombre AS linea_nombre, l.color,
               le.orden, e.estacion_id, e.nombre AS estacion_nombre,
               e.latitud, e.longitud
          FROM transmetro.linea l
          JOIN transmetro.linea_estacion le ON le.linea_id = l.linea_id
          JOIN transmetro.estacion e ON e.estacion_id = le.estacion_id
         WHERE e.latitud IS NOT NULL AND e.longitud IS NOT NULL
         ORDER BY l.linea_id, le.orden;
    """
    df_rutas = query_df(sql_rutas)
    
    if selected_linea_id is not None:
        df_rutas = df_rutas[df_rutas["linea_id"] == selected_linea_id]
        est_ids = df_rutas["estacion_id"].unique()
        df_estaciones = df_estaciones[df_estaciones["estacion_id"].isin(est_ids)]
        
    return df_estaciones, df_rutas

def render_transmetro_map(selected_linea_id: int = None, height: int = 500):
    """Renderiza el mapa de la red con PyDeck en Streamlit."""
    df_estaciones, df_rutas = get_map_data(selected_linea_id)
    
    if df_estaciones.empty:
        st.warning("No hay estaciones con coordenadas para visualizar en el mapa.")
        return
    
    # Forzar coordenadas a float puro (vital si psycopg2 / SQLALchemy las trajo como Decimal)
    df_estaciones["latitud"] = df_estaciones["latitud"].astype(float)
    df_estaciones["longitud"] = df_estaciones["longitud"].astype(float)
    
    # Crear una única columna de lista [longitud, latitud] que es la que PyDeck nunca falla en leer
    df_estaciones["coordinates"] = df_estaciones.apply(
        lambda row: [row["longitud"], row["latitud"]], axis=1
    )
    

    # Convertir las rutas en segmentos de caminos para PathLayer
    paths_data = []
    for linea_cod, group in df_rutas.groupby("linea_codigo"):
        group_sorted = group.sort_values("orden")
        # Asegurar float en rutas también
        coords = group_sorted[["longitud", "latitud"]].astype(float).values.tolist()
        if len(coords) >= 2:
            paths_data.append({
                "linea": linea_cod,
                "nombre": group_sorted["linea_nombre"].iloc[0],
                "path": coords,
                "color": hex_to_rgb(group_sorted["color"].iloc[0])
            })
    
    df_paths = pd.DataFrame(paths_data)
    layers = []
    
    # Capa de trazo de rutas (PathLayer) - pickable=False
    if not df_paths.empty:
        path_layer = pdk.Layer(
            "PathLayer",
            df_paths,
            get_path="path",
            get_color="color",
            width_scale=20,
            width_min_pixels=4,
            width_max_pixels=8,
            pickable=False
        )
        layers.append(path_layer)
        
    # Capa de etiquetas de texto (TextLayer)
    text_layer = pdk.Layer(
        "TextLayer",
        df_estaciones,
        get_position="coordinates",
        get_text="nombre",
        get_size=11,
        get_color=[30, 30, 30, 240],
        get_angle=0,
        get_text_anchor="'start'",
        get_alignment_baseline="'center'",
        get_pixel_offset=[12, -4],
        pickable=False
    )
    layers.append(text_layer)
        
    # Capa de puntos (ScatterplotLayer)
    df_estaciones["fill_color"] = df_estaciones["lineas"].apply(
        lambda l: [41, 128, 185, 230] if l == "Ninguna" or "," not in str(l) else [46, 204, 113, 230]
    )
    df_estaciones["radius"] = df_estaciones["lineas"].apply(
        lambda l: 65 if l == "Ninguna" or "," not in str(l) else 90
    )
    
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        df_estaciones,
        get_position="coordinates",
        get_color="fill_color",
        get_radius="radius",
        radius_min_pixels=6,
        radius_max_pixels=15,
        pickable=True,
        stroked=True,
        get_line_color=[255, 255, 255, 255],
        get_line_width=2,
        line_width_min_pixels=1
    )
    layers.append(scatter_layer)
    
    # Centro del mapa
    center_lat = float(df_estaciones["latitud"].mean())
    center_lon = float(df_estaciones["longitud"].mean())
    
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=DEFAULT_ZOOM,
        pitch=0,
        bearing=0
    )
    
    # Configuración del Tooltip
    tooltip = {
        "html": """
            <div style="font-family: sans-serif; padding: 6px 10px; font-size: 12px;">
                <b style="font-size: 14px; color: #2C5364;">{nombre} ({codigo})</b><br/>
                <b>Municipalidad:</b> {municipalidad}<br/>
                <b>Líneas asignadas:</b> <span style="color: #27ae60;">{lineas}</span><br/>
                <b>Total de Accesos:</b> {total_accesos}<br/>
                <b>Parqueos asociados:</b> {total_parqueos}
            </div>
        """,
        "style": {
            "backgroundColor": "rgba(255, 255, 255, 0.95)",
            "color": "#333",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.15)",
            "borderRadius": "6px",
            "border": "1px solid #ccc"
        }
    }
    
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="light"
    )

    html_badges = []

    for item in paths_data:
        nombre = item["nombre"]
        r, g, b, _ = item["color"]  # Desempaquetamos el RGB obtenido de hex_to_rgb

        # Creamos un diseño de etiqueta (badge) personalizado con el color dinámico
        badge_html = f"""
        <span style="
            background-color: rgba({r}, {g}, {b}, 0.15); 
            color: rgb({r}, {g}, {b}); 
            padding: 3px 8px; 
            border-radius: 6px; 
            font-size: 0.9rem;
            font-weight: 600;
            display: inline-block;
            margin: 3px;
            border: 1px solid rgba({r}, {g}, {b}, 0.4);
        ">
             {nombre}
        </span>
        """
        html_badges.append(badge_html)

    contenedor_html = f"""
    <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px;">
        {"".join(html_badges)}
    </div>
    """

    resultado_final = "".join(contenedor_html)


    st.html(resultado_final)    
    st.pydeck_chart(deck, height=height, use_container_width=True)
