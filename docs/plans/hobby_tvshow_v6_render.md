# hobby_tvshow — plan/v6 render

- plan_hash `dab9cd6ed46801f2…` · config_hash `bdfd12d8a8dc7d55…` · pack `computer_science@v1`
- stage 1 `plan-compiler/v2.0+stage1-v6.0` · 38 criteria · 82 checks
- scope origins: q1.א=planner, q1.ב=repaired, q1.ג=planner, q2.א=repaired, q2.ב=planner, q2.ג=repaired

## q1.א — planner

### q1.א.c0 · 4 נק׳ · components

**Teacher's text:** סעיף א: כותרת ותכונות המחלקה Hobby

**Collapsed:** 4 checks · credit max 4 / 4

- **q1.א.c0.c1** · credit · binary · origin `planner`
  - הגדרת המחלקה Hobby
  - `full` **1** — הוגדרה מחלקה בשם Hobby
  - `absent` **0** — לא הוגדרה מחלקה בשם Hobby
- **q1.א.c0.c2** · credit · binary · origin `planner`
  - תכונת hobbyName מטיפוס מחרוזת
  - שקילות: שם התכונה בקוד יכול להיות כלשהו, ובלבד שטיפוסה מחרוזת והיא מייצגת את שם התחביב
  - `full` **1** — הוגדרה תכונה מטיפוס מחרוזת המייצגת את שם התחביב
  - `absent` **0** — לא הוגדרה תכונה מטיפוס מחרוזת המייצגת את שם התחביב
- **q1.א.c0.c3** · credit · binary · origin `planner`
  - תכונת isSportive מטיפוס בוליאני
  - שקילות: שם התכונה בקוד יכול להיות כלשהו, ובלבד שטיפוסה בוליאני והיא מייצגת אם התחביב דורש פעילות ספורטיבית
  - `full` **1** — הוגדרה תכונה מטיפוס בוליאני המייצגת אם התחביב דורש פעילות ספורטיבית
  - `absent` **0** — לא הוגדרה תכונה מטיפוס בוליאני המייצגת אם התחביב דורש פעילות ספורטיבית
- **q1.א.c0.c4** · credit · binary · origin `planner`
  - תכונת minutes מטיפוס מספר שלם
  - שקילות: שם התכונה בקוד יכול להיות כלשהו (למשל durationInMinutes), ובלבד שטיפוסה מספר שלם והיא מייצגת את משך הפעילות בדקות
  - `full` **1** — הוגדרה תכונה מטיפוס מספר שלם המייצגת את זמן פעילות התחביב בדקות
  - `absent` **0** — לא הוגדרה תכונה מטיפוס מספר שלם המייצגת את זמן פעילות התחביב בדקות

**Interpretation notes:**
- בדיקת הטווח 1 עד 60 עבור minutes אינה נדרשת בהגדרת התכונה עצמה, אלא נבדקת (אם בכלל) בפעולה הבונה.

### q1.א.c1 · 4 נק׳ · components

**Teacher's text:** סעיף א: פעולה בונה Hobby(string hobbyName, bool isSportive, int minutes)

**Collapsed:** 4 checks · credit max 4 / 4

- **q1.א.c1.c1** · credit · binary · origin `planner`
  - הגדרת פעולה בונה בשם Hobby עם הפרמטרים hobbyName, isSportive ו-minutes בטיפוסים הנכונים
  - `full` **1** — הוגדרה פעולה בונה בשם Hobby המקבלת את שלושת הפרמטרים בטיפוסים הנכונים
  - `absent` **0** — לא הוגדרה פעולה בונה בשם Hobby עם שלושת הפרמטרים הנדרשים
- **q1.א.c1.c2** · credit · binary · origin `planner`
  - קביעת ערך תכונת hobbyName לפי הפרמטר המתקבל
  - `full` **1** — ערך הפרמטר hobbyName הוצב בתכונה המייצגת את שם התחביב
  - `absent` **0** — ערך הפרמטר hobbyName לא הוצב בתכונה המייצגת את שם התחביב
- **q1.א.c1.c3** · credit · binary · origin `planner`
  - קביעת ערך תכונת isSportive לפי הפרמטר המתקבל
  - `full` **1** — ערך הפרמטר isSportive הוצב בתכונה המייצגת אם התחביב ספורטיבי
  - `absent` **0** — ערך הפרמטר isSportive לא הוצב בתכונה המייצגת אם התחביב ספורטיבי
- **q1.א.c1.c4** · credit · binary · origin `planner`
  - קביעת ערך תכונת minutes לפי הפרמטר המתקבל
  - שקילות: בהתאם להנחיה שהפרמטרים תקינים, אין צורך בבדיקת טווח הערך (1 עד 60); הצבה עם או בלי בדיקת טווח מתקבלת במלואה
  - `full` **1** — ערך הפרמטר minutes הוצב בתכונה המייצגת את משך הפעילות בדקות
  - `absent` **0** — ערך הפרמטר minutes לא הוצב בתכונה המייצגת את משך הפעילות בדקות

**Interpretation notes:**
- בהתאם להנחיה שהפרמטרים תקינים, אין צורך בבדיקת טווח הערכים בפעולה הבונה.

## q1.ב — repaired

> validator messages that sent this scope to repair/fallback:
> - V20: q1.ב.c0 component 1 span differs from the compiled one
> - V20: q1.ב.c3 component 1 span differs from the compiled one
> - V20: q1.ב.c3 component 2 span differs from the compiled one
> - V20: q1.ב.c3 component 3 span differs from the compiled one
> - V20: q1.ב.c6 component 1 span differs from the compiled one
> - V20: q1.ב.c6 component 2 span differs from the compiled one

### q1.ב.c0 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב: פעולה פנימית בשם PopulateHobbies (סה"כ 16)כותרת הפעולה + טיפוס מוחזר bool

**Collapsed:** 2 checks · credit max 2 / 2

