# grader-v6 planner re-record — per-model report

| model | exam | prompt | origins (planner/repaired/fallback/compiled) | validator msgs | V19 | expressible | planner miss | unwritten | $ | wall s | calls | out tok | served | fallback scopes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-sonnet-5.5 | bagrut_899371 | planner-v6.1 | 12/0/0/1 | 0 | 0 | **274/298** | 24 | 0 | 0.7100 | 310 | 12 | 43130 | claude-sonnet-5-5 | 0 |
| claude-sonnet-5.5 | hobby_tvshow | planner-v6.1 | 6/0/0/0 | 0 | 1 | **180/190** | 8 | 2 | 0.4200 | 187 | 6 | 26934 | claude-sonnet-5-5 | 0 |
| claude-sonnet-5 | bagrut_899371 | planner-v6.1 | 10/2/0/1 | 2 | 1 | **276/298** | 22 | 0 | 1.2309 | 1242 | 14 | 89554 | claude-sonnet-5 | 0 |
| claude-sonnet-5 | hobby_tvshow | planner-v6.1 | 5/1/0/0 | 1 | 0 | **180/190** | 8 | 2 | 0.7341 | 532 | 7 | 54727 | claude-sonnet-5 | 0 |

## §13.1 choice rule
- claude-sonnet-5.5: inexpressible 34 (planner misses 32) · $1.1300 for both exams
- claude-sonnet-5: inexpressible 32 (planner misses 30) · $1.9650 for both exams
- step 1: **claude-sonnet-5** (fewer inexpressible cells by 2)

### claude-sonnet-5.5 · bagrut_899371 — inexpressible cells
| fixture | terminal | GT | label | reachable | plan decision |
|---|---|---|---|---|---|
| bagrut_899371.din_ezra | q3.א.c2 | 0.5 | planner_miss | 0, 1, 2 | c1 binary[1/0]; c2 binary[1/0] |
| bagrut_899371.din_ezra | q3.ב.c6 | 2.5 | planner_miss | 0, 3 | c1 binary[3/0] |
| bagrut_899371.din_ezra | q5.ב.c3 | 1 | planner_miss | 0, 2 | c1 binary[2/0] |
| bagrut_899371.itay_kraft | q3.א.c2 | 0.5 | planner_miss | 0, 1, 2 | c1 binary[1/0]; c2 binary[1/0] |
| bagrut_899371.itay_kraft | q3.ב.c6 | 1.5 | planner_miss | 0, 3 | c1 binary[3/0] |
| bagrut_899371.itay_kraft | q6.c4 | 0.5 | planner_miss | 0, 1, 2 | c1 binary[1/0]; c2 binary[1/0] |
| bagrut_899371.itay_kraft | q6.c5 | 2 | planner_miss | 0, 1.25, 1.5, 2.5, 2.75, 4 | c1 binary[1.5/0]; c2 binary[1.25/0]; c3 binary[1.25/0] |
| bagrut_899371.itay_kraft | q6.c8 | 4 | planner_miss | 0, 2.5, 2.75, 5.25, 5.5, 8 | c1 binary[2.75/0]; c2 binary[2.75/0]; c3 binary[2.5/0] |
| bagrut_899371.noam_breinshtein | q1.א.2.c0 | 0.75 | planner_miss | 0, 1.5 | c1 binary[1.5/0] |
| bagrut_899371.noam_breinshtein | q1.ב.2.c1 | 1 | planner_miss | 0, 2 | c1 binary[2/0] |
| bagrut_899371.noam_breinshtein | q3.ב.c5 | 2.5 | planner_miss | 0, 1.5, 3 | c1 ladder[3/1.5/0] |
| bagrut_899371.noam_breinshtein | q3.ב.c6 | 2.5 | planner_miss | 0, 3 | c1 binary[3/0] |
| bagrut_899371.noam_breinshtein | q6.c5 | 1 | planner_miss | 0, 1.25, 1.5, 2.5, 2.75, 4 | c1 binary[1.5/0]; c2 binary[1.25/0]; c3 binary[1.25/0] |
| bagrut_899371.raz_cohen | q1.א.2.c0 | 0.75 | planner_miss | 0, 1.5 | c1 binary[1.5/0] |
| bagrut_899371.raz_cohen | q1.ב.2.c1 | 1.5 | planner_miss | 0, 2 | c1 binary[2/0] |
| bagrut_899371.raz_cohen | q3.ב.c4 | 1 | planner_miss | 0, 2, 4 | c1 binary[2/0]; c2 binary[2/0] |
| bagrut_899371.raz_cohen | q3.ב.c6 | 2 | planner_miss | 0, 3 | c1 binary[3/0] |
| bagrut_899371.raz_cohen | q4.א.c0 | 0.5 | planner_miss | 0, 1 | c1 binary[1/0] |
| bagrut_899371.raz_cohen | q6.c5 | 1 | planner_miss | 0, 1.25, 1.5, 2.5, 2.75, 4 | c1 binary[1.5/0]; c2 binary[1.25/0]; c3 binary[1.25/0] |
| bagrut_899371.raz_cohen | q6.c8 | 3 | planner_miss | 0, 2.5, 2.75, 5.25, 5.5, 8 | c1 binary[2.75/0]; c2 binary[2.75/0]; c3 binary[2.5/0] |
| bagrut_899371.roni_ben_ezra | q3.ב.c6 | 2 | planner_miss | 0, 3 | c1 binary[3/0] |
| bagrut_899371.yael_kogan | q2.ב.c5 | 0.5 | planner_miss | 0, 1, 2 | c1 ladder[2/1/0] |
| bagrut_899371.yael_kogan | q3.ב.c6 | 2 | planner_miss | 0, 3 | c1 binary[3/0] |
| bagrut_899371.yahli_cohen | q3.ב.c6 | 2.5 | planner_miss | 0, 3 | c1 binary[3/0] |

