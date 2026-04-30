# Especificación funcional y de diseño — YouTube Subscription Tagger

## 1) Propósito del sistema

YouTube Subscription Tagger es una aplicación web personal para **organizar suscripciones de YouTube** con metadatos locales (tags, colores y rating), y para **vigilar videos nuevos** en canales favoritos.

El sistema está diseñado para:
- Importar y mantener sincronizada la lista de suscripciones del usuario autenticado.
- Permitir clasificación flexible por etiquetas múltiples por canal.
- Priorizar canales con un sistema de rating de 1 a 5 estrellas.
- Mostrar una vista especializada de “nuevos videos” para canales favoritos (4★ y 5★).
- Persistir toda la información de organización localmente en SQLite.

---

## 2) Alcance funcional

### 2.1 Gestión de suscripciones
- Obtención de suscripciones del usuario autenticado vía YouTube Data API v3.
- Carga inicial automática en DB cuando la base está vacía.
- Refresco manual que:
  - agrega canales nuevos,
  - actualiza metadatos de canales existentes,
  - elimina de la base canales que ya no están en YouTube del usuario.

### 2.2 Enriquecimiento local por canal
- Asignación de **tags múltiples** por canal (entrada separada por comas).
- Normalización de tags (trim, deduplicación, orden).
- Asignación de **color por tag** (catálogo global, persistente).
- Asignación de **rating** por canal (1–5, o vacío).

### 2.3 Exploración y filtrado
- Filtros por:
  - tag específico,
  - sin tags,
  - múltiples tags simultáneos (intersección lógica),
  - canales “nuevos” detectados tras refresh,
  - búsqueda por texto (título y tags).

### 2.4 Vista de “Nuevos de favoritos”
- Selecciona canales con rating >= 4.
- Consulta videos nuevos desde última verificación registrada.
- Muestra agrupaciones/orden alternativos:
  - por canal,
  - fecha descendente,
  - fecha ascendente,
  - últimos 7 días,
  - últimos 30 días.
- Usa caché local para resiliencia ante fallos de API.

---

## 3) Actores y contexto de uso

### 3.1 Actor principal
- **Usuario autenticado de YouTube** que desea organizar su feed de suscripciones de forma personalizada.

### 3.2 Entorno
- Ejecución local (desktop/server personal), interfaz web vía navegador.
- Persistencia en archivo SQLite local.
- Integración externa con APIs de Google/YouTube mediante OAuth 2.0.

---

## 4) Arquitectura lógica

## 4.1 Capas

1. **Presentación (Frontend web)**
   - Plantillas HTML server-side.
   - JavaScript para interacción, filtros dinámicos y llamadas API internas.
   - CSS para layout responsive y componentes UI.

2. **Aplicación (Flask)**
   - Rutas de render y API JSON.
   - Orquestación entre autenticación, obtención de datos externos y persistencia local.

3. **Dominio/Servicios**
   - Módulo de integración YouTube (OAuth, llamadas API, parsing/normalización de respuesta, tratamiento de errores).

4. **Persistencia**
   - Módulo SQLite con funciones CRUD y estado de aplicación.

## 4.2 Principios de diseño observados
- Persistencia local y simple (single-user mindset).
- UI orientada a productividad (filtros rápidos, colorización, búsqueda instantánea).
- Degradación controlada ante errores de API (mensajes útiles + fallback a caché en favoritos).

---

## 5) Modelo de datos (conceptual)

### 5.1 Entidad Channel
- `channel_id` (PK)
- `title`
- `thumbnail_url`
- `tags` (lista serializada)
- `rating` (nullable, 1–5)

### 5.2 Entidad TagColor
- `tag` (PK)
- `color` (hex)

### 5.3 Entidad AppState
- `key` (PK)
- `value`

Uso principal:
- `favorites_last_check_at`: marca de tiempo ISO de la última consulta de nuevos favoritos.

