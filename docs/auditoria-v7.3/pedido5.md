# Pedido 5 — ventana SQL de E4 frente al intervalo del generador

Ejecutado el 2026-11-21. Todas las horas en **UTC**. Material en `v75_2026-11-21/`; cada archivo está en `SHA256SUMS`. No se ejecutó ninguna consulta nueva sobre B: se leyeron archivos del repositorio y la exportación de la ventana de la auditoría 1 (`raw/export.tsv.gz`, no publicada; el script comprueba su SHA-256 `28cee4f9…0f05`, el de `README.md`).

```bash
py -I docs/auditoria-v7.3/v75_2026-11-21/ventana_e4.py --export <ruta>/export.tsv.gz
```

Sin `--export` el script reescribe `ventana_e4_fases.csv`, `ventana_e4_tramos.csv` y `ventana_e4_corridas_b.csv` con los mismos bytes, y no toca el resumen ni los bordes.

Relojes: Artillery usa el del PC cliente; `received_at`, el de data-receiving en el servidor de B. El desfase entre ambos no se midió durante la campaña.

## 1. Generador (corrida de 12 h de B)

Escenario `go-tesis-infra@c6732b0:load-tests/scenarios/vu-sustained-12h.yml` (igual en HEAD salvo fines de línea): fase `ramp-up` de 180 s con `arrivalRate: 1` y `rampTo: 100`, y fase `sustained-load-12h` de 43 200 s a 100/s. El informe (`data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json`) no registra eventos de fase; los límites nominales salen del primer evento más la duración de cada fase.

| | valor (reloj del cliente) | fuente |
|---|---|---|
| primer evento (`firstCounterAt`, primera trama creada) | 2026-09-23 12:31:20.398 | `aggregate` |
| último evento (`lastCounterAt`, último ACK) | 2026-09-24 00:34:21.989 | `aggregate` |
| duración primer–último evento | 43 381,591 s = 12 h 3 min 1,591 s | cálculo |
| rampa, nominal | 12:31:20.398 – 12:34:20.398 (180 s) | escenario |
| fase de 12 h, nominal | 12:34:20.398 – 00:34:20.398 (43 200 s) | escenario |

`ventana_e4_fases.csv` da las tramas por fase con los periodos de 10 s del informe. El periodo que empieza a las 12:34:20.000 contiene los últimos 0,398 s de la rampa; se asigna a la fase de 12 h.

## 2. Los 37 tramos

`ventana_e4_tramos.csv`: los 37 tramos de `v73_b_2026-11-20/dm_tramos_completo.csv` con el predicado con que se ejecutó cada uno, leído de `raw/dm.sql` (tramos 1–4, de 1 h) y `raw/dm2/dm2.sql` (tramos 5–37, de 15 min; el 37 dura 481 s).

- Todos usan `received_at >= desde AND received_at < hasta`: **semiabiertos**.
- El `hasta` de cada tramo es el `desde` del siguiente: sin solapes ni huecos.
- Cubren [2026-09-23 12:31:20, 2026-09-24 00:39:21) = 43 681 s = 12 h 8 min 1 s; suman 4 328 780 filas y 4 328 780 `message_id` distintos.
- La auditoría 1 (`sql/db_s0.sql`, `sql/db_export.sql`) usó `BETWEEN`, cerrado. Da el mismo recuento: no hay filas en 00:39:21 (§4).

**De dónde salen los 12 h 8 min 1 s:** 180 s de rampa + 43 200 s de carga sostenida + 1 s (`lastMetricAt` 00:34:21.989 truncado a 00:34:21) + 300 s de margen de vaciado (`docs/auditoria-resistencia-12h.md` §3). La prueba de 12 h es la fase sostenida; la ventana SQL incluye además la rampa y el margen.

## 3. Columna de tiempo

`gnss_readings.received_at`, `DATETIME` sin fracción, en UTC. Es la hora de **recepción en data-receiving** (`p.now().UTC()`, `go-data-receiving@13ac6fe:internal/parsing/parser.go:39`), que data-management guarda con `utc(e.ReceivedAt)` (`go-data-management@3d960a5:internal/persistence/repository.go:26,35`; DSN con `loc=UTC`, `internal/config/config.go:60`). No es `timestamp`, la marca virtual de la lectura (2019). Servidor MySQL: `@@system_time_zone = UTC` (`fuente/auditoria_db_b_2026-11-20/raw/s0_out.txt`).

