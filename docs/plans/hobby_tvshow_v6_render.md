# hobby_tvshow — plan/v6 render

- plan_hash `f068fa66efd7ef66…` · config_hash `49bfd89112fa1a20…` · pack `computer_science@v1`
- stage 1 `plan-compiler/v2.0+stage1-v6.0` · 38 criteria · 85 checks
- scope origins: q1.א=planner, q1.ב=planner, q1.ג=planner, q2.א=planner, q2.ב=planner, q2.ג=planner

## q1.א — planner

### q1.א.c0 · 4 נק׳ · components

**Teacher's text:** סעיף א: כותרת ותכונות המחלקה Hobby

**Collapsed:** 4 checks · credit max 4 / 4

- **q1.א.c0.c1** · credit · binary · origin `planner` · element `binary`
  - כותרת המחלקה Hobby
  - שקילות: כותרת עם public, עם internal או בלי מציין גישה מתקבלת
  - `full` **1** — נכתבה כותרת מחלקה בשם Hobby
  - `absent` **0** — אין כותרת למחלקה Hobby, או שנכתבה כותרת של מחלקה אחרת
- **q1.א.c0.c2** · credit · binary · origin `planner` · element `binary`
  - תכונת שם התחביב מטיפוס מחרוזת
  - `full` **1** — במחלקה Hobby מוגדרת תכונה לשם התחביב מטיפוס string
  - `absent` **0** — אין במחלקה Hobby תכונה לשם התחביב, או שהיא אינה מטיפוס מחרוזת
- **q1.א.c0.c3** · credit · binary · origin `planner` · element `binary`
  - תכונה האם התחביב ספורטיבי מטיפוס בוליאני
  - `full` **1** — במחלקה Hobby מוגדרת תכונה isSportive מטיפוס bool
  - `absent` **0** — אין במחלקה Hobby תכונה המציינת אם התחביב ספורטיבי, או שהיא אינה מטיפוס בוליאני
- **q1.א.c0.c4** · credit · binary · origin `planner` · element `binary`
  - תכונת זמן פעילות התחביב בדקות מטיפוס שלם
  - שקילות: שם התכונה minutes או durationInMinutes מתקבל
  - `full` **1** — במחלקה Hobby מוגדרת תכונה לזמן הפעילות בדקות מטיפוס int
  - `absent` **0** — אין במחלקה Hobby תכונה לזמן הפעילות בדקות, או שהיא אינה מטיפוס שלם

**Interpretation notes:**
- הכותרת וכל אחת משלוש התכונות נבדקות בנפרד.
- הגדרת התכונות כפרטיות אינה נדרשת במפורש בטקסט הקריטריון, ולכן אינה תנאי לזיכוי.

### q1.א.c1 · 4 נק׳ · components

**Teacher's text:** סעיף א: פעולה בונה Hobby(string hobbyName, bool isSportive, int minutes)

**Collapsed:** 4 checks · credit max 4 / 4

- **q1.א.c1.c1** · credit · binary · origin `planner` · element `binary`
  - כותרת הפעולה הבונה Hobby
  - שקילות: שמות פרמטרים שונים מתקבלים כל עוד הטיפוסים והסדר תואמים
  - `full` **1** — נכתבה פעולה בונה בשם Hobby, ללא טיפוס החזרה, המקבלת מחרוזת, ערך בוליאני ומספר שלם
  - `absent` **0** — אין פעולה בונה Hobby, או שהיא אינה מקבלת את שלושת הפרמטרים בטיפוסים הנדרשים
- **q1.א.c1.c2** · credit · binary · origin `planner` · element `binary`
  - קביעת ערך תכונת שם התחביב לפי הפרמטר
  - שקילות: השמה עם this או בלעדיו, כשהשמות נבדלים, שקולה
  - `full` **1** — ערך הפרמטר של שם התחביב מושם בתכונת שם התחביב של העצם
  - `absent` **0** — אין השמה לתכונת שם התחביב, או שהפרמטר מושם לעצמו ולא לתכונה
- **q1.א.c1.c3** · credit · binary · origin `planner` · element `binary`
  - קביעת ערך התכונה isSportive לפי הפרמטר
  - שקילות: השמה עם this או בלעדיו, כשהשמות נבדלים, שקולה
  - `full` **1** — ערך הפרמטר isSportive מושם בתכונה isSportive של העצם
  - `absent` **0** — אין השמה לתכונה isSportive, או שהפרמטר מושם לעצמו ולא לתכונה
- **q1.א.c1.c4** · credit · binary · origin `planner` · element `binary`
  - קביעת ערך תכונת זמן הפעילות בדקות לפי הפרמטר
  - שקילות: השמה עם בדיקת טווח ובלעדיה מתקבלת
  - `full` **1** — ערך הפרמטר minutes מושם בתכונת זמן הפעילות בדקות של העצם
  - `absent` **0** — אין השמה לתכונת זמן הפעילות בדקות, או שהפרמטר מושם לעצמו או למשתנה שאינו מוגדר כתכונה

**Interpretation notes:**
- בדיקת טווח הדקות אינה נדרשת, בהתאם להערה בפתרון לדוגמה.
- השמה של פרמטר לעצמו, כששמו זהה לשם התכונה ובלי this, אינה קובעת את ערך התכונה.

## q1.ב — planner

### q1.ב.c0 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב: פעולה פנימית בשם PopulateHobbies (סה"כ 16)כותרת הפעולה + טיפוס מוחזר bool

**Collapsed:** 2 checks · credit max 2 / 2

- **q1.ב.c0.c1** · credit · binary · origin `planner` · element `binary`
  - כותרת הפעולה הפנימית PopulateHobbies
  - `full` **1** — נכתבה כותרת לפעולה פנימית (לא סטטית) בשם PopulateHobbies, ללא פרמטרים
  - `absent` **0** — אין כותרת לפעולה PopulateHobbies, או שהיא אינה פעולה פנימית
- **q1.ב.c0.c2** · credit · binary · origin `planner` · element `binary`
  - טיפוס מוחזר bool
  - `full` **1** — בכותרת הפעולה PopulateHobbies הטיפוס המוחזר הוא bool
  - `absent` **0** — הטיפוס המוחזר בכותרת הפעולה PopulateHobbies אינו bool או חסר

### q1.ב.c1 · 1 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: לפני הלולאה - לבדוק אם המערך מלא, להחזיר false

**Collapsed:** 1 checks · credit max 1 / 1

- **q1.ב.c1.c1** · credit · binary · origin `planner` · element `non_binary`
  - לפני הלולאה - לבדוק אם המערך מלא, להחזיר false
  - שקילות: בדיקה שקולה, כגון countHobbies >= hobbies.Length, תקפה
  - `full` **1** — לפני הלולאה נבדק אם המערך hobbies מלא (countHobbies שווה לאורך המערך), ובמקרה זה מוחזר false
  - `absent` **0** — אין לפני הלולאה בדיקה אם המערך hobbies מלא עם החזרת false