### claude-sonnet-5.5 · hobby_tvshow — inexpressible cells
| fixture | terminal | GT | label | reachable | plan decision |
|---|---|---|---|---|---|
| dan_basiuk | q1.א.c1 | 3.5 | planner_miss | 0, 1, 2, 3, 4 | c1 binary[2/0]; c2 ladder[2/1/0] |
| dan_basiuk | q2.א.c1 | 9 | unwritten_ruling | 0, 1.75, 3.25, 3.5, 5, 5.25, 6.5, 6.75, 8.5, 10 | c1 binary[3.5/0]; c2 binary[3.25/0]; c3 ladder[3.25/1.75/0] |
| din_ezra | q2.א.c0 | 4 | planner_miss | 0, 1, 1.5, 1.75, 2.5, 2.75, 3.25, 3.5, 4.25, 5 | c1 ladder[1.75/1/0]; c2 binary[1.75/0]; c3 binary[1.5/0] |
| din_ezra | q2.א.c1 | 8 | planner_miss | 0, 1.75, 3.25, 3.5, 5, 5.25, 6.5, 6.75, 8.5, 10 | c1 binary[3.5/0]; c2 binary[3.25/0]; c3 ladder[3.25/1.75/0] |
| din_ezra | q2.ב.c0 | 1 | planner_miss | 0, 2 | c1 binary[2/0] |
| din_ezra | q2.ב.c4.s5 | 0.5 | planner_miss | 0, 1 | c1 binary[1/0] |
| din_ezra | q2.ב.c5 | 0.5 | planner_miss | 0, 1 | c1 binary[1/0] |
| din_ezra | q2.ג.c0.s0 | 1 | planner_miss | 0, 2 | c1 binary[2/0] |
| din_ezra | q2.ג.c0.s1 | 1.5 | planner_miss | 0, 3 | c1 binary[3/0] |
| yonatan_basiuk | q2.ב.c4.s2 | 1.5 | unwritten_ruling | 0, 2 | c1 binary[2/0] |

