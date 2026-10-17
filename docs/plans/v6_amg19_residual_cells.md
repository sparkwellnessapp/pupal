# grader-v6 · AM-G19 CS run (Oct 17) — the residual, cell by cell

Run `20261017-162850_v6-cs-sonnet55-amg19`, plans hobby `f068fa66…` · bagrut `773ea231…` (Opus 5.5, planner-v6.2). Generated offline from the drafts ($0).

### K2 and G-Z by full value (cells and points)

| run | band | GT-partial cells | K2 cells | K2 points over-credited | G-Z cells | G-Z points lost |
|---|---|---|---|---|---|---|
| v5 | <2 | 18 | 6 (33.3%) | 4 | 8 (44.4%) | 4 |
| v5 | ≥2 | 178 | 14 (7.9%) | 18 | 54 (30.3%) | 78 |
| v5 | all | 196 | 20 (10.2%) | 22 | 62 (31.6%) | 82 |
| v6_v61_s55 | <2 | 27 | 12 (44.4%) | 7.5 | 9 (33.3%) | 4.5 |
| v6_v61_s55 | ≥2 | 267 | 38 (14.2%) | 46 | 87 (32.6%) | 122 |
| v6_v61_s55 | all | 294 | 50 (17.0%) | 53.5 | 96 (32.7%) | 126.5 |
| v6_v61_s5diag | <2 | 18 | 9 (50.0%) | 5.5 | 7 (38.9%) | 3.5 |
| v6_v61_s5diag | ≥2 | 178 | 28 (15.7%) | 32.5 | 46 (25.8%) | 58.5 |
| v6_v61_s5diag | all | 196 | 37 (18.9%) | 38 | 53 (27.0%) | 62 |
| v6_amg19 | <2 | 27 | 7 (25.9%) | 3.5 | 15 (55.6%) | 9 |
| v6_amg19 | ≥2 | 267 | 37 (13.9%) | 32.5 | 49 (18.4%) | 59.5 |
| v6_amg19 | all | 294 | 44 (15.0%) | 36 | 64 (21.8%) | 68.5 |

### The K2 and G-Z cells of `v6_amg19`: can each plan price the GT award?

| cells | n | expressible under `pinned_opus_v62` |
|---|---|---|
| K2 | 44 | 27 (61.4%) |
| G-Z | 64 | 44 (68.8%) |

