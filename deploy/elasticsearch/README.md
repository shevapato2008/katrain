# Elasticsearch 9.5.5 Deployment & Provisioning

## 1. Plugin Preparation
Verified plugins (IK, Kuromoji, Nori) locked to specific SHA-512 hashes:
```bash
python3 deploy/elasticsearch/prepare_plugins.py
docker build -t katrain-elasticsearch:9.5.5-plugins deploy/elasticsearch
```

## 2. TLS Certificate Provisioning
Elasticsearch runs with HTTPS enabled on private/loopback interfaces. To generate the CA and server certificates with SAN (`localhost`, `127.0.0.1`, `kifu-search`, `elasticsearch`):

```bash
mkdir -p certs
# 1. Generate CA key and certificate (valid 10 years)
openssl genrsa -out certs/ca.key 2048
openssl req -x509 -new -nodes -key certs/ca.key -sha256 -days 3650 -out certs/ca.crt -subj "/CN=KifuSearchCA"

# 2. Generate node key and CSR
openssl genrsa -out certs/http.key 2048
openssl req -new -key certs/http.key -out certs/http.csr -subj "/CN=kifu-search"

# 3. Sign node certificate with Subject Alternative Names (SAN)
cat > certs/openssl-san.cnf <<EOF
[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = kifu-search
DNS.3 = elasticsearch
IP.1 = 127.0.0.1
EOF

openssl x509 -req -in certs/http.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
  -out certs/http.crt -days 3650 -sha256 -extfile certs/openssl-san.cnf -extensions v3_req

chmod 0600 certs/*.key
chmod 0644 certs/*.crt
```

## 3. Credentials & Permissions
- Store elastic superuser password in `secrets/elastic_password` with file mode `0600` (ES requires strict permissions on secret files).
- Start container: `docker compose -f deploy/elasticsearch/compose.yml up -d`
- Create security roles from `roles.json`:
  ```bash
  curl -sk -u elastic:<password> -X POST https://127.0.0.1:9200/_security/role/kifu_search_admin -H "Content-Type: application/json" -d @deploy/elasticsearch/roles.json
  ```
- Generate role API keys (admin, writer, read) and store in environment files with mode `0600`.
