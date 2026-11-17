# Observatorio de conversación digital — Manuel Doblado 2027

Aplicación piloto de investigación independiente, hecha con Streamlit, pandas, Plotly y SQLite.

## Publicar con GitHub y Streamlit Community Cloud

1. Crea un repositorio nuevo en GitHub, por ejemplo `observatorio-manuel-doblado`.
2. En el repositorio selecciona **Add file > Upload files**.
3. Sube **el contenido de esta carpeta** a la raíz del repositorio (no la carpeta contenedora): `app.py`, `requirements.txt`, `runtime.txt`, `.streamlit/config.toml`, `.gitignore` y este README.
   - GitHub web puede omitir archivos ocultos al arrastrar carpetas; puedes crear `.streamlit/config.toml` manualmente. Este archivo es opcional.
4. En https://share.streamlit.io/ inicia sesión con GitHub y elige **Create app**.
5. Selecciona repositorio, rama `main` y archivo principal **`app.py`**. Publica.
6. Espera la instalación de dependencias y abre la URL que Streamlit genere.

**Si la interfaz de GitHub no muestra el archivo `app.py` en la raíz, vuelve a subir el contenido de la carpeta, no el ZIP.**

## Uso

- Fuentes: registra páginas públicas y medios.
- Publicaciones: registra enlaces públicos de las publicaciones observadas.
- Comentarios: captura manualmente texto sin nombres ni identificadores de usuarios.
- Importación: carga CSV o XLSX con `url_publicacion`, `fecha`, `texto` (la publicación debe existir primero).
- Dashboard: visualiza temas, tono y evolución de comentarios.
- Datos y metodología: exporta datos a CSV.

La clasificación es una aproximación por palabras clave; **no es un modelo de IA ni una encuesta electoral**. Revisa etiquetas antes de publicar resultados.

## Advertencia crítica: SQLite en Streamlit Cloud

La aplicación guarda `observatorio.db` en el disco local de la instancia. En Streamlit Community Cloud ese almacenamiento es **efímero**: reinicios, suspensión, redespliegues o reemplazos de instancia pueden borrar registros. Tampoco está preparada para edición simultánea multiusuario.

**Usa esta edición para una demostración o piloto, no como base definitiva de investigación.** Exporta los CSV después de cada sesión. Para operación real, migrar a PostgreSQL administrado con credenciales en `st.secrets` y acceso restringido. No subas bases con datos personales a GitHub.

## Ejecutar localmente (opcional)

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Privacidad y acceso a redes

La aplicación no extrae automáticamente datos de Facebook. Solo admite contenido capturado manualmente o importado con acceso permitido. No recolectes nombres de comentaristas, perfiles, identificadores ni contenido de grupos privados. Las métricas no representan la intención de voto del municipio.
