### Run 11 against run 10's frozen K2 classes (run 10 `20261017-162850_v6-cs-sonnet55-amg19` · run 11 `20261018-153424_v6-cs-run11`)

| class | run-10 cells | criteria (fixture · terminal) | fixed | still failing (K2 in any run-11 trial) |
|---|---|---|---|---|
| split | 11 | 5 | 0 | 5 |
| verifier-miss | 21 | 11 | 4 | 7 |
| plan-wording | 6 | 2 | 0 | 2 |
| other | 6 | 2 | 1 | 1 |

| class | fixture · terminal | run-10 K2 trials | run-11 K2 trials | |
|---|---|---|---|---|
| split | bagrut_899371.din_ezra · `q3.ב.c6` | 3 | 2 | still failing |
| split | bagrut_899371.noam_breinshtein · `q3.ב.c5` | 3 | 2 | still failing |
| split | bagrut_899371.noam_breinshtein · `q3.ב.c6` | 3 | 2 | still failing |
| split | bagrut_899371.raz_cohen · `q3.ב.c5` | 1 | 1 | still failing |
| split | bagrut_899371.yahli_cohen · `q3.ב.c6` | 1 | 2 | still failing |
| verifier-miss | bagrut_899371.noam_breinshtein · `q6.c7` | 1 | 0 | fixed |
| verifier-miss | bagrut_899371.raz_cohen · `q3.ב.c6` | 1 | 1 | still failing |
| verifier-miss | bagrut_899371.raz_cohen · `q6.c1` | 1 | 1 | still failing |
| verifier-miss | bagrut_899371.raz_cohen · `q6.c6` | 1 | 0 | fixed |
| verifier-miss | bagrut_899371.roni_ben_ezra · `q3.ב.c6` | 3 | 2 | still failing |
| verifier-miss | bagrut_899371.roni_ben_ezra · `q6.c6` | 3 | 2 | still failing |
| verifier-miss | bagrut_899371.roni_ben_ezra · `q6.c7` | 3 | 0 | fixed |
| verifier-miss | bagrut_899371.yael_kogan · `q3.ב.c6` | 2 | 2 | still failing |
| verifier-miss | din_ezra · `q1.ב.c2` | 1 | 1 | still failing |
| verifier-miss | din_ezra · `q2.ג.c0.s1` | 2 | 0 | fixed |
| verifier-miss | yonatan_basiuk · `q2.ב.c3.s0` | 3 | 1 | still failing |
| plan-wording | bagrut_899371.yahli_cohen · `q3.א.c2` | 3 | 2 | still failing |
| plan-wording | din_ezra · `q2.ב.c4.s1` | 3 | 2 | still failing |
| other | din_ezra · `q2.ב.c5` | 3 | 2 | still failing |
| other | yonatan_basiuk · `q2.ב.c4.s2` | 3 | 0 | fixed |

### NEW failing cells in run 11 (not failing the same way in run 10): 10

- **GZ** · bagrut_899371.itay_kraft r0 · `q6.c8` · GT 4 / AI 0 of 8
  - credit · מילוי המערך החדש רק עבור מכינות שנרשמו אליהן תלמידים → **אין לולאה על מערך המונים למילוי מערך התוצאה** · «אין לולאה על מערך מונים; הלולאה על מערך העתק ללא סינון»
  - credit · השמת מספר המכינה בתא הראשון של הזוג → **מספר המכינה אינו מושם בתא הראשון של הזוג במערך התוצאה** · «order[count] = studentsMechina[i];»
  - credit · השמת מספר התלמידים בתא העוקב → **מונה המכינה אינו מושם בתא העוקב במערך התוצאה** · «מושם num שחושב מחדש ולא מונה מכינה ממערך מונים»
  - credit · קידום ידני תקין של אינדקס מערך היעד ב-2 בכל פעם → **אין אינדקס נפרד למערך היעד, או שהוא אינו מקודם, או שהמילוי נעשה לפי אינדקס מערך המונים** · «count += 2;»
