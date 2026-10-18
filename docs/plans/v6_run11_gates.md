## CS eval (Phase 6, §13.2) — v6 vs the v5 production-pin baseline

**Verdict against ship criteria (1)–(4): NOT MET: (1) kills hold, (2) G-D1 = G-D2 = 0.** (5) is the Math/English smoke (Oct 7).

| | criterion | met |
|---|---|---|
| | (1) kills hold | ❌ |
| | (2) G-D1 = G-D2 = 0 | ❌ |
| | (3) K3 and G-Z no worse than v5 | ✅ |
| | (4) cost per test below v5 | ✅ |

### Kills and gates

| | v6 | v5 baseline | bar |
|---|---|---|---|
| K1 | 60/62 ❌ | 62/62 | GT-ZERO→AI-ZERO must be total (any false credit kills) |
| K2 | 29/196 = 14.80% ❌ | 20/196 = 10.20% | kill: ≤ v5 on the same fixtures (10.2%); target 2.4% not met |
| K4 | 2.5 ✅ | 10.25 | max ai_total_spread ≤ 8.25 |
| K3 within-precision | 0.8111 | 0.693 | ≥ v5 |
| G-Z GT-PARTIAL→AI-ZERO | 32/196 (16.3%) | 62/196 (31.6%) | ≤ v5 |
| G-D1 double-charged cells in D | 0 | — | 0 |
| G-D2 multi-tier charges in D | 4 | — | 0 |
| G-B bounds_clamped | 0 | — | report all |
| valid trials | 24/24 | 24/24 | |
| model_fallback (excluded) | 0 trials · 0 scopes | | AM-G18 |

### Cost per test (registry cards)

| component | v6 mean $ | cache hit |
|---|---|---|
| verifier (Sonnet 5.5) | 0.0652 | 89% |
| explainer (claude-sonnet-5-5) | 0.0853 | 62% |
| **v6 total (verifier + explainer)** | **0.1505** | |
| v5 baseline (verifier, incl. basis_he) | 0.1774 | |
| aspirational target (AM-G11) | 0.1000 | |
| student feedback | not run in the eval harness (reported at G3–5) | |

E-1..E-5: 947/976 lines passed (97.0% — bar ≥ 98%); failed rules: {'E-4': 6, 'E-1': 23}.

### Unwritten-ruling cells (reported apart, A-5)

- dan_basiuk r0 q2.א.c1: GT 9 · AI 9.50
- dan_basiuk r1 q2.א.c1: GT 9 · AI 9.50
- yonatan_basiuk r0 q2.ב.c4.s2: GT 1.5 · AI 1.50
- yonatan_basiuk r1 q2.ב.c4.s2: GT 1.5 · AI 1.50

### G-D2 cells

- ('bagrut_899371.din_ezra', 0, 'q5.ב.c4', ['q5.ב.c4.f1', 'q5.ב.c4.f2'])
- ('bagrut_899371.din_ezra', 1, 'q5.ב.c4', ['q5.ב.c4.f1', 'q5.ב.c4.f2'])
- ('bagrut_899371.roni_ben_ezra', 0, 'q5.ב.c4', ['q5.ב.c4.f1', 'q5.ב.c4.f2'])
- ('bagrut_899371.roni_ben_ezra', 1, 'q5.ב.c4', ['q5.ב.c4.f1', 'q5.ב.c4.f2'])

