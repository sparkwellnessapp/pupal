# hobby_tvshow — plan/v6 render

- plan_hash `ae19776ce2d2077d…` · config_hash `8401b943980225ea…` · pack `computer_science@v1`
- stage 1 `plan-compiler/v2.0+stage1-v6.0` · 38 criteria · 83 checks
- scope origins: q1.א=planner, q1.ב=planner, q1.ג=repaired, q2.א=planner, q2.ב=planner, q2.ג=planner

## q1.א — planner

### q1.א.c0 · 4 נק׳ · components

**Teacher's text:** סעיף א: כותרת ותכונות המחלקה Hobby

**Collapsed:** 4 checks · credit max 4 / 4

- **q1.א.c0.c1** · credit · binary · origin `planner`
  - כותרת המחלקה Hobby
  - `full` **1** — המחלקה Hobby הוגדרה עם כותרת מתאימה
  - `absent` **0** — לא הוגדרה כותרת למחלקה Hobby
- **q1.א.c0.c2** · credit · binary · origin `planner`
  - התכונה hobbyName מטיפוס מחרוזת
  - `full` **1** — הוגדרה תכונה hobbyName מטיפוס מחרוזת המייצגת את שם התחביב
  - `absent` **0** — לא הוגדרה תכונה hobbyName מטיפוס מחרוזת
- **q1.א.c0.c3** · credit · binary · origin `planner`
  - התכונה isSportive מטיפוס בוליאני
  - `full` **1** — הוגדרה תכונה isSportive מטיפוס בוליאני המייצגת אם התחביב דורש פעילות ספורטיבית
  - `absent` **0** — לא הוגדרה תכונה isSportive מטיפוס בוליאני
- **q1.א.c0.c4** · credit · binary · origin `planner`
  - התכונה minutes מטיפוס שלם
  - שקילות: שם התכונה יכול להיות שונה מהשם minutes (כגון durationInMinutes), ובלבד שהיא מייצגת את זמן הפעילות בדקות
  - `full` **1** — הוגדרה תכונה minutes מטיפוס שלם המייצגת את זמן הפעילות בדקות
  - `absent` **0** — לא הוגדרה תכונה minutes מטיפוס שלם

**Interpretation notes:**
- הנחת קיום פעולות Get/Set לכל תכונה אינה נבדקת בסעיף זה, שכן היא נתונה בשאלה.

### q1.א.c1 · 4 נק׳ · components

**Teacher's text:** סעיף א: פעולה בונה Hobby(string hobbyName, bool isSportive, int minutes)

**Collapsed:** 4 checks · credit max 4 / 4

- **q1.א.c1.c1** · credit · binary · origin `planner`
  - בנאי המקבל את שלושת הפרמטרים hobbyName, isSportive ו-minutes
  - `full` **1** — הבנאי מקבל את שלושת הפרמטרים hobbyName, isSportive ו-minutes בהתאם לחתימה שהוגדרה
  - `absent` **0** — הבנאי אינו מקבל את שלושת הפרמטרים הנדרשים
- **q1.א.c1.c2** · credit · binary · origin `planner`
  - קביעת ערך התכונה hobbyName מהפרמטר שהתקבל
  - `full` **1** — התכונה hobbyName מקבלת את ערך הפרמטר hobbyName
  - `absent` **0** — התכונה hobbyName אינה מקבלת את ערך הפרמטר
- **q1.א.c1.c3** · credit · binary · origin `planner`
  - קביעת ערך התכונה isSportive מהפרמטר שהתקבל
  - `full` **1** — התכונה isSportive מקבלת את ערך הפרמטר isSportive
  - `absent` **0** — התכונה isSportive אינה מקבלת את ערך הפרמטר
- **q1.א.c1.c4** · credit · binary · origin `planner`
  - קביעת ערך התכונה minutes מהפרמטר שהתקבל
  - שקילות: בדיקת תקינות הטווח (1 עד 60) לפני ההצבה אינה נדרשת, שכן הונח כי הפרמטרים תקינים
  - `full` **1** — התכונה minutes מקבלת את ערך הפרמטר minutes
  - `absent` **0** — התכונה minutes אינה מקבלת את ערך הפרמטר

**Interpretation notes:**
- בהתאם להנחיה כי הפרמטרים תקינים, אין נדרשת בדיקת טווח 1–60 עבור minutes בבנאי.

## q1.ב — planner

### q1.ב.c0 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב: פעולה פנימית בשם PopulateHobbies (סה"כ 16)כותרת הפעולה + טיפוס מוחזר bool

**Collapsed:** 2 checks · credit max 2 / 2

- **q1.ב.c0.c1** · credit · binary · origin `planner`
  - כותרת הפעולה הפנימית PopulateHobbies
  - `full` **1** — הפעולה מוגדרת בתוך המחלקה SchoolHobbies בשם PopulateHobbies וללא פרמטרים
  - `absent` **0** — הפעולה אינה מוגדרת בשם PopulateHobbies או מוגדרת עם פרמטרים
- **q1.ב.c0.c2** · credit · binary · origin `planner`
  - טיפוס מוחזר bool
  - `full` **1** — הפעולה מוגדרת עם טיפוס החזרה bool
  - `absent` **0** — טיפוס ההחזרה של הפעולה אינו bool

### q1.ב.c1 · 1 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: לפני הלולאה - לבדוק אם המערך מלא, להחזיר false

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ב.c1.c1** · credit · binary · origin `planner`
  - בדיקה לפני הלולאה האם המערך מלא
  - `full` **0.5** — לפני הכניסה ללולאה נבדק אם אין מקום פנוי במערך (countHobbies שווה לגודל המערך)
  - `absent` **0** — אין בדיקה לפני הלולאה האם המערך מלא