### 5.4 Entidad FavoriteVideoCache
- `video_id` (PK)
- `channel_id`
- `channel_title`
- `title`
- `published_at`
- `thumbnail_url`
- `video_url`
- `duration_text`

Objetivo: conservar el último snapshot utilizable de videos nuevos de favoritos.

---

## 6) Integraciones externas

### 6.1 YouTube Data API v3
- Scope mínimo: `youtube.readonly`.
- Operaciones usadas:
  - lectura de datos del canal autenticado,
  - lectura paginada de suscripciones,
  - lectura de playlist de uploads por canal,
  - lectura de duración por lote de videos.

### 6.2 OAuth 2.0
- Flujo de app instalada con servidor local temporal para consentimiento.
- Persistencia de credenciales en token local reutilizable.
- Reintento con refresh token cuando expira.
- Invalidación de token local cuando hay errores de autorización.

---

## 7) Especificación de comportamientos clave

### 7.1 Inicio de aplicación y autenticación
1. Verifica existencia de token local.
2. Si falta o es inválido, inicia flujo OAuth.
3. Construye cliente YouTube.
4. Si DB está vacía, ejecuta importación inicial de suscripciones.

### 7.2 Refresh de suscripciones
1. Descarga suscripciones actuales desde YouTube.
2. Compara IDs API vs IDs DB.
3. Elimina IDs ausentes en API.
4. Inserta/actualiza todas las suscripciones obtenidas.
5. Retorna estado actualizado para repintado cliente.

### 7.3 Gestión de tags
- Entrada tipo texto CSV.
- Proceso de normalización:
  - trim por ítem,
  - eliminación de vacíos,
  - deduplicación,
  - orden alfabético.
- Guardado en canal y actualización de:
  - tags visibles del canal,
  - catálogo global de tags,
  - colores vigentes por tag.

### 7.4 Gestión de color por tag
- Validación de color hex (`#rgb` o `#rrggbb`).
- Persistencia por nombre de tag.
- Propagación visual del color en:
  - filtros,
  - listado interactivo de tags,
  - badges en canales.

### 7.5 Gestión de rating
- Validación entera 1–5 o null.
- Persistencia por canal.
- Reordenamiento natural del listado por rating descendente y luego título.

### 7.6 Nuevos videos en favoritos
1. Obtiene canales con rating >= 4.
2. Lee timestamp de última verificación.
3. Para cada canal favorito:
   - obtiene uploads playlist,
   - lista videos recientes (límite de páginas),
   - filtra por `published_after`.
4. Enriquece duración de videos en lotes.
5. Si todo OK: reemplaza caché y actualiza timestamp.
6. Si falla API: usa caché local y muestra warning.

---

## 8) Contratos de interfaz (API interna)

### 8.1 `POST /refresh_from_youtube`
- **Objetivo:** sincronizar suscripciones con YouTube.
- **Salida:**
  - `success`,
  - mensaje de resultado,
  - canales actualizados,
  - tags únicos,
  - colores,
  - IDs de canales nuevos detectados.

### 8.2 `POST /api/tags/<channel_id>`
- **Entrada JSON:** `{ "tags": "tag1, tag2" }`
- **Objetivo:** actualizar tags de un canal.
- **Salida:** estado, tags normalizados, catálogo global y colores.

### 8.3 `POST /api/tags/color/<tag_name>`
- **Entrada JSON:** `{ "color": "#aabbcc" }`
- **Objetivo:** actualizar color de un tag.
- **Salida:** estado y mapa de colores actualizado.

### 8.4 `POST /api/rating/<channel_id>`
- **Entrada JSON:** `{ "rating": 1..5 | null }`
- **Objetivo:** actualizar rating de canal.
- **Salida:** estado y listado de canales actualizado.

### 8.5 `GET /`
- **Objetivo:** vista principal de canales, filtros y acciones.

### 8.6 `GET /nuevos-favoritos`
- **Objetivo:** vista de videos nuevos para favoritos con modos de visualización.

