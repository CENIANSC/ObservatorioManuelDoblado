import hashlib
import io
import re
import sqlite3
import unicodedata
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'observatorio.db'
st.set_page_config(page_title='Observatorio Manuel Doblado', page_icon='📊', layout='wide')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS fuentes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, plataforma TEXT NOT NULL, url TEXT, tipo TEXT NOT NULL, creado TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS publicaciones (id INTEGER PRIMARY KEY, fuente_id INTEGER NOT NULL REFERENCES fuentes(id), url TEXT NOT NULL UNIQUE, fecha TEXT NOT NULL, texto TEXT NOT NULL DEFAULT '', actor TEXT NOT NULL DEFAULT '', reacciones INTEGER NOT NULL DEFAULT 0, compartidos INTEGER NOT NULL DEFAULT 0, creado TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS comentarios (id INTEGER PRIMARY KEY, publicacion_id INTEGER NOT NULL REFERENCES publicaciones(id) ON DELETE CASCADE, fecha TEXT NOT NULL, texto TEXT NOT NULL, huella TEXT NOT NULL UNIQUE, tema TEXT NOT NULL, tono TEXT NOT NULL, metodo TEXT NOT NULL DEFAULT 'reglas', creado TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_comentarios_pub ON comentarios(publicacion_id);
CREATE INDEX IF NOT EXISTS idx_comentarios_fecha ON comentarios(fecha);
'''

def connection():
    con = sqlite3.connect(DB, timeout=15)
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=15000')
    return con

def initialize():
    with connection() as con:
        con.executescript(SCHEMA)

def query(sql, args=()):
    with connection() as con:
        return pd.read_sql_query(sql, con, params=args)

def normalize(t):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(t).lower()) if not unicodedata.combining(c))

TOPICS = {
    'Agua y drenaje': ['agua', 'drenaje', 'pozo', 'fuga', 'alcantarill', 'tuberia'],
    'Seguridad': ['seguridad', 'robo', 'policia', 'delincuencia', 'asalto', 'inseguridad'],
    'Obra pública': ['obra', 'paviment', 'calle', 'camino', 'puente', 'bache'],
    'Servicios públicos': ['basura', 'alumbrado', 'luminaria', 'recoleccion', 'limpieza'],
    'Economía y empleo': ['empleo', 'trabajo', 'comercio', 'inversion', 'negocio', 'salario'],
    'Gobierno y transparencia': ['alcalde', 'presidente municipal', 'ayuntamiento', 'corrupcion', 'transparencia', 'cabildo'],
}
POSITIVE = ['bien hecho', 'felicidades', 'excelente', 'gracias', 'buen trabajo', 'muy bien', 'apoyo', 'bravo', 'mejoro', 'cumplieron']
NEGATIVE = ['pesimo', 'mal trabajo', 'mentira', 'no cumplen', 'corrupcion', 'vergüenza', 'verguenza', 'terrible', 'incompetente', 'no sirve', 'fracaso', 'abandonado']

def classify(text):
    t = normalize(text)
    scores = {name: sum(t.count(term) for term in terms) for name, terms in TOPICS.items()}
    topic = max(scores, key=scores.get) if any(scores.values()) else 'Otros'
    p = sum(t.count(term) for term in POSITIVE)
    n = sum(t.count(term) for term in NEGATIVE)
    tone = 'Mixto' if p and n else 'Favorable' if p else 'Crítico' if n else 'Indeterminado'
    return topic, tone

def valid_url(u):
    try:
        p = urlparse(str(u).strip())
        return p.scheme in ('http', 'https') and bool(p.netloc) and '.' in p.netloc
    except Exception:
        return False

def iso_date(v):
    if isinstance(v, (datetime, date, pd.Timestamp)):
        return v.strftime('%Y-%m-%d')
    s = str(v).strip()
    return pd.to_datetime(s, errors='raise', dayfirst=False).strftime('%Y-%m-%d')

def add_comment(con, pub_id, fecha, texto):
    fecha = iso_date(fecha)
    texto = str(texto).strip()
    if not texto:
        raise ValueError('Comentario vacío')
    # Fingerprint intentionally collapses identical text on the same publication/date.
    key = hashlib.sha256(f'{pub_id}|{fecha}|{normalize(texto)}'.encode('utf-8')).hexdigest()
    topic, tone = classify(texto)
    cur = con.execute('INSERT OR IGNORE INTO comentarios(publicacion_id,fecha,texto,huella,tema,tono,creado) VALUES(?,?,?,?,?,?,?)', (pub_id, fecha, texto, key, topic, tone, datetime.now().isoformat(timespec='seconds')))
    return cur.rowcount

initialize()
st.title('📊 Observatorio de conversación digital')
st.caption('Manuel Doblado 2027 · Investigación independiente · Datos capturados por el equipo, no extracción automática de Facebook')
st.info('El análisis de tono es una **clasificación exploratoria por palabras clave**, no un modelo de IA validado ni una estimación de intención de voto. Revisa manualmente las etiquetas antes de publicar.')

section = st.sidebar.radio('Secciones', ['Dashboard', 'Fuentes', 'Publicaciones', 'Comentarios', 'Importar CSV / Excel', 'Datos y metodología'])

if section == 'Fuentes':
    st.header('Registrar fuentes públicas')
    with st.form('fuentes'):
        name = st.text_input('Nombre de la página o medio')
        platform = st.selectbox('Plataforma', ['Facebook', 'Instagram', 'TikTok', 'Otra'])
        kind = st.selectbox('Tipo', ['Institucional', 'Medio', 'Actor político', 'Comunitaria', 'Otra'])
        url = st.text_input('URL de la fuente (opcional)')
        sent = st.form_submit_button('Guardar fuente')
    if sent:
        if not name.strip() or (url.strip() and not valid_url(url)):
            st.error('Indica un nombre y, si agregas una URL, usa http(s) válido.')
        else:
            with connection() as con:
                con.execute('INSERT INTO fuentes(nombre,plataforma,url,tipo,creado) VALUES(?,?,?,?,?)', (name.strip(), platform, url.strip(), kind, datetime.now().isoformat(timespec='seconds')))
            st.success('Fuente guardada.')
    st.dataframe(query('SELECT id,nombre,plataforma,tipo,url FROM fuentes ORDER BY id DESC'), use_container_width=True, hide_index=True)

elif section == 'Publicaciones':
    st.header('Captura de publicaciones')
    sources = query('SELECT id,nombre FROM fuentes ORDER BY nombre')
    if sources.empty:
        st.warning('Primero registra una fuente.')
    else:
        opts = {f"{r['nombre']} (ID {r['id']})": int(r['id']) for _, r in sources.iterrows()}
        with st.form('pub'):
            chosen = st.selectbox('Fuente', list(opts))
            url = st.text_input('Enlace de la publicación')
            when = st.date_input('Fecha de publicación', value=date.today())
            actor = st.text_input('Figura o institución mencionada (opcional)')
            content = st.text_area('Texto de la publicación')
            reactions = st.number_input('Reacciones observadas', min_value=0, step=1)
            shares = st.number_input('Compartidos observados', min_value=0, step=1)
            sent = st.form_submit_button('Guardar publicación')
        if sent:
            if not valid_url(url):
                st.error('Ingresa una URL http(s) válida.')
            else:
                try:
                    with connection() as con:
                        con.execute('INSERT INTO publicaciones(fuente_id,url,fecha,texto,actor,reacciones,compartidos,creado) VALUES(?,?,?,?,?,?,?,?)', (opts[chosen], url.strip(), when.isoformat(), content.strip(), actor.strip(), int(reactions), int(shares), datetime.now().isoformat(timespec='seconds')))
                    st.success('Publicación guardada.')
                except sqlite3.IntegrityError:
                    st.warning('Esa URL ya está registrada.')
    st.dataframe(query('SELECT p.id,p.fecha,f.nombre AS fuente,p.actor,p.url,p.reacciones,p.compartidos FROM publicaciones p JOIN fuentes f ON f.id=p.fuente_id ORDER BY p.id DESC'), use_container_width=True, hide_index=True)

elif section == 'Comentarios':
    st.header('Captura y revisión de comentarios')
    pubs = query('SELECT id,fecha,url FROM publicaciones ORDER BY id DESC')
    if pubs.empty:
        st.warning('Primero registra una publicación.')
    else:
        opts = {f"ID {r['id']} · {r['fecha']} · {str(r['url'])[:75]}": int(r['id']) for _, r in pubs.iterrows()}
        with st.form('comment'):
            chosen = st.selectbox('Publicación', list(opts))
            when = st.date_input('Fecha del comentario', value=date.today())
            content = st.text_area('Texto del comentario público (sin nombres de usuarios)')
            sent = st.form_submit_button('Guardar y clasificar')
        if sent:
            try:
                with connection() as con:
                    inserted = add_comment(con, opts[chosen], when, content)
                st.success('Comentario guardado.' if inserted else 'Comentario duplicado: no se agregó.')
            except ValueError as e:
                st.error(str(e))
        st.subheader('Revisión manual de etiquetas')
        comments = query('SELECT id,fecha,texto,tema,tono FROM comentarios ORDER BY id DESC LIMIT 300')
        if not comments.empty:
            st.dataframe(comments, use_container_width=True, hide_index=True)
            with st.form('review'):
                cid = st.selectbox('ID de comentario a corregir', comments['id'].astype(int).tolist())
                topic = st.selectbox('Tema revisado', list(TOPICS) + ['Otros'])
                tone = st.selectbox('Tono revisado', ['Favorable', 'Crítico', 'Neutral', 'Mixto', 'Indeterminado'])
                save = st.form_submit_button('Guardar revisión humana')
            if save:
                with connection() as con:
                    con.execute("UPDATE comentarios SET tema=?,tono=?,metodo='revision_humana' WHERE id=?", (topic,tone,int(cid)))
                st.success('Revisión guardada.')
        else:
            st.caption('Sin comentarios todavía.')

elif section == 'Importar CSV / Excel':
    st.header('Importación de comentarios')
    st.write('Columnas obligatorias: `url_publicacion`, `fecha`, `texto`. La URL debe corresponder a una publicación previamente registrada. No importes nombres, perfiles ni identificadores de usuarios.')
    sample = pd.DataFrame([{'url_publicacion':'https://www.facebook.com/ejemplo/posts/123', 'fecha':'2026-11-17', 'texto':'Ejemplo ficticio: falta alumbrado en mi calle'}])
    st.download_button('Descargar plantilla CSV', sample.to_csv(index=False).encode('utf-8-sig'), file_name='plantilla_comentarios.csv', mime='text/csv')
    upload = st.file_uploader('Archivo CSV o Excel', type=['csv','xlsx'])
    if upload:
        try:
            df = pd.read_csv(upload, encoding='utf-8-sig') if upload.name.lower().endswith('.csv') else pd.read_excel(upload)
            required = {'url_publicacion','fecha','texto'}
            if not required.issubset(df.columns):
                st.error('Faltan columnas: ' + ', '.join(sorted(required - set(df.columns))))
            else:
                st.write(f'Registros en archivo: {len(df)}')
                st.dataframe(df[list(required)].head(20), use_container_width=True, hide_index=True)
                if st.button('Importar registros válidos'):
                    mapping = dict(query('SELECT id,url FROM publicaciones').set_index('url')['id'])
                    count, skipped, errors = 0, 0, []
                    with connection() as con:
                        for i,r in df.iterrows():
                            try:
                                url = str(r['url_publicacion']).strip()
                                if url not in mapping:
                                    raise ValueError('URL no registrada')
                                count += add_comment(con, int(mapping[url]), r['fecha'], r['texto'])
                            except Exception as e:
                                skipped += 1
                                if len(errors) < 12: errors.append(f'Fila {i+2}: {e}')
                    st.success(f'Importados: {count}. Omitidos (duplicados o inválidos): {len(df)-count}.')
                    if errors: st.warning('\n'.join(errors))
        except Exception as e:
            st.error(f'No fue posible leer el archivo: {e}')

elif section == 'Dashboard':
    st.header('Dashboard')
    pubs = query('SELECT COUNT(*) AS n FROM publicaciones')['n'][0]
    comments = query('SELECT COUNT(*) AS n FROM comentarios')['n'][0]
    sources = query('SELECT COUNT(*) AS n FROM fuentes')['n'][0]
    a,b,c = st.columns(3)
    a.metric('Fuentes', int(sources)); b.metric('Publicaciones', int(pubs)); c.metric('Comentarios', int(comments))
    data = query('SELECT c.fecha,c.tema,c.tono,c.metodo,p.actor,f.nombre AS fuente FROM comentarios c JOIN publicaciones p ON p.id=c.publicacion_id JOIN fuentes f ON f.id=p.fuente_id')
    if data.empty:
        st.info('Aún no hay comentarios. Registra una fuente, una publicación y después comentarios.')
    else:
        data['fecha'] = pd.to_datetime(data['fecha'])
        sources_sel = st.multiselect('Fuentes', sorted(data['fuente'].unique()), default=sorted(data['fuente'].unique()))
        tones_sel = st.multiselect('Tonos', sorted(data['tono'].unique()), default=sorted(data['tono'].unique()))
        data = data[data['fuente'].isin(sources_sel) & data['tono'].isin(tones_sel)]
        if data.empty:
            st.warning('No hay datos con los filtros elegidos.')
        else:
            x,y = st.columns(2)
            with x:
                fig = px.bar(data.groupby('tono').size().reset_index(name='comentarios'),x='tono',y='comentarios',title='Tono observado')
                st.plotly_chart(fig,use_container_width=True)
            with y:
                fig = px.bar(data.groupby('tema').size().reset_index(name='comentarios'),x='tema',y='comentarios',title='Temas mencionados')
                st.plotly_chart(fig,use_container_width=True)
            daily = data.groupby(data['fecha'].dt.date).size().reset_index(name='comentarios')
            daily.columns = ['fecha','comentarios']
            st.plotly_chart(px.line(daily,x='fecha',y='comentarios',markers=True,title='Comentarios por fecha'),use_container_width=True)
            st.caption(f'Base observada: {len(data)} comentarios accesibles y registrados. No es muestra representativa de electores.')

else:
    st.header('Datos y metodología')
    st.markdown('''**Alcance.** Registros de publicaciones públicas capturados manualmente o importados con autorización. La aplicación no consulta Facebook ni otras redes automáticamente.\n\n**Clasificación.** Las reglas de palabras clave son orientativas. Un comentario sin palabras reconocidas queda *Indeterminado*, no *Neutral*. La revisión humana puede corregir etiquetas.\n\n**Sesgos.** La disponibilidad de comentarios, la selección de fuentes, la moderación de las páginas y la repetición de autores limitan las conclusiones. No inferir intención de voto ni apoyo ciudadano general.\n\n**Privacidad.** No registrar nombres de comentaristas ni identificadores de perfil. Antes de publicar, revisar derechos de autor, protección de datos y términos de las plataformas.\n\n**Almacenamiento.** El archivo `observatorio.db` se guarda en la carpeta del programa. Hacer copias de seguridad periódicas. En alojamientos efímeros, SQLite puede perderse al reiniciar.''')
    for name,sql in [('fuentes','SELECT * FROM fuentes'),('publicaciones','SELECT * FROM publicaciones'),('comentarios','SELECT id,publicacion_id,fecha,texto,tema,tono,metodo FROM comentarios')]:
        df = query(sql)
        st.download_button(f'Exportar {name} CSV',df.to_csv(index=False).encode('utf-8-sig'),file_name=f'{name}.csv',mime='text/csv')