- **q1.ב.c1.c2** · credit · binary · origin `planner`
  - החזרת false כאשר המערך מלא מראש
  - `full` **0.5** — כאשר המערך מלא מראש, הפעולה מחזירה false לפני הכניסה ללולאה
  - `absent` **0** — לא מוחזר false במקרה שהמערך מלא מראש

### q1.ב.c2 · 3 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: לולאה עד שאין מקום במערך (כל עוד countHobbies קטן מ-length) או כל עוד המשתמש יענה Y או y לשאלה

**Collapsed:** 2 checks · credit max 3 / 3

- **q1.ב.c2.c1** · credit · binary · origin `planner`
  - המשך הלולאה כל עוד יש מקום פנוי במערך
  - `full` **1.5** — הלולאה בודקת שcountHobbies קטן מגודל המערך כתנאי להמשך הריצה
  - `absent` **0** — אין בדיקה שיש מקום פנוי במערך כתנאי להמשך הלולאה
- **q1.ב.c2.c2** · credit · binary · origin `planner`
  - המשך הלולאה כל עוד המשתמש לא ענה N או n
  - `full` **1.5** — הלולאה ממשיכה לרוץ כל עוד תשובת המשתמש אינה N או n
  - `absent` **0** — אין בדיקה של תשובת המשתמש כתנאי להמשך הלולאה

### q1.ב.c3 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קליטה של 3 נתוני התחביב (name, isSportive, minutes)

**Collapsed:** 3 checks · credit max 3 / 3

- **q1.ב.c3.c1** · credit · binary · origin `planner`
  - קליטת שם התחביב (hobbyName)
  - `full` **1** — נקלט מהמשתמש שם התחביב
  - `absent` **0** — שם התחביב אינו נקלט מהמשתמש
- **q1.ב.c3.c2** · credit · binary · origin `planner`
  - קליטת האם התחביב ספורטיבי (isSportive)
  - `full` **1** — נקלט מהמשתמש האם התחביב ספורטיבי
  - `absent` **0** — אין קליטה של isSportive מהמשתמש
- **q1.ב.c3.c3** · credit · binary · origin `planner`
  - קליטת משך הפעילות בדקות (minutes)
  - `full` **1** — נקלט מהמשתמש משך הפעילות בדקות
  - `absent` **0** — אין קליטה של minutes מהמשתמש

### q1.ב.c4 · 3 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה יצירה של עצם חדש מטיפוס Hobby בתא המתאים במערך (hobbies[countHobbies])

**Collapsed:** 2 checks · credit max 3 / 3

- **q1.ב.c4.c1** · credit · binary · origin `planner`
  - יצירת עצם חדש מטיפוס Hobby מהנתונים שנקלטו
  - `full` **1.5** — נוצר עצם חדש מטיפוס Hobby על סמך הנתונים שנקלטו מהמשתמש
  - `absent` **0** — לא נוצר עצם חדש מטיפוס Hobby
- **q1.ב.c4.c2** · credit · binary · origin `planner`
  - שמירת העצם החדש בתא הפנוי הראשון במערך
  - `full` **1.5** — העצם החדש נשמר בתא hobbies[countHobbies], שהוא התא הפנוי הראשון במערך
  - `absent` **0** — העצם החדש אינו נשמר בתא הנכון במערך

### q1.ב.c5 · 1 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קידום countHobbies

**Collapsed:** 1 checks · credit max 1 / 1

- **q1.ב.c5.c1** · credit · binary · origin `planner`
  - קידום countHobbies בתוך הלולאה
  - `full` **1** — לאחר הוספת תחביב, countHobbies מקודם באחד
  - `absent` **0** — countHobbies אינו מקודם לאחר הוספת תחביב

### q1.ב.c6 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בדיקה אם עדיין יש מקום ושאלה למשתמש האם להמשיך + קליטת תשובהאם הציגו את ההודעה בלי לבדוק האם יש עדיין מקום להוריד 1

**Collapsed:** 2 checks · credit max 2 / 2

- **q1.ב.c6.c1** · credit · binary · origin `planner`
  - בדיקה אם עדיין יש מקום במערך ושאלת המשתמש האם להמשיך
  - `full` **1** — לפני הצגת השאלה למשתמש נבדק אם יש עדיין מקום פנוי במערך, ורק במקרה זה מוצגת השאלה האם להוסיף תחביב נוסף
  - `absent` **0** — השאלה מוצגת למשתמש ללא בדיקה מוקדמת האם יש מקום פנוי, או שלא מוצגת כלל
- **q1.ב.c6.c2** · credit · binary · origin `planner`
  - קליטת תשובת המשתמש לשאלה
  - `full` **1** — נקלטת תשובת המשתמש כתו בודד (char)
  - `absent` **0** — לא נקלטת תשובת המשתמש לשאלה

### q1.ב.c7 · 1 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: מחוץ ללולאה - להחזיר ערך true

**Collapsed:** 1 checks · credit max 1 / 1

- **q1.ב.c7.c1** · credit · binary · origin `planner`
  - החזרת ערך true מחוץ ללולאה
  - `full` **1** — לאחר סיום הלולאה מוחזר הערך true, בהתאם לכך שנוסף לפחות תחביב אחד
  - `absent` **0** — לא מוחזר true מחוץ ללולאה

**Interpretation notes:**
- הכניסה ללולאה מותנית בכך שהמערך אינו מלא מראש, ולכן ריצה של הלולאה כרוכה בהוספת תחביב אחד לפחות; החזרת true מתייחסת למקרה זה.