### claude-sonnet-5 · bagrut_899371 — inexpressible cells
| fixture | terminal | GT | label | reachable | plan decision |
|---|---|---|---|---|---|
| bagrut_899371.din_ezra | q3.א.c2 | 0.5 | planner_miss | 0, 1, 2 | c1 binary[1/0]; c2 binary[1/0] |
| bagrut_899371.din_ezra | q3.ב.c6 | 2.5 | planner_miss | 0, 1.5, 3 | c1 ladder[3/1.5/0] |
| bagrut_899371.din_ezra | q5.ב.c3 | 1 | planner_miss | 0, 2 | c1 binary[2/0] |
| bagrut_899371.itay_kraft | q3.א.c2 | 0.5 | planner_miss | 0, 1, 2 | c1 binary[1/0]; c2 binary[1/0] |
| bagrut_899371.itay_kraft | q6.c4 | 0.5 | planner_miss | 0, 1, 2 | c1 binary[1/0]; c2 binary[1/0] |
| bagrut_899371.noam_breinshtein | q1.א.2.c0 | 0.75 | planner_miss | 0, 1.5 | c1 binary[1.5/0] |
| bagrut_899371.noam_breinshtein | q3.ב.c5 | 2.5 | planner_miss | 0, 1.5, 3 | c1 ladder[3/1.5/0] |
| bagrut_899371.noam_breinshtein | q3.ב.c6 | 2.5 | planner_miss | 0, 1.5, 3 | c1 ladder[3/1.5/0] |
| bagrut_899371.noam_breinshtein | q6.c5 | 1 | planner_miss | 0, 2, 4 | c1 binary[2/0]; c2 binary[2/0] |
| bagrut_899371.raz_cohen | q1.א.2.c0 | 0.75 | planner_miss | 0, 1.5 | c1 binary[1.5/0] |
| bagrut_899371.raz_cohen | q1.ב.2.c1 | 1.5 | planner_miss | 0, 1, 2 | c1 ladder[2/1/0] |
| bagrut_899371.raz_cohen | q3.ב.c4 | 1 | planner_miss | 0, 2, 4 | c1 ladder[4/2/0] |
| bagrut_899371.raz_cohen | q3.ב.c6 | 2 | planner_miss | 0, 1.5, 3 | c1 ladder[3/1.5/0] |
| bagrut_899371.raz_cohen | q4.א.c0 | 0.5 | planner_miss | 0, 1 | c1 binary[1/0] |
| bagrut_899371.raz_cohen | q6.c5 | 1 | planner_miss | 0, 2, 4 | c1 binary[2/0]; c2 binary[2/0] |
| bagrut_899371.raz_cohen | q6.c8 | 3 | planner_miss | 0, 4, 8 | c1 binary[4/0]; c2 binary[4/0] |
| bagrut_899371.roni_ben_ezra | q3.ב.c6 | 2 | planner_miss | 0, 1.5, 3 | c1 ladder[3/1.5/0] |
| bagrut_899371.yael_kogan | q2.ב.c4 | 1.5 | planner_miss | 0, 3 | c1 binary[3/0] |
| bagrut_899371.yael_kogan | q2.ב.c5 | 0.5 | planner_miss | 0, 2 | c1 binary[2/0] |
| bagrut_899371.yael_kogan | q3.ב.c6 | 2 | planner_miss | 0, 1.5, 3 | c1 ladder[3/1.5/0] |
| bagrut_899371.yahli_cohen | q2.ב.c4 | 1.5 | planner_miss | 0, 3 | c1 binary[3/0] |
| bagrut_899371.yahli_cohen | q3.ב.c6 | 2.5 | planner_miss | 0, 1.5, 3 | c1 ladder[3/1.5/0] |

### claude-sonnet-5 · hobby_tvshow — inexpressible cells
| fixture | terminal | GT | label | reachable | plan decision |
|---|---|---|---|---|---|
| dan_basiuk | q1.א.c1 | 3.5 | planner_miss | 0, 1, 2, 3, 4 | c1 binary[1/0]; c2 binary[1/0]; c3 binary[1/0]; c4 binary[1/0] |
| dan_basiuk | q2.א.c1 | 9 | unwritten_ruling | 0, 3.25, 3.5, 6.5, 6.75, 10 | c1 binary[3.5/0]; c2 binary[3.25/0]; c3 binary[3.25/0] |
| din_ezra | q2.א.c0 | 4 | planner_miss | 0, 1.25, 2.5, 3.75, 5 | c1 binary[1.25/0]; c2 binary[1.25/0]; c3 binary[1.25/0]; c4 binary[1.25/0] |
| din_ezra | q2.א.c1 | 8 | planner_miss | 0, 3.25, 3.5, 6.5, 6.75, 10 | c1 binary[3.5/0]; c2 binary[3.25/0]; c3 binary[3.25/0] |
| din_ezra | q2.ב.c0 | 1 | planner_miss | 0, 2 | c1 binary[2/0] |
| din_ezra | q2.ב.c4.s5 | 0.5 | planner_miss | 0, 1 | c1 binary[1/0] |
| din_ezra | q2.ב.c5 | 0.5 | planner_miss | 0, 1 | c1 binary[1/0] |
| din_ezra | q2.ג.c0.s0 | 1 | planner_miss | 0, 2 | c1 binary[2/0] |
| din_ezra | q2.ג.c0.s1 | 1.5 | planner_miss | 0, 3 | c1 binary[3/0] |
| yonatan_basiuk | q2.ב.c4.s2 | 1.5 | unwritten_ruling | 0, 2 | c1 binary[2/0] |