- **q1.ב.c0.c1** · credit · binary · origin `planner`
  - כתיבת כותרת הפעולה הפנימית בשם PopulateHobbies
  - `full` **1** — הפעולה מוגדרת ככותרת פנימית (private) בשם PopulateHobbies
  - `absent` **0** — הפעולה אינה מוגדרת ככותרת פנימית בשם PopulateHobbies
- **q1.ב.c0.c2** · credit · binary · origin `planner`
  - טיפוס ההחזרה של הפעולה
  - `full` **1** — הפעולה מוגדרת עם טיפוס החזרה bool
  - `absent` **0** — הפעולה אינה מחזירה טיפוס bool

### q1.ב.c1 · 1 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: לפני הלולאה - לבדוק אם המערך מלא, להחזיר false

**Collapsed:** 1 checks · credit max 1 / 1

- **q1.ב.c1.c1** · credit · ladder · origin `planner`
  - בדיקה לפני הלולאה האם המערך מלא והחזרת false בהתאם
  - `full` **1** — לפני הלולאה נבדק אם המערך מלא, ואם כן מוחזר false
  - `p1` **0.5** — קיימת בדיקה האם המערך מלא לפני הלולאה, אך לא מוחזר false בעקבותיה
  - `absent` **0** — אין בדיקה לפני הלולאה אם המערך מלא ואין החזרת false בהתאם

### q1.ב.c2 · 3 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: לולאה עד שאין מקום במערך (כל עוד countHobbies קטן מ-length) או כל עוד המשתמש יענה Y או y לשאלה

**Collapsed:** 2 checks · credit max 3 / 3

- **q1.ב.c2.c1** · credit · binary · origin `planner`
  - תנאי המשך הלולאה כל עוד יש מקום פנוי במערך
  - `full` **1.5** — הלולאה ממשיכה כל עוד countHobbies קטן ממספר האיברים במערך
  - `absent` **0** — הלולאה אינה בודקת אם יש מקום פנוי במערך
- **q1.ב.c2.c2** · credit · binary · origin `planner`
  - תנאי המשך הלולאה בהתאם לתשובת המשתמש
  - `full` **1.5** — הלולאה ממשיכה כל עוד המשתמש לא השיב N או n
  - `absent` **0** — הלולאה אינה בודקת את תשובת המשתמש כתנאי להמשך

**Interpretation notes:**
- תנאי הלולאה פוצל לשני רכיבים בלתי תלויים: מקום פנוי במערך ותשובת המשתמש, שכן ניתן לממש כל אחד מהם בנפרד.

### q1.ב.c3 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קליטה של 3 נתוני התחביב (name, isSportive, minutes)

**Collapsed:** 3 checks · credit max 3 / 3

- **q1.ב.c3.c1** · credit · binary · origin `planner`
  - קליטת שם התחביב (hobbyName) מהמשתמש
  - `full` **1** — נקלט שם התחביב מהמשתמש
  - `absent` **0** — לא נקלט שם התחביב מהמשתמש
- **q1.ב.c3.c2** · credit · binary · origin `planner`
  - קליטת האם התחביב ספורטיבי (isSportive) מהמשתמש
  - `full` **1** — נקלט מהמשתמש האם התחביב ספורטיבי
  - `absent` **0** — לא נקלט מהמשתמש האם התחביב ספורטיבי
- **q1.ב.c3.c3** · credit · binary · origin `planner`
  - קליטת משך הזמן בדקות (minutes) מהמשתמש
  - `full` **1** — נקלט מהמשתמש משך הזמן בדקות
  - `absent` **0** — לא נקלט מהמשתמש משך הזמן בדקות

### q1.ב.c4 · 3 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה יצירה של עצם חדש מטיפוס Hobby בתא המתאים במערך (hobbies[countHobbies])

**Collapsed:** 2 checks · credit max 3 / 3

- **q1.ב.c4.c1** · credit · binary · origin `planner`
  - יצירת עצם חדש מטיפוס Hobby מהנתונים שנקלטו
  - `full` **1.5** — נוצר אובייקט חדש מטיפוס Hobby עם שלושת הנתונים שנקלטו
  - `absent` **0** — לא נוצר אובייקט חדש מטיפוס Hobby
- **q1.ב.c4.c2** · credit · binary · origin `planner`
  - שמירת העצם החדש בתא הפנוי הראשון במערך
  - `full` **1.5** — האובייקט נשמר בתא hobbies[countHobbies], התא הפנוי הראשון במערך
  - `absent` **0** — האובייקט אינו נשמר בתא הנכון (hobbies[countHobbies])

**Interpretation notes:**
- יצירת האובייקט ושיבוצו בתא הנכון פוצלו לשני רכיבים בלתי תלויים, שכן ניתן ליצור אובייקט תקין ולשבצו בתא שגוי או להפך.

### q1.ב.c5 · 1 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קידום countHobbies

**Collapsed:** 1 checks · credit max 1 / 1

- **q1.ב.c5.c1** · credit · binary · origin `planner`
  - קידום countHobbies לאחר הוספת תחביב
  - `full` **1** — countHobbies מקודם לאחר הוספת התחביב לתא במערך
  - `absent` **0** — countHobbies אינו מקודם לאחר הוספת התחביב

### q1.ב.c6 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב בתוך PopulateHobbies: בדיקה אם עדיין יש מקום ושאלה למשתמש האם להמשיך + קליטת תשובהאם הציגו את ההודעה בלי לבדוק האם יש עדיין מקום להוריד 1

**Collapsed:** 2 checks · credit max 2 / 2

- **q1.ב.c6.c1** · credit · binary · origin `planner`
  - בדיקה אם נותר מקום פנוי במערך ושאלת המשתמש האם להמשיך
  - `full` **1** — מתבצעת בדיקה אם נותר מקום פנוי במערך, ובהתאם נשאלת השאלה למשתמש האם להמשיך
  - `absent` **0** — לא מתבצעת בדיקה אם נותר מקום פנוי לפני שנשאלת השאלה להמשך