## q1.ג — repaired

> validator messages that sent this scope to repair/fallback:
> - q1.ג.c0: credits must be exactly the components ['q1.ג.c0.k1', 'q1.ג.c0.k2'], in order; got ['q1.ג.c0.k1']

### q1.ג.c0 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ג': פעולה פנימית בשם PrintAverages (סה"כ 16)כותרת הפעולה + void

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ג.c0.c1** · credit · binary · origin `planner`
  - כתיבת כותרת הפעולה הפנימית PrintAverages במחלקת SchoolHobbies
  - `full` **0.5** — הפעולה מוגדרת כפעולה פנימית בשם PrintAverages בתוך המחלקה SchoolHobbies
  - `absent` **0** — הפעולה אינה מוגדרת כפנימית בשם PrintAverages בתוך המחלקה, או שמה שונה
- **q1.ג.c0.c2** · credit · binary · origin `planner`
  - הגדרת הפעולה כפעולה שאינה מחזירה ערך
  - `full` **0.5** — הפעולה מוגדרת מטיפוס void
  - `absent` **0** — הפעולה אינה מוגדרת מטיפוס void

### q1.ג.c1 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : יצירת 2 מונה לכמות החוגים בספורטיבים והלא ספורטיבים + אתחולם ב-0 (0.5 כ"א)

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ג.c1.c1** · credit · binary · origin `planner`
  - יצירת שני מונים נפרדים: אחד לכמות החוגים הספורטיביים ואחד לכמות החוגים הלא ספורטיביים
  - `full` **0.5** — הוגדרו שני משתני מונה נפרדים, אחד לחוגים ספורטיביים ואחד לחוגים לא ספורטיביים
  - `absent` **0** — לא הוגדרו שני מוני חוגים נפרדים
- **q1.ג.c1.c2** · credit · binary · origin `planner`
  - אתחול שני המונים לאפס
  - `full` **0.5** — שני המונים אותחלו לערך 0
  - `absent` **0** — המונים לא אותחלו ל-0

### q1.ג.c2 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : יצירת 2 צוברים לדקות של החוגים הספורטיבים והלא ספורטיבים + אתחולם ב-0 (0.5 כ"א)

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ג.c2.c1** · credit · binary · origin `planner`
  - יצירת שני צוברים נפרדים: אחד לדקות החוגים הספורטיביים ואחד לדקות החוגים הלא ספורטיביים
  - `full` **0.5** — הוגדרו שני משתני צובר נפרדים לסכימת דקות חוגים ספורטיביים וחוגים לא ספורטיביים
  - `absent` **0** — לא הוגדרו שני צוברי דקות נפרדים
- **q1.ג.c2.c2** · credit · binary · origin `planner`
  - אתחול שני הצוברים לאפס
  - `full` **0.5** — שני הצוברים אותחלו לערך 0
  - `absent` **0** — הצוברים לא אותחלו ל-0

### q1.ג.c3 · 3 נק׳ · components

**Teacher's text:** סעיף ג' בתוך PrintAverages : לולאה על מערך התחביבים מ-0 עד countHobbiesאו לולאה על מערך התחביבים עד hobbies.length ובדיקה בתוך הלולאה אם hobbies[i]!=nullאם עשו לולאה עד length ולא בדקו בפנים שהתא שונה מ-null להוריד 1

**Collapsed:** 2 checks · credit max 3 / 3

- **q1.ג.c3.c1** · credit · binary · origin `planner`
  - לולאה על מערך התחביבים העוברת בדיוק על התחביבים הקיימים בפועל
  - שקילות: לולאה עד countHobbies שקולה ללולאה עד hobbies.length בתוספת בדיקת hobbies[i]!=null בתוך הלולאה
  - `full` **3** — קיימת לולאה שעוברת על התחביבים הקיימים בפועל - עד countHobbies, או עד hobbies.length בצירוף בדיקה בתוך הלולאה שהתא שונה מ-null
  - `absent` **0** — אין לולאה שעוברת על התחביבים הקיימים בפועל במערך
- **q1.ג.c3.f1** · fault · fault · origin `planner` · requires `q1.ג.c3.c1`
  - לולאה עד hobbies.length ללא בדיקה שהתא שונה מ-null
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — בוצעה לולאה עד hobbies.length ללא בדיקה בתוך הלולאה שהתא שונה מ-null ← `q1.ג.c3.m1`

### q1.ג.c4 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, בדיקת האם החוג הנוכחי ספורטיבי (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1 כ"א)

**Collapsed:** 3 checks · credit max 3 / 3

- **q1.ג.c4.c1** · credit · binary · origin `planner`
  - בדיקה בתוך הלולאה האם החוג הנוכחי ספורטיבי
  - `full` **1** — קיימת בתוך הלולאה בדיקה האם החוג הנוכחי ספורטיבי
  - `absent` **0** — אין בתוך הלולאה בדיקה האם החוג ספורטיבי
- **q1.ג.c4.c2** · credit · binary · origin `planner`
  - צבירת דקות החוג הספורטיבי לצובר המתאים
  - `full` **1** — דקות החוג הספורטיבי מצטרפות לצובר הדקות הספורטיבי
  - `absent` **0** — דקות החוג הספורטיבי אינן נצברות לצובר
- **q1.ג.c4.c3** · credit · binary · origin `planner`
  - קידום מונה החוגים הספורטיביים
  - `full` **1** — מונה החוגים הספורטיביים מתקדם
  - `absent` **0** — מונה החוגים הספורטיביים אינו מתקדם

### q1.ג.c5 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, אם החוג הנוכחי לא ספורטיבי (else) (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1)

