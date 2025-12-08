import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import base64
from io import BytesIO
from PIL import Image
import os
import tempfile
import sys

# PostgreSQL support
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="Caballebrios One",
    page_icon="👿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for clean aesthetic with larger tab text
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 4rem;
        padding: 0 2rem;
        background-color: #f0f2f6;
        border-radius: 8px;
        font-size: 1.2rem;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ff4b4b;
        color: white;
    }
    h1 {
        color: #1f1f1f;
        font-weight: 700;
    }
    h2 {
        color: #262730;
        font-weight: 600;
        margin-top: 2rem;
    }
    h3 {
        color: #31333F;
        font-weight: 500;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #ff4b4b;
    }
    .success-box {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Database setup
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None and PSYCOPG2_AVAILABLE

# Always use temp directory for SQLite to avoid read-only filesystem issues
DB_PATH = os.path.join(tempfile.gettempdir(), 'caballebrios.db')

def get_db_connection():
    """Get database connection (PostgreSQL if DATABASE_URL set, else SQLite).
    
    - PostgreSQL is preferred when DATABASE_URL environment variable is set.
    - SQLite fallback uses temp directory to avoid read-only filesystem issues.
    """
    if USE_POSTGRES:
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            return conn
        except Exception as e:
            # Log and continue - try SQLite fallback
            pass
    
    # Use SQLite (either as fallback or primary)
    return sqlite3.connect(DB_PATH)

def execute_query(c, query, params=None):
    """Execute query with proper parameter placeholders for both SQLite and PostgreSQL"""
    if params and USE_POSTGRES:
        # Convert ? to %s for PostgreSQL
        pg_query = query.replace('?', '%s')
        c.execute(pg_query, params)
    elif params:
        c.execute(query, params)
    else:
        c.execute(query)

def read_sql_query(query, conn, params=None):
    """Wrapper for pd.read_sql_query that handles SQLite vs PostgreSQL placeholder syntax.

    - Converts SQLite-style `?` placeholders to PostgreSQL `%s` when using Postgres.
    - Converts `GROUP_CONCAT(...)` to `string_agg(...)` for PostgreSQL.
    - Uses DATABASE_URL string URI with pandas for PostgreSQL (avoids psycopg2 warning).
    """
    if USE_POSTGRES:
        # PostgreSQL: convert SQLite syntax to PostgreSQL syntax
        pg_query = query.replace('?', '%s')
        pg_query = pg_query.replace('GROUP_CONCAT(', 'string_agg(')
        pg_query = pg_query.replace(", ', ')", ", ', ' ORDER BY 1)")
        
        # Use DATABASE_URL string URI with pandas to leverage SQLAlchemy and avoid psycopg2 warning
        try:
            return pd.read_sql_query(pg_query, DATABASE_URL, params=params)
        except Exception:
            # Fallback to using the raw psycopg2 connection
            return pd.read_sql_query(pg_query, conn, params=params)
    
    # SQLite path (default)
    return pd.read_sql_query(query, conn, params=params)

def init_db():
    """Initialize the database with all required tables"""
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        # PostgreSQL SQL syntax
        execute_query(c, '''CREATE TABLE IF NOT EXISTS players
                     (id SERIAL PRIMARY KEY,
                      name TEXT NOT NULL UNIQUE,
                      profile_pic BYTEA,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS seasons
                     (id SERIAL PRIMARY KEY,
                      name TEXT NOT NULL UNIQUE,
                      start_date DATE,
                      end_date DATE,
                      is_active INTEGER DEFAULT 0,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS games
                     (id SERIAL PRIMARY KEY,
                      name TEXT NOT NULL UNIQUE,
                      points_per_win INTEGER NOT NULL,
                      description TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS game_nights
                     (id SERIAL PRIMARY KEY,
                      season_id INTEGER NOT NULL,
                      date DATE NOT NULL,
                      notes TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (season_id) REFERENCES seasons(id))''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS game_rounds
                     (id SERIAL PRIMARY KEY,
                      game_night_id INTEGER NOT NULL,
                      game_id INTEGER NOT NULL,
                      round_number INTEGER NOT NULL,
                      notes TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (game_night_id) REFERENCES game_nights(id),
                      FOREIGN KEY (game_id) REFERENCES games(id))''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS round_winners
                     (id SERIAL PRIMARY KEY,
                      round_id INTEGER NOT NULL,
                      player_id INTEGER NOT NULL,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (round_id) REFERENCES game_rounds(id),
                      FOREIGN KEY (round_id) REFERENCES game_rounds(id),
                      FOREIGN KEY (player_id) REFERENCES players(id))''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS penalties
                     (id SERIAL PRIMARY KEY,
                      game_night_id INTEGER NOT NULL,
                      player_id INTEGER NOT NULL,
                      penalty_type TEXT NOT NULL,
                      amount REAL NOT NULL,
                      reason TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (game_night_id) REFERENCES game_nights(id),
                      FOREIGN KEY (player_id) REFERENCES players(id))''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS settings
                     (key TEXT PRIMARY KEY,
                      value TEXT NOT NULL)''')
    else:
        # SQLite SQL syntax
        execute_query(c, '''CREATE TABLE IF NOT EXISTS players
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL UNIQUE,
                      profile_pic BLOB,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS seasons
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL UNIQUE,
                      start_date DATE,
                      end_date DATE,
                      is_active BOOLEAN DEFAULT 1,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS games
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL UNIQUE,
                      points_per_win INTEGER NOT NULL,
                      description TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS game_nights
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      season_id INTEGER NOT NULL,
                      date DATE NOT NULL,
                      notes TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (season_id) REFERENCES seasons(id))''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS game_rounds
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      game_night_id INTEGER NOT NULL,
                      game_id INTEGER NOT NULL,
                      round_number INTEGER NOT NULL,
                      notes TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (game_night_id) REFERENCES game_nights(id),
                      FOREIGN KEY (game_id) REFERENCES games(id))''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS round_winners
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      round_id INTEGER NOT NULL,
                      player_id INTEGER NOT NULL,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (round_id) REFERENCES game_rounds(id),
                      FOREIGN KEY (player_id) REFERENCES players(id))''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS penalties
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      game_night_id INTEGER NOT NULL,
                      player_id INTEGER NOT NULL,
                      penalty_type TEXT NOT NULL,
                      amount REAL NOT NULL,
                      reason TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (game_night_id) REFERENCES game_nights(id),
                      FOREIGN KEY (player_id) REFERENCES players(id))''')
        
        execute_query(c, '''CREATE TABLE IF NOT EXISTS settings
                     (key TEXT PRIMARY KEY,
                      value TEXT NOT NULL)''')
    
    # Insert default penalty amount if not exists
    if USE_POSTGRES:
        execute_query(c, "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", 
                  ('default_penalty_amount', '10'))
    else:
        execute_query(c, "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                  ('default_penalty_amount', '10'))
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Helper functions
def get_active_season():
    """Get the currently active season"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        if USE_POSTGRES:
            execute_query(c, "SELECT id, name FROM seasons WHERE is_active = %s LIMIT 1", (1,))
        else:
            execute_query(c, "SELECT id, name FROM seasons WHERE is_active = ?", (1,))
        result = c.fetchone()
    except Exception as e:
        result = None
    finally:
        conn.close()
    return result


def image_to_bytes(image):
    """Convert PIL Image to bytes"""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return buffered.getvalue()

def bytes_to_image(byte_data):
    """Convert bytes to PIL Image"""
    return Image.open(BytesIO(byte_data))

def get_current_leaderboard(season_id):
    """Get real-time leaderboard for a season"""
    conn = get_db_connection()
    query = """
    SELECT 
        p.id,
        p.name,
        COALESCE(SUM(g.points_per_win), 0) as total_points,
        COUNT(DISTINCT rw.id) as total_wins
    FROM players p
    LEFT JOIN round_winners rw ON p.id = rw.player_id
    LEFT JOIN game_rounds gr ON rw.round_id = gr.id
    LEFT JOIN games g ON gr.game_id = g.id
    LEFT JOIN game_nights gn ON gr.game_night_id = gn.id
    WHERE gn.season_id = ? OR gn.season_id IS NULL
    GROUP BY p.id, p.name
    ORDER BY total_points DESC
    """
    leaderboard = read_sql_query(query, conn, params=(season_id,))
    conn.close()
    return leaderboard

# Main app
def main():
    st.title("🎮 Caballebrios One")
    st.markdown("### Sistema de Seguimiento de Noches de Juego")
    
    # Sidebar
    with st.sidebar:
        st.image("https://via.placeholder.com/200x200.png?text=Caballebrios", width=200)
        st.markdown("---")
        
        active_season = get_active_season()
        if active_season:
            st.success(f"**Temporada Activa:** {active_season[1]}")
        else:
            st.warning("Sin temporada activa")
        
        st.markdown("---")
        st.markdown("**Estadísticas Rápidas**")
        
        conn = get_db_connection()
        total_players = read_sql_query("SELECT COUNT(*) as count FROM players", conn)['count'][0]
        total_games = read_sql_query("SELECT COUNT(*) as count FROM games", conn)['count'][0]
        total_nights = read_sql_query("SELECT COUNT(*) as count FROM game_nights", conn)['count'][0]
        conn.close()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Jugadores", total_players)
        col2.metric("Juegos", total_games)
        col3.metric("Noches", total_nights)
        
        st.markdown("---")
        st.caption(f"📁 Base de datos: `{DB_PATH}`")
    
    # Main tabs with bigger text - REORDERED
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🎯 Tablero",
        "🌙 Noches de Juego",
        "📊 Reportes",
        "🎲 Juegos",
        "📅 Temporadas",
        "👥 Jugadores",
        "⚙️ Admin"
    ])
    
    with tab1:
        show_dashboard()
    
    with tab2:
        manage_game_nights()
    
    with tab3:
        show_reports()
    
    with tab4:
        manage_games()
    
    with tab5:
        manage_seasons()
    
    with tab6:
        manage_players()
    
    with tab7:
        show_admin()

def show_dashboard():
    """Show main dashboard with overview"""
    st.header("Tablero")
    
    active_season = get_active_season()
    if not active_season:
        st.warning("⚠️ ¡Por favor crea y activa una temporada primero!")
        return
    
    conn = get_db_connection()
    
    # Current season leaderboard
    st.subheader(f"🏆 Tabla de Posiciones - {active_season[1]}")
    
    leaderboard = get_current_leaderboard(active_season[0])
    
    if not leaderboard.empty and leaderboard['total_points'].sum() > 0:
        # Display top 3 in columns
        col1, col2, col3 = st.columns(3)
        
        medals = ["🥈", "🥇", "🥉"]
        cols = [col1, col2, col3]
        
        for idx in range(min(3, len(leaderboard))):
            with cols[idx]:
                st.markdown(f"### {medals[idx]} {leaderboard.iloc[idx]['name']}")
                st.metric("Puntos", int(leaderboard.iloc[idx]['total_points']))
                st.caption(f"{int(leaderboard.iloc[idx]['total_wins'])} victorias")
        
        st.markdown("---")
        st.dataframe(leaderboard[['name', 'total_points', 'total_wins']], 
                    width='stretch', hide_index=True,
                    column_config={
                        "name": "Jugador",
                        "total_points": "Puntos Totales",
                        "total_wins": "Victorias"
                    })
    else:
        st.info("¡No hay juegos registrados para esta temporada!")
    
    # Recent activity
    st.subheader("📅 Noches de Juego Recientes")
    
    recent_nights = read_sql_query("""
        SELECT 
            gn.date as fecha,
            gn.notes as notas,
            COUNT(DISTINCT gr.id) as rondas_jugadas,
            COUNT(DISTINCT gr.game_id) as juegos_unicos
        FROM game_nights gn
        LEFT JOIN game_rounds gr ON gn.id = gr.game_night_id
        WHERE gn.season_id = ?
         GROUP BY gn.id, gn.date, gn.notes
        ORDER BY gn.date DESC
        LIMIT 5
    """, conn, params=(active_season[0],))
    
    if not recent_nights.empty:
        st.dataframe(recent_nights, width='stretch', hide_index=True)
    else:
        st.info("¡No hay noches de juego registradas!")
    
    conn.close()

def manage_players():
    """Manage players section"""
    st.header("👥 Gestión de Jugadores")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Agregar Nuevo Jugador")
        with st.form("add_player_form"):
            player_name = st.text_input("Nombre del Jugador")
            uploaded_file = st.file_uploader("Foto de Perfil (opcional)", type=['png', 'jpg', 'jpeg'])
            
            submitted = st.form_submit_button("Agregar Jugador")
            
            if submitted and player_name:
                conn = get_db_connection()
                c = conn.cursor()
                
                try:
                    profile_pic = None
                    if uploaded_file:
                        image = Image.open(uploaded_file)
                        # Resize to standard size
                        image.thumbnail((200, 200))
                        profile_pic = image_to_bytes(image)
                    
                    execute_query(c, "INSERT INTO players (name, profile_pic) VALUES (?, ?)",
                             (player_name, profile_pic))
                    conn.commit()
                    st.success(f"✅ ¡Jugador '{player_name}' agregado!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("⚠️ ¡El nombre del jugador ya existe!")
                finally:
                    conn.close()
    
    with col2:
        st.subheader("Jugadores Actuales")
        
        conn = get_db_connection()
        players = read_sql_query("SELECT id, name, profile_pic FROM players ORDER BY name", conn)
        conn.close()
        
        if not players.empty:
            # Display players in a grid
            cols = st.columns(4)
            for idx, row in players.iterrows():
                with cols[idx % 4]:
                    if row['profile_pic']:
                        img = bytes_to_image(row['profile_pic'])
                        st.image(img, width=100)
                    else:
                        st.markdown("👤")
                    st.markdown(f"**{row['name']}**")
        else:
            st.info("¡No hay jugadores agregados!")

def manage_seasons():
    """Manage seasons section"""
    st.header("📅 Gestión de Temporadas")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Crear Nueva Temporada")
        with st.form("add_season_form"):
            season_name = st.text_input("Nombre de la Temporada", placeholder="ej., Temporada 2, Invierno 2024")
            start_date = st.date_input("Fecha de Inicio")
            end_date = st.date_input("Fecha de Fin (opcional)", value=None)
            make_active = st.checkbox("Establecer como temporada activa", value=True)
            
            submitted = st.form_submit_button("Crear Temporada")
            
            if submitted and season_name:
                conn = get_db_connection()
                c = conn.cursor()
                
                try:
                    # If making this active, deactivate others
                    if make_active:
                        execute_query(c, "UPDATE seasons SET is_active = 0")
                    
                    execute_query(c, """INSERT INTO seasons (name, start_date, end_date, is_active) 
                                VALUES (?, ?, ?, ?)""",
                             (season_name, start_date, end_date, 1 if make_active else 0))
                    conn.commit()
                    st.success(f"✅ ¡Temporada '{season_name}' creada!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("⚠️ ¡El nombre de temporada ya existe!")
                finally:
                    conn.close()
    
    with col2:
        st.subheader("Todas las Temporadas")
        
        conn = get_db_connection()
        seasons = read_sql_query("""
            SELECT id, name, start_date, end_date, is_active 
            FROM seasons 
            ORDER BY start_date DESC
        """, conn)
        
        if not seasons.empty:
            for _, season in seasons.iterrows():
                with st.expander(f"{'🟢 ' if season['is_active'] else '⚪ '}{season['name']}", 
                               expanded=season['is_active']):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.write(f"**Inicio:** {season['start_date']}")
                    col_b.write(f"**Fin:** {season['end_date'] or 'En curso'}")
                    
                    if not season['is_active']:
                        if st.button("Activar", key=f"activate_{season['id']}"):
                            c = conn.cursor()
                            execute_query(c, "UPDATE seasons SET is_active = 0")
                            execute_query(c, "UPDATE seasons SET is_active = 1 WHERE id = ?", (season['id'],))
                            conn.commit()
                            st.success("¡Temporada activada!")
                            st.rerun()
        else:
            st.info("¡No hay temporadas creadas!")
        
        conn.close()

def manage_games():
    """Manage games section"""
    st.header("🎲 Gestión de Juegos")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Agregar Nuevo Juego")
        with st.form("add_game_form"):
            game_name = st.text_input("Nombre del Juego")
            points_per_win = st.number_input("Puntos por Victoria", min_value=1, value=10, step=1)
            description = st.text_area("Condiciones de Victoria / Descripción")
            
            submitted = st.form_submit_button("Agregar Juego")
            
            if submitted and game_name:
                conn = get_db_connection()
                c = conn.cursor()
                
                try:
                    execute_query(c, """INSERT INTO games (name, points_per_win, description) 
                                VALUES (?, ?, ?)""",
                             (game_name, points_per_win, description))
                    conn.commit()
                    st.success(f"✅ ¡Juego '{game_name}' agregado!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("⚠️ ¡El nombre del juego ya existe!")
                finally:
                    conn.close()
    
    with col2:
        st.subheader("Todos los Juegos")
        
        conn = get_db_connection()
        games = read_sql_query("SELECT * FROM games ORDER BY name", conn)
        conn.close()
        
        if not games.empty:
            for _, game in games.iterrows():
                with st.expander(f"🎲 {game['name']} ({game['points_per_win']} pts)"):
                    st.write(f"**Puntos por Victoria:** {game['points_per_win']}")
                    st.write(f"**Descripción:** {game['description'] or 'Sin descripción'}")
                    
                    # Edit functionality
                    with st.form(f"edit_game_{game['id']}"):
                        new_points = st.number_input("Actualizar Puntos", value=int(game['points_per_win']), 
                                                    min_value=1, key=f"pts_{game['id']}")
                        new_desc = st.text_area("Actualizar Descripción", value=game['description'] or "",
                                               key=f"desc_{game['id']}")
                        
                        if st.form_submit_button("Actualizar"):
                            conn = get_db_connection()
                            c = conn.cursor()
                            execute_query(c, """UPDATE games 
                                       SET points_per_win = ?, description = ? 
                                       WHERE id = ?""",
                                     (new_points, new_desc, game['id']))
                            conn.commit()
                            conn.close()
                            st.success("¡Juego actualizado!")
                            st.rerun()
        else:
            st.info("¡No hay juegos agregados!")

def manage_game_nights():
    """Manage game nights section - IMPROVED VERSION"""
    st.header("🌙 Gestión de Noches de Juego")
    
    active_season = get_active_season()
    if not active_season:
        st.warning("⚠️ ¡Por favor crea y activa una temporada primero!")
        return
    
    st.info(f"Registrando para: **{active_season[1]}**")
    
    conn = get_db_connection()
    
    # Get all players and games for dropdowns
    players = read_sql_query("SELECT id, name FROM players ORDER BY name", conn)
    games = read_sql_query("SELECT id, name, points_per_win FROM games ORDER BY name", conn)
    
    if players.empty:
        st.error("⚠️ ¡Primero debes agregar jugadores en la pestaña 'Jugadores'!")
        conn.close()
        return
    
    if games.empty:
        st.error("⚠️ ¡Primero debes agregar juegos en la pestaña 'Juegos'!")
        conn.close()
        return
    
    # Create or select game night
    st.subheader("1️⃣ Seleccionar o Crear Noche de Juego")
    
    # Get recent game nights
    recent_nights = read_sql_query("""
        SELECT id, date, notes 
        FROM game_nights 
        WHERE season_id = ?
        ORDER BY date DESC
        LIMIT 10
    """, conn, params=(active_season[0],))
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not recent_nights.empty:
            night_options = ["➕ Crear nueva noche de juego"] + [
                f"{row['date']} - {row['notes'] or 'Sin notas'}" 
                for _, row in recent_nights.iterrows()
            ]
            selected_night = st.selectbox("Seleccionar noche de juego", night_options)
            
            if selected_night == "➕ Crear nueva noche de juego":
                selected_night_id = None
            else:
                night_idx = night_options.index(selected_night) - 1
                selected_night_id = recent_nights.iloc[night_idx]['id']
        else:
            st.info("No hay noches de juego. Crea una nueva abajo.")
            selected_night_id = None
    
    with col2:
        if selected_night_id is None:
            with st.form("create_night_form"):
                night_date = st.date_input("Fecha", value=datetime.now())
                notes = st.text_input("Notas (opcional)")
                
                if st.form_submit_button("Crear Noche de Juego"):
                    c = conn.cursor()
                    execute_query(c, """INSERT INTO game_nights (season_id, date, notes) 
                                VALUES (?, ?, ?)""",
                             (active_season[0], night_date, notes))
                    conn.commit()
                    st.success("✅ ¡Noche de juego creada!")
                    st.rerun()
    
    # If we have a selected night, show game recording interface
    if selected_night_id:
        st.markdown("---")
        st.subheader("2️⃣ Registrar Juego y Ganadores")
        
        # Show current scoreboard for this night
        night_scores = read_sql_query("""
            SELECT 
                p.name as jugador,
                COUNT(DISTINCT rw.id) as victorias,
                COALESCE(SUM(g.points_per_win), 0) as puntos
            FROM players p
            LEFT JOIN round_winners rw ON p.id = rw.player_id
            LEFT JOIN game_rounds gr ON rw.round_id = gr.id
            LEFT JOIN games g ON gr.game_id = g.id
            WHERE gr.game_night_id = ?
            GROUP BY p.id, p.name
            ORDER BY puntos DESC
        """, conn, params=(selected_night_id,))
        
        if not night_scores.empty:
            st.success("🏆 **Marcador de Esta Noche**")
            col1, col2, col3, col4 = st.columns(4)
            for idx, row in night_scores.iterrows():
                with [col1, col2, col3, col4][idx % 4]:
                    st.metric(row['jugador'], f"{int(row['puntos'])} pts", 
                             f"{int(row['victorias'])} victorias")
        
        st.markdown("---")
        
        # Game recording form
        with st.form("record_game_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                selected_game = st.selectbox(
                    "Juego Jugado", 
                    options=games['id'].tolist(),
                    format_func=lambda x: f"{games[games['id']==x]['name'].values[0]} ({games[games['id']==x]['points_per_win'].values[0]} pts)"
                )
                
                round_number = st.number_input("Número de Ronda", min_value=1, value=1, step=1)
            
            with col2:
                winners = st.multiselect(
                    "Ganador(es)", 
                    options=players['id'].tolist(),
                    format_func=lambda x: players[players['id']==x]['name'].values[0]
                )
            
            submitted = st.form_submit_button("✅ Registrar Juego")
            
            if submitted:
                if not winners:
                    st.error("⚠️ Debes seleccionar al menos un ganador")
                else:
                    c = conn.cursor()
                    
                    # Insert round
                    execute_query(c, """INSERT INTO game_rounds (game_night_id, game_id, round_number) 
                               VALUES (?, ?, ?)""",
                             (selected_night_id, selected_game, round_number))
                    round_id = c.lastrowid
                    
                    # Insert winners
                    for winner_id in winners:
                        execute_query(c, "INSERT INTO round_winners (round_id, player_id) VALUES (?, ?)",
                                (round_id, winner_id))
                    
                    conn.commit()
                    
                    # Get game name and points for success message
                    game_info = games[games['id']==selected_game].iloc[0]
                    winner_names = [players[players['id']==w]['name'].values[0] for w in winners]
                    
                    st.success(f"✅ ¡Registrado! {', '.join(winner_names)} ganó {game_info['name']} (+{game_info['points_per_win']} pts cada uno)")
                    st.rerun()
        
        # Show games played this night
        st.markdown("---")
        st.subheader("📋 Juegos Jugados Esta Noche")
        
        rounds_played = read_sql_query("""
            SELECT 
                g.name as juego,
                gr.round_number as ronda,
                GROUP_CONCAT(p.name, ', ') as ganadores,
                g.points_per_win as puntos
            FROM game_rounds gr
            JOIN games g ON gr.game_id = g.id
            LEFT JOIN round_winners rw ON gr.id = rw.round_id
            LEFT JOIN players p ON rw.player_id = p.id
            WHERE gr.game_night_id = ?
             GROUP BY gr.id, g.name, gr.round_number, g.points_per_win
            ORDER BY gr.created_at DESC
        """, conn, params=(selected_night_id,))
        
        if not rounds_played.empty:
            st.dataframe(rounds_played, width='stretch', hide_index=True)
        else:
            st.info("No se han registrado juegos aún para esta noche.")
        
        # Penalties section
        st.markdown("---")
        st.subheader("💰 Registrar Penalización")
        
        default_penalty = float(read_sql_query(
            "SELECT value FROM settings WHERE key = 'default_penalty_amount'", 
            conn)['value'][0])
        
        with st.form("penalty_form"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                penalized_player = st.selectbox(
                    "Jugador", 
                    options=players['id'].tolist(),
                    format_func=lambda x: players[players['id']==x]['name'].values[0]
                )
            
            with col2:
                penalty_type = st.selectbox("Tipo", ["Ausencia", "Personalizada"])
            
            with col3:
                penalty_amount = st.number_input("Monto", value=default_penalty, step=0.5)
            
            penalty_reason = st.text_input("Razón (para penalizaciones personalizadas)")
            
            if st.form_submit_button("Registrar Penalización"):
                c = conn.cursor()
                execute_query(c, """INSERT INTO penalties 
                           (game_night_id, player_id, penalty_type, amount, reason) 
                           VALUES (?, ?, ?, ?, ?)""",
                         (selected_night_id, penalized_player, penalty_type, 
                          penalty_amount, penalty_reason))
                conn.commit()
                st.success("✅ ¡Penalización registrada!")
                st.rerun()
        
        # Show penalties for this night
        penalties_tonight = read_sql_query("""
            SELECT 
                p.name as jugador,
                pen.penalty_type as tipo,
                pen.amount as monto,
                pen.reason as razon
            FROM penalties pen
            JOIN players p ON pen.player_id = p.id
            WHERE pen.game_night_id = ?
            ORDER BY pen.created_at DESC
        """, conn, params=(selected_night_id,))
        
        if not penalties_tonight.empty:
            st.markdown("**Penalizaciones Esta Noche:**")
            st.dataframe(penalties_tonight, width='stretch', hide_index=True)
    
    conn.close()

def show_reports():
    """Show comprehensive reports and statistics"""
    st.header("📊 Reportes y Estadísticas")
    
    active_season = get_active_season()
    if not active_season:
        st.warning("⚠️ ¡Por favor crea y activa una temporada primero!")
        return
    
    conn = get_db_connection()
    
    # Season leaderboard with detailed stats
    st.subheader("🏆 Tabla de Posiciones de Temporada")
    
    leaderboard_query = """
    SELECT 
        p.name as jugador,
        COALESCE(SUM(g.points_per_win), 0) as puntos_totales,
        COUNT(DISTINCT rw.id) as victorias_totales,
        COUNT(DISTINCT gr.game_id) as juegos_unicos,
        COUNT(DISTINCT gr.game_night_id) as noches_asistidas,
        COALESCE(SUM(pen.amount), 0) as penalizaciones_totales
    FROM players p
    LEFT JOIN round_winners rw ON p.id = rw.player_id
    LEFT JOIN game_rounds gr ON rw.round_id = gr.id
    LEFT JOIN games g ON gr.game_id = g.id
    LEFT JOIN game_nights gn ON gr.game_night_id = gn.id AND gn.season_id = ?
    LEFT JOIN penalties pen ON p.id = pen.player_id AND pen.game_night_id IN 
        (SELECT id FROM game_nights WHERE season_id = ?)
    GROUP BY p.id, p.name
    ORDER BY puntos_totales DESC
    """
    
    leaderboard = read_sql_query(leaderboard_query, conn, params=(active_season[0], active_season[0]))
    
    if not leaderboard.empty and leaderboard['puntos_totales'].sum() > 0:
        st.dataframe(leaderboard, width='stretch', hide_index=True)
        
        # Points progression chart
        st.subheader("📈 Progresión de Puntos")
        
        progression_query = """
        SELECT 
            p.name,
            gn.date as fecha,
            SUM(g.points_per_win) OVER (PARTITION BY p.id ORDER BY gn.date, gr.id) as puntos_acumulados
        FROM players p
        JOIN round_winners rw ON p.id = rw.player_id
        JOIN game_rounds gr ON rw.round_id = gr.id
        JOIN games g ON gr.game_id = g.id
        JOIN game_nights gn ON gr.game_night_id = gn.id
        WHERE gn.season_id = ?
        ORDER BY gn.date, p.name
        """
        
        progression = read_sql_query(progression_query, conn, params=(active_season[0],))
        
        if not progression.empty:
            fig = px.line(progression, x='fecha', y='puntos_acumulados', color='name',
                         title='Puntos Acumulados en el Tiempo',
                         labels={'fecha': 'Fecha', 'puntos_acumulados': 'Puntos', 'name': 'Jugador'},
                         markers=True)
            fig.update_layout(height=500, hovermode='x unified')
            st.plotly_chart(fig, width='stretch')
        
        # Best game for each player
        st.subheader("🎯 Mejor Juego por Jugador")
        
        best_game_query = """
        SELECT 
            p.name as jugador,
            g.name as mejor_juego,
            COUNT(*) as victorias,
            COUNT(*) * g.points_per_win as puntos_ganados
        FROM players p
        JOIN round_winners rw ON p.id = rw.player_id
        JOIN game_rounds gr ON rw.round_id = gr.id
        JOIN games g ON gr.game_id = g.id
        JOIN game_nights gn ON gr.game_night_id = gn.id
        WHERE gn.season_id = ?
        GROUP BY p.id, g.id
        HAVING victorias = (
            SELECT MAX(win_count) FROM (
                SELECT COUNT(*) as win_count
                FROM round_winners rw2
                JOIN game_rounds gr2 ON rw2.round_id = gr2.id
                JOIN game_nights gn2 ON gr2.game_night_id = gn2.id
                WHERE rw2.player_id = p.id AND gn2.season_id = ?
                GROUP BY gr2.game_id
            )
        )
        ORDER BY puntos_ganados DESC
        """
        
        best_games = read_sql_query(best_game_query, conn, params=(active_season[0], active_season[0]))
        
        if not best_games.empty:
            st.dataframe(best_games, width='stretch', hide_index=True)
        
        # Game popularity
        st.subheader("🎲 Popularidad de Juegos")
        
        game_stats = read_sql_query("""
            SELECT 
                g.name as juego,
                COUNT(DISTINCT gr.id) as veces_jugado,
                COUNT(DISTINCT rw.player_id) as ganadores_unicos
            FROM games g
            JOIN game_rounds gr ON g.id = gr.game_id
            JOIN game_nights gn ON gr.game_night_id = gn.id
            LEFT JOIN round_winners rw ON gr.id = rw.round_id
            WHERE gn.season_id = ?
             GROUP BY g.id, g.name
            ORDER BY veces_jugado DESC
        """, conn, params=(active_season[0],))
        
        if not game_stats.empty:
            fig = px.bar(game_stats, x='juego', y='veces_jugado',
                        title='Juegos Más Jugados',
                        labels={'juego': 'Juego', 'veces_jugado': 'Veces Jugado'},
                        color='veces_jugado',
                        color_continuous_scale='Reds')
            st.plotly_chart(fig, width='stretch')
        
        # Win distribution pie chart
        st.subheader("🥧 Distribución de Victorias")
        
        win_dist = read_sql_query("""
            SELECT 
                p.name as jugador,
                COUNT(*) as victorias
            FROM players p
            JOIN round_winners rw ON p.id = rw.player_id
            JOIN game_rounds gr ON rw.round_id = gr.id
            JOIN game_nights gn ON gr.game_night_id = gn.id
            WHERE gn.season_id = ?
             GROUP BY p.id, p.name
        """, conn, params=(active_season[0],))
        
        if not win_dist.empty:
            fig = px.pie(win_dist, values='victorias', names='jugador',
                        title='Distribución Total de Victorias',
                        color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig, width='stretch')
        
        # Attendance tracking
        st.subheader("📅 Asistencia")
        
        attendance = read_sql_query("""
            SELECT 
                p.name as jugador,
                COUNT(DISTINCT gn.id) as noches_asistidas,
                (SELECT COUNT(*) FROM game_nights WHERE season_id = ?) as total_noches,
                ROUND(COUNT(DISTINCT gn.id) * 100.0 / 
                    (SELECT COUNT(*) FROM game_nights WHERE season_id = ?), 1) as tasa_asistencia
            FROM players p
            LEFT JOIN round_winners rw ON p.id = rw.player_id
            LEFT JOIN game_rounds gr ON rw.round_id = gr.id
            LEFT JOIN game_nights gn ON gr.game_night_id = gn.id AND gn.season_id = ?
            GROUP BY p.id
            ORDER BY tasa_asistencia DESC
        """, conn, params=(active_season[0], active_season[0], active_season[0]))
        
        if not attendance.empty:
            fig = px.bar(attendance, x='jugador', y='tasa_asistencia',
                        title='Tasa de Asistencia (%)',
                        labels={'jugador': 'Jugador', 'tasa_asistencia': 'Asistencia %'},
                        color='tasa_asistencia',
                        color_continuous_scale='Greens')
            st.plotly_chart(fig, width='stretch')
        
        # Penalties summary
        st.subheader("💰 Resumen de Penalizaciones")
        
        penalties = read_sql_query("""
            SELECT 
                p.name as jugador,
                COUNT(*) as cantidad_penalizaciones,
                SUM(pen.amount) as monto_total
            FROM players p
            JOIN penalties pen ON p.id = pen.player_id
            JOIN game_nights gn ON pen.game_night_id = gn.id
            WHERE gn.season_id = ?
             GROUP BY p.id, p.name
            ORDER BY monto_total DESC
        """, conn, params=(active_season[0],))
        
        if not penalties.empty:
            st.dataframe(penalties, width='stretch', hide_index=True)
        else:
            st.success("¡No hay penalizaciones registradas esta temporada! 🎉")
    else:
        st.info("No hay datos disponibles aún. ¡Comienza a registrar noches de juego!")
    
    conn.close()

def show_admin():
    """Admin section for database management"""
    st.header("⚙️ Panel de Administración")
    st.warning("⚠️ **Precaución:** Esta sección permite editar y eliminar datos. Los cambios son permanentes.")
    
    admin_tabs = st.tabs([
        "🗑️ Eliminar Rondas",
        "✏️ Editar Jugadores", 
        "💰 Editar Penalizaciones",
        "🎲 Editar/Eliminar Juegos",
        "🌙 Eliminar Noches",
        "📊 Vista SQL Directa",
        "🔧 Configuración"
    ])
    
    conn = get_db_connection()
    
    # Tab 1: Delete Rounds
    with admin_tabs[0]:
        st.subheader("Eliminar Rondas de Juego")
        
        active_season = get_active_season()
        if active_season:
            rounds_query = """
            SELECT 
                gr.id,
                gn.date as fecha,
                g.name as juego,
                gr.round_number as ronda,
                GROUP_CONCAT(p.name, ', ') as ganadores,
                g.points_per_win as puntos
            FROM game_rounds gr
            JOIN game_nights gn ON gr.game_night_id = gn.id
            JOIN games g ON gr.game_id = g.id
            LEFT JOIN round_winners rw ON gr.id = rw.round_id
            LEFT JOIN players p ON rw.player_id = p.id
            WHERE gn.season_id = ?
             GROUP BY gr.id, gn.date, g.name, gr.round_number, g.points_per_win
            ORDER BY gn.date DESC, gr.id DESC
            """
            
            rounds_df = read_sql_query(rounds_query, conn, params=(active_season[0],))
            
            if not rounds_df.empty:
                st.dataframe(rounds_df, width='stretch', hide_index=True)
                
                round_to_delete = st.selectbox(
                    "Seleccionar ronda para eliminar",
                    options=rounds_df['id'].tolist(),
                    format_func=lambda x: f"ID {x}: {rounds_df[rounds_df['id']==x]['fecha'].values[0]} - {rounds_df[rounds_df['id']==x]['juego'].values[0]} - Ronda {rounds_df[rounds_df['id']==x]['ronda'].values[0]}"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Eliminar Ronda Seleccionada", type="primary"):
                        c = conn.cursor()
                        # Delete winners first (foreign key constraint)
                        execute_query(c, "DELETE FROM round_winners WHERE round_id = ?", (round_to_delete,))
                        # Delete round
                        execute_query(c, "DELETE FROM game_rounds WHERE id = ?", (round_to_delete,))
                        conn.commit()
                        st.success("✅ Ronda eliminada exitosamente!")
                        st.rerun()
            else:
                st.info("No hay rondas registradas para esta temporada.")
        else:
            st.warning("No hay temporada activa.")
    
    # Tab 2: Edit Players
    with admin_tabs[1]:
        st.subheader("Editar o Eliminar Jugadores")
        
        players_df = read_sql_query("SELECT id, name FROM players ORDER BY name", conn)
        
        if not players_df.empty:
            st.dataframe(players_df, width='stretch', hide_index=True)
            
            selected_player = st.selectbox(
                "Seleccionar jugador",
                options=players_df['id'].tolist(),
                format_func=lambda x: players_df[players_df['id']==x]['name'].values[0]
            )
            
            current_name = players_df[players_df['id']==selected_player]['name'].values[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Editar Nombre**")
                with st.form("edit_player_form"):
                    new_name = st.text_input("Nuevo nombre", value=current_name)
                    
                    if st.form_submit_button("✏️ Actualizar Nombre"):
                        c = conn.cursor()
                        try:
                            execute_query(c, "UPDATE players SET name = ? WHERE id = ?", (new_name, selected_player))
                            conn.commit()
                            st.success(f"✅ Nombre actualizado a '{new_name}'")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⚠️ Ese nombre ya existe!")
            
            with col2:
                st.markdown("**Actualizar Foto de Perfil**")
                uploaded_new_pic = st.file_uploader(
                    "Subir nueva foto de perfil (png/jpg)", type=['png', 'jpg', 'jpeg'], key=f"profile_upload_{selected_player}"
                )

                if uploaded_new_pic:
                    try:
                        new_img = Image.open(uploaded_new_pic)
                        new_img.thumbnail((200, 200))
                        st.image(new_img, width=100)
                        if st.button("Actualizar Foto", key=f"update_pic_{selected_player}"):
                            pic_bytes = image_to_bytes(new_img)
                            c = conn.cursor()
                            execute_query(c, "UPDATE players SET profile_pic = ? WHERE id = ?", (pic_bytes, selected_player))
                            conn.commit()
                            st.success("✅ Foto de perfil actualizada!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Error al procesar la imagen: {e}")

                st.markdown("**Eliminar Jugador**")
                st.warning("Esto eliminará todas las victorias y penalizaciones del jugador.")

                confirm_delete = st.checkbox(f"Confirmar eliminación de {current_name}")

                if st.button("🗑️ Eliminar Jugador", type="primary", disabled=not confirm_delete):
                    c = conn.cursor()
                    # Delete all related records
                    execute_query(c, """DELETE FROM round_winners WHERE player_id = ?""", (selected_player,))
                    execute_query(c, """DELETE FROM penalties WHERE player_id = ?""", (selected_player,))
                    execute_query(c, """DELETE FROM players WHERE id = ?""", (selected_player,))
                    conn.commit()
                    st.success(f"✅ Jugador '{current_name}' eliminado!")
                    st.rerun()
        else:
            st.info("No hay jugadores registrados.")
    
    # Tab 3: Edit Penalties
    with admin_tabs[2]:
        st.subheader("Editar o Eliminar Penalizaciones")
        
        penalties_query = """
        SELECT 
            pen.id,
            p.name as jugador,
            gn.date as fecha,
            pen.penalty_type as tipo,
            pen.amount as monto,
            pen.reason as razon
        FROM penalties pen
        JOIN players p ON pen.player_id = p.id
        JOIN game_nights gn ON pen.game_night_id = gn.id
        ORDER BY gn.date DESC
        """
        
        penalties_df = read_sql_query(penalties_query, conn)
        
        if not penalties_df.empty:
            st.dataframe(penalties_df, width='stretch', hide_index=True)
            
            selected_penalty = st.selectbox(
                "Seleccionar penalización",
                options=penalties_df['id'].tolist(),
                format_func=lambda x: f"ID {x}: {penalties_df[penalties_df['id']==x]['jugador'].values[0]} - {penalties_df[penalties_df['id']==x]['fecha'].values[0]} - ${penalties_df[penalties_df['id']==x]['monto'].values[0]}"
            )
            
            penalty_row = penalties_df[penalties_df['id']==selected_penalty].iloc[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Editar Penalización**")
                with st.form("edit_penalty_form"):
                    new_amount = st.number_input("Nuevo monto", value=float(penalty_row['monto']), step=0.5)
                    new_reason = st.text_input("Nueva razón", value=penalty_row['razon'] or "")
                    
                    if st.form_submit_button("✏️ Actualizar Penalización"):
                        c = conn.cursor()
                        execute_query(c, "UPDATE penalties SET amount = ?, reason = ? WHERE id = ?", 
                                 (new_amount, new_reason, selected_penalty))
                        conn.commit()
                        st.success("✅ Penalización actualizada!")
                        st.rerun()
            
            with col2:
                st.markdown("**Eliminar Penalización**")
                
                if st.button("🗑️ Eliminar Penalización", type="primary"):
                    c = conn.cursor()
                    execute_query(c, "DELETE FROM penalties WHERE id = ?", (selected_penalty,))
                    conn.commit()
                    st.success("✅ Penalización eliminada!")
                    st.rerun()
        else:
            st.info("No hay penalizaciones registradas.")
    
    # Tab 4: Edit/Delete Games
    with admin_tabs[3]:
        st.subheader("Editar o Eliminar Juegos")
        
        games_df = read_sql_query("SELECT id, name, points_per_win, description FROM games ORDER BY name", conn)
        
        if not games_df.empty:
            st.dataframe(games_df, width='stretch', hide_index=True)
            
            selected_game = st.selectbox(
                "Seleccionar juego",
                options=games_df['id'].tolist(),
                format_func=lambda x: games_df[games_df['id']==x]['name'].values[0]
            )
            
            game_row = games_df[games_df['id']==selected_game].iloc[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Editar Juego**")
                with st.form("edit_game_admin_form"):
                    new_game_name = st.text_input("Nombre", value=game_row['name'])
                    new_points = st.number_input("Puntos por victoria", value=int(game_row['points_per_win']), min_value=1)
                    new_description = st.text_area("Descripción", value=game_row['description'] or "")
                    
                    if st.form_submit_button("✏️ Actualizar Juego"):
                        c = conn.cursor()
                        try:
                            execute_query(c, "UPDATE games SET name = ?, points_per_win = ?, description = ? WHERE id = ?",
                                     (new_game_name, new_points, new_description, selected_game))
                            conn.commit()
                            st.success("✅ Juego actualizado!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⚠️ Ese nombre de juego ya existe!")
            
            with col2:
                st.markdown("**Eliminar Juego**")
                st.warning("Esto eliminará todas las rondas jugadas de este juego.")
                
                # Check how many rounds would be deleted
                rounds_count = read_sql_query(
                    "SELECT COUNT(*) as count FROM game_rounds WHERE game_id = ?", 
                    conn, params=(selected_game,))['count'][0]
                
                st.info(f"Se eliminarán {rounds_count} rondas jugadas.")
                
                confirm_delete_game = st.checkbox(f"Confirmar eliminación de {game_row['name']}")
                
                if st.button("🗑️ Eliminar Juego", type="primary", disabled=not confirm_delete_game):
                    c = conn.cursor()
                    # Delete winners of rounds with this game
                    execute_query(c, """DELETE FROM round_winners WHERE round_id IN 
                                (SELECT id FROM game_rounds WHERE game_id = ?)""", (selected_game,))
                    # Delete rounds
                    execute_query(c, "DELETE FROM game_rounds WHERE game_id = ?", (selected_game,))
                    # Delete game
                    execute_query(c, "DELETE FROM games WHERE id = ?", (selected_game,))
                    conn.commit()
                    st.success(f"✅ Juego '{game_row['name']}' eliminado!")
                    st.rerun()
        else:
            st.info("No hay juegos registrados.")
    
    # Tab 5: Delete Game Nights
    with admin_tabs[4]:
        st.subheader("Eliminar Noches de Juego")
        
        nights_query = """
        SELECT 
            gn.id,
            gn.date as fecha,
            s.name as temporada,
            gn.notes as notas,
            COUNT(DISTINCT gr.id) as rondas
        FROM game_nights gn
        JOIN seasons s ON gn.season_id = s.id
        LEFT JOIN game_rounds gr ON gn.id = gr.game_night_id
         GROUP BY gn.id, gn.date, s.name, gn.notes
        ORDER BY gn.date DESC
        """
        
        nights_df = read_sql_query(nights_query, conn)
        
        if not nights_df.empty:
            st.dataframe(nights_df, width='stretch', hide_index=True)
            
            selected_night = st.selectbox(
                "Seleccionar noche de juego",
                options=nights_df['id'].tolist(),
                format_func=lambda x: f"{nights_df[nights_df['id']==x]['fecha'].values[0]} - {nights_df[nights_df['id']==x]['temporada'].values[0]} ({nights_df[nights_df['id']==x]['rondas'].values[0]} rondas)"
            )
            
            night_row = nights_df[nights_df['id']==selected_night].iloc[0]
            
            st.warning(f"⚠️ Esto eliminará la noche del {night_row['fecha']} con {night_row['rondas']} rondas y todas sus penalizaciones.")
            
            confirm_delete_night = st.checkbox(f"Confirmar eliminación de noche del {night_row['fecha']}")
            
            if st.button("🗑️ Eliminar Noche de Juego", type="primary", disabled=not confirm_delete_night):
                c = conn.cursor()
                # Delete winners of rounds in this night
                execute_query(c, """DELETE FROM round_winners WHERE round_id IN 
                            (SELECT id FROM game_rounds WHERE game_night_id = ?)""", (selected_night,))
                # Delete rounds
                execute_query(c, "DELETE FROM game_rounds WHERE game_night_id = ?", (selected_night,))
                # Delete penalties
                execute_query(c, "DELETE FROM penalties WHERE game_night_id = ?", (selected_night,))
                # Delete night
                execute_query(c, "DELETE FROM game_nights WHERE id = ?", (selected_night,))
                conn.commit()
                st.success(f"✅ Noche del {night_row['fecha']} eliminada!")
                st.rerun()
        else:
            st.info("No hay noches de juego registradas.")
    
    # Tab 6: Direct SQL View
    with admin_tabs[5]:
        st.subheader("Vista SQL Directa")
        st.info("Ejecuta consultas SQL personalizadas (solo lectura por seguridad)")
        
        query_templates = {
            "Seleccionar plantilla...": "",
            "Ver todas las tablas": "SELECT name FROM sqlite_master WHERE type='table'",
            "Ver todos los jugadores": "SELECT * FROM players",
            "Ver todas las temporadas": "SELECT * FROM seasons",
            "Ver todos los juegos": "SELECT * FROM games",
            "Ver todas las rondas": "SELECT * FROM game_rounds",
            "Ver todos los ganadores": "SELECT * FROM round_winners",
            "Ver todas las penalizaciones": "SELECT * FROM penalties",
            "Contar registros por tabla": """
                SELECT 'players' as tabla, COUNT(*) as registros FROM players
                UNION ALL SELECT 'seasons', COUNT(*) FROM seasons
                UNION ALL SELECT 'games', COUNT(*) FROM games
                UNION ALL SELECT 'game_nights', COUNT(*) FROM game_nights
                UNION ALL SELECT 'game_rounds', COUNT(*) FROM game_rounds
                UNION ALL SELECT 'round_winners', COUNT(*) FROM round_winners
                UNION ALL SELECT 'penalties', COUNT(*) FROM penalties
            """
        }
        
        selected_template = st.selectbox("Plantillas de consulta", list(query_templates.keys()))
        
        custom_query = st.text_area(
            "Consulta SQL (solo SELECT)", 
            value=query_templates[selected_template],
            height=150
        )
        
        if st.button("▶️ Ejecutar Consulta"):
            if custom_query.strip().upper().startswith("SELECT"):
                try:
                    result = read_sql_query(custom_query, conn)
                    st.success(f"✅ Consulta ejecutada. {len(result)} filas devueltas.")
                    st.dataframe(result, width='stretch')
                    
                    # Download option
                    csv = result.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Descargar como CSV",
                        csv,
                        "query_result.csv",
                        "text/csv"
                    )
                except Exception as e:
                    st.error(f"❌ Error en la consulta: {str(e)}")
            else:
                st.error("⚠️ Solo se permiten consultas SELECT por seguridad.")
        
        # Database info
        st.markdown("---")
        st.subheader("📊 Información de la Base de Datos")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Tamaño del Archivo", f"{os.path.getsize(DB_PATH) / 1024:.2f} KB")
        
        with col2:
            tables_count = read_sql_query(
                "SELECT COUNT(*) as count FROM sqlite_master WHERE type='table'", 
                conn)['count'][0]
            st.metric("Tablas en la BD", tables_count)
    
    # Tab 7: Settings
    with admin_tabs[6]:
        st.subheader("Configuración Global")
        
        # Default penalty amount
        current_penalty = float(read_sql_query(
            "SELECT value FROM settings WHERE key = 'default_penalty_amount'", 
            conn)['value'][0])
        
        with st.form("settings_form"):
            new_penalty = st.number_input(
                "Monto de Penalización por Defecto ($)", 
                value=current_penalty, 
                step=0.5,
                min_value=0.0
            )
            
            if st.form_submit_button("💾 Guardar Configuración"):
                c = conn.cursor()
                execute_query(c, "UPDATE settings SET value = ? WHERE key = 'default_penalty_amount'", 
                         (str(new_penalty),))
                conn.commit()
                st.success("✅ Configuración actualizada!")
                st.rerun()
        
        st.markdown("---")
        st.subheader("🔄 Backup y Restauración")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Exportar Base de Datos**")
            
            # Create backup
            if st.button("📥 Crear Backup", type="primary"):
                import shutil
                from datetime import datetime
                
                backup_name = f"caballebrios_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                backup_path = os.path.join(os.getcwd(), backup_name)
                shutil.copy2(DB_PATH, backup_path)
                
                with open(backup_path, 'rb') as f:
                    st.download_button(
                        "📥 Descargar Backup",
                        f,
                        backup_name,
                        "application/x-sqlite3"
                    )
        
        with col2:
            st.markdown("**Importar Temporada Anterior**")
            
            if st.button("📤 Importar Temporada 1", type="secondary"):
                try:
                    # Run import inline
                    c = conn.cursor()
                    
                    # Create Season 1
                    try:
                        execute_query(c, """INSERT INTO seasons (name, start_date, end_date, is_active) 
                                    VALUES (?, ?, ?, ?)""",
                                 ("Temporada 1", "2025-04-08", "2025-12-03", 0))
                        season_id = c.lastrowid
                    except sqlite3.IntegrityError:
                        execute_query(c, "SELECT id FROM seasons WHERE name = 'Temporada 1'")
                        season_id = c.fetchone()[0]
                    
                    # Check if already imported
                    execute_query(c, "SELECT COUNT(*) FROM game_nights WHERE season_id = ?", (season_id,))
                    if c.fetchone()[0] > 0:
                        st.warning("⚠️ Temporada 1 ya ha sido importada anteriormente.")
                    else:
                        # Add players
                        players_list = ["Choly", "Olivas", "Othon", "Oscar", "Edgar", "Miguel", "Jaime"]
                        player_ids = {}
                        for player in players_list:
                            try:
                                execute_query(c, "INSERT INTO players (name) VALUES (?)", (player,))
                                player_ids[player] = c.lastrowid
                            except sqlite3.IntegrityError:
                                execute_query(c, "SELECT id FROM players WHERE name = ?", (player,))
                                player_ids[player] = c.fetchone()[0]
                        
                        # Add games with correct points
                        games_to_add = [
                            ("Saboteur", 1), ("Secret Hitler", 1), ("7 Wonders", 2),
                            ("Catan", 3), ("Exploding Kittens", 1), ("Asesino", 2),
                            ("Chameleon", 1), ("Cover Your Assets", 2), ("Flip 7", 1)
                        ]
                        game_ids = {}
                        for game_name, points in games_to_add:
                            try:
                                execute_query(c, "INSERT INTO games (name, points_per_win) VALUES (?, ?)", 
                                         (game_name, points))
                                game_ids[game_name] = c.lastrowid
                            except sqlite3.IntegrityError:
                                execute_query(c, "SELECT id FROM games WHERE name = ?", (game_name,))
                                game_ids[game_name] = c.fetchone()[0]
                        
                        # Import all game nights
                        nights_imported = 0
                        rounds_imported = 0
                        
                        # Night data structure
                        import_data = [
                            ("2025-12-03", [
                                ("Saboteur", 1, ["Othon", "Miguel", "Oscar"]),
                                ("Saboteur", 1, ["Oscar", "Othon"]),
                                ("Secret Hitler", 1, ["Olivas", "Edgar", "Oscar", "Othon"]),
                                ("Secret Hitler", 1, ["Othon"]),
                                ("7 Wonders", 2, ["Othon"]),
                            ], [("Choly", 200.00)]),
                            ("2025-11-03", [
                                ("Catan", 3, ["Olivas"]),
                                ("7 Wonders", 2, ["Othon"]),
                            ], []),
                            ("2025-10-09", [
                                ("Exploding Kittens", 1, ["Oscar"]),
                                ("Saboteur", 2, ["Jaime"]),
                                ("7 Wonders", 2, ["Jaime"]),
                                ("7 Wonders", 2, ["Oscar"]),
                                ("Secret Hitler", 1, ["Olivas", "Jaime", "Othon", "Choly"]),
                                ("Secret Hitler", 1, ["Edgar", "Choly", "Oscar", "Miguel"]),
                            ], []),
                            ("2025-09-20", [
                                ("7 Wonders", 1, ["Jaime"]),
                                ("7 Wonders", 1, ["Edgar"]),
                            ], []),
                            ("2025-09-06", [
                                ("Asesino", 3, ["Othon"]),
                                ("Asesino", 2, ["Oscar"]),
                                ("Asesino", 1, ["Jaime"]),
                                ("Catan", 3, ["Choly"]),
                                ("Saboteur", 2, ["Miguel"]),
                                ("7 Wonders", 2, ["Jaime"]),
                            ], [("Olivas", 100.00)]),
                            ("2025-08-07", [
                                ("Chameleon", 1, ["Edgar"]),
                                ("Saboteur", 2, ["Edgar"]),
                                ("Catan", 3, ["Miguel"]),
                            ], [("Olivas", 300.00)]),
                            ("2025-07-09", [
                                ("Cover Your Assets", 2, ["Choly"]),
                                ("Exploding Kittens", 1, ["Oscar"]),
                                ("Exploding Kittens", 1, ["Othon"]),
                                ("7 Wonders", 2, ["Oscar"]),
                                ("7 Wonders", 2, ["Othon"]),
                            ], []),
                            ("2025-06-18", [
                                ("Flip 7", 1, ["Edgar"]),
                                ("Secret Hitler", 1, ["Jaime", "Choly", "Othon"]),
                                ("Secret Hitler", 1, ["Oscar", "Miguel", "Othon", "Olivas", "Edgar"]),
                                ("Exploding Kittens", 1, ["Olivas"]),
                                ("7 Wonders", 2, ["Miguel"]),
                                ("7 Wonders", 2, ["Edgar"]),
                            ], []),
                            ("2025-05-13", [
                                ("Exploding Kittens", 1, ["Miguel"]),
                                ("Exploding Kittens", 1, ["Miguel"]),
                                ("7 Wonders", 2, ["Choly"]),
                                ("7 Wonders", 2, ["Edgar"]),
                            ], []),
                            ("2025-04-08", [
                                ("Cover Your Assets", 2, ["Jaime"]),
                                ("Catan", 3, ["Oscar"]),
                                ("Exploding Kittens", 1, ["Jaime"]),
                            ], []),
                        ]
                        
                        for date, rounds, penalties in import_data:
                            # Create night
                            execute_query(c, """INSERT INTO game_nights (season_id, date, notes) 
                                        VALUES (?, ?, ?)""",
                                     (season_id, date, "Importado de temporada anterior"))
                            night_id = c.lastrowid
                            nights_imported += 1
                            
                            # Add rounds
                            for round_num, (game, pts, winners) in enumerate(rounds, 1):
                                execute_query(c, """INSERT INTO game_rounds (game_night_id, game_id, round_number) 
                                            VALUES (?, ?, ?)""",
                                         (night_id, game_ids[game], round_num))
                                round_id = c.lastrowid
                                rounds_imported += 1
                                
                                # Add winners
                                for winner in winners:
                                    execute_query(c, "INSERT INTO round_winners (round_id, player_id) VALUES (?, ?)",
                                             (round_id, player_ids[winner]))
                            
                            # Add penalties
                            for player, amount in penalties:
                                execute_query(c, """INSERT INTO penalties 
                                           (game_night_id, player_id, penalty_type, amount, reason) 
                                           VALUES (?, ?, ?, ?, ?)""",
                                         (night_id, player_ids[player], "Ausencia", amount, 
                                          "Importado de temporada anterior"))
                        
                        conn.commit()
                        st.success(f"✅ ¡Temporada 1 importada exitosamente! ({nights_imported} noches, {rounds_imported} rondas)")
                        st.info("💡 Activa 'Temporada 1' en la pestaña Temporadas para ver los datos")
                        
                except Exception as e:
                    st.error(f"❌ Error durante la importación: {str(e)}")
        
        st.markdown("---")
        st.markdown("**Estadísticas**")

        total_query = """
        SELECT 
            (SELECT COUNT(*) FROM players) as jugadores,
            (SELECT COUNT(*) FROM games) as juegos,
            (SELECT COUNT(*) FROM seasons) as temporadas,
            (SELECT COUNT(*) FROM game_nights) as noches,
            (SELECT COUNT(*) FROM game_rounds) as rondas,
            (SELECT COUNT(*) FROM penalties) as penalizaciones
        """

        stats = read_sql_query(total_query, conn).iloc[0]

        st.metric("Total Jugadores", int(stats['jugadores']))
        st.metric("Total Juegos", int(stats['juegos']))
        st.metric("Total Rondas Jugadas", int(stats['rondas']))
    
    conn.close()

if __name__ == "__main__":
    main()