- **q1.ב.c6.c2** · credit · binary · origin `planner`
  - קליטת תשובת המשתמש (Y/N) כתו בודד
  - `full` **1** — תשובת המשתמש נקלטת כתו בודד
  - `absent` **0** — תשובת המשתמש אינה נקלטת

**Interpretation notes:**
- ההערה בטקסט המתייחסת להצגת ההודעה ללא בדיקת מקום פנוי מתייחסת לדרישה המתוארת ברכיב הבדיקה, ואינה בדיקה נפרדת.

### q1.ב.c7 · 1 נק׳ · components

**Teacher's text:** סעיף ב בתוך PopulateHobbies: מחוץ ללולאה - להחזיר ערך true

**Collapsed:** 1 checks · credit max 1 / 1

- **q1.ב.c7.c1** · credit · binary · origin `planner`
  - החזרת ערך true מחוץ ללולאה
  - `full` **1** — מחוץ ללולאה מוחזר ערך true
  - `absent` **0** — מחוץ ללולאה לא מוחזר ערך true

## q1.ג — planner

### q1.ג.c0 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ג': פעולה פנימית בשם PrintAverages (סה"כ 16)כותרת הפעולה + void

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ג.c0.c1** · credit · binary · origin `planner`
  - כותרת הפעולה הפנימית PrintAverages
  - `full` **0.5** — נכתבה כותרת לפעולה בשם PrintAverages כפעולה פנימית במחלקת SchoolHobbies
  - `absent` **0** — לא נכתבה כותרת מתאימה לפעולה פנימית בשם PrintAverages
- **q1.ג.c0.c2** · credit · binary · origin `planner`
  - טיפוס ההחזרה void
  - `full` **0.5** — טיפוס ההחזרה של הפעולה הוא void
  - `absent` **0** — טיפוס ההחזרה של הפעולה אינו void

### q1.ג.c1 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : יצירת 2 מונה לכמות החוגים בספורטיבים והלא ספורטיבים + אתחולם ב-0 (0.5 כ"א)

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ג.c1.c1** · credit · binary · origin `planner`
  - יצירת שני מוני תחביבים
  - `full` **0.5** — נוצרו שני משתני מונה: אחד לכמות התחביבים הספורטיביים ואחד לכמות התחביבים הלא ספורטיביים
  - `absent` **0** — לא נוצרו שני משתני מונה נפרדים לתחביבים הספורטיביים והלא ספורטיביים
- **q1.ג.c1.c2** · credit · binary · origin `planner`
  - אתחול המונים ב-0
  - `full` **0.5** — שני המונים אותחלו לערך 0
  - `absent` **0** — המונים לא אותחלו ל-0

### q1.ג.c2 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : יצירת 2 צוברים לדקות של החוגים הספורטיבים והלא ספורטיבים + אתחולם ב-0 (0.5 כ"א)

**Collapsed:** 2 checks · credit max 1 / 1

- **q1.ג.c2.c1** · credit · binary · origin `planner`
  - יצירת שני צוברי דקות
  - `full` **0.5** — נוצרו שני משתני צובר לסכימת הדקות: אחד לתחביבים הספורטיביים ואחד לתחביבים הלא ספורטיביים
  - `absent` **0** — לא נוצרו שני משתני צובר נפרדים לסכימת הדקות
- **q1.ג.c2.c2** · credit · binary · origin `planner`
  - אתחול הצוברים ב-0
  - `full` **0.5** — שני הצוברים אותחלו לערך 0
  - `absent` **0** — הצוברים לא אותחלו ל-0

### q1.ג.c3 · 3 נק׳ · components

**Teacher's text:** סעיף ג' בתוך PrintAverages : לולאה על מערך התחביבים מ-0 עד countHobbiesאו לולאה על מערך התחביבים עד hobbies.length ובדיקה בתוך הלולאה אם hobbies[i]!=nullאם עשו לולאה עד length ולא בדקו בפנים שהתא שונה מ-null להוריד 1

**Collapsed:** 2 checks · credit max 3 / 3

- **q1.ג.c3.c1** · credit · binary · origin `planner`
  - לולאה על מערך התחביבים בטווח התקף
  - שקילות: לולאה עד countHobbies ולולאה עד hobbies.length עם בדיקת null שקולות זו לזו
  - `full` **3** — בוצעה לולאה המבקרת רק בתאים תקפים במערך התחביבים: מ-0 עד countHobbies, או לחלופין עד hobbies.length תוך בדיקה בתוך הלולאה שהתא שונה מ-null
  - `absent` **0** — לא בוצעה לולאה תקינה על מערך התחביבים בטווח המתאים
- **q1.ג.c3.f1** · fault · fault · origin `planner` · requires `q1.ג.c3.c1`
  - לולאה שנעה עד hobbies.length ללא בדיקת null בתוך הלולאה
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — בוצעה לולאה עד hobbies.length ללא בדיקה בתוך הלולאה שהתא שונה מ-null ← `q1.ג.c3.m1`

### q1.ג.c4 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, בדיקת האם החוג הנוכחי ספורטיבי (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1 כ"א)

**Collapsed:** 3 checks · credit max 3 / 3

- **q1.ג.c4.c1** · credit · binary · origin `planner`
  - בדיקה האם החוג הנוכחי ספורטיבי
  - `full` **1** — בתוך הלולאה נבדק האם התחביב הנוכחי ספורטיבי
  - `absent` **0** — לא נבדק בתוך הלולאה האם התחביב הנוכחי ספורטיבי
- **q1.ג.c4.c2** · credit · binary · origin `planner`
  - צבירת הדקות של תחביב ספורטיבי
  - `full` **1** — כאשר התחביב ספורטיבי, דקות הפעילות שלו נצברו לצובר המתאים
  - `absent` **0** — דקות התחביב הספורטיבי לא נצברו