### q1.ב.c2 · 3 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: לולאה עד שאין מקום במערך (כל עוד countHobbies קטן מ-length) או כל עוד המשתמש יענה Y או y לשאלה

**Collapsed:** 2 checks · credit max 3 / 3

- **q1.ב.c2.c1** · credit · binary · origin `planner` · element `binary`
  - לולאה עד שאין מקום במערך (כל עוד countHobbies קטן מ-length)
  - `full` **1.5** — הלולאה ממשיכה רק כל עוד countHobbies קטן מאורך המערך hobbies
  - `absent` **0** — אין לולאה, או שתנאי הלולאה אינו עוצר כשאין עוד מקום במערך hobbies
- **q1.ב.c2.c2** · credit · binary · origin `planner` · element `non_binary`
  - הלולאה ממשיכה כל עוד המשתמש יענה Y או y לשאלה
  - שקילות: בדיקת המשך לפי Y/y או עצירה לפי N/n שקולות; גם מימוש בעזרת break או משתנה דגל תקף
  - `full` **1.5** — תנאי הלולאה עוצר את הקליטה כשתשובת המשתמש לשאלה היא N או n, ואחרת ממשיך
  - `absent` **0** — תנאי הלולאה אינו תלוי בתשובת המשתמש לשאלה האם להמשיך

**Interpretation notes:**
- המילה «או» בטקסט מתפרשת כך שהלולאה נעצרת כשמתקיים אחד מתנאי העצירה, כלומר ממשיכה רק כשיש מקום וגם המשתמש מבקש להמשיך.

### q1.ב.c3 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קליטה של 3 נתוני התחביב (name, isSportive, minutes)

**Collapsed:** 3 checks · credit max 3 / 3

- **q1.ב.c3.c1** · credit · binary · origin `planner` · element `binary`
  - בתוך הלולאה קליטה של שם התחביב (name)
  - `full` **1** — בתוך הלולאה נקלט מהמשתמש שם התחביב (name)
  - `absent` **0** — שם התחביב (name) אינו נקלט בתוך הלולאה
- **q1.ב.c3.c2** · credit · binary · origin `planner` · element `binary`
  - בתוך הלולאה קליטה של isSportive
  - שקילות: כל דרך המביאה את הקלט לערך בוליאני (למשל bool.Parse) תקפה
  - `full` **1** — בתוך הלולאה נקלט מהמשתמש ערך isSportive והומר לבוליאני
  - `absent` **0** — הנתון isSportive אינו נקלט בתוך הלולאה
- **q1.ב.c3.c3** · credit · binary · origin `planner` · element `binary`
  - בתוך הלולאה קליטה של minutes
  - שקילות: המרה למספר שלם בכל דרך שקולה (int.Parse, Convert.ToInt32) תקפה
  - `full` **1** — בתוך הלולאה נקלט מהמשתמש זמן הפעילות minutes והומר למספר שלם
  - `absent` **0** — הנתון minutes אינו נקלט בתוך הלולאה

### q1.ב.c4 · 3 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה יצירה של עצם חדש מטיפוס Hobby בתא המתאים במערך (hobbies[countHobbies])

**Collapsed:** 2 checks · credit max 3 / 3

- **q1.ב.c4.c1** · credit · binary · origin `planner` · element `binary`
  - בתוך הלולאה יצירה של עצם חדש מטיפוס Hobby
  - `full` **1.5** — בתוך הלולאה נוצר עצם חדש מטיפוס Hobby מהנתונים שנקלטו (new Hobby עם שם, isSportive ו-minutes)
  - `absent` **0** — בתוך הלולאה לא נוצר עצם חדש מטיפוס Hobby מהנתונים שנקלטו
- **q1.ב.c4.c2** · credit · binary · origin `planner` · element `binary`
  - השמת העצם בתא המתאים במערך (hobbies[countHobbies])
  - שקילות: יצירה לתוך משתנה עזר ואחריה השמה ל-hobbies[countHobbies] שקולה
  - `full` **1.5** — העצם החדש נשמר בתא hobbies[countHobbies], התא הפנוי הראשון במערך
  - `absent` **0** — העצם החדש אינו נשמר בתא hobbies[countHobbies] של המערך

### q1.ב.c5 · 1 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קידום countHobbies

**Collapsed:** 1 checks · credit max 1 / 1

- **q1.ב.c5.c1** · credit · binary · origin `planner` · element `binary`
  - בתוך הלולאה קידום countHobbies
  - `full` **1** — בתוך הלולאה, אחרי הוספת תחביב, countHobbies גדל באחד
  - `absent` **0** — countHobbies אינו מקודם בתוך הלולאה

### q1.ב.c6 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בדיקה אם עדיין יש מקום ושאלה למשתמש האם להמשיך + קליטת תשובהאם הציגו את ההודעה בלי לבדוק האם יש עדיין מקום להוריד 1

**Collapsed:** 2 checks · credit max 2 / 2

- **q1.ב.c6.c1** · credit · binary · origin `planner` · element `non_binary`
  - בדיקה אם עדיין יש מקום ושאלה למשתמש האם להמשיך
  - `full` **1** — רק כאשר עדיין יש מקום במערך hobbies מוצגת למשתמש השאלה האם להמשיך
  - `absent` **0** — לא מוצגת שאלה למשתמש האם להמשיך, או שהיא מוצגת בלי לבדוק קודם האם יש עדיין מקום במערך
- **q1.ב.c6.c2** · credit · binary · origin `planner` · element `binary`
  - קליטת תשובה
  - שקילות: קליטת התשובה כתו בודד (char) או כמחרוזת תקפה
  - `full` **1** — תשובת המשתמש לשאלה האם להמשיך נקלטת למשתנה שתנאי הלולאה בודק
  - `absent` **0** — תשובת המשתמש לשאלה האם להמשיך אינה נקלטת

**Interpretation notes:**
- ההנחיה «אם הציגו את ההודעה בלי לבדוק האם יש עדיין מקום להוריד» מיושמת כאי-זיכוי של רכיב הבדיקה והשאלה, ולא כהורדה נוספת.

### q1.ב.c7 · 1 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: מחוץ ללולאה - להחזיר ערך true

**Collapsed:** 1 checks · credit max 1 / 1

- **q1.ב.c7.c1** · credit · binary · origin `planner` · element `binary`
  - מחוץ ללולאה - להחזיר ערך true
  - שקילות: החזרת משתנה שערכו true כאשר נוסף לפחות תחביב אחד שקולה
  - `full` **1** — אחרי הלולאה הפעולה מחזירה true
  - `absent` **0** — אחרי הלולאה הפעולה אינה מחזירה true

