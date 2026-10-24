FROM katrain-golaxy:4bf9a699a-name-guard-overlay
COPY assets/ /app/katrain/web/static/assets/
COPY index.html /app/katrain/web/static/index.html
LABEL io.smartbox.overlay.scope="Galaxy Latin brand font static only" io.smartbox.overlay.artifact="galaxy-brand-font-20261024" io.smartbox.overlay.css-sha256="10e120749af95841006d16e2fa96dc7ff1f3c2500e6ed4e20214126eee6ccaab" io.smartbox.overlay.font-sha256="01e17adcd642631e89b529fd50fb42a236abd603455d4b9aa63304de46f00794"