- **q1.ג.c4.c3** · credit · binary · origin `planner`
  - קידום מונה התחביבים הספורטיביים
  - `full` **1** — כאשר התחביב ספורטיבי, מונה התחביבים הספורטיביים קודם
  - `absent` **0** — מונה התחביבים הספורטיביים לא קודם

### q1.ג.c5 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, אם החוג הנוכחי לא ספורטיבי (else) (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1)

**Collapsed:** 3 checks · credit max 3 / 3

- **q1.ג.c5.c1** · credit · binary · origin `planner`
  - טיפול בענף else עבור תחביב לא ספורטיבי
  - `full` **1** — כאשר התחביב אינו ספורטיבי, מתבצע טיפול בענף else
  - `absent` **0** — לא קיים טיפול (else) עבור תחביב שאינו ספורטיבי
- **q1.ג.c5.c2** · credit · binary · origin `planner`
  - צבירת הדקות של תחביב לא ספורטיבי
  - `full` **1** — דקות התחביב הלא ספורטיבי נצברו לצובר המתאים
  - `absent` **0** — דקות התחביב הלא ספורטיבי לא נצברו
- **q1.ג.c5.c3** · credit · binary · origin `planner`
  - קידום מונה התחביבים הלא ספורטיביים
  - `full` **1** — מונה התחביבים הלא ספורטיביים קודם
  - `absent` **0** — מונה התחביבים הלא ספורטיביים לא קודם

### q1.ג.c6 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : מחוץ ללולאה, בדיקה האם המונה של התחביבים הספורטיבים שונה מאפס (1) אם לא מנעו חלוקה באפס להוריד 1חישוב הממוצע והדפסה (1) (אם טעו בחישוב מתמטי להוריד 0.5)אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)

**Collapsed:** 4 checks · credit max 2 / 2

- **q1.ג.c6.c1** · credit · binary · origin `planner`
  - בדיקה האם מונה התחביבים הספורטיביים שונה מאפס
  - `full` **1** — בוצעה בדיקה האם מונה התחביבים הספורטיביים שונה מאפס
  - `absent` **0** — לא בוצעה בדיקה האם מונה התחביבים הספורטיביים שונה מאפס
- **q1.ג.c6.c2** · credit · binary · origin `planner`
  - מניעת חלוקה באפס וחישוב והדפסת הממוצע הספורטיבי
  - `full` **1** — כאשר המונה שונה מאפס, מחושב ומודפס ממוצע הדקות של התחביבים הספורטיביים; כאשר המונה אפס, לא מתבצעת חלוקה בו
  - `absent` **0** — מתבצעת חלוקה במונה גם כשהוא אפס, או שהממוצע הספורטיבי אינו מחושב או אינו מודפס
- **q1.ג.c6.f1** · fault · fault · origin `planner` · requires `q1.ג.c6.c2`
  - טעות בחישוב המתמטי של ממוצע התחביבים הספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — נפלה טעות בחישוב המתמטי של ממוצע התחביבים הספורטיביים ← `q1.ג.c6.m1`
- **q1.ג.c6.f2** · fault · fault · origin `planner` · requires `q1.ג.c6.c2` · group `q1.ג:once:c2ce2a97`
  - אי המרה לממשי בחישוב ממוצע התחביבים הספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — חישוב ממוצע התחביבים הספורטיביים בוצע כחלוקת שלמים ללא המרה לממשי ← `q1.ג.c6.m2`

**Interpretation notes:**
- ההנחיה 'רק פעם אחת' לגבי אי-המרה לממשי פורשה כחלה בתוך סעיף זה בלבד, בהתאם לעוגן הנפרד לכל ממוצע.

### q1.ג.c7 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ג' בתוך PrintAverages : מחוץ ללולאה,בדיקה האם המונה של התחביבים הלא-הספורטיבים שונה מאפס (1)אם לא מנעו חלוקה באפס להוריד 1חישוב הממוצע והדפסה (1) (אם טעו בחישוב מתמטי להוריד 0.5)אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)

**Collapsed:** 4 checks · credit max 2 / 2

- **q1.ג.c7.c1** · credit · binary · origin `planner`
  - בדיקה האם מונה התחביבים הלא-ספורטיביים שונה מאפס
  - `full` **1** — בוצעה בדיקה האם מונה התחביבים הלא-ספורטיביים שונה מאפס
  - `absent` **0** — לא בוצעה בדיקה האם מונה התחביבים הלא-ספורטיביים שונה מאפס
- **q1.ג.c7.c2** · credit · binary · origin `planner`
  - מניעת חלוקה באפס וחישוב והדפסת הממוצע הלא-ספורטיבי
  - `full` **1** — כאשר המונה שונה מאפס, מחושב ומודפס ממוצע הדקות של התחביבים הלא-ספורטיביים; כאשר המונה אפס, לא מתבצעת חלוקה בו
  - `absent` **0** — מתבצעת חלוקה במונה גם כשהוא אפס, או שהממוצע הלא-ספורטיבי אינו מחושב או אינו מודפס
- **q1.ג.c7.f1** · fault · fault · origin `planner` · requires `q1.ג.c7.c2`
  - טעות בחישוב המתמטי של ממוצע התחביבים הלא-ספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — נפלה טעות בחישוב המתמטי של ממוצע התחביבים הלא-ספורטיביים ← `q1.ג.c7.m1`
- **q1.ג.c7.f2** · fault · fault · origin `planner` · requires `q1.ג.c7.c2` · group `q1.ג:once:c2ce2a97`
  - אי המרה לממשי בחישוב ממוצע התחביבים הלא-ספורטיביים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — חישוב ממוצע התחביבים הלא-ספורטיביים בוצע כחלוקת שלמים ללא המרה לממשי ← `q1.ג.c7.m2`

**Interpretation notes:**
- ההנחיה 'רק פעם אחת' לגבי אי-המרה לממשי פורשה כחלה בתוך סעיף זה בלבד, בהתאם לעוגן הנפרד לכל ממוצע.

**Markers and dispositions:**