**Collapsed:** 3 checks · credit max 3 / 3

- **q1.ג.c5.c1** · credit · binary · origin `planner`
  - טיפול ב-else עבור חוג שאינו ספורטיבי
  - `full` **1** — קיים טיפול (else) עבור חוג שאינו ספורטיבי
  - `absent` **0** — אין טיפול (else) עבור חוג שאינו ספורטיבי
- **q1.ג.c5.c2** · credit · binary · origin `planner`
  - צבירת דקות החוג הלא ספורטיבי לצובר המתאים
  - `full` **1** — דקות החוג הלא ספורטיבי מצטרפות לצובר הדקות הלא ספורטיבי
  - `absent` **0** — דקות החוג הלא ספורטיבי אינן נצברות לצובר
- **q1.ג.c5.c3** · credit · binary · origin `planner`
  - קידום מונה החוגים הלא ספורטיביים
  - `full` **1** — מונה החוגים הלא ספורטיביים מתקדם
  - `absent` **0** — מונה החוגים הלא ספורטיביים אינו מתקדם

### q1.ג.c6 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : מחוץ ללולאה, בדיקה האם המונה של התחביבים הספורטיבים שונה מאפס (1) אם לא מנעו חלוקה באפס להוריד 1חישוב הממוצע והדפסה (1) (אם טעו בחישוב מתמטי להוריד 0.5)אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)

**Collapsed:** 4 checks · credit max 2 / 2

- **q1.ג.c6.c1** · credit · binary · origin `planner`
  - בדיקה מחוץ ללולאה שהמונה של החוגים הספורטיביים שונה מאפס
  - `full` **1** — קיימת מחוץ ללולאה בדיקה שהמונה של החוגים הספורטיביים שונה מאפס
  - `absent` **0** — אין בדיקה שהמונה של החוגים הספורטיביים שונה מאפס
- **q1.ג.c6.c2** · credit · binary · origin `planner`
  - חישוב ממוצע זמן החוגים הספורטיביים והדפסתו
  - `full` **1** — מחושב ממוצע הדקות של החוגים הספורטיביים והוא מודפס
  - `absent` **0** — הממוצע אינו מחושב, או שאינו מודפס
- **q1.ג.c6.f1** · fault · fault · origin `planner` · requires `q1.ג.c6.c2`
  - טעות בחישוב המתמטי של ממוצע החוגים הספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — נפלה טעות בחישוב המתמטי של ממוצע זמן החוגים הספורטיביים ← `q1.ג.c6.m1`
- **q1.ג.c6.f2** · fault · fault · origin `planner` · requires `q1.ג.c6.c2` · group `q1.ג:once:c2ce2a97`
  - אי המרה לממשי בחישוב ממוצע החוגים הספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — חישוב הממוצע של החוגים הספורטיביים בוצע בחילוק שלם ללא המרה לממשי ← `q1.ג.c6.m2`

**Interpretation notes:**
- הניסוח 'אם לא מנעו חלוקה באפס להוריד 1' מתייחס להיעדר הבדיקה שהמונה שונה מאפס, ולכן טופל במסגרת הבדיקה על קיום אותה בדיקה ולא כפגם נפרד.

### q1.ג.c7 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : מחוץ ללולאה,בדיקה האם המונה של התחביבים הלא-הספורטיבים שונה מאפס (1)אם לא מנעו חלוקה באפס להוריד 1חישוב הממוצע והדפסה (1) (אם טעו בחישוב מתמטי להוריד 0.5)אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)

**Collapsed:** 4 checks · credit max 2 / 2

- **q1.ג.c7.c1** · credit · binary · origin `planner`
  - בדיקה מחוץ ללולאה שהמונה של החוגים הלא ספורטיביים שונה מאפס
  - `full` **1** — קיימת מחוץ ללולאה בדיקה שהמונה של החוגים הלא ספורטיביים שונה מאפס
  - `absent` **0** — אין בדיקה שהמונה של החוגים הלא ספורטיביים שונה מאפס
- **q1.ג.c7.c2** · credit · binary · origin `planner`
  - חישוב ממוצע זמן החוגים הלא ספורטיביים והדפסתו
  - `full` **1** — מחושב ממוצע הדקות של החוגים הלא ספורטיביים והוא מודפס
  - `absent` **0** — הממוצע אינו מחושב, או שאינו מודפס
- **q1.ג.c7.f1** · fault · fault · origin `planner` · requires `q1.ג.c7.c2`
  - טעות בחישוב המתמטי של ממוצע החוגים הלא ספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — נפלה טעות בחישוב המתמטי של ממוצע זמן החוגים הלא ספורטיביים ← `q1.ג.c7.m1`
- **q1.ג.c7.f2** · fault · fault · origin `planner` · requires `q1.ג.c7.c2` · group `q1.ג:once:c2ce2a97`
  - אי המרה לממשי בחישוב ממוצע החוגים הלא ספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — חישוב הממוצע של החוגים הלא ספורטיביים בוצע בחילוק שלם ללא המרה לממשי ← `q1.ג.c7.m2`

**Interpretation notes:**
- הניסוח 'אם לא מנעו חלוקה באפס להוריד 1' מתייחס להיעדר הבדיקה שהמונה שונה מאפס, ולכן טופל במסגרת הבדיקה על קיום אותה בדיקה ולא כפגם נפרד.

**Markers and dispositions:**