La fracción de segundo se **trunca** en data-receiving: `parser.go:39` formatea con `"2006-01-02T15:04:05Z"`, sin fracción, así que MySQL recibe segundos enteros. `received_at = 00:34:23` significa una recepción en [00:34:23, 00:34:24) del reloj del servidor.

## 4. Filas de la ventana fuera del intervalo del generador

`ventana_e4_bordes_por_segundo.csv`: filas por segundo de `received_at` en los 15 primeros y los 15 últimos segundos con filas.

| | filas |
|---|---|
| `received_at` < 12:31:20 (antes del primer envío) | 0 (`MIN(received_at)` = 12:31:21) |
| `received_at` = 00:34:22 | 75 |
| `received_at` = 00:34:23 | 3 (`MAX(received_at)`) |
| `received_at` ≥ 00:34:24 (resto del margen de vaciado, hasta 00:39:21) | 0 |

**No es 0: 78 filas** tienen `received_at` posterior al segundo del último evento del cliente (00:34:21). Son tramas del generador, no otro tráfico:

- llevan `sensor_id` del conjunto del generador (§5);
- `received_at` se fija al recibir la trama, antes del ACK, así que el reloj del servidor iba por delante del del cliente. Estimación: el cliente creó 134 tramas desde las 00:34:20.000; las 134 últimas filas son 3 (00:34:23) + 75 (00:34:22) + las 56 últimas de 00:34:21 (100 filas), que empiezan hacia las 00:34:21.44. Desfase ≈ +1,4 s;
- el inicio cuadra: primera trama creada a las 12:31:20.398 (cliente), primera fila en [12:31:21, 12:31:22) (servidor), desfase entre +0,6 y +1,6 s.

El margen de 300 s no contiene ninguna fila después de las 00:34:23. La ventana [12:31:20, 00:34:24) da el mismo recuento que la publicada.

## 5. Otro tráfico en la ventana

`ventana_e4_corridas_b.csv` lista cada informe de Artillery y cada archivo de caos de B que hay en el repositorio.

- **Escalera y otras corridas de Artillery:** ninguna en la ventana. La última de la escalera de B (`vu-100-r5.json`) acabó el 2026-09-23 a las 08:59:23.985; no hay informes posteriores a la ventana.
- **Pruebas dirigidas** (AP5–AP7, retardo hacia user-management): 2026-09-29 y 2026-09-30, fuera de la ventana.
- **Inyecciones de la propia corrida** (`chaos/run-during-endurance.sh`, `docs/metrics-methodology.md`): `kill-rabbitmq` (snapshots 14:32:15 y 14:33:26), `pause-data-management` (18:32:20 y 18:34:04) y `netem-delay-ew-da` (22:32:18 y 22:36:07) caen **dentro** de la ventana porque forman parte de E4. Inyectan fallos, no tráfico: ninguno de los tres scripts envía tramas ni publica mensajes (`go-tesis-infra@c6732b0:chaos/kill-rabbitmq.sh`, `pause-data-management.sh`, `netem-delay-ew-da.sh`).
- **Reinicios:** el de data-receiving de las 14:33:02–14:33:04 cae dentro (`docs/auditoria-resistencia-12h.md`). No genera tramas propias; las 3 740 tramas que vació del buffer de Redis conservan su `message_id` y su `received_at` original, y `INSERT IGNORE` por `message_id` impide duplicados.
- **Comprobación sobre las filas:** filas = `message_id` distintos = ACK de Artillery = 4 328 780; las 4 328 780 tienen `sensor_id` del conjunto `GXZM-DB000…099` del generador (100 sensores, 0 fuera de él). Las pruebas dirigidas usan otros sensores (`pedido4.md` §6–7).

## 6. Los 9 095 envíos sobre 4 320 000

