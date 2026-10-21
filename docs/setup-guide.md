# Deploying System A and System B from scratch

How to rebuild the two systems the thesis compares **as they are today** on
the servers, not as the latest code in each repo describes them. Where the
server and a repo disagree, the server wins (it is what was measured) and the
difference is noted.

*infra* = [`tifacusil/go-tesis-infra`](https://github.com/tifacusil/go-tesis-infra),
which holds the manifests, scripts and runbooks.

| for… | see |
|---|---|
| running Phase 1 / Phase 2 on A and B | infra [`docs/runbook-fases.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/docs/runbook-fases.md) |
| the test methodology | infra [`docs/plan-pruebas.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/docs/plan-pruebas.md) |
| setting up the load client machine (TCP engine, dtu-emulator) | infra [`load-tests/README-engine.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/load-tests/README-engine.md) |
| fault injection | infra [`chaos/README.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/chaos/README.md) |
| k3s cluster bootstrap, step by step | infra [`k8s/bootstrap/README.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/k8s/bootstrap/README.md) |
| local Docker environment (neither of the measured systems) | infra [`local/README.local.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/local/README.local.md) |
| how the metrics were then extracted | [`metrics-methodology.md`](metrics-methodology.md) |

**Survey:** 2026-10-20, read-only, as each server's non-root user (neither
has passwordless sudo). Source tags:

- **[srv]** read on the live server (`systemctl cat`, `dpkg -l`, `--version`, `kubectl get`, `ss -ltn`, config files).
- **[repo]** read in a repository.
- **[inf]** inferred from [srv]/[repo] facts.
- **[NV]** not verified (§7).

---

## 0. Conventions

- **Repos:** System A's code lives in the repos **without** a prefix
  (`data-management-service`, `data-receiving-module-csharp`, …); System B's
  in the repos **with** the `go-` prefix. The *image name* does not follow
  that rule (§2), and `go-data-analysis` is Python, not Go.