- `q1.ג.c3.m1` −1 · candidates ['q1.ג.c3'] · fault · «אם עשו לולאה עד length ולא בדקו בפנים שהתא שונה מ-null להוריד 1»
- `q1.ג.c6.m1` −0.5 · candidates ['q1.ג.c6'] · fault · «אם טעו בחישוב מתמטי להוריד 0.5)»
- `q1.ג.c6.m2` −0.5 · candidates ['q1.ג.c6'] · fault · «אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)»
- `q1.ג.c7.m1` −0.5 · candidates ['q1.ג.c7'] · fault · «אם טעו בחישוב מתמטי להוריד 0.5)»
- `q1.ג.c7.m2` −0.5 · candidates ['q1.ג.c7'] · fault · «אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)»

## q2.א — planner

### q2.א.c0 · 5 נק׳ · components

**Teacher's text:** סעיף א': פעולה בונה public TvShow (string name, int channel)

**Collapsed:** 4 checks · credit max 5 / 5

- **q2.א.c0.c1** · credit · binary · origin `planner`
  - קביעת התכונה name לפי הפרמטר name שהתקבל בפעולה הבונה
  - שקילות: שימוש בפעולת Set על התכונה name, במקום הצבה ישירה, שקול
  - `full` **1.25** — התכונה name מוגדרת לערך הפרמטר name שהתקבל בפעולה הבונה
  - `absent` **0** — התכונה name אינה מוגדרת לפי הפרמטר name שהתקבל
- **q2.א.c0.c2** · credit · binary · origin `planner`
  - קביעת התכונה chl לפי הפרמטר channel שהתקבל בפעולה הבונה
  - שקילות: שימוש בפעולת Set על התכונה chl, במקום הצבה ישירה, שקול
  - `full` **1.25** — התכונה chl מוגדרת לערך הפרמטר channel שהתקבל בפעולה הבונה
  - `absent` **0** — התכונה chl אינה מוגדרת לפי הפרמטר channel שהתקבל
- **q2.א.c0.c3** · credit · binary · origin `planner`
  - קביעת התכונה rate לאפס בפעולה הבונה
  - `full` **1.25** — התכונה rate מוגדרת לאפס (0) בפעולה הבונה
  - `absent` **0** — התכונה rate אינה מוגדרת לאפס בפעולה הבונה
- **q2.א.c0.c4** · credit · binary · origin `planner`
  - קביעת התכונה isOn לאמת בפעולה הבונה
  - `full` **1.25** — התכונה isOn מוגדרת לאמת (true) בפעולה הבונה
  - `absent` **0** — התכונה isOn אינה מוגדרת לאמת בפעולה הבונה

### q2.א.c1 · 10 נק׳ · components