4 329 095 − 4 320 000 = 9 095. No son 91 s de carga sostenida adicional:

| parte | tramas | fuente |
|---|---|---|
| periodos de la rampa (12:31:20.000–12:34:20.000) | 8 952 | `ventana_e4_fases.csv` |
| periodos de la fase de 12 h (12:34:20.000–00:34:21.989) | 4 320 143 | ídem |
| total | 4 329 095 | `aggregate.counters["vusers.created"]` |

- **La rampa explica casi todo el excedente.** 4 320 000 es solo la fase sostenida; la rampa de 180 s de 1 a 100/s añade 8 952 tramas en sus 18 periodos completos (9 090 si fuera lineal y continua) más los últimos 0,398 s, a unas 100/s, que caen en el periodo de las 12:34:20.
- **Los 143 restantes** son esos ≈40 de la cola de la rampa más ≈1 s de emisión tras el fin nominal (00:34:20.398): el último periodo tiene 134 tramas creadas desde las 00:34:20.000.
- La fase sostenida fue estable: los 4 319 periodos completos de 10 s tienen entre 997 y 1 003 tramas.
- Emisión real: 12 h 3 min 1,6 s entre el primer y el último evento, frente a 12 h 3 min nominales.

## Tabla ítem → valor → archivo → SHA-256

| ítem | valor | archivo | SHA-256 |
|---|---|---|---|
| 1 primer / último evento del generador | 12:31:20.398 / 00:34:21.989 | `data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json` | `57fc9df4aec189820abdda08fdfa98b8060aa1a7a92543bb3439d9b17e985f50` |
| 1 fases (nominal, tramas) | rampa 180 s, 8 952; sostenida 43 200 s, 4 320 143 | `v75_2026-11-21/ventana_e4_fases.csv` | `16a168781f4de86914290ba1a0045edfac07d5657d234182beb9fc580dc9370f` |
| 2 tramos | 37, semiabiertos, contiguos, [12:31:20, 00:39:21) | `v75_2026-11-21/ventana_e4_tramos.csv` | `1a7ff284ef19391d9b8d0b392d79d5e7d0c89c7d77e8ea07567241f8bf913cc0` |
| 2 tramos (origen) | 4 328 780 filas | `v73_b_2026-11-20/dm_tramos_completo.csv` | `d53f673986c6ce41bc11307f497b7f8e13f101d926b1d4bb47fe6bf768a03783` |
| 2 consulta, tramos 1–4 | `received_at >= … AND received_at < …` | `v73_b_2026-11-20/raw/dm.sql` | `bb4c5f77cb6e9cee03ad547802140ea99f52fb8bbb3014688a3f44afa2bba3ad` |
| 2 consulta, tramos 5–37 | ídem | `v73_b_2026-11-20/raw/dm2/dm2.sql` | `3a53ff1f687ac135885709fd1e058abdf1a7ec2d05046453cb12fd26c4c47c9c` |
| 3–4 consulta de la exportación | `BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'` | `sql/db_export.sql` | `499e12e6474d0399cb544d2249546f20c7245cb0be2e9efad59ed86ebbdcf747` |
| 4 filas fuera del intervalo | 0 antes; 78 después (00:34:22: 75, 00:34:23: 3); 0 desde 00:34:24 | `v75_2026-11-21/ventana_e4_bordes_por_segundo.csv` | `969ccb85577e153a588b37c270501ec79c58f90a0a7cf23efc5e3daad49f834e` |
| 5 otras corridas en la ventana | 0 de Artillery; 3 inyecciones de la propia E4 | `v75_2026-11-21/ventana_e4_corridas_b.csv` | `f5665bc98d24a1d65ced3c1cf473a03346998213b30becbe7299412a73ed5d1e` |
| 1–6 resumen | todas las cifras de arriba | `v75_2026-11-21/ventana_e4_resumen.csv` | `642297616fa87aa81d4cb7279daeda9d2f06fa1fb422256ee88fc3ea77f30711` |
| script | — | `v75_2026-11-21/ventana_e4.py` | `c8db9f8771567c27ecde30f4a915e1a10d62eaae176e67d39213123edace4a2a` |
