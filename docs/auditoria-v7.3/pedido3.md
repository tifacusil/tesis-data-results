# Pedido 3 — alertas sin push por estado del breaker

Fuente: logs de early-warning del 29–30/09 (`v73_b_2026-11-20/pedido2/raw/logs_ew/`, ver `pedido2.md`). Script: `v73_b_2026-11-20/pedido2/alertas_sin_push_por_estado.py`. Salida: `v73_b_2026-11-20/pedido2/alertas_sin_push_por_estado.csv`. Ejecutado el 2026-11-20 (UTC), solo sobre archivos locales.

Método. Cada línea `alert_emitted` se une, por `trace_id` y pod, con la línea `push_flow_failed` de la misma alerta. El estado del breaker al despacharse sale del error:

- **(a) cerrado**: `rpc error: code = DeadlineExceeded`, invocaciones 1–5 de la repetición en esa réplica (la 5.ª abre el circuito);
- **(b) abierto**: `grpcx: circuit open` (rechazo sin llamar a user-management);
- **(c) semiabierto**: `DeadlineExceeded` a partir de la 6.ª invocación, es decir, sondas semiabiertas fallidas.

La partición coincide con la columna `lectura` de `cronologia_breaker_eventos.csv` en las 6 combinaciones de repetición y réplica. Ventana: de la inyección al retiro del retardo, ambos incluidos, por la hora de `alert_emitted`.

## Resumen

| repetición | pod | (a) cerrado | (b) abierto | (c) semiabierto | sin push (`resolve_failed`) | push entregado |
|---|---|---|---|---|---|---|
| 1 (03:33:12–03:37:16) | cgprm | 5 | 90 | 2 | 97 | 3 |
| 1 | chqw5 | 5 | 95 | 2 | 102 | 2 |
| 1 | **total** | **10** | **185** | **4** | **199** | **5** |
| 2 (03:41:32–03:45:35) | cgprm | 5 | 85 | 2 | 92 | 2 |
| 2 | chqw5 | 5 | 84 | 2 | 91 | 3 |
| 2 | **total** | **10** | **169** | **4** | **183** | **5** |
| 3 (03:49:53–03:53:56) | cgprm | 5 | 94 | 2 | 101 | 3 |
| 3 | chqw5 | 5 | 84 | 2 | 91 | 2 |
| 3 | **total** | **10** | **178** | **4** | **192** | **5** |

- Las sumas de sin push son 199 / 183 / 192, como en `alertas_breaker_por_push_path.csv`. No hay otros errores.
- Las 5 alertas con push entregado de cada repetición son las primeras tras la inyección (3,3–4,6 s), antes de que el retardo alcance a las llamadas en curso.
- La columna (b) es menor que las «Llamadas rechazadas» (190 / 174 / 183) porque esta ventana termina en el retiro: los rechazos entre el retiro y el cierre (13–14 s después) quedan fuera.

## Apertura de la repetición 3

Quinta invocación agotada: cgprm 113,335 s y chqw5 113,397 s tras la inyección. Las dos cifras son correctas: 113,3 s es la primera réplica en abrir y 113,4 s la segunda. Las tablas de `pedido2.md` y del artículo usan la segunda réplica (114,3 / 113,8 / 113,4 s), el instante desde el que el circuito está abierto en las dos.

## Commit y fechas de las pruebas dirigidas

| dato | valor | fuente |
|---|---|---|
| commit de `go-early-warning` | `fd5a866db21bfcb08066ded89b5ad51ab3b82b22`, 2026-09-29T22:02:40Z, «Merge pull request #4 from tifacusil/feat/o6-o7-alert-path-evidence» | campo `version` de cada línea de log de `early-warning-55859f5589-{cgprm,chqw5}`; `git log -1` en el clon local |
| imagen | `sha256:d5bae3eeaf58c5e0aaf962f00ce987e470bf12a91d85a19dfe1fd9d6d41026ad`, construida 2026-09-29T22:08:19Z | `experiment-manifest.json` → `imagenes_pruebas_dirigidas` |
| arranque de los pods | chqw5 2026-09-29T22:08:49Z, cgprm 2026-09-29T22:09:07Z, sin reinicios | `kubectl get pods` (`startTime`) |
| retardo hacia user-management | repeticiones a las 03:33:12, 03:41:32 y 03:49:53 del **2026-09-30 UTC** (22:33, 22:41 y 22:49 del 29/09 en hora local, UTC−5) | `netem-delay-ew-um-run-*.log` |

La fecha «29/09» de algunos documentos es la hora local del PC cliente; en UTC las tres repeticiones son del 30/09.