| exam · terminal · GT award / full | K2 · G-Z cells | `pinned_opus_v62` can price it |
|---|---|---|
| hobby_tvshow `q1.ב.c2` 1.5/3 | 1 · 8 | ✅ |
| bagrut_899371 `q3.ב.c6` 2.5/3 | 7 · 0 | ❌ |
| hobby_tvshow `q1.ג.c7` 0.5/2 | 0 · 7 | ✅ |
| bagrut_899371 `q1.א.2.c0` 0.75/1.5 | 0 · 6 | ❌ |
| bagrut_899371 `q3.ב.c6` 2/3 | 6 · 0 | ✅ |
| hobby_tvshow `q2.ב.c3.s0` 2/3 | 3 · 3 | ✅ |
| hobby_tvshow `q2.ב.c4.s1` 0.5/1 | 3 · 3 | ✅ |
| bagrut_899371 `q6.c7` 3/4 | 4 · 0 | ✅ |
| bagrut_899371 `q6.c6` 1/2 | 4 · 0 | ✅ |
| hobby_tvshow `q1.ג.c6` 0.5/2 | 0 · 4 | ✅ |
| hobby_tvshow `q2.ג.c0.s2` 2/3 | 0 · 4 | ✅ |
| bagrut_899371 `q5.ב.c3` 1/2 | 0 · 3 | ❌ |
| bagrut_899371 `q6.c5` 2/4 | 0 · 3 | ✅ |
| bagrut_899371 `q1.ב.2.c1` 1/2 | 0 · 3 | ✅ |
| bagrut_899371 `q3.ב.c5` 2.5/3 | 3 · 0 | ❌ |
| bagrut_899371 `q1.ב.2.c1` 1.5/2 | 0 · 3 | ✅ |
| bagrut_899371 `q4.א.c0` 0.5/1 | 0 · 3 | ❌ |
| bagrut_899371 `q2.ב.c5` 0.5/2 | 0 · 3 | ❌ |
| bagrut_899371 `q3.א.c2` 1/2 | 3 · 0 | ✅ |
| hobby_tvshow `q2.ב.c4.s5` 0.5/1 | 0 · 3 | ❌ |
| hobby_tvshow `q2.ב.c5` 0.5/1 | 3 · 0 | ❌ |
| hobby_tvshow `q2.ב.c4.s2` 1.5/2 | 3 · 0 | ❌ |
| bagrut_899371 `q3.ב.c6` 1.5/3 | 0 · 2 | ❌ |
| bagrut_899371 `q2.ב.c4` 1.5/3 | 0 · 2 | ✅ |
| hobby_tvshow `q2.ג.c0.s1` 1.5/3 | 2 · 0 | ✅ |
| hobby_tvshow `q1.ב.c6` 1/2 | 0 · 2 | ✅ |
| bagrut_899371 `q6.c1` 0.5/1 | 1 · 0 | ✅ |
| bagrut_899371 `q3.ב.c5` 1.5/3 | 1 · 0 | ❌ |
| hobby_tvshow `q2.ב.c0` 1/2 | 0 · 1 | ✅ |
| hobby_tvshow `q2.ג.c0.s0` 1/2 | 0 · 1 | ✅ |

## K4 — din_ezra (hobby) cells that move across trials

| terminal | GT | r0 | r1 | r2 |
|---|---|---|---|---|
| `q1.ב.c2` | 1.5 | 0 | 3.00 | 0 |
| `q1.ב.c3` | 3 | 2 | 3 | 2 |
| `q1.ב.c7` | 1 | 1 | 1 | 0 |
| `q2.ב.c0` | 1 | 1.00 | 0 | 1.00 |
| `q2.ב.c4.s2` | 0 | 1.00 | 1.00 | 0 |
| `q2.ב.c4.s3` | 3 | 3 | 0 | 0 |
| `q2.ב.c4.s4` | 1 | 1 | 0 | 0 |
| `q2.ג.c0.s0` | 1 | 1.00 | 1.00 | 0 |
| `q2.ג.c0.s1` | 1.5 | 3 | 3 | 1.50 |

## The 44 K2 cells — the plan's options and the verifier's picks


### bagrut_899371 `q3.א.c2` (full 2) — expressible; reachable [Decimal('0'), Decimal('1'), Decimal('2')]
- credit/binary `c1` element=binary · הגדרה והקצאה נכונה של מערך המונים בגודל 21
    - `full` 1: מוגדר ומוקצה מערך מונים של מספרים שלמים בגודל 21
    - `absent` 0: לא מוקצה מערך מונים, או שמערך המונים מוקצה בגודל שאינו 21
- credit/binary `c2` element=binary · איפוס מערך המונים
    - `full` 1: תאי מערך המונים מאופסים לפני הספירה, בהקצאה חדשה של המערך או בלולאת איפוס
    - `absent` 0: תאי מערך המונים אינם מאופסים לפני הספירה
  - bagrut_899371.yahli_cohen r0: GT 1 → AI 2 · `c1`→`full` «int[] newArr = new int[21];»; `c2`→`full` «int[] newArr = new int[21];»
  - bagrut_899371.yahli_cohen r1: GT 1 → AI 2 · `c1`→`full` «int[] newArr = new int[21];»; `c2`→`full` «int[] newArr = new int[21];»
  - bagrut_899371.yahli_cohen r2: GT 1 → AI 2 · `c1`→`full` «int[] newArr = new int[21];»; `c2`→`full` «int[] newArr = new int[21];»