- **GZ** · dan_basiuk r0 · `q2.ב.c3.s0` · GT 2 / AI 0 of 3
  - credit · הגדרת לולאה על מערך התוכניות → **אין לולאה על מערך התוכניות, או שהלולאה עוברת על מערך אחר** · «for(int J=0; J< A.Length; J++)»
  - fault · הלולאה על מערך התוכניות מתחילה מ-1 במקום מ-0 → **ללא הטעות הזו**
  - fault · גישה למערך התוכניות בלי Getter → **הגישה למערך התוכניות נעשית ישירות לתכונה arrShows ולא דרך GetArrShows** · «A[J].get.chl()»
  - fault · טעות בגבול העליון של הלולאה על מערך התוכניות → **ללא הטעות הזו**
- **GZ** · din_ezra r0 · `q2.ג.c0.s1` · GT 1.5 / AI 0 of 3
  - credit · מציאת הערוץ בעל דירוג מינימלי ע"י זימון LowestRateChannel → **הערוץ בעל הדירוג המינימלי לא נמצא כלל, או שהזימון נעשה על אובייקט אחר ולא על האובייקט מטיפוס TvRate שהתקבל** · «if(LowestRateChannel == arr[i].getName())»
- **GZ** · din_ezra r1 · `q2.ג.c0.s1` · GT 1.5 / AI 0 of 3
  - credit · מציאת הערוץ בעל דירוג מינימלי ע"י זימון LowestRateChannel → **הערוץ בעל הדירוג המינימלי לא נמצא כלל, או שהזימון נעשה על אובייקט אחר ולא על האובייקט מטיפוס TvRate שהתקבל** · «LowestRateChannel מופיע ללא סוגריים וללא העברת אובייקט TvRate, ולא מזומן כפעולה»
- **K1** · din_ezra r0 · `q2.ב.c1` · GT 0 / AI 1.00 of 2
  - credit · הגדרת מערך צוברים int לכל 100 הערוצים → **הוגדר מערך צוברים לערוצים, אך גודלו אינו מכסה את כל הערוצים 1-100 או שטיפוסו אינו int** · «int[] arr = new int[tv]»
- **K1** · din_ezra r1 · `q2.ב.c1` · GT 0 / AI 1.00 of 2
  - credit · הגדרת מערך צוברים int לכל 100 הערוצים → **הוגדר מערך צוברים לערוצים, אך גודלו אינו מכסה את כל הערוצים 1-100 או שטיפוסו אינו int** · «int[] arr = new int[tv]»
- **K2** · bagrut_899371.noam_breinshtein r0 · `q1.א.2.c0` · GT 0.75 / AI 1.5 of 1.5
  - credit · הבנת הבדיקה של "מחלק ללא שארית" → **התשובה מתארת שהפעולה בודקת אם קיים במערך איבר שהוא מחלק של x, כלומר ש-x מתחלק בו ללא שארית** · «לבדוק אם במערך יש מספר
שמתחלק במספר שמביאים»
- **K2** · bagrut_899371.noam_breinshtein r1 · `q1.א.2.c0` · GT 0.75 / AI 1.5 of 1.5
  - credit · הבנת הבדיקה של "מחלק ללא שארית" → **התשובה מתארת שהפעולה בודקת אם קיים במערך איבר שהוא מחלק של x, כלומר ש-x מתחלק בו ללא שארית** · «לבדוק אם במערך יש מספר
שמתחלק במספר שמביאים»
- **K2** · bagrut_899371.raz_cohen r0 · `q1.א.2.c0` · GT 0.75 / AI 1.5 of 1.5
  - credit · הבנת הבדיקה של "מחלק ללא שארית" → **התשובה מתארת שהפעולה בודקת אם קיים במערך איבר שהוא מחלק של x, כלומר ש-x מתחלק בו ללא שארית** · «לבדוק אם יש במערך מספר המתחלק בX ללא שארית»
- **K2** · bagrut_899371.raz_cohen r1 · `q1.א.2.c0` · GT 0.75 / AI 1.5 of 1.5
  - credit · הבנת הבדיקה של "מחלק ללא שארית" → **התשובה מתארת שהפעולה בודקת אם קיים במערך איבר שהוא מחלק של x, כלומר ש-x מתחלק בו ללא שארית** · «לבדוק אם יש במערך מספר המתחלק בX ללא שארית»
