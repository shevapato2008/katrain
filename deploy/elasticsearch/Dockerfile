# Fixed official amd64 patch manifest; change only with versions.lock.json review.
FROM docker.elastic.co/elasticsearch/elasticsearch:9.5.5-amd64@sha256:c40a1fb2bc6976821e5625d2329992a1e9c29df576e5955fdcba02421abf0d3c
COPY --chown=elasticsearch:root .plugins/ /tmp/kifu-es-plugins/
RUN cd /tmp/kifu-es-plugins && sha512sum --check plugins.sha512 \
    && /usr/share/elasticsearch/bin/elasticsearch-plugin install --batch file:///tmp/kifu-es-plugins/elasticsearch-analysis-ik-9.5.5.zip \
    && /usr/share/elasticsearch/bin/elasticsearch-plugin install --batch file:///tmp/kifu-es-plugins/analysis-kuromoji-9.5.5.zip \
    && /usr/share/elasticsearch/bin/elasticsearch-plugin install --batch file:///tmp/kifu-es-plugins/analysis-nori-9.5.5.zip \
    && rm -rf /tmp/kifu-es-plugins