### bagrut_899371 `q3.ב.c5` (full 3) — INEXPRESSIBLE; reachable [Decimal('0'), Decimal('1.00'), Decimal('2.00'), Decimal('3.00')]
- credit/binary `c1` element=non_binary · לולאה נפרדת הסורקת את מערך המונים מאינדקס 1 עד 20
    - `full` 1.00: אחרי מציאת maxCount יש לולאה נפרדת העוברת על מערך המונים מאינדקס 1 עד 20
    - `absent` 0: אין לולאה נפרדת על מערך המונים אחרי מציאת maxCount, או שהלולאה סורקת מערך אחר
- credit/binary `c2` element=binary · בדיקה שערך התא שווה ל-maxCount
    - `full` 1.00: בלולאה נבדק אם המונה באינדקס הנוכחי שווה ל-maxCount
    - `absent` 0: אין בדיקה שהמונה באינדקס הנוכחי שווה ל-maxCount
- credit/binary `c3` element=binary · הדפסת כל האינדקסים שמונם שווה ל-maxCount (תמיכה בריבוי שכיחים)
    - `full` 1.00: מודפס האינדקס עצמו של כל תא שמונהו שווה ל-maxCount, כך שכל השכיחים מודפסים
    - `absent` 0: לא מודפסים האינדקסים, למשל מודפס ערך המונה במקום האינדקס או מודפס שכיח אחד בלבד
  - bagrut_899371.noam_breinshtein r0: GT 2.5 → AI 3.00 · `c1`→`full` «for (int i=1; i<counter.length; i++)
{
if (counter[i]==big)»; `c2`→`full` «if (counter[i]==big)»; `c3`→`full` «biggest += (i + " ");»
  - bagrut_899371.noam_breinshtein r1: GT 2.5 → AI 3.00 · `c1`→`full` «for (int i=1; i<counter.length; i++)
{
if (counter[i]==big)»; `c2`→`full` «if (counter[i]==big)»; `c3`→`full` «biggest += (i + " ");»
  - bagrut_899371.noam_breinshtein r2: GT 2.5 → AI 3.00 · `c1`→`full` «for (int i=1; i<counter.length; i++)
{
if (counter[i]==big)»; `c2`→`full` «if (counter[i]==big)»; `c3`→`full` «biggest += (i + " ");»
  - bagrut_899371.raz_cohen r2: GT 1.5 → AI 3.00 · `c1`→`full` «for (int i = 0; i < stats.length-1; i++)»; `c2`→`full` «if ( stats[i] == count)»; `c3`→`full` «console.WriteLine("max valiue"+ i)»

### bagrut_899371 `q3.ב.c6` (full 3) — INEXPRESSIBLE; reachable [Decimal('0'), Decimal('1.00'), Decimal('2.00'), Decimal('3.00')]
- credit/binary `c1` element=non_binary · לולאה הסורקת את מערך המונים מאינדקס 1 עד 20
    - `full` 1.00: יש לולאה העוברת על מערך המונים מאינדקס 1 עד 20
    - `absent` 0: אין לולאה על מערך המונים, או שהלולאה סורקת מערך אחר
- credit/binary `c2` element=binary · בדיקה שהמונה שווה ל-0
    - `full` 1.00: בלולאה נבדק אם המונה באינדקס הנוכחי שווה ל-0
    - `absent` 0: אין בדיקה שהמונה באינדקס הנוכחי שווה ל-0
- credit/binary `c3` element=binary · הדפסת האינדקסים של הערכים שלא הופיעו
    - `full` 1.00: מודפס האינדקס עצמו של כל תא שמונהו שווה ל-0
    - `absent` 0: לא מודפסים האינדקסים של הערכים שלא הופיעו, למשל מודפס ערך המונה במקום האינדקס
  - bagrut_899371.din_ezra r0: GT 2.5 → AI 3.00 · `c1`→`full` «for(i =0; i < student.Length; i++)»; `c2`→`full` «if (student[i] == 0)»; `c3`→`full` «Console.WriteLine ("have 0: " + i);»
  - bagrut_899371.din_ezra r1: GT 2.5 → AI 3.00 · `c1`→`full` «for(i =0; i < student.Length; i++)»; `c2`→`full` «if (student[i] == 0)»; `c3`→`full` «Console.WriteLine ("have 0: " + i);»
  - bagrut_899371.din_ezra r2: GT 2.5 → AI 3.00 · `c1`→`full` «for(i =0; i < student.Length; i++)»; `c2`→`full` «if (student[i] == 0)»; `c3`→`full` «Console.WriteLine ("have 0: " + i);»
  - bagrut_899371.noam_breinshtein r0: GT 2.5 → AI 3.00 · `c1`→`full` «for (int i=1; i<counter.length; i++)»; `c2`→`full` «else if (counter[i]==0)»; `c3`→`full` «zero += (i + " ");»
  - bagrut_899371.noam_breinshtein r1: GT 2.5 → AI 3.00 · `c1`→`full` «for (int i=1; i<counter.length; i++)»; `c2`→`full` «else if (counter[i]==0)»; `c3`→`full` «zero += (i + " ");»
  - bagrut_899371.noam_breinshtein r2: GT 2.5 → AI 3.00 · `c1`→`full` «for (int i=1; i<counter.length; i++)»; `c2`→`full` «else if (counter[i]==0)»; `c3`→`full` «zero += (i + " ");»
  - bagrut_899371.raz_cohen r2: GT 2 → AI 3.00 · `c1`→`full` «for (int i = 0; i < stats.length-1; i++)»; `c2`→`full` «if (stats[i]==0)»; `c3`→`full` «console.WriteLine("Low valiue" + i)»
  - bagrut_899371.roni_ben_ezra r0: GT 2 → AI 3.00 · `c1`→`full` «For (int i=1; i< newArr.length; i++)»; `c2`→`full` «if (newArr[i] == 0 )»; `c3`→`full` «C.W (i + "," );»
  - bagrut_899371.roni_ben_ezra r1: GT 2 → AI 3.00 · `c1`→`full` «For (int i=1; i< newArr.length; i++)»; `c2`→`full` «if (newArr[i] == 0 )»; `c3`→`full` «C.W (i + "," );»
  - bagrut_899371.roni_ben_ezra r2: GT 2 → AI 3.00 · `c1`→`full` «For (int i=1; i< newArr.length; i++)»; `c2`→`full` «if (newArr[i] == 0 )»; `c3`→`full` «C.W (i + "," );»
  - bagrut_899371.yael_kogan r0: GT 2 → AI 3.00 · `c1`→`full` «for ( int i = 0 ; i < num1.Length ; i++)»; `c2`→`full` «if (num[i] == 0 && i != 0)»; `c3`→`full` «Console.Write(i) ;»
  - bagrut_899371.yael_kogan r1: GT 2 → AI 3.00 · `c1`→`full` «for ( int i = 0 ; i < num1.Length ; i++)»; `c2`→`full` «if (num[i] == 0 && i != 0)»; `c3`→`full` «if (num[i] == 0 && i != 0) .2
}
Console.Write(i) ;»
  - bagrut_899371.yahli_cohen r0: GT 2.5 → AI 3.00 · `c1`→`full` «for(int i=0; i<newArr.Length; i++)»; `c2`→`full` «if(0==newArr[i])»; `c3`→`full` «Console.WriteLine(i)»

### bagrut_899371 `q6.c1` (full 1) — expressible; reachable [Decimal('0'), Decimal('0.5'), Decimal('1.0')]
- credit/binary `c1` element=non_binary · משתנים משמעותיים
    - `full` 0.5: שמות המשתנים מתארים את תפקידם, כגון מערך המונים, מספר המכינות הפעילות ואינדקס מערך היעד
    - `absent` 0: שמות המשתנים אינם מתארים את תפקידם
- credit/binary `c2` element=non_binary · קוד קריא
    - `full` 0.5: הקוד מסודר וקריא, ושלבי הפעולה ניתנים לזיהוי
    - `absent` 0: הקוד אינו קריא ושלביו אינם ניתנים לזיהוי
  - bagrut_899371.raz_cohen r0: GT 0.5 → AI 1.0 · `c1`→`full` «int count=0;»; `c2`→`full` «int[] result = new int [count*2];»

### bagrut_899371 `q6.c6` (full 2) — expressible; reachable [Decimal('0'), Decimal('1'), Decimal('2')]
- credit/binary `c1` element=binary · הדפסת מספר המכינה בעלת כמות מקסימלית
    - `full` 2: יש הדפסה של תוצאת החיפוש אחר המכינה בעלת הכמות המקסימלית
    - `absent` 0: אין הדפסה של תוצאת החיפוש אחר המכינה בעלת הכמות המקסימלית
- fault/fault `f1` element=None · הודפסה הכמות במקום מספר המכינה
    - `none` 0: ללא הטעות הזו
    - `f1` -1: הודפסה כמות התלמידים של המכינה בעלת הכמות המקסימלית במקום מספר המכינה
  - bagrut_899371.raz_cohen r2: GT 1 → AI 2 · `c1`→`full` «console.WriteLine(big);»; `f1`→`none` «»
  - bagrut_899371.roni_ben_ezra r0: GT 1 → AI 2 · `c1`→`full` «c.w("The mechina with max student: " + i) ;»; `f1`→`none` «»
  - bagrut_899371.roni_ben_ezra r1: GT 1 → AI 2 · `c1`→`full` «c.w("The mechina with max student: " + i) ;»; `f1`→`none` «»
  - bagrut_899371.roni_ben_ezra r2: GT 1 → AI 2 · `c1`→`full` «c.w("The mechina with max student: " + i) ;»; `f1`→`none` «»

### bagrut_899371 `q6.c7` (full 4) — expressible; reachable [Decimal('0'), Decimal('1'), Decimal('2'), Decimal('3.00'), Decimal('4')]
- credit/binary `c1` element=non_binary · חישוב גודל מערך היעד: סריקת מערך המונים
    - `full` 1: יש סריקה של מערך המונים לצורך חישוב גודל מערך היעד
    - `absent` 0: אין סריקה של מערך המונים לצורך חישוב גודל מערך היעד
- credit/binary `c2` element=non_binary · ספירת התאים שגדולים מ-0
    - `full` 1: מונה גדל עבור כל תא במערך המונים שערכו גדול מ-0
    - `absent` 0: אין ספירה של תאי מערך המונים שגדולים מ-0
- credit/ladder `c3` element=non_binary · יצירה והקצאת מערך חדש בגודל count * 2
    - `full` 2: נוצר מערך חדש שגודלו פעמיים מספר המכינות שנרשמו אליהן תלמידים
    - `p1` 1.00: נוצר מערך חדש לפי מספר המכינות שנרשמו אליהן תלמידים, אך בלי הכפלה פי שניים
    - `absent` 0: לא נוצר מערך חדש לפי מספר המכינות שנרשמו אליהן תלמידים
  - bagrut_899371.noam_breinshtein r0: GT 3 → AI 4 · `c1`→`full` «for (int i=0; i< counter.length; i++)»; `c2`→`full` «if (counter[i] > 0)

count++;»; `c3`→`full` «int[] analyze = new int[count * 2 + 1];»
  - bagrut_899371.roni_ben_ezra r0: GT 3 → AI 4 · `c1`→`full` «For(int i = 0 ; i < studentsMechina.Length ; i++) // כמות המכינות השונ»; `c2`→`full` «if (mechina[i] != 0)
            count++ ;»; `c3`→`full` «int [] newArr = new int [coun*2] ;»
  - bagrut_899371.roni_ben_ezra r1: GT 3 → AI 4 · `c1`→`full` «For(int i = 0 ; i < studentsMechina.Length ; i++) // כמות המכינות השונ»; `c2`→`full` «if (mechina[i] != 0)
            count++ ;»; `c3`→`full` «int [] newArr = new int [coun*2] ;»
  - bagrut_899371.roni_ben_ezra r2: GT 3 → AI 4 · `c1`→`full` «For(int i = 0 ; i < studentsMechina.Length ; i++) // כמות המכינות השונ»; `c2`→`full` «if (mechina[i] != 0)
            count++ ;»; `c3`→`full` «int [] newArr = new int [coun*2] ;»

### hobby_tvshow `q1.ב.c2` (full 3) — expressible; reachable [Decimal('0'), Decimal('1.50'), Decimal('3.00')]
- credit/binary `c1` element=binary · לולאה עד שאין מקום במערך (כל עוד countHobbies קטן מ-length)
    - `full` 1.50: הלולאה ממשיכה רק כל עוד countHobbies קטן מאורך המערך hobbies
    - `absent` 0: אין לולאה, או שתנאי הלולאה אינו עוצר כשאין עוד מקום במערך hobbies
- credit/binary `c2` element=non_binary · הלולאה ממשיכה כל עוד המשתמש יענה Y או y לשאלה
    - `full` 1.50: תנאי הלולאה עוצר את הקליטה כשתשובת המשתמש לשאלה היא N או n, ואחרת ממשיך
    - `absent` 0: תנאי הלולאה אינו תלוי בתשובת המשתמש לשאלה האם להמשיך
  - din_ezra r1: GT 1.5 → AI 3.00 · `c1`→`full` «for(int i=0; i<this.hobbies.length; i++)»; `c2`→`full` «if(a=="n" || a=="N")»

### hobby_tvshow `q2.ב.c3.s0` (full 3) — expressible; reachable [Decimal('0'), Decimal('1.0'), Decimal('1.5'), Decimal('2'), Decimal('2.5'), Decimal('3')]
- credit/binary `c1` element=binary · הגדרת לולאה על מערך התוכניות
    - `full` 3: יש לולאה שעוברת על תאי מערך התוכניות של אובייקט ה-TvRate
    - `absent` 0: אין לולאה על מערך התוכניות
- fault/fault `f1` element=None · הלולאה על מערך התוכניות התחילה מ-1 במקום מ-0
    - `none` 0: ללא הטעות הזו
    - `f1` -0.5: הלולאה על מערך התוכניות מתחילה מהתא השני ומדלגת על התא הראשון
- fault/fault `f2` element=None · גישה למערך התוכניות בלי Getter
    - `none` 0: ללא הטעות הזו
    - `f1` -1: מערך התוכניות נלקח בגישה ישירה לתכונה arrShows של TvRate ולא באמצעות פעולת Get
- fault/fault `f3` element=None · טעות בגבול העליון של הלולאה על מערך התוכניות
    - `none` 0: ללא הטעות הזו
    - `f1` -0.5: הגבול העליון של הלולאה על מערך התוכניות שגוי: אינו קטן ממש מאורך המערך
  - yonatan_basiuk r0: GT 2 → AI 3 · `c1`→`full` «for(int i = 0; i < tvRate.Length; i++)»; `f1`→`none` «»; `f2`→`none` «»; `f3`→`none` «»
  - yonatan_basiuk r1: GT 2 → AI 3 · `c1`→`full` «for(int i = 0; i < tvRate.Length; i++)»; `f1`→`none` «»; `f2`→`none` «»; `f3`→`none` «i < tvRate.Length»
  - yonatan_basiuk r2: GT 2 → AI 3 · `c1`→`full` «for(int i = 0; i < tvRate.Length; i++)»; `f1`→`none` «»; `f2`→`none` «»; `f3`→`none` «»

### hobby_tvshow `q2.ב.c4.s1` (full 1) — expressible; reachable [Decimal('0'), Decimal('0.5'), Decimal('1.0')]
- credit/binary `c1` element=binary · הגדרת ערוץ מינימלי
    - `full` 0.5: הוגדר משתנה לערוץ המינימלי
    - `absent` 0: לא הוגדר משתנה לערוץ המינימלי
- credit/binary `c2` element=binary · אתחול הערוץ המינימלי
    - `full` 0.5: משתנה הערוץ המינימלי אותחל לפני הלולאה
    - `absent` 0: משתנה הערוץ המינימלי לא אותחל
  - din_ezra r0: GT 0.5 → AI 1.0 · `c1`→`full` «string min1 = " ";»; `c2`→`full` «string min1 = " ";»
  - din_ezra r1: GT 0.5 → AI 1.0 · `c1`→`full` «string min1 = " ";»; `c2`→`full` «string min1 = " ";»
  - din_ezra r2: GT 0.5 → AI 1.0 · `c1`→`full` «string min1 = " ";»; `c2`→`full` «string min1 = " ";»

### hobby_tvshow `q2.ב.c4.s2` (full 2) — INEXPRESSIBLE; reachable [Decimal('0'), Decimal('1.00'), Decimal('2')]
- credit/ladder `c1` element=non_binary · הגדרת לולאה על מערך צוברים על כל הערוצים
    - `full` 2: לולאה עוברת על תאי מערך הצוברים מהערוץ הראשון ועד הערוץ הגבוה ביותר כולל
    - `p1` 1.00: יש לולאה על מערך הצוברים, אך היא מחמיצה את התא של הערוץ הגבוה ביותר או חורגת מגבולות המערך
    - `absent` 0: אין לולאה על מערך הצוברים
  - yonatan_basiuk r0: GT 1.5 → AI 2 · `c1`→`full` «for(int i = 0; i < chRate.Length; i++)
    {
        if(chRate[i] < ch»
  - yonatan_basiuk r1: GT 1.5 → AI 2 · `c1`→`full` «for(int i = 0; i < chRate.Length; i++)
    {
        if(chRate[i] < ch»
  - yonatan_basiuk r2: GT 1.5 → AI 2 · `c1`→`full` «for(int i = 0; i < chRate.Length; i++)»

### hobby_tvshow `q2.ב.c5` (full 1) — INEXPRESSIBLE; reachable [Decimal('0'), Decimal('1')]
- credit/binary `c1` element=binary · החזרת הערוץ המינימלי
    - `full` 1: הפעולה מחזירה את משתנה הערוץ המינימלי
    - `absent` 0: הפעולה אינה מחזירה את הערוץ המינימלי
  - din_ezra r0: GT 0.5 → AI 1 · `c1`→`full` «return min1»
  - din_ezra r1: GT 0.5 → AI 1 · `c1`→`full` «return min1»
  - din_ezra r2: GT 0.5 → AI 1 · `c1`→`full` «return min1»

### hobby_tvshow `q2.ג.c0.s1` (full 3) — expressible; reachable [Decimal('0'), Decimal('1.50'), Decimal('3')]
- credit/ladder `c1` element=non_binary · מציאת הערוץ בעל דירוג מינימלי ע"י זימון LowestRateChannel
    - `full` 3: הפעולה LowestRateChannel מזומנת עם אובייקט ה-TvRate שהתקבל, והערוץ בעל הדירוג המינימלי שהיא מחזירה נשמר או משמש בהמשך
    - `p1` 1.50: הערוץ בעל הדירוג המינימלי נמצא בקוד שנכתב בתוך הפעולה, ללא זימון LowestRateChannel
    - `absent` 0: הערוץ בעל הדירוג המינימלי אינו נמצא כלל, לא בזימון LowestRateChannel ולא בדרך אחרת
  - din_ezra r0: GT 1.5 → AI 3 · `c1`→`full` «if(LowestRateChannel == arr[i].getName())»
  - din_ezra r1: GT 1.5 → AI 3 · `c1`→`full` «if(LowestRateChannel == arr[i].getName())»