## q1.ג — planner

### q1.ג.c0 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ג': פעולה פנימית בשם PrintAverages (סה"כ 16)כותרת הפעולה + void

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ג.c0.c1** · credit · binary · origin `planner` · element `binary`
  - כותרת הפעולה הפנימית PrintAverages
  - `full` **0.5** — נכתבה כותרת של פעולה פנימית בשם PrintAverages במחלקה SchoolHobbies
  - `absent` **0** — אין כותרת לפעולה PrintAverages, או שהיא מוגדרת כפעולה סטטית ולא כפעולה פנימית
- **q1.ג.c0.c2** · credit · binary · origin `planner` · element `binary`
  - טיפוס ההחזרה void
  - `full` **0.5** — בכותרת הפעולה PrintAverages מופיע טיפוס ההחזרה void
  - `absent` **0** — בכותרת הפעולה PrintAverages אין void, או שמופיע טיפוס החזרה אחר

### q1.ג.c1 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : יצירת 2 מונה לכמות החוגים בספורטיבים והלא ספורטיבים + אתחולם ב-0 (0.5 כ"א)

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ג.c1.c1** · credit · binary · origin `planner` · element `non_binary`
  - יצירת 2 מונים לכמות החוגים הספורטיביים והלא ספורטיביים
  - `full` **0.5** — הוגדרו שני מונים נפרדים: אחד לכמות החוגים הספורטיביים ואחד לכמות החוגים הלא ספורטיביים
  - `absent` **0** — לא הוגדרו שני מונים נפרדים לכמות החוגים הספורטיביים והלא ספורטיביים
- **q1.ג.c1.c2** · credit · binary · origin `planner` · element `non_binary`
  - אתחול שני המונים ב-0
  - `full` **0.5** — שני המונים של כמות החוגים אותחלו ב-0
  - `absent` **0** — מוני כמות החוגים לא אותחלו ב-0

### q1.ג.c2 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : יצירת 2 צוברים לדקות של החוגים הספורטיבים והלא ספורטיבים + אתחולם ב-0 (0.5 כ"א)

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ג.c2.c1** · credit · binary · origin `planner` · element `non_binary`
  - יצירת 2 צוברים לדקות של החוגים הספורטיביים והלא ספורטיביים
  - שקילות: צובר מטיפוס ממשי שקול לצובר מטיפוס שלם
  - `full` **0.5** — הוגדרו שני צוברים נפרדים: אחד לדקות של החוגים הספורטיביים ואחד לדקות של החוגים הלא ספורטיביים
  - `absent` **0** — לא הוגדרו שני צוברים נפרדים לדקות של החוגים הספורטיביים והלא ספורטיביים
- **q1.ג.c2.c2** · credit · binary · origin `planner` · element `non_binary`
  - אתחול שני הצוברים ב-0
  - `full` **0.5** — שני צוברי הדקות אותחלו ב-0
  - `absent` **0** — צוברי הדקות לא אותחלו ב-0

### q1.ג.c3 · 3 נק׳ · components

**Teacher's text:** סעיף ג' בתוך PrintAverages : לולאה על מערך התחביבים מ-0 עד countHobbiesאו לולאה על מערך התחביבים עד hobbies.length ובדיקה בתוך הלולאה אם hobbies[i]!=nullאם עשו לולאה עד length ולא בדקו בפנים שהתא שונה מ-null להוריד 1

**Collapsed:** 2 checks · credit max 3 / 3

- **q1.ג.c3.c1** · credit · ladder · origin `planner` · element `non_binary`
  - לולאה על מערך התחביבים מ-0 עד countHobbies
  - שקילות: לולאה עד hobbies.length מתקבלת כחלופה ללולאה עד countHobbies
  - `full` **3** — לולאה העוברת על מערך התחביבים hobbies מ-0 ועד countHobbies (לא כולל), או עד hobbies.length
  - `p1` **2.25** — יש לולאה על מערך התחביבים hobbies, אך גבול הלולאה חורג בתא אחד (למשל עד countHobbies כולל)
  - `p2` **1.5** — יש לולאה על מערך התחביבים hobbies, אך הגבול שלה אינו קשור ל-countHobbies או ל-hobbies.length, או שהיא מתחילה מתא שאינו הראשון
  - `absent` **0** — אין לולאה העוברת על מערך התחביבים hobbies, או שהלולאה עוברת על אוסף אחר
- **q1.ג.c3.f1** · fault · fault · origin `planner` · requires `q1.ג.c3.c1`
  - לולאה עד length בלי בדיקה שהתא שונה מ-null
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הלולאה רצה עד hobbies.length, ובתוכה אין בדיקה ש-hobbies[i] שונה מ-null ← `q1.ג.c3.m1`

### q1.ג.c4 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, בדיקת האם החוג הנוכחי ספורטיבי (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1 כ"א)

**Collapsed:** 3 checks · credit max 3 / 3

- **q1.ג.c4.c1** · credit · binary · origin `planner` · element `binary`
  - בתוך הלולאה, בדיקה האם החוג הנוכחי ספורטיבי
  - שקילות: השוואה מפורשת ל-true שקולה לשימוש ישיר בערך המוחזר
  - `full` **1** — בתוך הלולאה יש תנאי הבודק האם החוג הנוכחי hobbies[i] ספורטיבי (למשל באמצעות GetIsSportive)
  - `absent` **0** — אין בתוך הלולאה בדיקה האם החוג הנוכחי ספורטיבי
- **q1.ג.c4.c2** · credit · binary · origin `planner` · element `binary`
  - צבירת הדקות של החוג הספורטיבי
  - שקילות: קבלת הדקות באמצעות GetMinutes או GetDurationInMinutes שקולה
  - `full` **1** — כשהחוג ספורטיבי, הדקות שלו מתווספות לצובר הדקות של החוגים הספורטיביים
  - `absent` **0** — הדקות של החוג הספורטיבי אינן מתווספות לצובר הדקות של החוגים הספורטיביים
- **q1.ג.c4.c3** · credit · binary · origin `planner` · element `binary`
  - קידום המונה של החוגים הספורטיביים
  - `full` **1** — כשהחוג ספורטיבי, מונה החוגים הספורטיביים גדל באחד
  - `absent` **0** — מונה החוגים הספורטיביים אינו מקודם כשהחוג ספורטיבי

**Interpretation notes:**
- השימוש המצופה הוא בפעולות Get של המחלקה Hobby; במחוון לא נקבע ניכוי נפרד על אי-שימוש בהן, ולכן הרכיבים נבדקים לפי מה שהקוד מבצע.