---

## 9) Reglas de negocio

1. Un canal se identifica de forma única por `channel_id`.
2. Los tags son metadatos locales y no alteran YouTube.
3. Un canal puede tener cero o múltiples tags.
4. El rating es opcional, entero de 1 a 5.
5. “Favorito” se define por rating mínimo configurable (actualmente 4).
6. Los colores se asignan por tag global (no por canal).
7. La sincronización elimina canales no vigentes en suscripciones remotas.
8. La vista de favoritos prioriza continuidad operativa usando caché ante fallos externos.

---

## 10) Requisitos no funcionales

### 10.1 Usabilidad
- Interfaz orientada a acciones frecuentes (etiquetar, filtrar, buscar, refrescar).
- Feedback inmediato de estados y errores.

### 10.2 Rendimiento
- Paginación de suscripciones y videos.
- Batching de consulta de duraciones (hasta 50 IDs por request).
- Re-render client-side para evitar recargas completas innecesarias.

### 10.3 Robustez
- Manejo explícito de errores HTTP/API.
- Mensajes de error amigables para usuario final.
- Migraciones simples de esquema al inicializar DB.

### 10.4 Persistencia y portabilidad
- Base SQLite local portable por archivo.
- Estado OAuth y DB migrables entre instalaciones.

### 10.5 Seguridad operativa
- Requiere secreto de cliente OAuth local.
- Recomendada configuración de `FLASK_SECRET_KEY` en entornos no dev.
- El sistema opera con permisos de solo lectura en YouTube (scope readonly).

---

## 11) Diseño de la experiencia de usuario (UX)

### 11.1 Vista principal
- Header con:
  - identidad del canal autenticado,
  - acción de refresh,
  - acceso a vista de nuevos favoritos con contador,
  - botón de filtro para canales nuevos,
  - estado de operaciones.

- Sidebar sticky:
  - filtros por tag (incluye “Show All” y “No Tags”),
  - catálogo interactivo de tags con selector de color.

- Área de contenido:
  - contador de canales,
  - buscador,
  - cards de canal con:
    - miniatura,
    - enlace a canal YouTube,
    - rating visual por estrellas,
    - tags actuales,
    - input para edición de tags.

### 11.2 Vista “Nuevos de favoritos”
- Indicadores de volumen (videos/canales).
- Modos de agrupación/orden temporal con botones.
- Lista de resultados con miniatura, título, publicación y duración.

---

## 12) Observabilidad y diagnósticos

- Logging estructurado básico en backend.
- Distinción de contextos de error API (suscripciones, channel_info, favorite_videos).
- Mensajería específica para `quotaExceeded` con pista de próximo reset diario.

---

## 13) Restricciones y supuestos

1. Escenario primario de un solo usuario por instancia.
2. Dependencia de disponibilidad/cuota de YouTube Data API.
3. No existe sincronización multi-dispositivo en tiempo real (solo por mover archivos locales).
4. No hay control de usuarios/roles internos (se delega identidad a OAuth Google).

---

## 14) Criterios de aceptación del sistema (alto nivel)

1. El usuario puede autenticarse y visualizar sus suscripciones.
2. Puede etiquetar canales y ver los tags aplicados de forma persistente.
3. Puede filtrar por tags (incluyendo combinaciones y “sin tags”).
4. Puede asignar y reutilizar colores por tag en toda la UI.
5. Puede refrescar y reflejar altas/bajas de suscripciones remotas.
6. Puede puntuar canales y obtener priorización visual.
7. Puede consultar videos nuevos de favoritos desde la última verificación.
8. Ante fallo de API en favoritos, recibe aviso y datos cacheados.

---

## 15) Entregable esperado para agentes de codificación

Este documento define el **qué** del sistema (objetivos, comportamiento, reglas, datos, endpoints, UX y restricciones) para que un agente pueda reconstruirlo o evolucionarlo sin necesidad de conocer la implementación concreta actual.