- **Secrets:** written as `<PLACEHOLDER>`. Test-script variables: infra
  [`load-tests/.env.example`](https://github.com/tifacusil/go-tesis-infra/blob/main/load-tests/.env.example);
  cluster secrets: infra [`k8s/bootstrap/secrets.example.env`](https://github.com/tifacusil/go-tesis-infra/blob/main/k8s/bootstrap/secrets.example.env).
- **Paths:** `config/…` is relative to this repo; commands that copy from it
  assume a clone of this repo on the target server.

---

## 1. Hosts

| | System A | System B | source |
|---|---|---|---|
| hostname | `concurso` | `go-tesis` | [srv] |
| public IP | `204.168.203.32` | `178.105.104.95` | [srv] |
| SSH user | `concurso` | `gotesis` | — |
| Hetzner zone | `hel1-dc2` (Helsinki) | `fsn1-dc8` (Falkenstein) | [srv] metadata `169.254.169.254/hetzner/v1/metadata` |
| type | CX23 | CX23 | [NV] the metadata does not expose the type; check the Hetzner console |
| OS | Ubuntu 24.04.4 LTS, kernel 6.8.0-134-generic | Ubuntu 24.04.4 LTS, kernel 6.8.0-134-generic | [srv] |
| vCPU | 2 | 2 | [srv] `nproc` |
| RAM | 3,911,572 kB (3.7 GiB) | 3.7 GiB | [srv] `/proc/meminfo`, `free -h` |

> A's host also runs processes **unrelated to the thesis** that compete for
> its 2 vCPU / 3.7 GiB: a PM2 bot (`pm2-concurso.service`, app `discord-bot`)
> [srv]. Docker is installed, but its 2 containers are stopped and not part
> of the system [srv]. A from-scratch deployment should not install them; if
> the measurement is repeated, stop the bot or document it.

---

## 2. Repo → component map

| component | System A: repo → artifact | System B: repo → image | replicas A / B |
|---|---|---|---|
| data-receiving | `data-receiving-module-csharp` → self-contained .NET binary | `go-data-receiving` → `ghcr.io/tifacusil/go-data-receiving` | 3 / 3 |
| data-management | `data-management-service` → `data-management.jar` | `go-data-management` → `ghcr.io/tifacusil/data-management` | 2 / 2 |
| data-analysis | `data-analysis-service` (Python) → venv + gunicorn | `go-data-analysis` (**Python 3.12**, gRPC) → `ghcr.io/tifacusil/data-analysis` | 2 / 2 |
| early-warning | `early-warning-service` (Python) → venv | `go-early-warning` → `ghcr.io/tifacusil/early-warning` | 2 / 2 |
| user-management | `user-management-service` → `user-management-1.0.0.jar` | `go-user-managament` → `ghcr.io/tifacusil/user-management` | 1 / 1 |
| project-management | `project-management-service` → `project-management.jar` | `go-project-management-service` → `ghcr.io/tifacusil/project-management` | 1 / 1 |

Image of each B repo: [repo] the `IMAGE:` in its `.github/workflows/cd.yml`.
Replicas: A [srv] `systemctl list-units`; B [srv] `kubectl -n landslide get deploy`.

---

## 3. System A — native systemd services

Everything runs directly on the host, no containers. Discovery through
Consul, gateway through nginx, and nginx reconfigures itself from Consul
through consul-template.

### 3.1 Packages and versions

| component | installed version | how it is installed | source |
|---|---|---|---|
| OpenJDK | 17.0.20.1 (`openjdk-17-jre-headless 17.0.20.1+1-1~24.04`) | apt (Ubuntu) | [srv] |
| .NET | runtime 8.0.28, `net8.0` | **bundled** in the self-contained binary; no `dotnet` on the host | [srv] `DataReceiving.runtimeconfig.json`, `.deps.json` |
| Python | 3.12.3 (`python3.12`, `python3.12-venv`) | apt (Ubuntu) | [srv] |
| nginx | 1.24.0 (`nginx 1.24.0-2ubuntu7.18`, `libnginx-mod-stream 1.24.0-2ubuntu7.18`) | apt (Ubuntu) | [srv] |
| Consul | v1.22.7 | package (`/usr/bin/consul`, unit in `/usr/lib/systemd/system/`) — [inf] HashiCorp apt repo | [srv] |
| consul-template | v0.37.0 | binary in `/usr/local/bin` | [srv] |
| RabbitMQ | 3.12.1 (`rabbitmq-server 3.12.1-1ubuntu1.7`), Erlang `erlang-base 1:25.3.2.8+dfsg-1ubuntu4.8` | apt (Ubuntu) | [srv] |
| Redis | 7.0.15 (`redis-server 5:7.0.15-1ubuntu0.24.04.5`) | apt (Ubuntu) | [srv] |
| MySQL | 8.0.46 (`mysql-server 8.0.46-0ubuntu0.24.04.4`) | apt (Ubuntu) | [srv] |
| Prometheus | 3.5.4 | tarball in `/home/concurso/prometheus-3.5.4.linux-amd64` | [srv] |
| node_exporter | 1.11.1 | tarball in `/home/concurso/node_exporter-1.11.1.linux-amd64` | [srv] |
| mysqld_exporter | 0.19.0 | tarball in `/home/concurso/mysqld_exporter-0.19.0.linux-amd64` | [srv] |
| redis_exporter | v1.86.0 | tarball in `/home/concurso/redis_exporter-v1.86.0.linux-amd64` | [srv] |

```bash
sudo apt update
sudo apt install openjdk-17-jre-headless python3.12-venv \
  nginx libnginx-mod-stream rabbitmq-server redis-server mysql-server
```

> Ubuntu does not keep old versions in its archive: `apt install
> package=version` can fail once an update has shipped. Record what ends up
> installed (`dpkg -l`) and compare it with the table; if it differs, version
> parity with B (§5) has to be justified again.

**Spring Boot** versions inside the jars [srv] `MANIFEST.MF`:
data-management 3.5.14, user-management 3.2.12, both `Build-Jdk-Spec: 17`.
project-management: [NV] (the jar is not readable by user `concurso`).

### 3.2 MySQL — five instances

One `mysqld` per service plus the package's own. Each is its own unit with
its own `--defaults-file` [srv]:

| unit | port | mysqlx | datadir | database / user | source |
|---|---|---|---|---|---|
| `mysql.service` (package) | 3306, `bind-address = 0.0.0.0` | 33060 (127.0.0.1) | default | used by `mysqld_exporter` (user `exporter`) | [srv] |
| `mysql-data-mgmt.service` | 3307 | 33061 | `/var/lib/mysql-data-mgmt` | `data_management_db` / [NV] | [srv] cnf + data-management unit |
| `mysql-early-warning.service` | **3308** | 33062 | `/var/lib/mysql-early-warning` | `early_warning_db` / `landslide` | [srv] cnf + early-warning `.env` |
| `mysql-project-mgmt.service` | 3309 | 33063 | `/var/lib/mysql-project-mgmt` | `project_management_db` / `landslide` | [srv] cnf + project-management unit |
| `mysql-user-management.service` | 3310 | 33064 | `/var/lib/mysql-user-management` | `user_management` / `landslide` | [srv] cnf + user-management `.env` |

Each `/etc/mysql/mysql-<x>.cnf` sets at least `port`, `datadir`, `socket`
(`/var/run/mysqld/mysqld-<x>.sock`), `mysqlx_port` and `mysqlx_socket`. The
unit always follows the same pattern:

```ini
# /etc/systemd/system/mysql-<x>.service
[Unit]
Description=MySQL - <x>
After=network.target
[Service]
ExecStart=/usr/sbin/mysqld --defaults-file=/etc/mysql/mysql-<x>.cnf
User=mysql
Restart=on-failure
[Install]
WantedBy=multi-user.target
```

Initializing each datadir: [NV] the server shows the result, not how it was
created. The standard way is
`sudo -u mysql mysqld --defaults-file=/etc/mysql/mysql-<x>.cnf --initialize`
before the first start, then creating the database and user. The Java apps
create their own schema at startup; for table reference see infra
`k8s/base/infra/mysql-*/initdb/` (those are B's).

### 3.3 Redis

The package's `redis-server.service`, listening on `0.0.0.0:6379` [srv]. It
requires a password (`requirepass`): without it `reset-state.sh` fails with
`NOAUTH` [repo infra `load-tests/.env.example`]. The rest of
`/etc/redis/redis.conf` (maxmemory, persistence) is [NV] (not readable
without sudo).

```
requirepass <REDIS_PASSWORD>
```

### 3.4 RabbitMQ

`rabbitmq-server.service`, AMQP on `5672`, `rabbitmq_management` plugin
enabled (UI on `15672`) [srv `/etc/rabbitmq/enabled_plugins`, `ss`]. There
is no `/etc/rabbitmq/rabbitmq.conf` [srv]. data-receiving publishes to the
`sensors.raw` exchange as user `data-receiver` [srv unit].

A's users, queues and bindings: [NV] (needs `sudo rabbitmqctl`). To survey
them: `sudo rabbitmqctl list_users`, `list_exchanges`, `list_queues name
arguments`, `list_bindings`. B's topology (infra
`k8s/base/infra/rabbitmq/config/definitions.json`) uses **different user
names** (`data_receiving` with an underscore), so it cannot be assumed to
match.

### 3.5 Consul

The package's `consul.service`, a single server [srv `/etc/consul.d/consul.hcl`]:

```hcl
datacenter       = "landslide-monitoring"
data_dir         = "/opt/consul/data"
node_name        = "consul-server-01"
bind_addr        = "0.0.0.0"
client_addr      = "0.0.0.0"
advertise_addr   = "204.168.203.32"
server           = true
bootstrap_expect = 1
ui_config { enabled = true }
ports {
  dns = 8600
  http = 8500
  serf_lan = 8301
  serf_wan = 8302
  server = 8300
}
acl {
  enabled        = true
  default_policy = "deny"
  down_policy    = "extend-cache"
}
```

(`dns_config`, `performance` and `log_level` omitted.) With `default_policy = "deny"`, every service needs a token to
register and consul-template needs one to read the catalog (§3.7). Creating
the tokens after `consul acl bootstrap` is [NV] (the ACL setup is not
readable without a token).

### 3.6 Microservices

Common pattern: a dedicated system user, code in `/opt/<service>`, secrets
outside the unit. Units copied from the server [srv `systemctl cat`]; only
passwords were replaced with placeholders.

> **Do not copy how secrets are stored today.** The live data-management and
> project-management units carry passwords in `Environment=` lines (readable
> by any user through `systemctl cat`). When rebuilding, move them to an
> `EnvironmentFile=` with mode `0640 root:<user>`, as data-receiving already
> does.

| service | unit | instances → ports | user | source |
|---|---|---|---|---|
| data-receiving | `data-receiving@.service` | `01`/`02`/`03` → TCP **5000/5006/5008**, HTTP health+metrics **8081/8087/8089** | `data-receiving` | [inf] per-instance env unreadable; ports from `ss`, the rendered stream config (§3.7) and `prometheus-system-a.yml` |
| data-management | `data-management@.service` | `8082`, `8086` (instance name = port) | `data-management` | [srv] |
| data-analysis | `data-analysis@.service` | `a`, `b` → **8090/8091** on 127.0.0.1 | `data-analysis` | [inf] env unreadable; ports from the nginx upstream and `ss` |
| early-warning | `early-warning-service.service` + `early-warning-service@8092.service` | **8088** (`FLASK_PORT` in `.env`) and **8092** (`/etc/early-warning-service/8092.env`) | root (the unit sets no `User=`) | [srv] |
| user-management | `user-management.service` | **8085** (`SERVER_PORT`) | `concurso` | [srv] |
| project-management | `project-management-service@.service` | `8084` | `projectmgmt` | [srv] |

#### data-receiving (C#)

```ini
# /etc/systemd/system/data-receiving@.service
[Unit]
Description=Landslide Monitoring — Data Receiving Service (instance %i)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=data-receiving
Group=data-receiving
WorkingDirectory=/opt/data-receiving
ExecStart=/opt/data-receiving/DataReceiving
ExecStopPost=/opt/data-receiving/consul-deregister.sh %i
Restart=on-failure
RestartSec=5s
StartLimitIntervalSec=60s
StartLimitBurst=5
Environment=DOTNET_ENVIRONMENT=Production
Environment=RECEIVER__OUTPUTMODE=rabbitmq
Environment=RECEIVER__REDIS__CONNECTIONSTRING=204.168.203.32:6379
Environment=RECEIVER__REDIS__BUFFERTLTHOURS=24
Environment=RECEIVER__REDIS__RETRYINTERVALSECONDS=30
Environment=RECEIVER__REDIS__RETRYMINAGEMINUTES=2
Environment=RECEIVER__RABBITMQ__HOST=204.168.203.32
Environment=RECEIVER__RABBITMQ__PORT=5672
Environment=RECEIVER__RABBITMQ__VIRTUALHOST=/
Environment=RECEIVER__RABBITMQ__USERNAME=data-receiver
Environment=RECEIVER__RABBITMQ__EXCHANGE=sensors.raw
Environment=RECEIVER__RABBITMQ__CONFIRMTIMEOUTSECONDS=5
Environment=RECEIVER__CONSUL__ADDRESS=http://204.168.203.32:8500
Environment=RECEIVER__CONSUL__SERVICEVERSION=1.0.0
Environment=RECEIVER__CONSUL__ENVIRONMENT=prod
# per instance: RECEIVER__PORT, RECEIVER__CONSUL__INSTANCEID,
# RECEIVER__CONSUL__HEALTHPORT, RECEIVER__DLXPATH
EnvironmentFile=/etc/data-receiving/%i.env
EnvironmentFile=/etc/data-receiving/secrets
StandardOutput=journal
StandardError=journal
SyslogIdentifier=data-receiving-%i
LimitNOFILE=65536
PrivateTmp=true
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
```

`/etc/data-receiving/<NN>.env` — values [inf] from the nginx template's rule
(TCP port = Consul port − 3081):

```
# 01.env               # 02.env               # 03.env
RECEIVER__PORT=5000    RECEIVER__PORT=5006    RECEIVER__PORT=5008
RECEIVER__CONSUL__HEALTHPORT=8081  (8087)     (8089)
RECEIVER__CONSUL__INSTANCEID=<instance-id>
RECEIVER__DLXPATH=/var/log/data-receiving/dlx-<NN>   # [NV] exact path
```

`/etc/data-receiving/secrets` (the format that `deploy/install.sh` in the
`data-receiving-module-csharp` repo writes):

```
RECEIVER__RABBITMQ__PASSWORD=<RABBITMQ_PASSWORD_DATA_RECEIVER>
RECEIVER__REDIS__CONNECTIONSTRING=204.168.203.32:6379,password=<REDIS_PASSWORD>
RECEIVER__CONSUL__TOKEN=<CONSUL_TOKEN_DATA_RECEIVING>
```

Build: `dotnet publish` self-contained for `linux-x64` and `net8.0`, and
copy the output to `/opt/data-receiving/` together with
`consul-deregister.sh` (present on the server, contents [NV]). The repo's
`deploy/install.sh` installs a **non-templated** single-instance unit: use
it for the user, directories and secrets, but replace the unit with the one
above.

#### data-management (Java)

```ini
# /etc/systemd/system/data-management@.service
[Unit]
Description=data-management (%i)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=data-management
WorkingDirectory=/opt/data-management
EnvironmentFile=/etc/data-management/secrets   # MYSQL_PASSWORD, RABBITMQ_PASSWORD, CONSUL_HTTP_TOKEN
Environment=CONSUL_BASE_URL=http://127.0.0.1:8500
Environment=SERVICE_IP=127.0.0.1
Environment=MYSQL_URL=jdbc:mysql://204.168.203.32:3307/data_management_db?useSSL=false&serverTimezone=UTC&allowPublicKeyRetrieval=true
ExecStart=/usr/bin/java -jar /opt/data-management/data-management.jar --server.port=%i
Restart=always
RestartSec=2
SuccessExitStatus=143
MemoryHigh=350M
MemoryMax=400M
[Install]
WantedBy=multi-user.target
```

Live drop-in at `data-management@8082.service.d/override.conf` [srv]
(whether instance 8086 has the same one is [NV]):

```ini
[Service]
Environment="JAVA_TOOL_OPTIONS=-Xms128m -Xmx256m -XX:+UseSerialGC -XX:MaxMetaspaceSize=160m -XX:TieredStopAtLevel=1 -Xss512k -Xlog:gc::time,level,tags"
Environment="SERVER_TOMCAT_THREADS_MAX=50"
Environment="CONSUL_ENABLED=true"
```

(Moving the inline secrets to the `EnvironmentFile` above is the only
intentional difference from the server.)

#### project-management (Java)

```ini
# /etc/systemd/system/project-management-service@.service
[Unit]
Description=Project Management Service (%i)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=projectmgmt
Group=projectmgmt
WorkingDirectory=/opt/project-management-service
Environment=APP_SEED_ENABLED=true
Environment=DB_URL=jdbc:mysql://204.168.203.32:3309/project_management_db
Environment=DB_USERNAME=landslide
EnvironmentFile=/etc/project-management-service/secrets   # DB_PASSWORD
ExecStart=/usr/bin/java -jar /opt/project-management-service/project-management.jar --server.port=%i
Restart=always
RestartSec=2
SuccessExitStatus=143
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/project-management-service
[Install]
WantedBy=multi-user.target
```

Drop-in `project-management-service@8084.service.d/override.conf` [srv]:

```ini
[Service]
Environment="JAVA_TOOL_OPTIONS=-Xms128m -Xmx384m -XX:+UseSerialGC -XX:MaxMetaspaceSize=160m -XX:TieredStopAtLevel=1 -Xss512k -Xlog:gc::time,level,tags"
Environment="SERVER_TOMCAT_THREADS_MAX=50"
Environment="SPRING_CLOUD_CONSUL_DISCOVERY_INSTANCE_ID=project-management-service-8084"
```

#### user-management (Java)

```ini
# /etc/systemd/system/user-management.service
[Unit]
Description=User Management Service
After=network.target
[Service]
User=concurso
WorkingDirectory=/opt/user-management
EnvironmentFile=/opt/user-management/.env
ExecStart=/usr/lib/jvm/java-17-openjdk-amd64/bin/java -jar /opt/user-management/user-management-1.0.0.jar
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=user-management
[Install]
WantedBy=multi-user.target
```

Drop-in `user-management.service.d/override.conf` [srv]: the same
`JAVA_TOOL_OPTIONS` as data-management (`-Xmx256m`) and
`SERVER_TOMCAT_THREADS_MAX=50`.

`/opt/user-management/.env` (non-secret keys surveyed [srv]):

```
DB_URL=jdbc:mysql://204.168.203.32:3310/user_management
DB_USERNAME=landslide
DB_PASSWORD=<MYSQL_PASSWORD_USER_MANAGEMENT>
CONSUL_HOST=204.168.203.32
CONSUL_PORT=8500
SERVER_PORT=8085
APP_HOST=204.168.203.32
# + seed keys: see user-management-service/.env.example
```

#### data-analysis (Python)

```ini
# /etc/systemd/system/data-analysis@.service
[Unit]
Description=Data Analysis Service (%i)
After=network.target
[Service]
Type=simple
User=data-analysis
Group=data-analysis
WorkingDirectory=/opt/data-analysis-service
EnvironmentFile=/etc/data-analysis-service/%i.env
ExecStart=/opt/data-analysis-service/venv/bin/gunicorn --bind ${ANALYSIS__HOST}:${ANALYSIS__PORT} --workers 2 --timeout 60 "app:create_app()"
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=data-analysis-service-%i
[Install]
WantedBy=multi-user.target
```

`/etc/data-analysis-service/{a,b}.env`: the keys in
`data-analysis-service/deploy/.env.example`, with `ANALYSIS__HOST=127.0.0.1`
and `ANALYSIS__PORT=8090` / `8091` [inf]. Install with
`python3.12 -m venv /opt/data-analysis-service/venv && venv/bin/pip install -r requirements.txt`.

> The repo's unit (`data-analysis-service/deploy/data-analysis.service`)
> **is not the one running**: it uses `/opt/data-analysis`,
> `gunicorn.conf.py` and `PROMETHEUS_MULTIPROC_DIR`. The live one has none
> of that. To reproduce the measurement, use the live one.

#### early-warning (Python)

Two units on the same code and the same `.env`; the `@8092` instance
overrides the port and turns off the scheduled jobs so they don't run twice:

```ini
# /etc/systemd/system/early-warning-service.service   (instance :8088)
[Unit]
Description=early-warning-service
After=network.target
[Service]
WorkingDirectory=/opt/early-warning-service
EnvironmentFile=/opt/early-warning-service/.env
ExecStart=/opt/early-warning-service/venv/bin/python app.py
Restart=always
[Install]
WantedBy=multi-user.target

# /etc/systemd/system/early-warning-service@.service  (instance :8092)
[Unit]
Description=early-warning-service (instance %i)
After=network.target
[Service]
WorkingDirectory=/opt/early-warning-service
EnvironmentFile=/opt/early-warning-service/.env
EnvironmentFile=-/etc/early-warning-service/%i.env
ExecStart=/opt/early-warning-service/venv/bin/python app.py
Restart=always
[Install]
WantedBy=multi-user.target
```

```
# /etc/early-warning-service/8092.env   [srv]
FLASK_PORT=8092
CONSUL_SERVICE_PORT=8092
REPORT_SCHEDULER_ENABLED=false
REPORT_PUSH_ENABLED=false
```

```
# /opt/early-warning-service/.env   (non-secret keys surveyed [srv])
FLASK_PORT=8088
MYSQL_HOST=204.168.203.32
MYSQL_PORT=3308
MYSQL_USER=landslide
MYSQL_DB=early_warning_db
MYSQL_PASSWORD=<MYSQL_PASSWORD_EARLY_WARNING>
USER_MANAGEMENT_URL=http://204.168.203.32
USER_MANAGEMENT_TOKEN=<USER_MANAGEMENT_TOKEN>
REPORT_SCHEDULER_ENABLED=true
REPORT_PUSH_ENABLED=true
FIREBASE_PRIVATE_KEY=<FIREBASE_PRIVATE_KEY>
# + remaining keys: see early-warning-service/README.md; full list [NV]
```

> Neither unit sets `User=`, so both run as **root**. When rebuilding, give
> them their own user.

### 3.7 nginx + consul-template (HTTP gateway :80 and TCP :5100)

nginx does two jobs, both with upstreams **generated** by consul-template
from the Consul catalog:

| job | listens on | rendered file | template |
|---|---|---|---|
| HTTP API gateway | `:80` | `/etc/nginx/sites-enabled/default` | [`config/system-a/nginx/templates/nginx.conf.ctmpl`](../config/system-a/nginx/templates/nginx.conf.ctmpl) |
| sensor TCP ingestion | `:5100` | `/etc/nginx/stream.d/data-receiving.conf` | [`config/system-a/nginx/templates/data-receiving.ctmpl`](../config/system-a/nginx/templates/data-receiving.ctmpl) |

The files in [`config/system-a/nginx/`](../config/system-a/nginx/) are
**copies from the server** taken on 2026-10-20, except
`consul-template.hcl`, which is **reconstructed** (the live one is 0600
root).

> The template in the `project-management-service` repo
> (`deploy/consul-template/`) is **out of date** compared with the server's:
> different service names (`user-management-service`,
> `data-analysis-service`), health on `/actuator/health` instead of
> `/health`, no `least_conn` on data-analysis, no regex route for
> readings/latest, and no stream template. Use the ones in
> `config/system-a/nginx/templates/`. Its README's rollback steps still apply.

**Step 1 — nginx with the stream module** [srv versions §3.1]

```bash
sudo apt install nginx libnginx-mod-stream
ls -l /etc/nginx/modules-enabled/50-mod-stream.conf   # symlink to mod-stream.conf (load_module ngx_stream_module.so)
sudo mkdir -p /etc/nginx/stream.d
sudo cp config/system-a/nginx/nginx.conf /etc/nginx/nginx.conf
```

The live `nginx.conf` is Ubuntu's plus a `stream { include
/etc/nginx/stream.d/*.conf; }` block at the end; `conf.d/` is empty.

**Step 2 — consul-template** [srv v0.37.0]

```bash
# official binary from releases.hashicorp.com/consul-template/0.37.0/
sudo install -m 0755 consul-template /usr/local/bin/consul-template
consul-template -v      # consul-template v0.37.0

sudo mkdir -p /etc/consul-template/templates
sudo cp config/system-a/nginx/templates/*.ctmpl /etc/consul-template/templates/
sudo install -m 0600 config/system-a/nginx/consul-template.hcl /etc/consul-template/consul-template.hcl
sudoedit /etc/consul-template/consul-template.hcl     # replace <CONSUL_TOKEN_CONSUL_TEMPLATE>
sudo cp config/system-a/nginx/consul-template.service /etc/systemd/system/
sudo mkdir -p /etc/systemd/system/consul-template.service.d
sudo cp config/system-a/nginx/consul-template.service.d/override.conf /etc/systemd/system/consul-template.service.d/
```

**Step 3 — service names in Consul.** The templates look up these names;
each service must register under them, with these ports:

| name in Consul | registered port | nginx upstream | fallback when no instance is healthy |
|---|---|---|---|
| `user-management` | 8085 | `user_management` | `127.0.0.1:8085` |
| `project-management-service` | 8084 | `project_management` | `127.0.0.1:8084` |
| `data-management-service` | 8082, 8086 | `data_management` | `127.0.0.1:8082` |
| `early-warning-service` | 8088, 8092 | `early_warning` | `127.0.0.1:8088` |
| `data-analysis` | 8090, 8091 | `data_analysis` (`least_conn`) | `127.0.0.1:8090`, `:8091` |
| `data-receiving` | **health** 8081/8087/8089 | `data_receiving` (stream, `least_conn`, port = registered − 3081) | `127.0.0.1:5000` |

Names: [srv] live templates. That the services actually register under those
names: [NV] (the catalog returns `{}` without a token because of the ACL).
Check with `curl -s -H "X-Consul-Token: <token>" http://127.0.0.1:8500/v1/catalog/services`.

> The fallbacks have **fewer instances** than the real system (a single one
> for data-management, early-warning and data-receiving). If consul-template
> cannot read Consul (wrong token, ACL), nginx keeps working but balances
> onto one replica, with no visible error. Always check the render (step 5).

**Step 4 — dry-run render and start**

```bash
sudo consul-template -config=/etc/consul-template/consul-template.hcl -once -dry
sudo systemctl daemon-reload
sudo systemctl enable --now consul-template
sudo nginx -t
```

**Step 5 — check that the render matches the reference server.** This is
what was rendered on `concurso` on 2026-10-20 [srv]:

```nginx
# sites-enabled/default (upstreams)
upstream user_management    { server 204.168.203.32:8085 max_fails=3 fail_timeout=10s; }
upstream project_management { server 204.168.203.32:8084 max_fails=3 fail_timeout=10s; }
upstream data_management    { server 127.0.0.1:8082 …; server 127.0.0.1:8086 …; }
upstream early_warning      { server 127.0.0.1:8088 …; server 127.0.0.1:8092 …; }
upstream data_analysis      { least_conn; server 127.0.0.1:8090; server 127.0.0.1:8091; }

# stream.d/data-receiving.conf
upstream data_receiving {
    least_conn;
    server 204.168.203.32:5000 max_fails=3 fail_timeout=10s;
    server 204.168.203.32:5006 max_fails=3 fail_timeout=10s;
    server 204.168.203.32:5008 max_fails=3 fail_timeout=10s;
}
server { listen 5100; proxy_pass data_receiving; proxy_timeout 30s; proxy_connect_timeout 5s; }
```

Routes of `server { listen 80; }` (from the template): `/api/v1/auth`,
`/api/v1/users`, `/api/v1/devices`, `/v3/api-docs` → user-management;
`~ ^/api/v1/projects/[^/]+/(readings|latest)` → data-management (the regex
beats the prefix); `/api/v1/projects` → project-management;
`/api/v1/sensors`, `/api/v1/readings` → data-management; `/api/v1/alerts` →
early-warning (rewritten to `/alerts`); `/data-analysis/` → data-analysis;
`/health/<service>` → the upstream's `/health`. All of them add an
`X-Upstream` header except `/v3/api-docs` and `/health/*`.

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://204.168.203.32/health/data-management   # the one chaos/ uses (runbook-fases.md)
curl -sI http://204.168.203.32/api/v1/sensors | grep -i x-upstream                       # alternates between :8082 and :8086
nc -zv 204.168.203.32 5100
```

### 3.8 Observability (Prometheus on the host)

```ini
# /etc/systemd/system/prometheus.service   [srv]
[Unit]
Description=Prometheus
After=network.target
[Service]
User=concurso
WorkingDirectory=/home/concurso/prometheus-3.5.4.linux-amd64
ExecStart=/home/concurso/prometheus-3.5.4.linux-amd64/prometheus \
  --config.file=/home/concurso/go-tesis-infra/local/infra/prometheus/prometheus-system-a.yml \
  --storage.tsdb.path=/home/concurso/prometheus-3.5.4.linux-amd64/data \
  --storage.tsdb.retention.time=365d \
  --web.enable-lifecycle
Restart=on-failure
[Install]
WantedBy=multi-user.target
```

- Listens on `:9090` [srv `ss`]; retention **365d** [srv].
- It reads its config **straight from a clone of the infra repo** on the
  server. The live content is identical to infra
  [`local/infra/prometheus/prometheus-system-a.yml`](https://github.com/tifacusil/go-tesis-infra/blob/main/local/infra/prometheus/prometheus-system-a.yml)
  on `main` [srv diff, 2026-10-20]; the server's clone is at `f6e641d` with
  that file modified and uncommitted.
- Scrapes every 15s. Jobs: `node` (`:9100`), `mysql` (`:9104`), `redis`
  (`:9121`), `microservices` (`/metrics` on 8082/8086, 8092, 8084, 8085,
  8090/8091, 8081/8087/8089) [repo].
- **Known gaps**, the same on the server, and relevant when comparing with B:
  - it does not scrape RabbitMQ (the file's comment says there is no
    management plugin, but the plugin **is** enabled [srv]);
  - early-warning only on `:8092`, not `:8088`;
  - `mysqld_exporter` points at `localhost:3306` (`mysql.service`), **not**
    at any of the four service databases (3307–3310) [srv];
  - `redis_exporter` runs with `-redis.addr redis://localhost:6379` and no
    password in its unit [srv], against a Redis that requires `requirepass`:
    whether its metrics are valid is [NV] (check `redis_up`).

Exporters (units [srv], all `User=concurso`, binaries from the §3.1 tarballs):

```
node_exporter      ExecStart=…/node_exporter
mysqld_exporter    ExecStart=…/mysqld_exporter --mysqld.address=localhost:3306 --mysqld.username=exporter --web.listen-address=:9104
                   Environment=MYSQLD_EXPORTER_PASSWORD=<MYSQL_EXPORTER_PASSWORD>
redis_exporter     ExecStart=…/redis_exporter -redis.addr redis://localhost:6379
```

### 3.9 A's port map

[srv] `ss -ltn` on 2026-10-20, with each port's owner taken from the configs above:

| port | bind | owner |
|---|---|---|
| 22 | 0.0.0.0 | ssh |
| 80 | 0.0.0.0 | nginx HTTP gateway |
| 5100 | 0.0.0.0 | nginx stream → data-receiving |
| 5000, 5006, 5008 | 0.0.0.0 | data-receiving 01/02/03 (TCP) |
| 8081, 8087, 8089 | 0.0.0.0 | data-receiving 01/02/03 (health/metrics) |
| 8082, 8086 | * | data-management |
| 8084 | * | project-management |
| 8085 | * | user-management |
| 8088, 8092 | 0.0.0.0 | early-warning |
| 8090, 8091 | 127.0.0.1 | data-analysis a/b |
| 3306 / 3307 / 3308 / 3309 / 3310 | 0.0.0.0 / * | MySQL (§3.2); mysqlx 33060–33064 |
| 5672, 15672, 25672, 4369 | * / 0.0.0.0 | RabbitMQ (AMQP, UI, clustering, epmd) |
| 6379 | 0.0.0.0 | Redis |
| 8300–8302, 8500, 8503, 8600 | * | Consul |
| 9090, 9100, 9104, 9121 | * | Prometheus and exporters |
| 127.0.0.1:8080, 127.0.0.1:6060 | 127.0.0.1 | [NV] unknown process (needs `sudo ss -ltnp`) |

---

## 4. System B — k3s

Everything lives in namespace `landslide`; infra `k8s/` is the source of
truth. On 2026-10-20 the live cluster matches `k8s/base` on infra `main`
[srv]: `kubectl diff -k` (a server-side dry run) against the server's clone
flagged only early-warning, rabbitmq, redis and the `rabbitmq-config`
ConfigMap, which are exactly the files changed on `main` after that clone;
the live values match `main`, and the live `definitions.json` /
`rabbitmq.conf` are identical to `main` except for CRLF line endings (they
were applied from a Windows checkout).

### 4.1 k3s

Follow infra `k8s/bootstrap/README.md` §1, but **pin the version** (the
README installs the latest):

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.35.5+k3s1 sh -
```

Versions on the server [srv]:

| component | version |
|---|---|
| k3s / Kubernetes | `v1.35.5+k3s1` |
| containerd | `2.2.3-k3s1` |
| Traefik (bundled with k3s) | `3.6.13` |
| CoreDNS | `1.14.3` |
| local-path-provisioner | `v0.0.36` |
| metrics-server | `v0.8.1` |

`/etc/rancher/k3s/k3s.yaml` is 0600 root; user `gotesis` uses a copy in
`~/.kube/config` (`export KUBECONFIG=$HOME/.kube/config`).

### 4.2 sealed-secrets, pull secret and secrets

Follow infra `k8s/bootstrap/README.md` §2–§4, pinning the controller to the
server's version (the README uses `latest`):

```bash
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.38.1/controller.yaml
```

Live controller: `bitnami/sealed-secrets-controller:0.38.1` [srv]. Use
`kubeseal` of the same version.

> **New cluster = new key.** The `SealedSecret`s in infra
> `k8s/overlays/prod/sealed-secrets/` can only be decrypted by the controller
> that sealed them. There are two ways forward: restore the controller key
> backup (bootstrap §2) **before** applying the overlay, or seal everything
> again with `k8s/bootstrap/seal-secrets.sh`. On top of that, the
> SealedSecrets committed on `main` are **older** than the ones running: the
> server's clone has those files modified and uncommitted [srv `git status`].
> Without the key backup, re-sealing is not optional.

Secrets the overlay expects [srv `kubectl get secrets`, repo infra
`overlays/prod/sealed-secrets/kustomization.yaml`]: `mysql-{data-management,
user-management,project-management,early-warning}`, `redis`, `rabbitmq`,
`data-receiving`, `data-management`, `early-warning`, `user-management`,
`project-management`, `mysqld-exporter`, plus the `ghcr` pull secret created
by hand. The live cluster also has a `data-analysis` secret that no
Deployment references (data-analysis only uses `configMapRef:
data-analysis-config`); it does not need to be recreated.

The MySQL user for the exporters is created with infra
`k8s/bootstrap/mysql-exporter-user.sh`.

### 4.3 Images — pin by digest

Every app Deployment uses `:latest` [repo and srv], and every `go-*` repo
republishes `:latest` from its `.github/workflows/cd.yml` [repo]. A fresh
deployment with `:latest` gets whatever is on `main`, **not** what was
measured. These are the digests running on 2026-10-20 [srv
`status.containerStatuses[].imageID`]:

| app | image | digest |
|---|---|---|
| data-receiving | `ghcr.io/tifacusil/go-data-receiving` | `sha256:bb3d9f0260a7c2748d39ce5ffe828d9fcecd92598aae4f90fa60257fda3b5df7` |
| data-management | `ghcr.io/tifacusil/data-management` | `sha256:2a1991e69e771f9ef92d4dd25667a2aa78346e4309e8e203ac9a893777ffab95` |
| data-analysis | `ghcr.io/tifacusil/data-analysis` | `sha256:b4bbf705e4a96c8dfd7d23f39937379694eed3e046401e530a1f498996e61d4f` |
| early-warning | `ghcr.io/tifacusil/early-warning` | `sha256:d5bae3eeaf58c5e0aaf962f00ce987e470bf12a91d85a19dfe1fd9d6d41026ad` |
| user-management | `ghcr.io/tifacusil/user-management` | `sha256:0cc0f2542ae8036248d362d3d60c3bc286b0162ebb23a01fb357495cbe73aba4` |
| project-management | `ghcr.io/tifacusil/project-management` | `sha256:e1c708090fc36064b30d0cb396018a8eeeb71e83d73c1e35ad960912717a718a` |

To pin them, add to infra `k8s/overlays/prod/kustomization.yaml`:

```yaml
images:
  - name: ghcr.io/tifacusil/go-data-receiving
    digest: sha256:bb3d9f0260a7c2748d39ce5ffe828d9fcecd92598aae4f90fa60257fda3b5df7
  - name: ghcr.io/tifacusil/data-management
    digest: sha256:2a1991e69e771f9ef92d4dd25667a2aa78346e4309e8e203ac9a893777ffab95
  # … one entry per table row
```

If GHCR no longer has those digests, rebuild from the `go-*` repos (§2); the
deployed code then differs from what was measured — record that.

Infrastructure: the versions (RabbitMQ `3.12.1-management-alpine`, Redis
`7.0.15-alpine`, MySQL `8.0.46`, Prometheus `v3.5.4`) and the reason for the
2026-09-15 downgrade are in infra
[`docs/runbook-fases.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/docs/runbook-fases.md)
("Versiones de infraestructura"); they match the live cluster [srv]. The
exporters, also live [srv]: `prom/mysqld-exporter:v0.19.0` (×4),
`kbudde/rabbitmq-exporter:1.0.0-RC22`, `oliver006/redis_exporter:v1.86.0`,
`prom/node-exporter:v1.9.1`, `kube-state-metrics:v2.13.0`.

### 4.4 Deploy

```bash
kubectl apply -k k8s/overlays/prod      # from a clone of the infra repo
kubectl -n landslide get pods,svc,ingressroute
```

Expected result [srv]: Deployments data-analysis 2/2, data-management 2/2,
data-receiving 3/3, early-warning 2/2, user-management 1/1,
project-management 1/1; StatefulSets mysql ×4, rabbitmq and redis 1/1;
`local-path` PVCs of 2Gi (each MySQL) and 1Gi (rabbitmq, redis).

### 4.5 Exposure

| what | how | port | source |
|---|---|---|---|
| TCP ingestion | Service `data-receiving-tcp`, `type: LoadBalancer` (k3s ServiceLB) | **5000** on the node IP | [repo + srv] |
| HTTP gateway | Traefik `IngressRoute landslide-gateway` (infra `k8s/base/ingress.yaml`), entrypoint `web` | 80 | [repo + srv] |
| health for chaos | `/api/v1/data/health` | 80 | [repo infra `runbook-fases.md`] |
| Prometheus | Service `prometheus`, `type: NodePort` | **31083** today | [srv] |

> **NodePort 31083 is not in the repo.** Infra
> `k8s/base/infra/observability/prometheus.yaml` declares `type: NodePort`
> with no `nodePort:`, so Kubernetes picked it at random. On a new
> cluster Prometheus will land on another port in 30000–32767; look it up
> with `kubectl -n landslide get svc prometheus` and update whatever points
> at 31083 (Grafana datasource, SSH tunnels, `metrics-methodology.md` §1).
> To pin it, add `nodePort: 31083` to the Service **before** the first
> `apply`.

### 4.6 B's Prometheus: do not restart it

Prometheus runs with `--storage.tsdb.retention.time=30d` on an **`emptyDir`**
volume [repo + srv]. An `emptyDir` lives as long as the *pod*: a container
restart (crash, OOMKill) keeps it, but anything that **recreates the pod**
—`kubectl rollout restart`, `kubectl delete pod`, an `apply` that changes the
Deployment's pod template, an eviction under memory pressure— **deletes all
the data**. Changing only the `prometheus-config` ConfigMap does not recreate
the pod (reload it with `/-/reload`, enabled by `--web.enable-lifecycle`).

On the measurement cluster it is **not** touched. The raw September data is
preserved in a TSDB backup; see [`metrics-methodology.md` §8](metrics-methodology.md#8-documentation-status).
On a new cluster, if persistence is wanted, swap the `data` volume for a PVC
before the first deployment; changing the volume on the existing cluster
recreates the pod.

### 4.7 Verification

The commands in infra `k8s/bootstrap/README.md` §6 and, for versions, the
ones in infra `docs/runbook-fases.md` ("Verificar contra el servidor antes de
una campaña").

---

## 5. A ↔ B version parity (as of 2026-10-20)

| component | A [srv] | B [srv] | same? |
|---|---|---|---|
| RabbitMQ | 3.12.1 (Erlang 25.3.2.8) | 3.12.1 (`-management-alpine`) | version yes; B's Erlang [NV] |
| Redis | 7.0.15 | 7.0.15 | yes |
| MySQL | 8.0.46 (Ubuntu) | 8.0.46 (official image) | yes |
| Prometheus | 3.5.4 | 3.5.4 | yes (retention: 365d vs 30d) |
| mysqld_exporter | 0.19.0 | 0.19.0 | yes (A watches 3306; B watches the 4 databases) |
| redis_exporter | v1.86.0 | v1.86.0 | yes |
| node_exporter | 1.11.1 | v1.9.1 | **no** |
| RabbitMQ exporter | — | 1.0.0-RC22 | A has none |

---

## 6. After deploying

1. Prepare the client machine: `cp load-tests/.env.example load-tests/.env`
   in the infra repo, then infra
   [`load-tests/README-engine.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/load-tests/README-engine.md).
2. Run the phases: infra
   [`docs/runbook-fases.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/docs/runbook-fases.md).
   Remember the three `reset-state.sh` defaults that are wrong for A (port
   3308, user `landslide`, database `early_warning_db`) and `REDIS_PASSWORD`.
3. Chaos: infra [`chaos/README.md`](https://github.com/tifacusil/go-tesis-infra/blob/main/chaos/README.md).
4. Extract the metrics: [`metrics-methodology.md`](metrics-methodology.md).

---

## 7. Not verified

| # | what | how to check |
|---|---|---|
| 1 | Server type CX23 (both) | Hetzner console |
| 2 | Live `consul-template.hcl`: second `template` block and where the token goes | `sudo cat /etc/consul-template/consul-template.hcl` |
| 3 | That the services register in Consul under the §3.7 names | `curl -H "X-Consul-Token: …" :8500/v1/catalog/services` |
| 4 | Consul ACL policies and tokens | `consul acl policy list` / `token list` with a management token |
| 5 | `/etc/data-receiving/0{1,2,3}.env` (inferred ports, `DLXPATH`) | `sudo cat` |
| 6 | `/etc/data-analysis-service/{a,b}.env` (inferred ports) | `sudo cat` |
| 7 | data-receiving's `consul-deregister.sh` | `cat /opt/data-receiving/consul-deregister.sh` |
| 8 | Full `redis.conf` (maxmemory, persistence) | `sudo grep -v '^#' /etc/redis/redis.conf` |
| 9 | A's RabbitMQ topology (users, queues, DLX) | `sudo rabbitmqctl list_users / list_queues name arguments / list_bindings` |
| 10 | data-management's MySQL user | `sudo systemctl show data-management@8082 -p Environment` (or `application.yml`) |
| 11 | project-management's Spring Boot version | `sudo unzip -p …/project-management.jar META-INF/MANIFEST.MF` |
| 12 | Drop-in for `data-management@8086` | `systemctl cat data-management@8086` |
| 13 | Processes on `127.0.0.1:8080` and `127.0.0.1:6060` | `sudo ss -ltnp` |
| 14 | Whether A's `redis_exporter` exports valid metrics without a password | `curl -s :9121/metrics \| grep '^redis_up'` |
| 15 | How A's MySQL datadirs and users were initialized | no source; rebuild following §3.2 |
| 16 | That GHCR still serves the §4.3 digests | `docker pull ghcr.io/tifacusil/<img>@sha256:…` |
| 17 | Erlang/OTP of B's RabbitMQ image | `kubectl -n landslide exec rabbitmq-0 -- rabbitmqctl status \| grep -i erlang` |