### q1.ג.c5 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, אם החוג הנוכחי לא ספורטיבי (else) (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1)

**Collapsed:** 3 checks · credit max 3 / 3

- **q1.ג.c5.c1** · credit · binary · origin `planner` · element `binary`
  - בתוך הלולאה, טיפול במקרה שהחוג הנוכחי לא ספורטיבי (else)
  - שקילות: תנאי נפרד הבודק שהחוג אינו ספורטיבי שקול ל-else
  - `full` **1** — בתוך הלולאה יש ענף else, או תנאי מפורש, לחוג שאינו ספורטיבי
  - `absent` **0** — אין בתוך הלולאה ענף לחוג שאינו ספורטיבי
- **q1.ג.c5.c2** · credit · binary · origin `planner` · element `binary`
  - צבירת הדקות של החוג הלא ספורטיבי
  - שקילות: קבלת הדקות באמצעות GetMinutes או GetDurationInMinutes שקולה
  - `full` **1** — כשהחוג אינו ספורטיבי, הדקות שלו מתווספות לצובר הדקות של החוגים הלא ספורטיביים
  - `absent` **0** — הדקות של החוג הלא ספורטיבי אינן מתווספות לצובר הדקות של החוגים הלא ספורטיביים
- **q1.ג.c5.c3** · credit · binary · origin `planner` · element `binary`
  - קידום המונה של החוגים הלא ספורטיביים
  - `full` **1** — כשהחוג אינו ספורטיבי, מונה החוגים הלא ספורטיביים גדל באחד
  - `absent` **0** — מונה החוגים הלא ספורטיביים אינו מקודם כשהחוג אינו ספורטיבי

### q1.ג.c6 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : מחוץ ללולאה, בדיקה האם המונה של התחביבים הספורטיבים שונה מאפס (1) אם לא מנעו חלוקה באפס להוריד 1חישוב הממוצע והדפסה (1) (אם טעו בחישוב מתמטי להוריד 0.5)אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)

**Collapsed:** 4 checks · credit max 2 / 2

- **q1.ג.c6.c1** · credit · binary · origin `planner` · element `binary`
  - מחוץ ללולאה, בדיקה האם המונה של התחביבים הספורטיביים שונה מאפס
  - שקילות: בדיקה שהמונה גדול מאפס שקולה
  - `full` **1** — לפני חישוב ממוצע התחביבים הספורטיביים נבדק שהמונה שלהם שונה מאפס, כך שנמנעת חלוקה באפס
  - `absent` **0** — אין בדיקה שמונה התחביבים הספורטיביים שונה מאפס לפני החלוקה
- **q1.ג.c6.c2** · credit · binary · origin `planner` · element `non_binary`
  - חישוב ממוצע זמן התחביבים הספורטיביים והדפסתו
  - `full` **1** — צובר הדקות של התחביבים הספורטיביים מחולק במונה שלהם, והממוצע מודפס
  - `absent` **0** — ממוצע זמן התחביבים הספורטיביים אינו מחושב או אינו מודפס, או שהחישוב נעשה על צובר או מונה אחר
- **q1.ג.c6.f1** · fault · fault · origin `planner` · requires `q1.ג.c6.c2`
  - טעות בחישוב המתמטי של ממוצע התחביבים הספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — בחישוב ממוצע התחביבים הספורטיביים יש טעות מתמטית (למשל סדר פעולות שגוי) ← `q1.ג.c6.m1`
- **q1.ג.c6.f2** · fault · fault · origin `planner` · requires `q1.ג.c6.c2` · group `q1.ג:once:c2ce2a97`
  - אי-המרה לממשי בחישוב ממוצע התחביבים הספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — בחישוב ממוצע התחביבים הספורטיביים החלוקה היא בין שני שלמים, בלי המרה לממשי (כגון (double) או הכפלה ב-1.0) ובלי שאחד מהם מטיפוס ממשי ← `q1.ג.c6.m2`

**Interpretation notes:**
- «אם לא מנעו חלוקה באפס להוריד» מתייחס להיעדר הבדיקה שהמונה שונה מאפס, ואינו ניכוי נוסף עליה.
- ניכוי על אי-המרה לממשי נגבה פעם אחת בלבד עבור שני הממוצעים יחד.

### q1.ג.c7 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : מחוץ ללולאה,בדיקה האם המונה של התחביבים הלא-הספורטיבים שונה מאפס (1)אם לא מנעו חלוקה באפס להוריד 1חישוב הממוצע והדפסה (1) (אם טעו בחישוב מתמטי להוריד 0.5)אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)

**Collapsed:** 4 checks · credit max 2 / 2

- **q1.ג.c7.c1** · credit · binary · origin `planner` · element `binary`
  - מחוץ ללולאה, בדיקה האם המונה של התחביבים הלא ספורטיביים שונה מאפס
  - שקילות: בדיקה שהמונה גדול מאפס שקולה
  - `full` **1** — לפני חישוב ממוצע התחביבים הלא ספורטיביים נבדק שהמונה שלהם שונה מאפס, כך שנמנעת חלוקה באפס
  - `absent` **0** — אין בדיקה שמונה התחביבים הלא ספורטיביים שונה מאפס לפני החלוקה
- **q1.ג.c7.c2** · credit · binary · origin `planner` · element `non_binary`
  - חישוב ממוצע זמן התחביבים הלא ספורטיביים והדפסתו
  - `full` **1** — צובר הדקות של התחביבים הלא ספורטיביים מחולק במונה שלהם, והממוצע מודפס
  - `absent` **0** — ממוצע זמן התחביבים הלא ספורטיביים אינו מחושב או אינו מודפס, או שהחישוב נעשה על צובר או מונה אחר
- **q1.ג.c7.f1** · fault · fault · origin `planner` · requires `q1.ג.c7.c2`
  - טעות בחישוב המתמטי של ממוצע התחביבים הלא ספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — בחישוב ממוצע התחביבים הלא ספורטיביים יש טעות מתמטית (למשל סדר פעולות שגוי) ← `q1.ג.c7.m1`
- **q1.ג.c7.f2** · fault · fault · origin `planner` · requires `q1.ג.c7.c2` · group `q1.ג:once:c2ce2a97`
  - אי-המרה לממשי בחישוב ממוצע התחביבים הלא ספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — בחישוב ממוצע התחביבים הלא ספורטיביים החלוקה היא בין שני שלמים, בלי המרה לממשי (כגון (double) או הכפלה ב-1.0) ובלי שאחד מהם מטיפוס ממשי ← `q1.ג.c7.m2`

**Interpretation notes:**
- «אם לא מנעו חלוקה באפס להוריד» מתייחס להיעדר הבדיקה שהמונה שונה מאפס, ואינו ניכוי נוסף עליה.

