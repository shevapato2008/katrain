FROM katrain-web:kifu-ea2f9a67-wu-five-978491a2

COPY deploy/ucloud/kifu_cn_first_pass_legacy/identity.py /app/katrain/web/kifu/identity.py
COPY deploy/ucloud/kifu_cn_first_pass_legacy/kifu.py /app/katrain/web/api/v1/endpoints/kifu.py
COPY katrain/web/kifu/first_pass_cn.py /app/katrain/web/kifu/first_pass_cn.py
COPY katrain/web/kifu/data/cn_first_pass_2026-10-05.json.gz /app/katrain/web/kifu/data/cn_first_pass_2026-10-05.json.gz
RUN PYTHONPYCACHEPREFIX=/tmp/kifu-pycache python -m py_compile /app/katrain/web/kifu/identity.py \
    /app/katrain/web/kifu/first_pass_cn.py \
    /app/katrain/web/api/v1/endpoints/kifu.py
