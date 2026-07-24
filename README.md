# Ransom Monitor LATAM → Teams

Consulta la API PRO de [ransomware.live](https://www.ransomware.live/) y publica
en Microsoft Teams (vía webhook, como Adaptive Cards) las víctimas de
ransomware más recientes. Cada víctima nueva se publica en **su propia
tarjeta** (no se agrupan varias víctimas en un mismo mensaje).

Hay tres tipos de feed, cada uno con su propio webhook/canal:

- **Por país** (`config/countries/<código>.yaml`): un canal por país, solo
  víctimas de ese país.
- **General** (`config/general.yaml`): un solo canal con las víctimas de
  **todos** los países LATAM configurados en `config/countries/` (33 países
  actualmente), sin importar si cada uno tiene además su propio canal
  individual habilitado.
- **Global** (`config/global.yaml`): un solo canal con las víctimas más
  recientes a **nivel mundial**, sin filtrar por región.

Estos tres tipos no son excluyentes: la misma víctima puede terminar
publicada en su canal de país, en General y en Global si los tres están
habilitados — es intencional, cada canal sirve una audiencia distinta.

## Cómo funciona

- `ransom_monitor/api_client.py` — cliente HTTP hacia `api-pro.ransomware.live`.
  Es **secuencial y con jitter** (espera aleatoria entre peticiones) y hace
  backoff exponencial ante `429`/`5xx`, respetando `Retry-After`. Esto es lo
  que nos mantiene discretos frente al rate-limiting del API.
- `ransom_monitor/cards.py` — arma **una Adaptive Card v1.4 por víctima**, con
  todos los campos que trae la API (grupo, país, sector, sitio web, fechas de
  ataque/descubrimiento, rescate, tamaño de datos, prensa, infostealer,
  captura de pantalla y link a la ficha completa), más un bloque de
  **inteligencia del grupo** cuando está disponible (ver abajo).
- `ransom_monitor/group_intel.py` — cachea en disco (`state/group_cache.json`)
  el perfil de cada grupo de ransomware (`/group/<nombre>`), para no pedirlo
  de nuevo en cada corrida.
- `ransom_monitor/state.py` — guarda en `state/state.json` la última fecha
  `discovered` procesada por feed (el **checkpoint**), para no reenviar
  víctimas ya notificadas.
- `ransom_monitor/main.py` — orquesta todo: por cada feed habilitado, trae
  víctimas, calcula cuáles son nuevas, arma una tarjeta por cada una y las
  publica con una pausa aleatoria entre mensajes.

El script está pensado para ejecutarse **una vez por invocación**, disparado
por un programador externo (cron en Linux, Task Scheduler en Windows), no
como proceso en loop infinito. Así se evita golpear la API más seguido de lo
necesario.

## Fuente de datos

- Feed **global**: `GET /victims/recent` (las ~100 víctimas más recientes a
  nivel mundial).
- Feed por **país**: `GET /victims/?country=XX` (todo el histórico conocido
  de ese país; el script filtra localmente qué es "nuevo" desde la última
  corrida usando el checkpoint guardado).
- Feed **general**: la unión de `GET /victims/?country=XX` de los 33 países
  LATAM configurados. Dentro de una misma corrida, si un país ya se consultó
  para su propio feed, **no se vuelve a pedir** para General (se comparte el
  resultado) — así tener los 33 países individuales Y el feed general
  habilitados no duplica peticiones.
- Enriquecimiento opcional por víctima: `GET /group/<nombre>` (perfil del
  grupo). Se cachea por grupo (no por víctima) durante
  `enrichment.group_cache_ttl_hours` (24h por defecto), así que en la
  práctica casi nunca se repite esta llamada — la mayoría de los grupos
  reaparecen en múltiples víctimas.

### Qué trae cada tarjeta

De la víctima (siempre, sin llamadas extra — ya viene en el listado):
grupo, país, sector, sitio web, descripción, fecha de ataque, fecha de
descubrimiento, monto de rescate (si se conoce), tamaño de datos filtrados,
cobertura de prensa, datos de infostealer (HudsonRock), captura de pantalla
del sitio de filtración y link permanente a la ficha en ransomware.live.

Del grupo (si `enrichment.group_intel: true`): descripción del grupo,
víctimas históricas totales, fecha de primera/última actividad conocida,
técnicas MITRE ATT&CK documentadas (conteo), CVEs conocidas que explota
(ordenadas por severidad CVSS), si hay chats de negociación o notas de
rescate filtradas disponibles, conteo de IOCs publicados (`/iocs`) y de
reglas YARA (`/yara`) — ambos con un link al perfil público del grupo en
ransomware.live para ver el detalle completo.

### Otros datos del API que **no** se están usando todavía

Si quieres, puedo sumar cualquiera de estos:

- **`/csirt/<país>`** — contactos CSIRT/CERT oficiales del país (para saber a
  quién reportar). Se podría mostrar un contacto de referencia por país,
  cacheado igual que el perfil de grupo.
- **`/stats`** — contador global (víctimas/grupos/press rastreados y última
  actualización). Serviría como pie de página del feed global.
- **`locations`** dentro de `/group/<nombre>` — URLs de los sitios de
  filtración (.onion). Las omití a propósito para no promover el acceso a
  esos sitios desde el canal de Teams; puedo agregarlas como texto plano si
  las necesitas para investigación.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate       # Windows (PowerShell/cmd)
pip install -r requirements.txt
```

## Configuración

1. **API key**: va en `.env` (nunca se sube a git — ver `.gitignore`). Usa
   `.env.example` como plantilla.

2. **Webhooks de Teams**: en cada canal de Teams donde quieras recibir
   alertas, agrega la app **Workflows** → plantilla *"Post to a channel when
   a webhook request is received"* (el conector clásico "Incoming Webhook" /
   MessageCard está deprecado por Microsoft). Copia la URL generada y
   pégala en `.env`:

   ```
   TEAMS_WEBHOOK_GLOBAL=https://...
   TEAMS_WEBHOOK_GENERAL=https://...
   TEAMS_WEBHOOK_MX=https://...
   TEAMS_WEBHOOK_CO=https://...
   ```

3. **Habilitar feeds**: cada país tiene su propio archivo en
   `config/countries/<código>.yaml`; el agregado LATAM está en
   `config/general.yaml`; el mundial en `config/global.yaml`. Por defecto
   están `enabled: true` México (`mx.yaml`), `global.yaml` y `general.yaml`;
   el resto de países arranca en `enabled: false`. Para activar otro país,
   edita su archivo y pon `enabled: true` (y asegúrate de tener su variable
   de webhook en `.env`). Feeds sin webhook configurado se omiten
   automáticamente aunque estén `enabled: true` — así que `general.yaml`
   simplemente no hace nada hasta que le pongas `TEAMS_WEBHOOK_GENERAL`.

4. Ajustes finos (delays, reintentos, cuántas víctimas por corrida, backfill
   inicial, enriquecimiento de grupo, orden de los países) están en
   `config/settings.yaml` y en cada archivo de país/`global.yaml`/`general.yaml`.

## Uso

```bash
# Ver qué haría, sin publicar en Teams ni tocar el estado
python -m ransom_monitor.main --dry-run

# Correr todo lo habilitado
python -m ransom_monitor.main

# Solo un feed
python -m ransom_monitor.main --feed MX
python -m ransom_monitor.main --feed global
python -m ransom_monitor.main --feed general

# Ignorar el estado guardado (recalcula todo como primera corrida)
python -m ransom_monitor.main --reset-state

# Sobrescribir la ventana de seguridad solo para esta corrida (pruebas puntuales)
python -m ransom_monitor.main --feed MX --max-lookback-hours 240
```

(En Windows usa `.venv\Scripts\python`, en Linux/Mac `.venv/bin/python` o
simplemente `python` con el venv activado.)

### Checkpoint incremental (clave si corres cada 10 minutos)

Cada feed guarda en `state/state.json` la fecha `discovered` de la víctima
más reciente que ya procesó. En cada corrida solo se consideran "nuevas" las
víctimas con `discovered` posterior a ese valor — **no** se vuelve a traer
todo el histórico ni todas las últimas 24h, solo lo que apareció desde la
corrida anterior. Si programas el script cada 10 minutos, en la práctica
cada ejecución solo procesa lo que pasó en esos 10 minutos.

Como red de seguridad adicional (`run.max_lookback_hours` en
`config/settings.yaml`, 12h por defecto), el script nunca mira más atrás de
esa ventana — así, si el checkpoint se pierde o el cron estuvo caído varias
horas, no inunda el canal con todo el backlog de golpe. En operación normal
esto no se nota: el checkpoint (que se actualiza cada corrida) es siempre
más reciente que la ventana de 12h.

En la **primera corrida** de un feed (sin checkpoint todavía) tampoco se
publica todo el histórico: se toman como máximo `initial_backfill` víctimas
(5 por defecto) y siempre dentro de la ventana de `max_lookback_hours`.

Si en una corrida aparecen más víctimas nuevas que `max_items_per_run`, se
publican esas y se manda una tarjeta corta avisando cuántas quedaron fuera
(no se pierden del checkpoint: quedan marcadas como vistas para no
reintentarlas eternamente, pero tampoco inundan el canal).

---

## Despliegue en un servidor Linux con cron

Pasos para clonar el repo en un servidor Linux y dejarlo corriendo con
crontab.

### 1. Clonar y crear el entorno virtual

```bash
git clone <url-de-tu-repo> ransom-monitor
cd ransom-monitor

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

Requiere Python 3.9+ (`python3 --version` para verificar; casi cualquier
distro reciente ya lo trae).

### 2. Configurar secretos

```bash
cp .env.example .env
chmod 600 .env          # solo el dueño puede leerlo — contiene la API key y los webhooks
nano .env                # o vim/tu editor preferido
```

Completa `RANSOMWARE_LIVE_API_KEY` y los `TEAMS_WEBHOOK_*` de los países que
vayas a usar (ver "Configuración" arriba). `.env` está en `.gitignore`, así
que nunca se sube al repo — transfiérelo al servidor por un canal seguro
(scp, un gestor de secretos, etc.), no lo pegues en el historial de git ni en
un ticket.

### 3. Habilitar los feeds que quieras

Edita `config/global.yaml` y `config/countries/<código>.yaml` (`enabled:
true`/`false`) según lo que hayas configurado en `.env`.

### 4. Probar antes de programarlo

```bash
cd ransom-monitor
.venv/bin/python -m ransom_monitor.main --dry-run
```

Revisa `logs/ransom_monitor.log` y confirma que valida la API key y detecta
los feeds esperados. Si quieres ver una tarjeta real llegar a Teams antes de
dejarlo en automático:

```bash
.venv/bin/python -m ransom_monitor.main --feed MX
```

### 5. Crontab cada 10 minutos

```bash
crontab -e
```

Agrega (ajusta la ruta a donde clonaste el repo):

```cron
*/10 * * * * cd /home/USUARIO/ransom-monitor && /usr/bin/flock -n /tmp/ransom-monitor.lock .venv/bin/python -m ransom_monitor.main >> logs/cron.log 2>&1
```

Notas sobre esta línea:

- `cd /home/USUARIO/ransom-monitor &&` — necesario para que `python -m
  ransom_monitor.main` encuentre el paquete (cron no hereda tu shell/PATH ni
  tu directorio de trabajo habitual).
- `flock -n /tmp/ransom-monitor.lock` — evita que se solapen dos corridas si
  una tarda más de 10 minutos (por ejemplo, si hay muchos países habilitados
  con muchas víctimas nuevas a la vez). Si el lock ya está tomado, esa
  invocación simplemente no hace nada y espera al siguiente tick.
- El log del propio cron (stdout/stderr del comando) queda en
  `logs/cron.log`, además del log interno más detallado en
  `logs/ransom_monitor.log` (con nivel `run.log_level` de
  `config/settings.yaml`).
- Todas las fechas que usa el checkpoint son ISO-8601 con offset de zona
  horaria (UTC), así que la zona horaria del servidor no afecta la lógica
  de "qué es nuevo".

Verifica que el cron esté corriendo:

```bash
tail -f logs/cron.log logs/ransom_monitor.log
```

### 6. Mantenimiento

- **Logs**: no rotan solos. Si te preocupa que crezcan, agrega una entrada
  de `logrotate` (`/etc/logrotate.d/ransom-monitor`) o trúncalos
  periódicamente con otro cron (`: > logs/ransom_monitor.log`).
- **Estado**: `state/state.json` (checkpoint por feed) y
  `state/group_cache.json` (caché de perfiles de grupo) son el único estado
  persistente. Haz backup si te importa no repetir el `initial_backfill` tras
  una migración de servidor.
- **Actualizar el código**: `git pull` + reinstalar dependencias si cambió
  `requirements.txt` (`pip install -r requirements.txt` con el venv
  activado). No hace falta tocar `.env` ni `state/`.
- **Cuota de la API**: con 24 feeds (global + 20 países LATAM) cada 10
  minutos son ~103,680 peticiones de víctimas al mes en el peor caso de
  tenerlos todos activos, muy por debajo del límite de 500,000/mes. Las
  llamadas a `/group/<nombre>` se cachean 24h, así que suman muy poco al
  total.

## Logs y estado

- Logs en `logs/ransom_monitor.log` (más `logs/cron.log` en Linux si usas la
  línea de crontab de arriba).
- Estado en `state/state.json` (checkpoint) y `state/group_cache.json`
  (perfiles de grupo). Bórralos (o usa `--reset-state` para el primero) si
  quieres reprocesar todo desde cero.

Ambas carpetas están en `.gitignore`.

## Seguridad

- `.env` contiene secretos (API key y webhooks) y **nunca** debe subirse a
  git — ya está en `.gitignore`. Usa `.env.example` como plantilla si
  necesitas recrearlo o compartir la estructura con alguien más. En el
  servidor, restringe sus permisos con `chmod 600 .env`.
- La API key que se compartió originalmente por chat quedó guardada en
  `.env` local. Como fue enviada en texto plano en una conversación,
  considera rotarla desde tu panel de ransomware.live si te preocupa su
  exposición.