**Markers and dispositions:**

- `q1.ג.c3.m1` −1 · candidates ['q1.ג.c3'] · fault · «אם עשו לולאה עד length ולא בדקו בפנים שהתא שונה מ-null להוריד 1»
- `q1.ג.c6.m1` −0.5 · candidates ['q1.ג.c6'] · fault · «אם טעו בחישוב מתמטי להוריד 0.5)»
- `q1.ג.c6.m2` −0.5 · candidates ['q1.ג.c6'] · fault · «אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)»
- `q1.ג.c7.m1` −0.5 · candidates ['q1.ג.c7'] · fault · «אם טעו בחישוב מתמטי להוריד 0.5)»
- `q1.ג.c7.m2` −0.5 · candidates ['q1.ג.c7'] · fault · «אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)»

## q2.א — planner

### q2.א.c0 · 5 נק׳ · components

**Teacher's text:** סעיף א': פעולה בונה public TvShow (string name, int channel)

**Collapsed:** 5 checks · credit max 5 / 5

- **q2.א.c0.c1** · credit · binary · origin `planner` · element `binary`
  - כותרת הפעולה הבונה public TvShow (string name, int channel)
  - שקילות: שמות פרמטרים אחרים שקולים, כל עוד הטיפוסים והסדר זהים
  - `full` **1** — כותרת הפעולה הבונה TvShow מקבלת מחרוזת name ומספר שלם channel
  - `absent` **0** — אין כותרת לפעולה הבונה TvShow, או שהיא אינה מקבלת מחרוזת ומספר שלם
- **q2.א.c0.c2** · credit · binary · origin `planner` · element `binary`
  - קביעת שם התכנית name
  - שקילות: השמה באמצעות פעולת Set של התכונה שקולה
  - `full` **1** — התכונה name מקבלת את ערך הפרמטר name
  - `absent` **0** — התכונה name אינה מקבלת את ערך הפרמטר name, או שההשמה נעשית ליעד שאינו התכונה
- **q2.א.c0.c3** · credit · binary · origin `planner` · element `binary`
  - קביעת ערוץ התכנית chl לפי channel
  - שקילות: השמה באמצעות פעולת Set של התכונה שקולה
  - `full` **1** — התכונה chl מקבלת את ערך הפרמטר channel
  - `absent` **0** — התכונה chl אינה מקבלת את ערך הפרמטר channel, או שההשמה נעשית לתכונה שאינה מוגדרת במחלקה
- **q2.א.c0.c4** · credit · binary · origin `planner` · element `binary`
  - קביעת התכונה rate להיות אפס
  - `full` **1** — התכונה rate מקבלת את הערך אפס
  - `absent` **0** — התכונה rate אינה מקבלת את הערך אפס
- **q2.א.c0.c5** · credit · binary · origin `planner` · element `binary`
  - קביעת התכונה isOn להיות אמת
  - `full` **1** — התכונה isOn מקבלת את הערך true
  - `absent` **0** — התכונה isOn אינה מקבלת את הערך true

**Interpretation notes:**
- הפעולה הבונה נבדקה לפי ההגדרה בשאלה: כותרת ושלוש השמות לתכונות ובנוסף שם התכנית.

### q2.א.c1 · 10 נק׳ · components

