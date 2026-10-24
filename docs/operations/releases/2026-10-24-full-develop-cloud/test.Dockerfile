FROM katrain-galaxy-brand:20261024-10e120749af9
USER root
WORKDIR /
RUN rm -rf /app
COPY --chown=10001:10001 source/ /app/
ENV KATRAIN_BUILD_SHA=495d0284c05cb7c9e8b388ded49a82f2959bfdf7 KATRAIN_FRONTEND_BUILD_SHA=495d0284c05cb7c9e8b388ded49a82f2959bfdf7
LABEL org.opencontainers.image.revision="495d0284c05cb7c9e8b388ded49a82f2959bfdf7" io.smartbox.release.scope="complete pinned application source and full/admin frontend; inherited dependency layer only"
WORKDIR /app
USER root
