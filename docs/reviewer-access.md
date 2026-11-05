# Read-only access for reviewers

Reviewers can log in to both servers to check how System A and System B are configured
and what data they hold, without being able to change anything. Access is through the
Linux user `revisor` with an SSH key handed over by the author, and it expires on
**31/03/2027**.

What "read-only" means here:

- no sudo, no docker, no access to the author's home directory;
- on B, a Kubernetes token bound to the built-in `view` role: every resource in the
  `landslide` namespace except Secrets, plus nodes, volumes and RBAC; no exec, no
  port-forward, no changes;
- a MySQL user with only `SELECT` (and `SHOW VIEW`) on the systems' databases;
- a per-user firewall: `revisor` can only open connections to the endpoints listed
  below. Redis, RabbitMQ, Consul, the services' own APIs and the internet are rejected.

## For reviewers

Before the first use on Linux/macOS: `chmod 600 revisor-key`.

### System B — go-tesis (k3s) · 178.105.104.95

```bash
ssh -i revisor-key revisor@178.105.104.95
```

| to check | command |
|---|---|
| everything deployed | `kubectl get all,pvc,configmap` |
| one component's manifest | `kubectl get deploy prometheus -o yaml` |
| Prometheus configuration | `kubectl get configmap prometheus-config -o yaml` |
| a service's logs | `kubectl logs deploy/early-warning --tail=100` |
| node, volumes, storage | `kubectl get nodes,pv,storageclass` |
| databases (SELECT only) | `revisor-mysql early-warning -e "SHOW TABLES"` (also `data-management`, `project-management`, `user-management`) |

Prometheus UI, from your own machine:

```bash
ssh -i revisor-key -L 8001:127.0.0.1:8001 revisor@178.105.104.95 kubectl proxy --port=8001
```

then open <http://localhost:8001/api/v1/namespaces/landslide/services/prometheus:9090/proxy/query>.
The proxy only lets `GET` through.

### System A — concurso (systemd) · 204.168.203.32

```bash
ssh -i revisor-key revisor@204.168.203.32
```

| to check | command |
|---|---|
| running services | `systemctl list-units --type=service --state=running` |
| a service's definition | `systemctl cat prometheus.service` |
| a service's logs | `journalctl -u early-warning-service -n 100` |
| Prometheus configuration | `curl -s localhost:9090/api/v1/status/config` |
| databases (SELECT only) | `mysql -P3307 -e "SHOW DATABASES"` (instances on ports 3306–3310) |

Prometheus UI, from your own machine:

```bash
ssh -i revisor-key -N -L 9090:127.0.0.1:9090 revisor@204.168.203.32
```

then open <http://localhost:9090>.

### Code and manifests

The systems' manifests and test tooling are in
[`tifacusil/go-tesis-infra`](https://github.com/tifacusil/go-tesis-infra); this repo holds
the data and scripts behind the results.

## For the author: granting and revoking access

The scripts are in [`scripts/reviewer-access/`](../scripts/reviewer-access/). Each one
prints its usage when run with no arguments (`setup_reviewer_k8s.sh` with `-h`).

| file | what it does |
|---|---|
| [`setup_reviewer_k8s.sh`](../scripts/reviewer-access/setup_reviewer_k8s.sh) | B only, no sudo. Applies `reviewer-readonly.yaml`, issues a token that expires on the given day and writes `~/revisor-kubeconfig.yaml`, and creates the SELECT-only MySQL user in the four `mysql-*-0` pods. |
| [`reviewer-readonly.yaml`](../scripts/reviewer-access/reviewer-readonly.yaml) | ServiceAccount `revisor` and its RBAC: `view`, cluster-scoped reads, and `GET` on Prometheus's Service proxy. |
| [`setup_reviewer.sh`](../scripts/reviewer-access/setup_reviewer.sh) | Both servers, with sudo. Creates the Linux user, `~/.my.cnf`, the per-user nftables firewall and, on A, the SELECT-only MySQL user on every instance, `systemd-journal` membership and Prometheus without `--web.enable-lifecycle`. `--revoke` undoes the Linux part. |

Granting, with a key pair made once on the author's machine
(`ssh-keygen -t ed25519 -C revisor-tesis -f revisor-key`) and `revisor-key.pub` copied to
both servers:

```bash
# System B (go-tesis), from the folder holding the scripts
bash setup_reviewer_k8s.sh 2027-03-31
sudo bash setup_reviewer.sh ~/revisor-key.pub 2027-03-31

# System A (concurso): any random string as the reviewer's MySQL password
head -c 32 /dev/urandom | base64 | tr -d '/+=\n' | head -c 24 > ~/revisor-mysql-password.txt
chmod 600 ~/revisor-mysql-password.txt
sudo bash setup_reviewer.sh ~/revisor-key.pub 2027-03-31
```

Hand the reviewers `revisor-key` (the private key) through a private channel and point
them to this document. The private key, the MySQL password and the kubeconfig never go
into this repo.

Revoking before the expiry date:

```bash
sudo bash setup_reviewer.sh --revoke          # on each server
kubectl -n landslide delete -f reviewer-readonly.yaml   # B: also invalidates the token
# MySQL, on every instance: DROP USER revisor@'%' (B) / revisor@'127.0.0.1' (A)
```
