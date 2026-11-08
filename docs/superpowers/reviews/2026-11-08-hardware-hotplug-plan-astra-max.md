# Hardware hotplug plan — independent Astra Max review

Reviewer: isolated `gpt-6-astra` / `max`, no inherited session reasoning. Plan: [implementation plan](../plans/2026-11-08-hardware-hotplug-recovery.md). Maximum two rounds, as requested.

## Round 1 — CHANGES REQUIRED

Four important amendments were identified against actual product/firmware/operator code:

1. The previous RK operator refused original Go mode. Specify combined idle evidence, owned fresh-start rollback, original page restoration and offline-camera handling before every transaction path; test success, startup API failure and early apply failure.
2. Serial deadlines must cover writes and boot/handshake reads, including unterminated input, rather than only command ACK reads. Retain lease protection for an uninterruptible native open.
3. Silent/invalid idle LINK responses must eventually close/reconnect the transport, while an explicit legacy `ERR cmd` retains transport and unknown Board A status.
4. Firmware BRIGHT displays the retained frame. Acknowledge CLEAR and SHOW before BRIGHT so recovery cannot display an old strict pattern.

The controller revised the plan for all four items. The plan also records the fresh develop baseline `954a374bdd0cf5661a9e7e556af7f699928edfbe` and the device's actual non-game baipu URL. No implementation began during this round.

## Round 2 — APPROVED

All four important amendments are explicit in implementation and tests. The reviewer additionally verified that baipu is an active hardware surface: the original-Go exception permits its URL only while the inactive calibration guard is rendered and collect=false, rejecting an active baipu board. The controller corrected this clause within round2.

Final verdict: **APPROVED**, no remaining blocking or important plan findings. Proceed to parallel implementation; product code and final release operators still require independent review. Physical unplug/replug acceptance remains pending. No third plan-review round occurred.
