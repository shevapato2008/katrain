# Transformer analysis engine (:8002)

Only the analysis service uses this image. Gameplay and ladder on `:8000` keep their existing image and certified models. Personal reports, live analysis, and professional kifu analysis use the default model on `:8002`.

## Pinned inputs

| Input | Identity |
| --- | --- |
| Network | `kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz` |
| Network SHA-256 | `93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871` |
| KataGo release | `v1.18.2`, Git `fd0723fdbc0e9d82cf269c9630af8c27c57c07c4`, CUDA 12.1/cuDNN 9.8.0 build |
| Official Linux zip SHA-256 | `3e30b486b7bc38287eeead350aa832ff8ca50d1f0c0a83b5409cabf8a3bc9c5d` |
| Runtime base | `docker.m.daocloud.io/nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04@sha256:2fcc4280646484290cc50dce5e65f388dd04352b07cbe89a635703bd1f9aedb6` |
| Wrapper | Vendored `realtime_api/` snapshot from KataGo checkout `74d7e7fe`, with `initialPlayer` preserved in the request model. |

The network and official zip are fetched from [KataGo's network archive](https://katagotraining.org/networks/) and [official v1.18.2 release](https://github.com/lightvector/KataGo/releases/tag/v1.18.2). Verify both checksums before building. Do not commit the binary or model.

## Build

In a separate staging directory, copy this directory, unzip the official release into `engine/` so `engine/katago` and `engine/analysis_example.cfg` exist, then run:

```sh
docker build -t katago-transformer:20261002-tf3-b11c768 .
```

The image has **one** configured analysis model and verifies its SHA before reporting `ready`. Mount the network file at `/opt/katago/models/kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz`. The wrapper serves `/health` and `/analyze` on container port 8000. `KATAGO_EXPECTED_MODEL_SHA256` must be set to the same SHA in `katrain-cron` when the service is switched.

## Evidence from the test host

- Host: `home-ubuntu`, RTX 3090 GPU 1, old gameplay and analysis engines left running during the probe.
- Official engine and network verified by SHA. A standalone 19×19 request at 2000 visits returned `rootInfo.visits=2003`, a final result, candidate moves, and 361 ownership values.
- The pinned wrapper on localhost `:18002` returned `ready=true`, `default_model=tf3-b11c768`, verified network SHA, and a complete 2000-visit response with the same KaTrain field names as b28.
- Handicap probe with two initial black stones and `initialPlayer=W` returned `rootInfo.currentPlayer=W`.
- Test image with `curl` for the existing Compose healthcheck: `sha256:7004f5721d21dac82831ba136d1e98b4c809e958a0032395da2025bd645ca589`.

## Production result and corpus capacity

- Production `ucloud-v100` runs `katago-transformer:20261002-tf3-b11c768` on `:8002` (image `sha256:b242fd2a379b28b7dda5cf965e41230324bc825e7d23cd4aa1c0c81f7a16798e`). `katrain-cron:transformer-20261002` (image `sha256:592ed2612af059eb0442a47e8fd0cf2aa1877ae5152bca6fa0368666b7ad4b8e`) checks the pinned SHA. Both services are healthy. A real cron-client request returned 2003 root visits, 10 candidate moves and a 19×19 ownership map. The gameplay service on `:8000` retained its b28 model.
- A warm 2000-visit request on the V100 took about 9 seconds; four concurrent requests took 14.57 seconds total (0.274 positions/second). The candidate and existing gameplay engine used 3186 MiB GPU memory together during the probe.
- The production kifu catalog has 173025 rows and 173016 distinct byte-identical SGFs; nine rows are existing duplicate aliases. At roughly 200 positions per game, the canonical corpus needs about 34.8 million positions, or roughly four years of uninterrupted compute at the measured four-request rate, before yielding to user workloads. Measured report rows were about 2.8–3.0 KB each, implying roughly 100 GB for analysis rows before indexes; production had about 40 GB free at the feasibility check.
- The user chose to implement the system and run a small pilot, while **deferring full-corpus backfill**. Keep bulk admission disabled until capacity and storage are explicitly revisited.
- The production cloud disk device was expanded to 200G on 2026-10-02, but `lsblk` still showed a ~100G root partition and `df` showed only 35G free on the PostgreSQL data volume (`/var/lib/docker/volumes/katrain-ucloud_postgres-data/_data`). The unallocated device capacity is not yet database capacity. A future partition/filesystem resize still would not address the measured GPU throughput.

## Production Compose integration

`ucloud.override.yml` overrides **only** `katago-cron`'s image, config location, and model mount, plus the cron application's expected SHA. Keep the existing production Compose file and environment file. Dry run with both files and verify that only `katago-cron` and, when application code changes, `katrain-cron` are recreated. Check `:8000`'s default model SHA before and after.

The old engine image ID on production is `sha256:efdeb9de4f64faf68072d236a3f73ff5c1f38af9566d78a52af78ec03f3026f3`; the prior cron image is tagged `katrain-cron:pre-transformer-20261002`. Rollback uses the production base Compose configuration without this override for both services and restores the prior cron code/environment. Any partially written transformer reports must stay on transformer or be explicitly restarted with billing reconciliation, never resumed on b28. Completed legacy reports keep their unknown historical model identity.
