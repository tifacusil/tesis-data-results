# /etc/consul-template/consul-template.hcl — copied from the server (2026-10-20);
# only the token was replaced with a placeholder. Install as root:root 0600.

# Configuración de consul-template para regenerar la config de Nginx
# a partir de los servicios registrados en Consul.
#
# Uso en el servidor:
#   sudo consul-template -config=/etc/consul-template/consul-template.hcl
# o como servicio systemd (ver README en esta carpeta).

consul {
  address = "127.0.0.1:8500"
  token   = "<CONSUL_TOKEN_CONSUL_TEMPLATE>"

  retry {
    enabled     = true
    attempts    = 0          # reintentar indefinidamente
    backoff     = "250ms"
    max_backoff = "10s"
  }
}

# Recarga Nginx solo si pasó la validación; evita aplicar una config rota.
template {
  source      = "/etc/consul-template/templates/nginx.conf.ctmpl"
  destination = "/etc/nginx/sites-enabled/default"
  perms       = 0644

  # Valida la sintaxis antes de sobrescribir el archivo destino.
  command     = "/bin/sh -c 'nginx -t && nginx -s reload'"

  # Agrupa cambios rápidos para no recargar Nginx en ráfaga.
  wait {
    min = "2s"
    max = "10s"
  }

  # Si el render produce un archivo vacío, NO sobreescribe el destino.
  error_on_missing_key = false
}

# Stream (TCP) upstream for data-receiving — auto-regenerated from Consul.
template {
  source      = "/etc/consul-template/templates/data-receiving.ctmpl"
  destination = "/etc/nginx/stream.d/data-receiving.conf"
  perms       = 0644
  command     = "/bin/sh -c 'nginx -t && nginx -s reload'"
  wait {
    min = "2s"
    max = "10s"
  }
  error_on_missing_key = false
}