**Teacher's text:** סעיף א': פעולה פנימית UpdateRate (סה"כ לפעולה 10)public TvShow (string name, int channel)

**Collapsed:** 3 checks · credit max 10 / 10

- **q2.א.c1.c1** · credit · binary · origin `planner`
  - ביצוע הפעולה מספר פעמים כמספר הצופים שהתקבל
  - `full` **3.5** — הפעולה חוזרת numViewers פעמים, פעם אחת לכל צופה
  - `absent` **0** — אין חזרה על פני מספר הצופים שהתקבל
- **q2.א.c1.c2** · credit · binary · origin `planner`
  - קליטת דירוג עבור כל צופה
  - `full` **3.25** — בכל חזרה נקלט דירוג בעבור הצופה הנוכחי
  - `absent` **0** — לא נקלט דירוג עבור כל צופה בחזרות
- **q2.א.c1.c3** · credit · binary · origin `planner`
  - הוספת הדירוג שנקלט לדירוג הקיים בתכונה rate
  - `full` **3.25** — הדירוג שנקלט מתווסף לערך הקיים של rate, כך שהתכונה משקפת סכום מתמשך של כל הדירוגים שנקלטו אי פעם
  - `absent` **0** — הדירוג שנקלט מחליף את rate הקיים במקום להצטרף אליו, או שאינו מתווסף כלל

**Interpretation notes:**
- הפעולה אינה מפרטת את אופן קליטת הדירוג עבור כל צופה, ולכן כל דרך לקליטת דירוג בעבור צופה מתקבלת.

## q2.ב — planner

### q2.ב.c0 · 2 נק׳ · components

**Teacher's text:** סעיף ב': פעולה חיצונית LowestRateChannel כותרת הפעולה

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c0.c1** · credit · binary · origin `planner`
  - כותרת הפעולה החיצונית LowestRateChannel
  - `full` **2** — כותרת הפעולה מוגדרת כפעולה חיצונית בשם LowestRateChannel, מקבלת אובייקט מטיפוס TvRate ומחזירה ערך מטיפוס int המייצג מספר ערוץ
  - `absent` **0** — כותרת הפעולה חסרה, או שאינה מקבלת אובייקט TvRate, או שאינה מחזירה מספר ערוץ מטיפוס int

### q2.ב.c1 · 2 נק׳ · components

**Teacher's text:** סעיף ב': בתוך LowestRateChannel : הגדרת מערך צוברים int לכל 100 הערוצים (ערוצים 1-100, המערך אמור להיות בגודל 101)

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c1.c1** · credit · ladder · origin `planner`
  - הגדרת מערך צוברים מסוג int לכל 100 הערוצים
  - `full` **2** — מוגדר מערך מסוג int בגודל 101 המשמש כמערך צוברים לדירוגי הערוצים
  - `p1` **1** — מוגדר מערך צוברים מסוג int, אך בגודל שאינו כולל את כל 100 הערוצים (למשל בגודל 100 במקום 101)
  - `absent` **0** — לא הוגדר מערך צוברים מסוג int לערוצים

### q2.ב.c2 · 3 נק׳ · components

**Teacher's text:** סעיף ב': בתוך LowestRateChannel : לולאה על מערך הצוברים לאיפוס המערך

**Collapsed:** 1 checks · credit max 3 / 3

- **q2.ב.c2.c1** · credit · binary · origin `planner`
  - לולאה על מערך הצוברים לאיפוס המערך
  - `full` **3** — קיימת לולאה שעוברת על כל תאי מערך הצוברים ומאפסת את ערכם
  - `absent` **0** — אין לולאה שמאפסת את מערך הצוברים

### q2.ב.c3.s0 · 3 נק׳ · components

**Teacher's text:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם התחילו מ-1 במקום מ-0 להוריד 0.5 אם ניגשו למערך TvShows בלי Getter להוריד 1 אם טעו בגבול העליון של הלולאה להוריד 0.5

**Collapsed:** 4 checks · credit max 3 / 3

- **q2.ב.c3.s0.c1** · credit · binary · origin `planner`
  - לולאה על מערך התוכניות TvShow מהאינדקס הראשון ועד קטן ממש מגודל המערך
  - `full` **3** — הלולאה מתחילה מאינדקס 0, ניגשת למערך התוכניות באמצעות הפעולה המתאימה, ומסתיימת כאשר האינדקס קטן ממש מאורך המערך
  - `absent` **0** — אין לולאה שעוברת על מערך התוכניות בטווח הנכון
- **q2.ב.c3.s0.f1** · fault · fault · origin `planner` · requires `q2.ב.c3.s0.c1`
  - אינדקס התחלת הלולאה על מערך התוכניות שגוי
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — הלולאה מתחילה מאינדקס 1 במקום מאינדקס 0 ← `q2.ב.c3.s0.m1`
- **q2.ב.c3.s0.f2** · fault · fault · origin `planner` · requires `q2.ב.c3.s0.c1`
  - גישה למערך התוכניות TvShows בלי שימוש בפעולת Getter
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הגישה למערך התוכניות מתבצעת ישירות, ללא שימוש בפעולת Getter מתאימה ← `q2.ב.c3.s0.m2`
- **q2.ב.c3.s0.f3** · fault · fault · origin `planner` · requires `q2.ב.c3.s0.c1`
  - טעות בגבול העליון של הלולאה על מערך התוכניות
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — הלולאה על מערך התוכניות מסתיימת בגבול שגוי, שונה מקטן ממש מאורך המערך ← `q2.ב.c3.s0.m3`

### q2.ב.c3.s1 · 2 נק׳ · components

**Teacher's text:** בתוך הלולאה על TvShows: בדיקה אם התא אינו null

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c3.s1.c1** · credit · binary · origin `planner`
  - בדיקה אם התא במערך התוכניות אינו null
  - `full` **2** — בתוך הלולאה קיימת בדיקה שהתא הנוכחי במערך התוכניות אינו null לפני שימוש בו
  - `absent` **0** — אין בדיקה שהתא במערך התוכניות אינו null

### q2.ב.c3.s2 · 2 נק׳ · components

**Teacher's text:** בתוך הלולאה על TvShows: אם התא אינו null , גישה לערוץ GetChl (ולא ע"י גישה ישירה לתכונה)אם ניגשו ישירות לתכונה chl להוריד 1

**Collapsed:** 2 checks · credit max 2 / 2

- **q2.ב.c3.s2.c1** · credit · binary · origin `planner`
  - גישה לערוץ התוכנית באמצעות הפעולה GetChl
  - `full` **2** — הגישה למספר הערוץ של התוכנית מתבצעת באמצעות הפעולה GetChl
  - `absent` **0** — אין גישה למספר הערוץ של התוכנית באמצעות GetChl
- **q2.ב.c3.s2.f1** · fault · fault · origin `planner` · requires `q2.ב.c3.s2.c1`
  - גישה ישירה לתכונת הערוץ chl במקום שימוש בפעולת GetChl
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הגישה למספר הערוץ מתבצעת ישירות לתכונה chl ולא באמצעות GetChl ← `q2.ב.c3.s2.m1`

### q2.ב.c3.s3 · 5 נק׳ · components

**Teacher's text:** בתוך הלולאה על TvShows: אם התא אינו null , צבירה של הדירוג של הערוץ (GetChl) לתוך מערך הצוברים במקום של הערוץ הזהאם ניגשו ישירות לתכונה rate במקום GetRate להוריד 1

**Collapsed:** 2 checks · credit max 5 / 5

- **q2.ב.c3.s3.c1** · credit · binary · origin `planner`
  - צבירת הדירוג של התוכנית לתוך מערך הצוברים במקום המתאים לערוץ שלה
  - `full` **5** — דירוג התוכנית הנוכחית נצבר (מתווסף) לתא במערך הצוברים המתאים למספר הערוץ שהתקבל
  - `absent` **0** — אין צבירה של דירוג התוכנית לתוך מערך הצוברים
- **q2.ב.c3.s3.f1** · fault · fault · origin `planner` · requires `q2.ב.c3.s3.c1`
  - גישה ישירה לתכונת הדירוג rate במקום שימוש בפעולת GetRate
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הגישה לדירוג התוכנית מתבצעת ישירות לתכונה rate ולא באמצעות GetRate ← `q2.ב.c3.s3.m1`

### q2.ב.c4.s0 · 1 נק׳ · components · fixed

**Teacher's text:** הגדרת מינימום דירוג + אתחול

**Collapsed:** 2 checks · credit max 1 / 1

- **q2.ב.c4.s0.c1** · credit · binary · origin `planner`
  - הגדרת מינימום דירוג
  - `full` **0.5** — מוגדר משתנה לשמירת הדירוג המינימלי שנמצא
  - `absent` **0** — לא הוגדר משתנה לדירוג המינימלי
- **q2.ב.c4.s0.c2** · credit · binary · origin `planner`
  - אתחול משתנה המינימום
  - `full` **0.5** — משתנה הדירוג המינימלי מאותחל לערך התחלתי מתאים (כגון הערך המקסימלי האפשרי)
  - `absent` **0** — משתנה הדירוג המינימלי אינו מאותחל

### q2.ב.c4.s1 · 1 נק׳ · components · fixed

**Teacher's text:** הגדרת ערוץ מינימלי +אתחול

**Collapsed:** 2 checks · credit max 1 / 1

- **q2.ב.c4.s1.c1** · credit · binary · origin `planner`
  - הגדרת ערוץ מינימלי
  - `full` **0.5** — מוגדר משתנה לשמירת מספר הערוץ בעל הדירוג המינימלי
  - `absent` **0** — לא הוגדר משתנה לערוץ המינימלי
- **q2.ב.c4.s1.c2** · credit · binary · origin `planner`
  - אתחול משתנה הערוץ המינימלי
  - `full` **0.5** — משתנה הערוץ המינימלי מאותחל לערך התחלתי מתאים
  - `absent` **0** — משתנה הערוץ המינימלי אינו מאותחל

### q2.ב.c4.s2 · 2 נק׳ · components

**Teacher's text:** הגדרת לולאה על מערך צוברים מ-1 עד 100

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c4.s2.c1** · credit · binary · origin `planner`
  - לולאה על מערך הצוברים מהערוץ הראשון עד הערוץ המאה
  - `full` **2** — קיימת לולאה שעוברת על מערך הצוברים בטווח הערוצים 1 עד 100
  - `absent` **0** — אין לולאה שעוברת על מערך הצוברים בטווח הערוצים הנכון

### q2.ב.c4.s3 · 3 נק׳ · components

**Teacher's text:** בתוך הלולאה על מערך הצוברים: בדיקה האם התא מתאים לערוץ הנוכחי של TvShow בתוך מערך הצוברים גדול מאפס (כלומר יש שימוש בערוץ זה) - לא להוריד, לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום - סה"כ 2 נקודות

**Collapsed:** 3 checks · credit max 3 / 3

- **q2.ב.c4.s3.c1** · credit · binary · origin `planner`
  - בדיקה האם סכום הדירוגים בתא הנוכחי במערך הצוברים קטן מהדירוג המינימלי שנמצא עד כה
  - `full` **3** — בתוך הלולאה על מערך הצוברים קיימת בדיקה האם סכום הדירוגים בתא הנוכחי קטן מהדירוג המינימלי שנמצא עד כה
  - `absent` **0** — אין בדיקה שסכום הדירוגים בתא הנוכחי קטן מהדירוג המינימלי
- **q2.ב.c4.s3.f1** · fault · fault · origin `planner` · requires `q2.ב.c4.s3.c1` · group `q2.ב:q2.ב.c4:d1`
  - חיפוש הערוץ בעל הדירוג המקסימלי במקום המינימלי, כאשר שאר הלוגיקה תקינה ועקבית
  - `none` **0** — ללא הטעות הזו
  - `f1` **-3** — הלוגיקה כולה עקבית אך מחפשת את הערוץ בעל הדירוג הגבוה ביותר במקום הנמוך ביותר ← `q2.ב.c4.s3.m1`
- **q2.ב.c4.s3.n1** · note · note · origin `compiler`
  - לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום
  - `none` **0** — לא רלוונטי
  - `observed` **0** — לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום

### q2.ב.c4.s4 · 1 נק׳ · components

**Teacher's text:** בתוך התנאי (בתוך הלולאה) - החלפה של מינימום דירוג

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c4.s4.c1** · credit · binary · origin `planner`
  - החלפת ערך המינימום בתוך התנאי
  - `full` **1** — כאשר מתקיים התנאי, משתנה הדירוג המינימלי מתעדכן לערך הדירוג החדש שנמצא
  - `absent` **0** — משתנה הדירוג המינימלי אינו מתעדכן כאשר מתקיים התנאי

### q2.ב.c4.s5 · 1 נק׳ · components

**Teacher's text:** בתוך התנאי (בתוך הלולאה) - החלפת הערוץ המינימלי

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c4.s5.c1** · credit · binary · origin `planner`
  - החלפת הערוץ המינימלי בתוך התנאי
  - `full` **1** — כאשר מתקיים התנאי, משתנה הערוץ המינימלי מתעדכן למספר הערוץ הנוכחי
  - `absent` **0** — משתנה הערוץ המינימלי אינו מתעדכן כאשר מתקיים התנאי

### q2.ב.c5 · 1 נק׳ · components

**Teacher's text:** סעיף ב': בתוך LowestRateChannel : החזרת הערוץ המינימלי

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c5.c1** · credit · binary · origin `planner`
  - החזרת הערוץ המינימלי מהפעולה
  - `full` **1** — הפעולה מחזירה את מספר הערוץ המינימלי שנמצא
  - `absent` **0** — הפעולה אינה מחזירה את מספר הערוץ המינימלי

**Markers and dispositions:**

- `q2.ב.c3.s0.m1` −0.5 · candidates ['q2.ב.c3.s0'] · fault · «אם התחילו מ-1 במקום מ-0 להוריד 0.5»
- `q2.ב.c3.s0.m2` −1 · candidates ['q2.ב.c3.s0'] · fault · «אם ניגשו למערך TvShows בלי Getter להוריד 1»
- `q2.ב.c3.s0.m3` −0.5 · candidates ['q2.ב.c3.s0'] · fault · «אם טעו בגבול העליון של הלולאה להוריד 0.5»
- `q2.ב.c3.s2.m1` −1 · candidates ['q2.ב.c3.s2'] · fault · «אם ניגשו ישירות לתכונה chl להוריד 1»
- `q2.ב.c3.s3.m1` −1 · candidates ['q2.ב.c3.s3'] · fault · «אם ניגשו ישירות לתכונה rate במקום GetRate להוריד 1»
- `q2.ב.c4.s3.m1` −3 · candidates ['q2.ב.c4.s0', 'q2.ב.c4.s1', 'q2.ב.c4.s2', 'q2.ב.c4.s3', 'q2.ב.c4.s4', 'q2.ב.c4.s5'] · fault · «פירוט ל-10:אם חיפשו את המקסימום אך הלוגיקה בסדר להוריד 3»

## q2.ג — planner

### q2.ג.c0.s0 · 2 נק׳ · components

**Teacher's text:** כותרת הפעולה PrintLowRatingChannel

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ג.c0.s0.c1** · credit · binary · origin `planner`
  - כותרת הפעולה PrintLowRatingChannel
  - `full` **2** — כותרת הפעולה תואמת את הנדרש: שם PrintLowRatingChannel, המקבלת אובייקט מטיפוס TvRate
  - `absent` **0** — הכותרת אינה תואמת - שם הפעולה או סוג הפרמטר שגויים

### q2.ג.c0.s1 · 3 נק׳ · components

**Teacher's text:** מציאת הערוץ בעל דירוג מינימלי ע"י זימון LowestRateChannel

**Collapsed:** 1 checks · credit max 3 / 3

- **q2.ג.c0.s1.c1** · credit · binary · origin `planner`
  - מציאת הערוץ בעל דירוג מינימלי ע"י זימון LowestRateChannel
  - `full` **3** — מזומנת הפעולה LowestRateChannel לקבלת הערוץ בעל הדירוג המינימלי
  - `absent` **0** — לא זומנה הפעולה LowestRateChannel למציאת הערוץ המינימלי, או שהערוץ המינימלי חושב בדרך אחרת

### q2.ג.c0.s2 · 3 נק׳ · components

**Teacher's text:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם הגישה למערך בלי getter להוריד 1

**Collapsed:** 2 checks · credit max 3 / 3

- **q2.ג.c0.s2.c1** · credit · ladder · origin `planner`
  - הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ-length של המערך
  - `full` **3** — לולאה הרצה על מערך התוכניות מאינדקס 0 ועד קטן ממש מ-length של המערך
  - `p1` **1.5** — הלולאה מוגדרת על מערך התוכניות אך תחום האינדקסים אינו מ-0 עד קטן ממש מ-length
  - `absent` **0** — לא הוגדרה לולאה כזו על מערך התוכניות
- **q2.ג.c0.s2.f1** · fault · fault · origin `planner` · requires `q2.ג.c0.s2.c1`
  - גישה למערך התוכניות ללא שימוש ב-getter
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הגישה למערך התוכניות נעשית ישירות ולא באמצעות getter ← `q2.ג.c0.s2.m1`

**Interpretation notes:**
- תחום האינדקסים בלולאה (מ-0 ועד קטן מ-length) נבחן כתנאי אחד הכולל את שתי הגבולות, ולא כשני תנאים נפרדים.

### q2.ג.c0.s3 · 8 נק׳ · components · fixed

**Teacher's text:** בתוך הלולאה על TvShows: בדיקה האם תוכנית מתאימה להדפסה:אינה null ב (2 נקודות) וגם הערוץ שלה תואם את הערוץ המינימלי (ע"י GetChl והשוואתם (2 נקודות) וגם היא באוויר (ע"י GetIsOn ב 2 נקודות) הדפסה של השם של התוכנית (ע"י GetName ב( 2 נקודות)

**Collapsed:** 4 checks · credit max 8 / 8

- **q2.ג.c0.s3.c1** · credit · binary · origin `planner`
  - בדיקה האם תוכנית מתאימה להדפסה: אינה null
  - `full` **2** — נבדק שהאיבר הנוכחי במערך אינו null לפני שאר הבדיקות
  - `absent` **0** — לא נבדק אם האיבר הנוכחי במערך אינו null
- **q2.ג.c0.s3.c2** · credit · binary · origin `planner`
  - הערוץ שלה תואם את הערוץ המינימלי, ע"י GetChl והשוואתם
  - `full` **2** — נבדק, באמצעות GetChl והשוואה, שהערוץ של התוכנית שווה לערוץ המינימלי
  - `absent` **0** — לא נבדקה התאמת ערוץ התוכנית לערוץ המינימלי, או שהבדיקה לא נעשית באמצעות GetChl
- **q2.ג.c0.s3.c3** · credit · binary · origin `planner`
  - היא באוויר, ע"י GetIsOn
  - `full` **2** — נבדק, באמצעות GetIsOn, שהתוכנית משודרת כעת
  - `absent` **0** — לא נבדק אם התוכנית משודרת כעת, או שהבדיקה לא נעשית באמצעות GetIsOn
- **q2.ג.c0.s3.c4** · credit · binary · origin `planner`
  - הדפסה של השם של התוכנית, ע"י GetName
  - `full` **2** — מודפס שם התוכנית שהתקבל באמצעות GetName
  - `absent` **0** — לא מודפס שם התוכנית, או שההדפסה לא נעשית באמצעות GetName

**Markers and dispositions:**

- `q2.ג.c0.s2.m1` −1 · candidates ['q2.ג.c0.s2'] · fault · «אם הגישה למערך בלי getter להוריד 1»