**Teacher's text:** סעיף א': פעולה פנימית UpdateRate (סה"כ לפעולה 10)public TvShow (string name, int channel)

**Collapsed:** 4 checks · credit max 10 / 10

- **q2.א.c1.c1** · credit · binary · origin `planner` · element `binary`
  - כותרת הפעולה public void UpdateRate (int numViewers)
  - שקילות: שם פרמטר אחר שקול
  - `full` **2.5** — כותרת הפעולה UpdateRate אינה מחזירה ערך ומקבלת מספר שלם של צופים
  - `absent` **0** — אין כותרת לפעולה UpdateRate, או שהיא אינה מקבלת את מספר הצופים
- **q2.א.c1.c2** · credit · ladder · origin `planner` · element `non_binary`
  - מעבר על כל צופה, לפי מספר הצופים numViewers
  - שקילות: כל סוג לולאה, וספירה מאפס או מאחד, שקולים כל עוד מספר הסיבובים הוא numViewers
  - `full` **2.5** — יש לולאה שמתבצעת בדיוק numViewers פעמים, פעם עבור כל צופה
  - `p1` **2** — יש לולאה שמספר סיבוביה נקבע לפי numViewers, אך היא מתבצעת פעם אחת יותר או פחות מדי
  - `p2` **1.25** — יש לולאה שמספר סיבוביה תלוי ב-numViewers, אך תנאי העצירה שגוי כך שהיא אינה מסתיימת או רצה מספר פעמים שונה בהרבה ממספר הצופים
  - `absent` **0** — אין לולאה, או שמספר סיבובי הלולאה אינו נקבע לפי numViewers
- **q2.א.c1.c3** · credit · ladder · origin `planner` · element `non_binary`
  - קליטת הדירוג של כל צופה
  - שקילות: כל דרך קליטה של מספר שלם מהקלט שקולה; הודעה למשתמש לפני הקליטה אינה נדרשת
  - `full` **2.5** — בכל סיבוב של הלולאה נקלט מהקלט דירוג של צופה כמספר שלם
  - `p1` **1.25** — דירוג נקלט מהקלט, אך פעם אחת בלבד מחוץ ללולאה ולא עבור כל צופה
  - `absent` **0** — לא נקלט דירוג מהקלט
- **q2.א.c1.c4** · credit · ladder · origin `planner` · element `non_binary`
  - הוספת הדירוג שנקלט לדירוג הקיים rate
  - שקילות: סכימה במשתנה עזר והוספתו ל-rate בסוף הפעולה, או עדכון באמצעות פעולות Get ו-Set, שקולים
  - `full` **2.5** — כל דירוג שנקלט מתווסף לתכונה rate, והערך הקודם של rate נשמר
  - `p1` **1.25** — הדירוגים נסכמים לתכונה rate, אך rate מאופס בתחילת הפעולה ולכן הדירוג הקיים אובד
  - `p2` **0.75** — הדירוג הנקלט מושם לתכונה rate במקום להתווסף לה, כך שנשמר רק הדירוג האחרון
  - `absent` **0** — הדירוג שנקלט אינו מתווסף לתכונה rate, או שהוא נסכם רק במשתנה אחר שאינו מועבר ל-rate

**Interpretation notes:**
- כותרת הפעולה הבונה המופיעה בטקסט הקריטריון של UpdateRate נקראה כהעתקה, והפעולה נבדקה לפי הגדרת UpdateRate בשאלה.

## q2.ב — planner

### q2.ב.c0 · 2 נק׳ · components

**Teacher's text:** סעיף ב': פעולה חיצונית LowestRateChannel כותרת הפעולה

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c0.c1** · credit · ladder · origin `planner` · element `non_binary`
  - כותרת הפעולה החיצונית LowestRateChannel
  - `full` **2** — כותרת פעולה חיצונית (static) בשם LowestRateChannel שמקבלת אובייקט מטיפוס TvRate ומחזירה int
  - `p1` **1** — כותרת LowestRateChannel מקבלת אובייקט מטיפוס TvRate, אך טיפוס ההחזרה אינו int או שהפעולה אינה חיצונית (חסר static)
  - `absent` **0** — אין כותרת לפעולה LowestRateChannel, או שהיא אינה מקבלת אובייקט מטיפוס TvRate

### q2.ב.c1 · 2 נק׳ · components

**Teacher's text:** סעיף ב': בתוך LowestRateChannel : הגדרת מערך צוברים int לכל 100 הערוצים (ערוצים 1-100, המערך אמור להיות בגודל 101)

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c1.c1** · credit · ladder · origin `planner` · element `non_binary`
  - הגדרת מערך צוברים int לכל הערוצים
  - שקילות: מערך בגודל מספר הערוצים, שבו כל ערוץ נצבר באופן עקבי בתא שלפניו, שקול
  - `full` **2** — הוגדר מערך צוברים מטיפוס int שיש בו תא לכל ערוץ, כולל הערוץ הגבוה ביותר
  - `p1` **1** — הוגדר מערך צוברים מטיפוס int לערוצים, אך הוא קצר בתא אחד ואין בו תא לערוץ הגבוה ביותר
  - `absent` **0** — לא הוגדר מערך צוברים לערוצים

### q2.ב.c2 · 3 נק׳ · components

**Teacher's text:** סעיף ב': בתוך LowestRateChannel : לולאה על מערך הצוברים לאיפוס המערך

**Collapsed:** 1 checks · credit max 3 / 3

- **q2.ב.c2.c1** · credit · ladder · origin `planner` · element `non_binary`
  - לולאה על מערך הצוברים לאיפוס המערך
  - `full` **3** — לולאה עוברת על כל תאי מערך הצוברים ומציבה אפס בכל תא
  - `p1` **2.25** — לולאה מאפסת את תאי מערך הצוברים, אך גבולותיה מחמיצים תא של ערוץ או חורגים מהמערך
  - `p2` **1.5** — יש לולאה על מערך הצוברים, אך היא אינה מציבה אפס בתאיו
  - `absent` **0** — אין לולאה שמאפסת את מערך הצוברים

### q2.ב.c3.s0 · 3 נק׳ · components

**Teacher's text:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם התחילו מ-1 במקום מ-0 להוריד 0.5 אם ניגשו למערך TvShows בלי Getter להוריד 1 אם טעו בגבול העליון של הלולאה להוריד 0.5

**Collapsed:** 4 checks · credit max 3 / 3

- **q2.ב.c3.s0.c1** · credit · binary · origin `planner` · element `binary`
  - הגדרת לולאה על מערך התוכניות
  - שקילות: לולאה שעוצרת בתא הריק הראשון של מערך התוכניות שקולה, שכן המערך מלא עד המקום הפנוי הראשון
  - `full` **3** — יש לולאה שעוברת על תאי מערך התוכניות של אובייקט ה-TvRate
  - `absent` **0** — אין לולאה על מערך התוכניות
- **q2.ב.c3.s0.f1** · fault · fault · origin `planner` · requires `q2.ב.c3.s0.c1`
  - הלולאה על מערך התוכניות התחילה מ-1 במקום מ-0
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — הלולאה על מערך התוכניות מתחילה מהתא השני ומדלגת על התא הראשון ← `q2.ב.c3.s0.m1`
- **q2.ב.c3.s0.f2** · fault · fault · origin `planner` · requires `q2.ב.c3.s0.c1`
  - גישה למערך התוכניות בלי Getter
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — מערך התוכניות נלקח בגישה ישירה לתכונה arrShows של TvRate ולא באמצעות פעולת Get ← `q2.ב.c3.s0.m2`
- **q2.ב.c3.s0.f3** · fault · fault · origin `planner` · requires `q2.ב.c3.s0.c1`
  - טעות בגבול העליון של הלולאה על מערך התוכניות
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — הגבול העליון של הלולאה על מערך התוכניות שגוי: אינו קטן ממש מאורך המערך ← `q2.ב.c3.s0.m3`

### q2.ב.c3.s1 · 2 נק׳ · components

**Teacher's text:** בתוך הלולאה על TvShows: בדיקה אם התא אינו null

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c3.s1.c1** · credit · binary · origin `planner` · element `binary`
  - בדיקה אם התא אינו null
  - שקילות: בדיקת null בתנאי הלולאה עצמה, שעוצרת בתא הריק הראשון, שקולה
  - `full` **2** — בתוך הלולאה נבדק שהתא הנוכחי במערך התוכניות אינו null לפני השימוש בו
  - `absent` **0** — אין בדיקה שהתא במערך התוכניות אינו null

### q2.ב.c3.s2 · 2 נק׳ · components

**Teacher's text:** בתוך הלולאה על TvShows: אם התא אינו null , גישה לערוץ GetChl (ולא ע"י גישה ישירה לתכונה)אם ניגשו ישירות לתכונה chl להוריד 1

**Collapsed:** 2 checks · credit max 2 / 2

- **q2.ב.c3.s2.c1** · credit · binary · origin `planner` · element `binary`
  - גישה לערוץ של התוכנית שבתא
  - `full` **2** — נקרא מספר הערוץ של התוכנית שבתא הנוכחי
  - `absent` **0** — מספר הערוץ של התוכנית שבתא אינו נקרא
- **q2.ב.c3.s2.f1** · fault · fault · origin `planner` · requires `q2.ב.c3.s2.c1`
  - גישה ישירה לתכונה chl
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — מספר הערוץ נקרא בגישה ישירה לתכונה chl ולא באמצעות GetChl ← `q2.ב.c3.s2.m1`

### q2.ב.c3.s3 · 5 נק׳ · components

**Teacher's text:** בתוך הלולאה על TvShows: אם התא אינו null , צבירה של הדירוג של הערוץ (GetChl) לתוך מערך הצוברים במקום של הערוץ הזהאם ניגשו ישירות לתכונה rate במקום GetRate להוריד 1

**Collapsed:** 3 checks · credit max 5 / 5

- **q2.ב.c3.s3.c1** · credit · binary · origin `planner` · element `binary`
  - צבירה של הדירוג של התוכנית
  - `full` **2.5** — הדירוג של התוכנית שבתא מתווסף לתא במערך הצוברים (צבירה ולא השמה)
  - `absent` **0** — הדירוג של התוכנית אינו נצבר במערך הצוברים, או שהוא מושם בתא במקום להתווסף אליו
- **q2.ב.c3.s3.c2** · credit · binary · origin `planner` · element `binary`
  - הצבירה לתוך מערך הצוברים במקום של הערוץ של התוכנית
  - `full` **2.5** — התא במערך הצוברים שאליו נצבר הדירוג הוא התא של ערוץ התוכנית
  - `absent` **0** — הדירוג נצבר לתא שאינו התא של ערוץ התוכנית (למשל לפי אינדקס הלולאה)
- **q2.ב.c3.s3.f1** · fault · fault · origin `planner` · requires `q2.ב.c3.s3.c1`
  - גישה ישירה לתכונה rate במקום GetRate
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הדירוג נקרא בגישה ישירה לתכונה rate ולא באמצעות GetRate ← `q2.ב.c3.s3.m1`

### q2.ב.c4.s0 · 1 נק׳ · components · fixed

**Teacher's text:** הגדרת מינימום דירוג + אתחול

**Collapsed:** 2 checks · credit max 1 / 1

- **q2.ב.c4.s0.c1** · credit · binary · origin `planner` · element `binary`
  - הגדרת מינימום דירוג
  - `full` **0.5** — הוגדר משתנה לדירוג המינימלי
  - `absent` **0** — לא הוגדר משתנה לדירוג המינימלי
- **q2.ב.c4.s0.c2** · credit · binary · origin `planner` · element `binary`
  - אתחול מינימום הדירוג
  - שקילות: אתחול לדירוג של ערוץ קיים מתוך מערך הצוברים שקול
  - `full` **0.5** — משתנה הדירוג המינימלי אותחל לפני הלולאה לערך שכל דירוג ערוץ קטן ממנו (כגון int.MaxValue)
  - `absent` **0** — משתנה הדירוג המינימלי לא אותחל, או אותחל לערך שאינו מאפשר למצוא את המינימום

### q2.ב.c4.s1 · 1 נק׳ · components · fixed

**Teacher's text:** הגדרת ערוץ מינימלי +אתחול

**Collapsed:** 2 checks · credit max 1 / 1

- **q2.ב.c4.s1.c1** · credit · binary · origin `planner` · element `binary`
  - הגדרת ערוץ מינימלי
  - `full` **0.5** — הוגדר משתנה לערוץ המינימלי
  - `absent` **0** — לא הוגדר משתנה לערוץ המינימלי
- **q2.ב.c4.s1.c2** · credit · binary · origin `planner` · element `binary`
  - אתחול הערוץ המינימלי
  - `full` **0.5** — משתנה הערוץ המינימלי אותחל לפני הלולאה
  - `absent` **0** — משתנה הערוץ המינימלי לא אותחל

**Interpretation notes:**
- כל ערך התחלתי לערוץ המינימלי מתקבל, שכן הוא מוחלף בלולאה.

### q2.ב.c4.s2 · 2 נק׳ · components

**Teacher's text:** הגדרת לולאה על מערך צוברים מ-1 עד 100

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c4.s2.c1** · credit · ladder · origin `planner` · element `non_binary`
  - הגדרת לולאה על מערך צוברים על כל הערוצים
  - שקילות: ריצה עד קטן ממש מאורך מערך הצוברים שקולה
  - `full` **2** — לולאה עוברת על תאי מערך הצוברים מהערוץ הראשון ועד הערוץ הגבוה ביותר כולל
  - `p1` **1** — יש לולאה על מערך הצוברים, אך היא מחמיצה את התא של הערוץ הגבוה ביותר או חורגת מגבולות המערך
  - `absent` **0** — אין לולאה על מערך הצוברים

### q2.ב.c4.s3 · 3 נק׳ · components

**Teacher's text:** בתוך הלולאה על מערך הצוברים: בדיקה האם התא מתאים לערוץ הנוכחי של TvShow בתוך מערך הצוברים גדול מאפס (כלומר יש שימוש בערוץ זה) - לא להוריד, לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום - סה"כ 2 נקודות

**Collapsed:** 3 checks · credit max 3 / 3

- **q2.ב.c4.s3.c1** · credit · binary · origin `planner` · element `binary`
  - בדיקה האם סה"כ הדירוגים של הערוץ קטן מהמינימום
  - `full` **3** — בתוך הלולאה על מערך הצוברים, התא של הערוץ הנוכחי מושווה למשתנה הדירוג המינימלי ונבחר כשהוא קטן ממנו
  - `absent` **0** — אין השוואה בין התא של הערוץ במערך הצוברים לבין משתנה הדירוג המינימלי
- **q2.ב.c4.s3.f1** · fault · fault · origin `planner` · requires `q2.ב.c4.s3.c1` · group `q2.ב:q2.ב.c4:d1`
  - חיפוש המקסימום במקום המינימום, כשהלוגיקה בסדר
  - `none` **0** — ללא הטעות הזו
  - `f1` **-3** — החיפוש מוצא את הערוץ בעל הדירוג הגבוה ביותר במקום הנמוך ביותר, אך הלוגיקה שלו תקינה ← `q2.ב.c4.s3.m1`
- **q2.ב.c4.s3.n1** · note · note · origin `compiler`
  - לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום
  - `none` **0** — לא רלוונטי
  - `observed` **0** — לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום

**Interpretation notes:**
- היעדר הבדיקה שהתא גדול מאפס אינו מוריד נקודות, ונרשמת עליו הערה בלבד.
- חיפוש מקסימום בלוגיקה תקינה מזכה ברכיבי החיפוש עצמם, וההורדה עליו נעשית פעם אחת בלבד.

### q2.ב.c4.s4 · 1 נק׳ · components

**Teacher's text:** בתוך התנאי (בתוך הלולאה) - החלפה של מינימום דירוג

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c4.s4.c1** · credit · binary · origin `planner` · element `binary`
  - החלפה של מינימום דירוג
  - `full` **1** — בתוך התנאי, משתנה הדירוג המינימלי מקבל את ערך התא של הערוץ הנוכחי
  - `absent` **0** — משתנה הדירוג המינימלי אינו מוחלף בתוך התנאי

### q2.ב.c4.s5 · 1 נק׳ · components

**Teacher's text:** בתוך התנאי (בתוך הלולאה) - החלפת הערוץ המינימלי

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c4.s5.c1** · credit · binary · origin `planner` · element `binary`
  - החלפת הערוץ המינימלי
  - `full` **1** — בתוך התנאי, משתנה הערוץ המינימלי מקבל את מספר הערוץ הנוכחי (אינדקס הלולאה)
  - `absent` **0** — משתנה הערוץ המינימלי אינו מוחלף בתוך התנאי, או מקבל ערך שאינו מספר הערוץ

### q2.ב.c5 · 1 נק׳ · components

**Teacher's text:** סעיף ב': בתוך LowestRateChannel : החזרת הערוץ המינימלי

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c5.c1** · credit · binary · origin `planner` · element `binary`
  - החזרת הערוץ המינימלי
  - `full` **1** — הפעולה מחזירה את משתנה הערוץ המינימלי
  - `absent` **0** — הפעולה אינה מחזירה את הערוץ המינימלי

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

- **q2.ג.c0.s0.c1** · credit · ladder · origin `planner` · element `non_binary`
  - כותרת הפעולה PrintLowRatingChannel
  - שקילות: כל שם לפרמטר מטיפוס TvRate תקף
  - `full` **2** — כותרת הפעולה PrintLowRatingChannel היא פעולה חיצונית (static) שאינה מחזירה ערך (void) ומקבלת פרמטר אחד מטיפוס TvRate
  - `p1` **1** — כותרת הפעולה PrintLowRatingChannel קיימת, אך הפרמטר אינו מטיפוס TvRate, או שטיפוס ההחזרה אינו void
  - `absent` **0** — אין כותרת לפעולה PrintLowRatingChannel

### q2.ג.c0.s1 · 3 נק׳ · components

**Teacher's text:** מציאת הערוץ בעל דירוג מינימלי ע"י זימון LowestRateChannel

**Collapsed:** 1 checks · credit max 3 / 3

- **q2.ג.c0.s1.c1** · credit · ladder · origin `planner` · element `non_binary`
  - מציאת הערוץ בעל דירוג מינימלי ע"י זימון LowestRateChannel
  - שקילות: זימון LowestRateChannel ישירות בתוך תנאי ההשוואה, במקום שמירת התוצאה במשתנה, שקול
  - `full` **3** — הפעולה LowestRateChannel מזומנת עם אובייקט ה-TvRate שהתקבל, והערוץ בעל הדירוג המינימלי שהיא מחזירה נשמר או משמש בהמשך
  - `p1` **1.5** — הערוץ בעל הדירוג המינימלי נמצא בקוד שנכתב בתוך הפעולה, ללא זימון LowestRateChannel
  - `absent` **0** — הערוץ בעל הדירוג המינימלי אינו נמצא כלל, לא בזימון LowestRateChannel ולא בדרך אחרת

**Interpretation notes:**
- השאלה קובעת שאי שימוש בפעולות המתאימות יגרור הורדת ניקוד, ולכן מציאת הערוץ המינימלי בקוד עצמאי מזכה בחלק מהניקוד ולא נפסלת לגמרי.

### q2.ג.c0.s2 · 3 נק׳ · components

**Teacher's text:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם הגישה למערך בלי getter להוריד 1

**Collapsed:** 2 checks · credit max 3 / 3

- **q2.ג.c0.s2.c1** · credit · ladder · origin `planner` · element `non_binary`
  - הגדרת לולאה על מערך התוכניות מתחילתו ועד קטן ממש מ-length של המערך
  - שקילות: לולאת foreach על מערך התוכניות, או לולאה שנעצרת גם בתא הריק הראשון בתוספת גבול length, שקולה
  - `full` **3** — מוגדרת לולאה העוברת על מערך התוכניות arrShows מהאיבר הראשון ועד קטן ממש מ-length של המערך
  - `p1` **1.5** — מוגדרת לולאה על מערך התוכניות arrShows, אך גבולותיה שגויים (למשל עד length וכולל, או שאינה מתחילה מהאיבר הראשון)
  - `absent` **0** — אין לולאה על מערך התוכניות arrShows, או שהלולאה עוברת על אוסף אחר
- **q2.ג.c0.s2.f1** · fault · fault · origin `planner` · requires `q2.ג.c0.s2.c1`
  - גישה למערך בלי getter
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הגישה למערך התוכניות נעשית ישירות לתכונה arrShows ולא באמצעות GetArrShows ← `q2.ג.c0.s2.m1`

**Interpretation notes:**
- הגישה למערך דרך GetArrShows או ישירות נבדקת בנפרד מהגדרת הלולאה.

### q2.ג.c0.s3 · 8 נק׳ · components · fixed

**Teacher's text:** בתוך הלולאה על TvShows: בדיקה האם תוכנית מתאימה להדפסה:אינה null ב (2 נקודות) וגם הערוץ שלה תואם את הערוץ המינימלי (ע"י GetChl והשוואתם (2 נקודות) וגם היא באוויר (ע"י GetIsOn ב 2 נקודות) הדפסה של השם של התוכנית (ע"י GetName ב( 2 נקודות)

**Collapsed:** 4 checks · credit max 8 / 8

- **q2.ג.c0.s3.c1** · credit · binary · origin `planner` · element `binary`
  - בדיקה האם התוכנית אינה null
  - שקילות: בדיקת null בתנאי הלולאה עצמה, שעוצרת בתא הריק הראשון, שקולה
  - `full` **2** — בתוך הלולאה נבדק שהתוכנית במערך אינה null לפני השימוש בה
  - `absent` **0** — אין בדיקה שהתוכנית במערך אינה null
- **q2.ג.c0.s3.c2** · credit · binary · origin `planner` · element `binary`
  - הערוץ של התוכנית תואם את הערוץ המינימלי, ע"י GetChl והשוואתם
  - `full` **2** — הערוץ של התוכנית נקרא ב-GetChl ומושווה לערוץ בעל הדירוג המינימלי
  - `absent` **0** — אין השוואה של ערוץ התוכנית ב-GetChl לערוץ בעל הדירוג המינימלי
- **q2.ג.c0.s3.c3** · credit · binary · origin `planner` · element `binary`
  - התוכנית באוויר, ע"י GetIsOn
  - שקילות: השוואה מפורשת של GetIsOn ל-true שקולה
  - `full` **2** — נבדק ב-GetIsOn שהתוכנית משודרת כעת
  - `absent` **0** — אין בדיקה ב-GetIsOn שהתוכנית משודרת כעת
- **q2.ג.c0.s3.c4** · credit · binary · origin `planner` · element `binary`
  - הדפסה של שם התוכנית ע"י GetName
  - `full` **2** — שם התוכנית העומדת בתנאים מודפס באמצעות GetName
  - `absent` **0** — שם התוכנית אינו מודפס באמצעות GetName

**Markers and dispositions:**

- `q2.ג.c0.s2.m1` −1 · candidates ['q2.ג.c0.s2'] · fault · «אם הגישה למערך בלי getter להוריד 1»