- `q1.ג.c3.m1` −1 · candidates ['q1.ג.c3'] · fault · «אם עשו לולאה עד length ולא בדקו בפנים שהתא שונה מ-null להוריד 1»
- `q1.ג.c6.m1` −0.5 · candidates ['q1.ג.c6'] · fault · «אם טעו בחישוב מתמטי להוריד 0.5)»
- `q1.ג.c6.m2` −0.5 · candidates ['q1.ג.c6'] · fault · «אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)»
- `q1.ג.c7.m1` −0.5 · candidates ['q1.ג.c7'] · fault · «אם טעו בחישוב מתמטי להוריד 0.5)»
- `q1.ג.c7.m2` −0.5 · candidates ['q1.ג.c7'] · fault · «אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)»

## q2.א — repaired

> validator messages that sent this scope to repair/fallback:
> - V16: q2.א.c1.c1 source_span is not verbatim in any allowed source

### q2.א.c0 · 5 נק׳ · components

**Teacher's text:** סעיף א': פעולה בונה public TvShow (string name, int channel)

**Collapsed:** 3 checks · credit max 5 / 5

- **q2.א.c0.c1** · credit · ladder · origin `planner`
  - קליטת הפרמטרים name ו-channel והשמתם לתכונות name ו-chl של האובייקט
  - שקילות: סדר ההשמות של name ו-chl אינו משנה
  - `full` **1.75** — התכונות name ו-chl מוגדרות מתוך הפרמטרים שהתקבלו לפעולה הבונה
  - `p1` **1** — רק אחת מבין התכונות name או chl הוגדרה מהפרמטר שהתקבל
  - `absent` **0** — התכונות name ו/או chl אינן מוגדרות מהפרמטרים שהתקבלו
- **q2.א.c0.c2** · credit · binary · origin `planner`
  - קביעת התכונה rate להיות אפס
  - `full` **1.75** — התכונה rate מאותחלת לערך אפס בפעולה הבונה
  - `absent` **0** — התכונה rate אינה מאותחלת לאפס בפעולה הבונה
- **q2.א.c0.c3** · credit · binary · origin `planner`
  - קביעת התכונה isOn להיות אמת
  - `full` **1.5** — התכונה isOn מאותחלת לערך true בפעולה הבונה
  - `absent` **0** — התכונה isOn אינה מאותחלת ל-true בפעולה הבונה

**Interpretation notes:**
- ההשמות של rate ו-isOn נבדקות כשתי דרישות נפרדות, מכיוון שכל אחת יכולה להתקיים בלי רעותה.

### q2.א.c1 · 10 נק׳ · components

