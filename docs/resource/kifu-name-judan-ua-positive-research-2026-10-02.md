# Pending Ukrainian Judan research record

Prepared 2026-10-02 for event reference `judan-series-2026-10-02`, product language `ua`, source language `ja`, registry `2026-10-02.5`. This is one positive conventional-name research row for the Japanese Go 十段戦 series. It remains pending independent review.

The pinned [Ukrainian Wikipedia revision 47335190](https://uk.wikipedia.org/w/index.php?title=%D2%90%D0%BE_(%D0%B3%D1%80%D0%B0)&oldid=47335190) has HTML language `uk` and says in context: `Внутрішні змагання в країнах із професіональними лігами також не мають одного визнаного чемпіонату. Замість цього, існують і щороку розігруються кілька престижних титулів. Наприклад, у Японії четвірку найпрестижніших титулів складають Хон'імбо , Мейдзін , Кісей та Дзюдан .` The exact source-used candidate is `Дзюдан`.

Independent identity corroboration is the registered Nihon Ki-in host page [64th Judan edition](https://www.nihonkiin.or.jp/match/jyudan/064.html), HTTP 200, HTML language `ja`. It identifies the 64th edition, uses `十段戦` and `大和ハウス杯十段戦`, names the Nihon Ki-in, Kansai Ki-in, and Sankei Shimbun as organizers, and describes the challenger tournament and title match. The original event name is recorded as `十段戦` (`ja`).

## Controlled pending artifact

Research JSONL is stored outside the repository at `/Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ua-positive/research.pending.jsonl`; the same directory retains the validated output, raw HTML bodies, and `capture-manifest.json` (directory mode 700; files mode 600).

- Captured Ukrainian Wikipedia response: HTTP 200, body SHA-256 `8aaced11debb1203006cb61c7f2fc74881b04d689058b44a1d3d36e2e218595f`; passage SHA-256 `8408254c99d4bd53a7b4f02090dd999cf4539286e5ee5113101c5d22457aaefe`.
- Captured Nihon Ki-in response: HTTP 200, body SHA-256 `8fbcb6874cb91b68fb9af0edbc548fcee8a6ca94686f51f37c4705439da10d78`.
- Registry canonical SHA-256: `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`; raw registry file SHA-256: `2ebd1c462887632717f0b281ed983db41de7065d9e5f7c4332a4fef8a5624511`.
- Pending JSONL file SHA-256: `4d0b6e2bee3a4f2c8d76782eecae9babe30de71244ae1d16cab8cba1942b760e`; canonical research-row SHA-256: `0ed3778dc2e8d57f507aa1a9db966a38b0256f9133246baf74d136e4cb1b9224`.

Validation command completed successfully:

```sh
python scripts/kifu_name_research.py --registry docs/resource/kifu-name-source-registry-2026-10-02.5.json validate \
  --input /Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ua-positive/research.pending.jsonl \
  --output /Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ua-positive/research.validated.jsonl
```

The record preserves the prior UFGO HTTP 402 attempt as incomplete and records that no Wikidata exact entity-field check was performed. Neither limitation is represented as a negative result. The positive path does not use a `negative_closure` or `generated_review`. The record has no reviewer signature and is not a candidate or database-write approval. No existing documents, code, database, or production data were edited; no commit was made.