**Teacher's text:** סעיף א': פעולה פנימית UpdateRate (סה"כ לפעולה 10)public TvShow (string name, int channel)

**Collapsed:** 2 checks · credit max 10 / 10

- **q2.א.c1.c1** · credit · ladder · origin `planner`
  - קליטת דירוג עבור כל אחד מהצופים לפי מספר הצופים שהתקבל
  - שקילות: אופן קליטת הדירוג (למשל קריאה מהמשתמש) יכול להיות בכל צורה סבירה, כל עוד מתבצעת קליטה נפרדת לכל צופה
  - `full` **5** — הפעולה עוברת על כל הצופים לפי המספר שהתקבל וקולטת דירוג בנפרד עבור כל אחד מהם
  - `p1` **2.5** — הדירוג נקלט פעם אחת בלבד ולא עבור כל אחד מהצופים בהתאם למספר שהתקבל
  - `absent` **0** — אין קליטה של דירוג בנפרד עבור כל אחד מהצופים לפי מספר הצופים שהתקבל
- **q2.א.c1.c2** · credit · binary · origin `planner`
  - הוספת הדירוג שנקלט לדירוג הקיים בתכונה rate ולא החלפתו
  - `full` **5** — כל דירוג שנקלט מצטבר ומתווסף לערך הקיים בתכונה rate
  - `absent` **0** — הדירוג שנקלט מחליף את הערך הקיים ב-rate במקום להצטבר אליו

**Interpretation notes:**
- מנגנון קליטת הדירוגים והוספתם לרייטינג הקיים נבדקים בנפרד, מכיוון שניתן לממש נכון את אחד מבלי השני.

## q2.ב — planner

### q2.ב.c0 · 2 נק׳ · components

**Teacher's text:** סעיף ב': פעולה חיצונית LowestRateChannel כותרת הפעולה

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c0.c1** · credit · binary · origin `planner`
  - כותרת הפעולה החיצונית LowestRateChannel
  - `full` **2** — הפעולה LowestRateChannel מוגדרת כפעולה חיצונית (static) המקבלת אובייקט מטיפוס TvRate ומחזירה מספר שלם המייצג ערוץ
  - `absent` **0** — לא הוגדרה כותרת מתאימה לפעולה החיצונית LowestRateChannel

### q2.ב.c1 · 2 נק׳ · components

**Teacher's text:** סעיף ב': בתוך LowestRateChannel : הגדרת מערך צוברים int לכל 100 הערוצים (ערוצים 1-100, המערך אמור להיות בגודל 101)

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c1.c1** · credit · ladder · origin `planner`
  - הגדרת מערך צוברים לדירוגי הערוצים
  - `full` **2** — הוגדר מערך מסוג int בגודל 101 שישמש כמערך צוברים עבור 100 הערוצים
  - `p1` **1** — הוגדר מערך צוברים מסוג int אך בגודל שגוי (למשל 100 במקום 101)
  - `absent` **0** — לא הוגדר מערך צוברים מתאים לערוצים

### q2.ב.c2 · 3 נק׳ · components

**Teacher's text:** סעיף ב': בתוך LowestRateChannel : לולאה על מערך הצוברים לאיפוס המערך

**Collapsed:** 2 checks · credit max 3 / 3

- **q2.ב.c2.c1** · credit · binary · origin `planner`
  - לולאה העוברת על תאי מערך הצוברים ומאפסת כל תא
  - שקילות: הסתמכות על ערך ברירת המחדל של מערך int (אפס), ללא לולאת איפוס מפורשת, שקולה
  - `full` **1.5** — קיימת לולאה שעוברת על תאי המערך ומאפסת כל תא לערך אפס
  - `absent` **0** — אין לולאה שמאפסת את תאי המערך
- **q2.ב.c2.c2** · credit · binary · origin `planner`
  - האיפוס מתבצע על מערך הצוברים עצמו
  - `full` **1.5** — הלולאה פועלת על מערך הצוברים ולא על מערך אחר
  - `absent` **0** — הלולאה פועלת על מערך שאינו מערך הצוברים

### q2.ב.c3.s0 · 3 נק׳ · components

**Teacher's text:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם התחילו מ-1 במקום מ-0 להוריד 0.5 אם ניגשו למערך TvShows בלי Getter להוריד 1 אם טעו בגבול העליון של הלולאה להוריד 0.5

**Collapsed:** 4 checks · credit max 3 / 3

- **q2.ב.c3.s0.c1** · credit · binary · origin `planner`
  - לולאה על מערך התוכניות TvShows המתחילה מאינדקס 0 ומסתיימת לפני length של המערך
  - `full` **3** — הלולאה מתחילה מאינדקס 0 ורצה כל עוד האינדקס קטן ממש מאורך מערך ה-TvShows
  - `absent` **0** — לא הוגדרה לולאה כזו על מערך ה-TvShows
- **q2.ב.c3.s0.f1** · fault · fault · origin `planner` · requires `q2.ב.c3.s0.c1`
  - הלולאה על מערך התוכניות מתחילה מאינדקס שגוי
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — הלולאה מתחילה מאינדקס 1 במקום מאינדקס 0 ← `q2.ב.c3.s0.m1`
- **q2.ב.c3.s0.f2** · fault · fault · origin `planner` · requires `q2.ב.c3.s0.c1`
  - גישה ישירה למערך התוכניות TvShows ללא שימוש בפעולת Get
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הגישה למערך התוכניות TvShows מתבצעת ישירות ולא באמצעות פעולת Get ← `q2.ב.c3.s0.m2`
- **q2.ב.c3.s0.f3** · fault · fault · origin `planner` · requires `q2.ב.c3.s0.c1`
  - טעות בגבול העליון של הלולאה על מערך התוכניות
  - `none` **0** — ללא הטעות הזו
  - `f1` **-0.5** — נפלה טעות בגבול העליון של הלולאה על מערך ה-TvShows ← `q2.ב.c3.s0.m3`

### q2.ב.c3.s1 · 2 נק׳ · components

**Teacher's text:** בתוך הלולאה על TvShows: בדיקה אם התא אינו null

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c3.s1.c1** · credit · binary · origin `planner`
  - בדיקה שהתא הנוכחי במערך TvShows אינו null
  - `full` **2** — בתוך הלולאה נבדק שהתא אינו null לפני שימוש בו
  - `absent` **0** — אין בדיקה שהתא אינו null

### q2.ב.c3.s2 · 2 נק׳ · components

**Teacher's text:** בתוך הלולאה על TvShows: אם התא אינו null , גישה לערוץ GetChl (ולא ע"י גישה ישירה לתכונה)אם ניגשו ישירות לתכונה chl להוריד 1

**Collapsed:** 2 checks · credit max 2 / 2

- **q2.ב.c3.s2.c1** · credit · binary · origin `planner`
  - גישה למספר הערוץ של התוכנית הנוכחית (כאשר התא אינו null) דרך GetChl
  - `full` **2** — מספר הערוץ של התוכנית הנוכחית מתקבל באמצעות הפעולה GetChl
  - `absent` **0** — לא מתבצעת גישה למספר הערוץ של התוכנית הנוכחית
- **q2.ב.c3.s2.f1** · fault · fault · origin `planner` · requires `q2.ב.c3.s2.c1`
  - גישה ישירה לתכונת הערוץ במקום שימוש ב-GetChl
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הגישה למספר הערוץ מתבצעת ישירות אל התכונה chl ולא באמצעות GetChl ← `q2.ב.c3.s2.m1`

### q2.ב.c3.s3 · 5 נק׳ · components

**Teacher's text:** בתוך הלולאה על TvShows: אם התא אינו null , צבירה של הדירוג של הערוץ (GetChl) לתוך מערך הצוברים במקום של הערוץ הזהאם ניגשו ישירות לתכונה rate במקום GetRate להוריד 1

**Collapsed:** 3 checks · credit max 5 / 5

- **q2.ב.c3.s3.c1** · credit · binary · origin `planner`
  - הוספת דירוג התוכנית הנוכחית לערך הקיים במערך הצוברים
  - `full` **2.5** — ערך הדירוג של התוכנית מצטבר (מתווסף) לערך הקיים בתא המתאים במערך הצוברים
  - `absent` **0** — הדירוג אינו נצבר לערך הקיים בתא (למשל, הערך נדרס במקום להצטבר)
- **q2.ב.c3.s3.c2** · credit · binary · origin `planner`
  - העדכון מתבצע בתא המתאים לערוץ של התוכנית הנוכחית במערך הצוברים
  - `full` **2.5** — העדכון נעשה באינדקס המערך המתאים למספר הערוץ שהתקבל עבור התוכנית הנוכחית
  - `absent` **0** — העדכון אינו מתבצע באינדקס המתאים לערוץ של התוכנית הנוכחית
- **q2.ב.c3.s3.f1** · fault · fault · origin `planner` · requires `q2.ב.c3.s3.c1`
  - גישה ישירה לתכונת הדירוג במקום שימוש ב-GetRate
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הגישה לדירוג התוכנית מתבצעת ישירות אל התכונה rate ולא באמצעות GetRate ← `q2.ב.c3.s3.m1`

### q2.ב.c4.s0 · 1 נק׳ · components · fixed

**Teacher's text:** הגדרת מינימום דירוג + אתחול

**Collapsed:** 2 checks · credit max 1 / 1

- **q2.ב.c4.s0.c1** · credit · binary · origin `planner`
  - הגדרת משתנה למינימום הדירוג
  - `full` **0.5** — הוגדר משתנה שישמש לשמירת הדירוג המינימלי שנמצא עד כה
  - `absent` **0** — לא הוגדר משתנה למינימום הדירוג
- **q2.ב.c4.s0.c2** · credit · binary · origin `planner`
  - אתחול משתנה המינימום לערך התחלתי מתאים
  - `full` **0.5** — המשתנה אותחל לערך גבוה מספיק כך שכל דירוג ממשי יהיה קטן ממנו
  - `absent` **0** — המשתנה לא אותחל, או אותחל לערך שאינו מבטיח החלפה בהמשך

### q2.ב.c4.s1 · 1 נק׳ · components · fixed

**Teacher's text:** הגדרת ערוץ מינימלי +אתחול

**Collapsed:** 2 checks · credit max 1 / 1

- **q2.ב.c4.s1.c1** · credit · binary · origin `planner`
  - הגדרת משתנה לערוץ המינימלי
  - `full` **0.5** — הוגדר משתנה שישמש לשמירת מספר הערוץ בעל הדירוג המינימלי
  - `absent` **0** — לא הוגדר משתנה לערוץ המינימלי
- **q2.ב.c4.s1.c2** · credit · binary · origin `planner`
  - אתחול משתנה הערוץ המינימלי לערך התחלתי
  - `full` **0.5** — המשתנה אותחל לערך התחלתי מתאים (למשל, ערך שאינו מספר ערוץ חוקי)
  - `absent` **0** — המשתנה לא אותחל

### q2.ב.c4.s2 · 2 נק׳ · components

**Teacher's text:** הגדרת לולאה על מערך צוברים מ-1 עד 100

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c4.s2.c1** · credit · binary · origin `planner`
  - לולאה על מערך הצוברים מהערוץ הראשון עד הערוץ המאה
  - `full` **2** — הלולאה עוברת על אינדקסים 1 עד 100 במערך הצוברים
  - `absent` **0** — לא הוגדרה לולאה כזו על מערך הצוברים

### q2.ב.c4.s3 · 3 נק׳ · components

**Teacher's text:** בתוך הלולאה על מערך הצוברים: בדיקה האם התא מתאים לערוץ הנוכחי של TvShow בתוך מערך הצוברים גדול מאפס (כלומר יש שימוש בערוץ זה) - לא להוריד, לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום - סה"כ 2 נקודות

**Collapsed:** 3 checks · credit max 3 / 3

- **q2.ב.c4.s3.c1** · credit · binary · origin `planner`
  - בדיקה האם סה"כ הדירוגים בתא הנוכחי של מערך הצוברים קטן מהמינימום שנשמר עד כה
  - `full` **3** — בתוך הלולאה נבדק אם ערך התא הנוכחי במערך הצוברים קטן מהמינימום שנשמר עד כה
  - `absent` **0** — אין בדיקה שמשווה את ערך התא הנוכחי למינימום הנוכחי
- **q2.ב.c4.s3.f1** · fault · fault · origin `planner` · requires `q2.ב.c4.s3.c1` · group `q2.ב:q2.ב.c4:d1`
  - הלוגיקה מחפשת את הדירוג הגבוה ביותר במקום הנמוך ביותר
  - `none` **0** — ללא הטעות הזו
  - `f1` **-3** — הלוגיקה מחפשת את הערוץ בעל הדירוג הגבוה ביותר במקום הנמוך ביותר, ושאר הפרטים תקינים ← `q2.ב.c4.s3.m1`
- **q2.ב.c4.s3.n1** · note · note · origin `compiler`
  - לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום
  - `none` **0** — לא רלוונטי
  - `observed` **0** — לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום

**Interpretation notes:**
- הבדיקה אם התא מתאים לערוץ בשימוש (גדול מאפס) היא הערה בלבד ואינה מנוקדת בנפרד.

### q2.ב.c4.s4 · 1 נק׳ · components

**Teacher's text:** בתוך התנאי (בתוך הלולאה) - החלפה של מינימום דירוג

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c4.s4.c1** · credit · binary · origin `planner`
  - עדכון (החלפה) של המינימום לערך התא הנוכחי כאשר מתקיים התנאי
  - `full` **1** — כאשר מתקיים התנאי, המשתנה השומר את המינימום מתעדכן לערך התא הנוכחי
  - `absent` **0** — המינימום אינו מתעדכן כאשר מתקיים התנאי

### q2.ב.c4.s5 · 1 נק׳ · components

**Teacher's text:** בתוך התנאי (בתוך הלולאה) - החלפת הערוץ המינימלי

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c4.s5.c1** · credit · binary · origin `planner`
  - עדכון (החלפה) של הערוץ המינימלי כאשר מתקיים התנאי
  - `full` **1** — כאשר מתקיים התנאי, המשתנה השומר את הערוץ המינימלי מתעדכן לערוץ הנוכחי
  - `absent` **0** — הערוץ המינימלי אינו מתעדכן כאשר מתקיים התנאי

### q2.ב.c5 · 1 נק׳ · components

**Teacher's text:** סעיף ב': בתוך LowestRateChannel : החזרת הערוץ המינימלי

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c5.c1** · credit · binary · origin `planner`
  - החזרת מספר הערוץ המינימלי מהפעולה
  - `full` **1** — הפעולה מחזירה את מספר הערוץ בעל הדירוג הנמוך ביותר שנמצא
  - `absent` **0** — הפעולה אינה מחזירה את הערוץ המינימלי

**Markers and dispositions:**

- `q2.ב.c3.s0.m1` −0.5 · candidates ['q2.ב.c3.s0'] · fault · «אם התחילו מ-1 במקום מ-0 להוריד 0.5»
- `q2.ב.c3.s0.m2` −1 · candidates ['q2.ב.c3.s0'] · fault · «אם ניגשו למערך TvShows בלי Getter להוריד 1»
- `q2.ב.c3.s0.m3` −0.5 · candidates ['q2.ב.c3.s0'] · fault · «אם טעו בגבול העליון של הלולאה להוריד 0.5»
- `q2.ב.c3.s2.m1` −1 · candidates ['q2.ב.c3.s2'] · fault · «אם ניגשו ישירות לתכונה chl להוריד 1»
- `q2.ב.c3.s3.m1` −1 · candidates ['q2.ב.c3.s3'] · fault · «אם ניגשו ישירות לתכונה rate במקום GetRate להוריד 1»
- `q2.ב.c4.s3.m1` −3 · candidates ['q2.ב.c4.s0', 'q2.ב.c4.s1', 'q2.ב.c4.s2', 'q2.ב.c4.s3', 'q2.ב.c4.s4', 'q2.ב.c4.s5'] · fault · «פירוט ל-10:אם חיפשו את המקסימום אך הלוגיקה בסדר להוריד 3»

**V19 candidates (telemetry):**
- `q2.ב.c3.s0.f2` requires `q2.ב.c3.s0.c1` — shared tokens ['TvShows']

## q2.ג — repaired

> validator messages that sent this scope to repair/fallback:
> - V20: q2.ג.c0.s3 component 1 span differs from the compiled one
> - V20: q2.ג.c0.s3 component 2 span differs from the compiled one
> - V20: q2.ג.c0.s3 component 3 span differs from the compiled one
> - V20: q2.ג.c0.s3 component 4 span differs from the compiled one

### q2.ג.c0.s0 · 2 נק׳ · components

**Teacher's text:** כותרת הפעולה PrintLowRatingChannel

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ג.c0.s0.c1** · credit · binary · origin `planner`
  - כותרת הפעולה PrintLowRatingChannel
  - `full` **2** — הוגדרה פעולה חיצונית בשם PrintLowRatingChannel המקבלת אובייקט מטיפוס TvRate
  - `absent` **0** — כותרת הפעולה חסרה או אינה תואמת לנדרש

### q2.ג.c0.s1 · 3 נק׳ · components

**Teacher's text:** מציאת הערוץ בעל דירוג מינימלי ע"י זימון LowestRateChannel

**Collapsed:** 1 checks · credit max 3 / 3

- **q2.ג.c0.s1.c1** · credit · binary · origin `planner`
  - מציאת הערוץ בעל דירוג מינימלי ע"י זימון LowestRateChannel
  - שקילות: שם משתנה שונה לאחסון התוצאה של הזימון אינו פוגם בתקינות
  - `full` **3** — הערוץ בעל הדירוג הנמוך ביותר נמצא באמצעות קריאה לפעולה LowestRateChannel
  - `absent` **0** — הערוץ בעל הדירוג הנמוך ביותר לא נמצא באמצעות זימון הפעולה LowestRateChannel

### q2.ג.c0.s2 · 3 נק׳ · components

**Teacher's text:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם הגישה למערך בלי getter להוריד 1

**Collapsed:** 2 checks · credit max 3 / 3

- **q2.ג.c0.s2.c1** · credit · binary · origin `planner`
  - הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ-length של המערך
  - `full` **3** — הוגדרה לולאה הרצה מאינדקס 0 ועד קטן ממש ממספר האיברים במערך TvShows
  - `absent` **0** — לא הוגדרה לולאה מתאימה על מערך התוכניות
- **q2.ג.c0.s2.f1** · fault · fault · origin `planner` · requires `q2.ג.c0.s2.c1`
  - גישה ישירה למערך התוכניות ללא שימוש בפעולת ה-getter
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הגישה לתכונות המערך (כגון אורכו) נעשית ישירות ולא באמצעות פעולת ה-getter ← `q2.ג.c0.s2.m1`

### q2.ג.c0.s3 · 8 נק׳ · components · fixed

**Teacher's text:** בתוך הלולאה על TvShows: בדיקה האם תוכנית מתאימה להדפסה:אינה null ב (2 נקודות) וגם הערוץ שלה תואם את הערוץ המינימלי (ע"י GetChl והשוואתם (2 נקודות) וגם היא באוויר (ע"י GetIsOn ב 2 נקודות) הדפסה של השם של התוכנית (ע"י GetName ב( 2 נקודות)

**Collapsed:** 4 checks · credit max 8 / 8

- **q2.ג.c0.s3.c1** · credit · binary · origin `planner`
  - בדיקה שהאיבר הנוכחי במערך אינו null
  - `full` **2** — נבדק שהאיבר הנוכחי במערך אינו null לפני המשך הבדיקות
  - `absent` **0** — לא נבדק שהאיבר במערך שונה מ-null
- **q2.ג.c0.s3.c2** · credit · binary · origin `planner`
  - בדיקה שהערוץ של התוכנית תואם את הערוץ המינימלי
  - `full` **2** — הערוץ של התוכנית מושווה לערוץ המינימלי באמצעות GetChl
  - `absent` **0** — לא נבדקת התאמת הערוץ של התוכנית לערוץ המינימלי
- **q2.ג.c0.s3.c3** · credit · binary · origin `planner`
  - בדיקה שהתוכנית משודרת כעת
  - `full` **2** — נבדק שהתוכנית משודרת כעת באמצעות GetIsOn
  - `absent` **0** — לא נבדק אם התוכנית משודרת כעת
- **q2.ג.c0.s3.c4** · credit · binary · origin `planner`
  - הדפסת שם התוכנית
  - `full` **2** — שם התוכנית מודפס באמצעות GetName
  - `absent` **0** — שם התוכנית אינו מודפס

**Markers and dispositions:**

- `q2.ג.c0.s2.m1` −1 · candidates ['q2.ג.c0.s2'] · fault · «אם הגישה למערך בלי getter להוריד 1»

