# bagrut_899371 — plan/v6 render

- plan_hash `54ae5ccf74cdcd09…` · config_hash `bdfd12d8a8dc7d55…` · pack `computer_science@v1`
- stage 1 `plan-compiler/v2.0+stage1-v6.0` · 61 criteria · 106 checks
- scope origins: q1.א.1=compiled, q1.א.2=planner, q1.ב.1=planner, q1.ב.2=planner, q2.א=planner, q2.ב=planner, q3.א=planner, q3.ב=planner, q4.א=planner, q4.ב=fallback, q5.א=planner, q5.ב=planner, q6=planner

## q1.א.1 — compiled

### q1.א.1.c0 · 12 נק׳ · count

**Teacher's text:** ניקוד טבלת מעקב סה"כ 12 נקודות: 17 תאים  0.7 כל תא

**Collapsed:** 1 checks · credit max 12 / 12

- **q1.א.1.c0.c1** · credit · count · origin `compiler`
  - ניקוד טבלת מעקב סה"כ ודות: 17 תאים 0.7 כל תא
  - `n17` **12** — 17 מתוך 17 נכונים
  - `n16` **11.25** — 16 מתוך 17 נכונים
  - `n15` **10.5** — 15 מתוך 17 נכונים
  - `n14` **10** — 14 מתוך 17 נכונים
  - `n13` **9.25** — 13 מתוך 17 נכונים
  - `n12` **8.5** — 12 מתוך 17 נכונים
  - `n11` **7.75** — 11 מתוך 17 נכונים
  - `n10` **7** — 10 מתוך 17 נכונים
  - `n9` **6.25** — 9 מתוך 17 נכונים
  - `n8` **5.75** — 8 מתוך 17 נכונים
  - `n7` **5** — 7 מתוך 17 נכונים
  - `n6` **4.25** — 6 מתוך 17 נכונים
  - `n5` **3.5** — 5 מתוך 17 נכונים
  - `n4` **2.75** — 4 מתוך 17 נכונים
  - `n3` **2** — 3 מתוך 17 נכונים
  - `n2` **1.5** — 2 מתוך 17 נכונים
  - `n1` **0.75** — 1 מתוך 17 נכונים
  - `n0` **0** — 0 מתוך 17 נכונים

## q1.א.2 — planner

### q1.א.2.c0 · 1.5 נק׳ · components

**Teacher's text:** הבנת הבדיקה של "מחלק ללא שארית"~  1.5 נק'

**Collapsed:** 1 checks · credit max 1.5 / 1.5

- **q1.א.2.c0.c1** · credit · ladder · origin `planner`
  - הבנת הבדיקה של "מחלק ללא שארית"
  - שקילות: ניסוח כגון "x מתחלק באיבר בשלמות" או "האיבר מחלק את x ללא שארית" נחשב שקול
  - `full` **1.5** — צוין שהבדיקה בודקת האם x מתחלק באיבר המועמד ללא שארית (כלומר x מתחלק בו בשלמות)
  - `p1` **0.75** — צוין שהאיבר הוא מחלק של x, אך לא צוין שמדובר בחלוקה ללא שארית
  - `absent` **0** — לא צוין שהבדיקה עוסקת בחלוקה ללא שארית

### q1.א.2.c1 · 1.5 נק׳ · components · fixed

**Teacher's text:** התייחסות לתנאי שהאיבר שונה מ-1 ומ-x עצמו  0.5 נק'

**Collapsed:** 2 checks · credit max 1.5 / 1.5

- **q1.א.2.c1.c1** · credit · binary · origin `planner`
  - התייחסות לתנאי שהאיבר שונה מ-1
  - `full` **0.5** — צוין שהאיבר הנבדק צריך להיות שונה מ-1
  - `absent` **0** — לא צוין שהאיבר צריך להיות שונה מ-1
- **q1.א.2.c1.c2** · credit · binary · origin `planner`
  - התייחסות לתנאי שהאיבר שונה מ-x עצמו
  - `full` **1** — צוין שהאיבר הנבדק צריך להיות שונה מ-x עצמו
  - `absent` **0** — לא צוין שהאיבר צריך להיות שונה מ-x עצמו

**Interpretation notes:**
- הקריטריון המקורי מנה שני תנאים נפרדים (שונה מ-1 ושונה מ-x) באותו משפט, ולכן פוצל לשתי בדיקות תואמות לשני הרכיבים שסיפק המהדר.

## q1.ב.1 — planner

### q1.ב.1.c0 · 6 נק׳ · components

**Teacher's text:** ניקוד: 6 נקודות

**Collapsed:** 1 checks · credit max 6 / 6

- **q1.ב.1.c0.c1** · credit · binary · origin `planner`
  - ציון הערך המוחזר מהפעולה What(arr)B
  - `full` **6** — נכתב שהערך המוחזר הוא 76
  - `absent` **0** — לא נכתב שהערך המוחזר הוא 76, או שנכתב ערך אחר

## q1.ב.2 — planner

### q1.ב.2.c0 · 2 נק׳ · components

**Teacher's text:** זיהוי שמדובר בפעולת סכימה של איברי המערך – 2 נק'

**Collapsed:** 1 checks · credit max 2 / 2

- **q1.ב.2.c0.c1** · credit · binary · origin `planner`
  - זיהוי שמדובר בפעולת סכימה של איברי המערך
  - `full` **2** — התשובה מזהה שהפעולה מחשבת ומחזירה סכום של איברים מהמערך
  - `absent` **0** — התשובה אינה מזהה שמדובר בפעולת סכימה של איברי המערך

### q1.ב.2.c1 · 2 נק׳ · components

**Teacher's text:** הגדרה נכונה של תנאי הסכימה (איברים שיש להם מחלק אחר במערך) 2  נק'

**Collapsed:** 1 checks · credit max 2 / 2

- **q1.ב.2.c1.c1** · credit · binary · origin `planner`
  - הגדרה נכונה של תנאי הסכימה
  - `full` **2** — התשובה מגדירה את תנאי הסכימה כאיברים שיש להם מחלק (השונה מ-1 ומעצמו) הנמצא במערך עצמו
  - `absent` **0** — התשובה אינה מגדירה נכון את תנאי הסכימה כמחלק הנמצא במערך

## q2.א — planner

### q2.א.c0 · 1 נק׳ · components

**Teacher's text:** סעיף א: חתימת הפעולה public static bool IsMirror(int[] arr)

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.א.c0.c1** · credit · binary · origin `planner`
  - כתיבת חתימת הפעולה כנדרש
  - שקילות: שם הפרמטר יכול להיות שונה מ-arr, ובלבד שהטיפוסים ושם הפעולה תואמים
  - `full` **1** — הפעולה מוגדרת עם החתימה public static bool IsMirror(int[] arr)
  - `absent` **0** — חתימת הפעולה אינה תואמת לנדרש (שם, טיפוס החזרה או פרמטרים שונים)

### q2.א.c1 · 0.5 נק׳ · components

**Teacher's text:** שמות משתנים משמעותיים וקוד קריא

**Collapsed:** 2 checks · credit max 0.5 / 0.5

- **q2.א.c1.c1** · credit · binary · origin `planner`
  - שימוש בשמות משתנים משמעותיים
  - `full` **0.25** — שמות המשתנים בקוד מתארים את תפקידם
  - `absent` **0** — שמות המשתנים אינם משמעותיים
- **q2.א.c1.c2** · credit · binary · origin `planner`
  - כתיבת קוד קריא
  - `full` **0.25** — הקוד בנוי ומסודר בצורה קריאה
  - `absent` **0** — הקוד אינו קריא או בנוי בצורה לא מסודרת

### q2.א.c2 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף א: בדיקה האם המערך לא באורך זוגי, להחזיר false (if נק' 1, החזרת false נקודה 1) if (arr.Length % 2 != 0) return false;

**Collapsed:** 2 checks · credit max 2 / 2

- **q2.א.c2.c1** · credit · binary · origin `planner`
  - בדיקת תנאי שאורך המערך אינו זוגי
  - `full` **1** — קיים תנאי הבודק האם אורך המערך אינו זוגי, כגון arr.Length % 2 != 0
  - `absent` **0** — אין בדיקה של תנאי אי-זוגיות אורך המערך
- **q2.א.c2.c2** · credit · binary · origin `planner`
  - החזרת false כאשר אורך המערך אינו זוגי
  - `full` **1** — כאשר התנאי מתקיים, הפעולה מחזירה false
  - `absent` **0** — אין החזרת false כאשר אורך המערך אינו זוגי

### q2.א.c3 · 1.5 נק׳ · components

**Teacher's text:** סעיף א: לולאה על המערך for (int i = 0; i < arr.Length; i++)

**Collapsed:** 1 checks · credit max 1.5 / 1.5

- **q2.א.c3.c1** · credit · binary · origin `planner`
  - לולאה העוברת על איברי המערך
  - `full` **1.5** — קיימת לולאה המבצעת מעבר על כל איברי המערך
  - `absent` **0** — אין לולאה העוברת על איברי המערך

### q2.א.c4 · 4 נק׳ · components

**Teacher's text:** סעיף א: בתוך הלולאה: חיפוש אחר המספר הנגדי של arr[i]: int target = -arr[i]; bool found = false; for (int j = 0; j < arr.Length && found == false; j++) { if (arr[j] == target) { found = true; } }

**Collapsed:** 2 checks · credit max 4 / 4

- **q2.א.c4.c1** · credit · binary · origin `planner`
  - חיפוש אחר המספר הנגדי במערך
  - `full` **2** — קיימת לולאה פנימית הבודקת עבור כל איבר במערך האם הוא שווה לערך המבוקש, ומסמנת שנמצא
  - `absent` **0** — אין לולאה פנימית המחפשת התאמה במערך
- **q2.א.c4.c2** · credit · binary · origin `planner`
  - חישוב הערך המבוקש כמספר הנגדי של האיבר הנוכחי
  - `full` **2** — הערך המבוקש מחושב כמינוס איבר הלולאה הנוכחי (-arr[i])
  - `absent` **0** — הערך המבוקש שגוי או אינו מחושב כ- -arr[i]

### q2.א.c5 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף א: מחוץ ללואה אם לא מצאנו את המספר הנגדי (1 נקודה) להחזיר false (1 נקודה)

**Collapsed:** 2 checks · credit max 2 / 2

- **q2.א.c5.c1** · credit · binary · origin `planner`
  - בדיקה מחוץ ללולאה האם לא נמצא המספר הנגדי
  - `full` **1** — קיים תנאי הבודק מחוץ ללולאה החיצונית האם המספר הנגדי לא נמצא
  - `absent` **0** — אין בדיקה מחוץ ללולאה האם המספר הנגדי לא נמצא
- **q2.א.c5.c2** · credit · binary · origin `planner`
  - החזרת false כאשר לא נמצא המספר הנגדי
  - `full` **1** — כאשר לא נמצא המספר הנגדי, הפעולה מחזירה false
  - `absent` **0** — אין החזרת false כאשר לא נמצא המספר הנגדי

### q2.א.c6 · 1 נק׳ · components

**Teacher's text:** סעיף א: שורה אחרונה: להחזיר true

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.א.c6.c1** · credit · binary · origin `planner`
  - החזרת true בסיום הבדיקה
  - `full` **1** — לאחר שכל האיברים נבדקו ונמצא עבורם נגדי, הפעולה מחזירה true
  - `absent` **0** — אין החזרת true בסיום הבדיקה

## q2.ב — planner

### q2.ב.c0 · 1 נק׳ · components

**Teacher's text:** סעיף ב: חתימת הפעולה public static void ArrangeMirror(int[] arr)

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c0.c1** · credit · binary · origin `planner`
  - כתיבת חתימת הפעולה כנדרש: פעולה בשם ArrangeMirror, מקבלת מערך שלמים ומחזירה void
  - שקילות: שם הפרמטר עצמו אינו מחייב; כל שם פרמטר מטיפוס מערך שלמים תקף
  - `full` **1** — החתימה תואמת: public static void ArrangeMirror(int[] arr)
  - `absent` **0** — החתימה אינה תואמת (שם הפעולה, טיפוס הפרמטר או טיפוס ההחזרה שגויים)

**Interpretation notes:**
- התייחסות היא לחתימה בלבד, ולא לתוכן הפעולה.

### q2.ב.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: שמות משתנים משמעותיים וקוד קריא

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q2.ב.c1.c1** · credit · binary · origin `planner`
  - שימוש בשמות משתנים משמעותיים וכתיבת קוד קריא
  - `full` **0.5** — שמות המשתנים משמעותיים והקוד ברור וקריא
  - `absent` **0** — שמות משתנים לא משמעותיים או קוד לא קריא

### q2.ב.c2 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב: יצירת מערך עזר באותו גודל של הפרמטר + משתנה למציין של מערך העזר + אתחול ל-0 int[] temp = new int[arr.Length]; // הקצאת מערך עזר באותו הגודל int tempIndex = 0;

**Collapsed:** 3 checks · credit max 2 / 2

- **q2.ב.c2.c1** · credit · binary · origin `planner`
  - יצירת מערך עזר באותו גודל של מערך הפרמטר
  - `full` **1** — נוצר מערך עזר חדש שגודלו שווה לגודל מערך הפרמטר
  - `absent` **0** — לא נוצר מערך עזר, או שנוצר בגודל שונה מגודל מערך הפרמטר
- **q2.ב.c2.c2** · credit · binary · origin `planner`
  - הגדרת משתנה אינדקס המציין את המיקום הבא במערך העזר
  - `full` **0.5** — הוגדר משתנה נפרד המשמש כאינדקס למערך העזר
  - `absent` **0** — לא הוגדר משתנה אינדקס נפרד למערך העזר
- **q2.ב.c2.c3** · credit · binary · origin `planner`
  - אתחול משתנה האינדקס של מערך העזר לאפס
  - `full` **0.5** — משתנה האינדקס של מערך העזר אותחל לערך אפס
  - `absent` **0** — משתנה האינדקס לא אותחל לאפס

### q2.ב.c3 · 4.5 נק׳ · components · fixed

**Teacher's text:** סעיף ב: סריקת המערך הפרמטר ומציאת המספרים החיוביים והעתקם למערך הזמני פלוס קידום האנדקס לולאה על המערך הפרמטר 0.5 אם המספר הנוכחי במערך הפרמטר חיובי 2 העתק המספר החיובי למערך העזר 1 קידום האנדקס 1 for (int i = 0; i < arr.Length; i++) { if (arr[i] > 0) // אם המספר חיובי { temp[tempIndex] = arr[i]; // העתקת המספר החיובי למערך העזר tempIndex++;

**Collapsed:** 4 checks · credit max 4.5 / 4.5

- **q2.ב.c3.c1** · credit · binary · origin `planner`
  - לולאה הסורקת את מערך הפרמטר לאיתור המספרים החיוביים והעתקתם למערך הזמני תוך קידום האינדקס
  - `full` **0.5** — קיימת לולאה העוברת על כל איברי מערך הפרמטר ומטפלת בהעתקה ובקידום האינדקס
  - `absent` **0** — אין לולאה הסורקת את מערך הפרמטר
- **q2.ב.c3.c2** · credit · binary · origin `planner`
  - בדיקה האם המספר הנוכחי במערך הפרמטר הוא חיובי
  - `full` **2** — בכל איטרציה נבדק האם האיבר הנוכחי גדול מאפס
  - `absent` **0** — אין בדיקה האם האיבר הנוכחי חיובי
- **q2.ב.c3.c3** · credit · binary · origin `planner`
  - העתקת המספר החיובי שנמצא למערך העזר
  - `full` **1** — מספר חיובי שנמצא מועתק למערך העזר
  - `absent` **0** — מספר חיובי שנמצא אינו מועתק למערך העזר
- **q2.ב.c3.c4** · credit · binary · origin `planner`
  - קידום האינדקס של מערך העזר לאחר ההעתקה
  - `full` **1** — אינדקס מערך העזר מתקדם לאחר כל העתקה של מספר חיובי
  - `absent` **0** — אינדקס מערך העזר אינו מתקדם לאחר ההעתקה

### q2.ב.c4 · 3 נק׳ · components

**Teacher's text:** סעיף ב: בתוך הלולאה: אופציה 1: מניחים שהמערך פרמטר הוא מערך מראה (כפי שכתוב בשאלה) ופשוט מבצעים: temp[tempIndex] = -arr[i]; tempIndex++; אופציה 2: מציאת המספר הנגדי המתאים (ע"י עוד לולאה) והשמתו בצמוד למספר שנמצא (באינדקס העוקב). bool found = false; for (int j = 0; j < arr.Length && found == false ; j++) { if (arr[j] == -arr[i]) { temp[tempIndex] = arr[j]; // העתקת המספר השלילי מיד לאחר החיובי tempIndex++; found = true; // מצאנו את הנגדי היחיד, יוצאים מהלולאה הפנימית } }

**Collapsed:** 1 checks · credit max 3 / 3

- **q2.ב.c4.c1** · credit · binary · origin `planner`
  - מציאת המספר השלילי הנגדי למספר החיובי שנמצא, והצבתו במערך העזר מיד לאחריו
  - שקילות: מקובלות שתי הדרכים: הנחה שהמערך הוא מערך מראה וחישוב הנגדי ישירות, או חיפוש הנגדי בלולאה נוספת בתוך המערך
  - `full` **3** — בכל איטרציה שבה נמצא מספר חיובי, מוצב מיד לאחריו במערך העזר המספר השלילי הנגדי לו, וקידום האינדקס בהתאם
  - `absent` **0** — לא מוצב המספר השלילי הנגדי מיד לאחר המספר החיובי במערך העזר

**Interpretation notes:**
- שתי הגישות שהוצגו בשאלה (הנחת מערך מראה או חיפוש) נחשבות מימוש תקין של אותה דרישה.

### q2.ב.c5 · 2 נק׳ · components

**Teacher's text:** סעיף ב: העתקה מסודרת של כל איברי מערך העזר חזרה למערך המקורי שנתקבל כפרמטר for (int i = 0; i < arr.Length; i++) arr[i] = temp[i];

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c5.c1** · credit · binary · origin `planner`
  - העתקה מסודרת של כל איברי מערך העזר חזרה למערך המקורי שנתקבל כפרמטר
  - `full` **2** — כל איברי מערך העזר הועתקו בסדר הנכון למערך המקורי
  - `absent` **0** — מערך העזר לא הועתק בחזרה למערך המקורי, או הועתק בסדר שגוי או חלקי

## q3.א — planner

### q3.א.c0 · 0.5 נק׳ · components

**Teacher's text:** סעיף א: חתימת הפעולה public static int[] DiceStatistics(int[] arr)

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q3.א.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה כנדרש
  - `full` **0.5** — הפעולה מוגדרת בשם DiceStatistics, מקבלת מערך שלמים arr ומחזירה מערך שלמים, כנדרש
  - `absent` **0** — חתימת הפעולה שונה מהנדרש (שם הפעולה, סוג/מספר הפרמטרים או סוג הערך המוחזר אינם תואמים)

### q3.א.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף א: משתנים משמעותיים + קוד קריא

**Collapsed:** 2 checks · credit max 0.5 / 0.5

- **q3.א.c1.c1** · credit · binary · origin `planner`
  - שימוש במשתנים בעלי שמות משמעותיים
  - `full` **0.25** — שמות המשתנים בקוד מבטאים את תפקידם
  - `absent` **0** — שמות המשתנים אינם משמעותיים (כגון אותיות בודדות ללא הקשר)
- **q3.א.c1.c2** · credit · binary · origin `planner`
  - כתיבת קוד קריא
  - `full` **0.25** — הקוד מאורגן ומסודר בצורה קריאה
  - `absent` **0** — הקוד אינו קריא (מבנה לא מסודר)

**Interpretation notes:**
- הדרישה פוצלה לשני היבטים נבדלים - שמות משתנים וקריאות הקוד - שכן ניתן לקיים אחד מבלי השני.

### q3.א.c2 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף א: הגדרה והקצאה נכונה של מערך המונים בגודל 21 + איפוס מערך מונים

**Collapsed:** 2 checks · credit max 2 / 2

- **q3.א.c2.c1** · credit · binary · origin `planner`
  - הגדרה והקצאה נכונה של מערך המונים בגודל 21
  - `full` **1** — מוגדר ומוקצה מערך שלמים בגודל 21
  - `absent` **0** — מערך המונים אינו מוגדר או אינו מוקצה בגודל הנכון
- **q3.א.c2.c2** · credit · binary · origin `planner`
  - איפוס מערך המונים
  - שקילות: הקצאת מערך חדש בעל ערכי ברירת מחדל אפס נחשבת איפוס תקין
  - `full` **1** — מערך המונים מאופס בתחילת הפעולה
  - `absent` **0** — מערך המונים אינו מאופס

### q3.א.c3 · 2 נק׳ · components

**Teacher's text:** סעיף א: לולאה הסורקת את מערך הקלט

**Collapsed:** 2 checks · credit max 2 / 2

- **q3.א.c3.c1** · credit · binary · origin `planner`
  - קיום לולאה העוברת על כל איברי מערך הקלט
  - `full` **1** — קיימת לולאה החוזרת על כל אינדקסי המערך
  - `absent` **0** — אין לולאה העוברת על כל איברי המערך
- **q3.א.c3.c2** · credit · binary · origin `planner`
  - הלולאה סורקת את מערך הקלט arr
  - `full` **1** — הלולאה פועלת על מערך הקלט arr המכיל את תוצאות ההטלות
  - `absent` **0** — הלולאה פועלת על מערך שאינו מערך הקלט

**Interpretation notes:**
- הדרישה פוצלה למנגנון הלולאה ולמערך שעליו היא פועלת, כדי שהרצת לולאה תקינה על מערך שגוי תיזקף למונגנון בלבד.

### q3.א.c4 · 3 נק׳ · components

**Teacher's text:** סעיף א: בתוך הלולאה, קידום תקין של המונה המתאים int diceValue = arr[i]; // תוצאת ההטלה -ערך בין 1 ל-20 counts[diceValue]++; // קידום המונה באינדקס המתאים אם עשו לולאה פנימית ועדכנו את מערך הונים רק כש- arr[i] == למונה של הלולאה הפנימית , לא להוריד כלום (לא ביקשנו פתרון עם מערך מונים)

**Collapsed:** 3 checks · credit max 3 / 3

- **q3.א.c4.c1** · credit · binary · origin `planner`
  - זיהוי האינדקס המתאים במערך המונים לפי ערך ההטלה
  - שקילות: שמירת ערך ההטלה במשתנה ביניים לפני השימוש כאינדקס שקולה
  - `full` **1.5** — האינדקס במערך המונים נגזר ישירות מערך ההטלה arr[i]
  - `absent` **0** — האינדקס במערך המונים אינו תואם את ערך ההטלה
- **q3.א.c4.c2** · credit · binary · origin `planner`
  - קידום המונה באינדקס המתאים
  - `full` **1.5** — המונה באינדקס המתאים מוגדל באחד
  - `absent` **0** — המונה באינדקס המתאים אינו מוגדל
- **q3.א.c4.n1** · note · note · origin `compiler`
  - כלום (לא ביקשנו פתרון עם מערך מונים
  - `none` **0** — לא רלוונטי
  - `observed` **0** — כלום (לא ביקשנו פתרון עם מערך מונים

**Interpretation notes:**
- הדרישה פוצלה לזיהוי האינדקס הנכון ולקידום המונה עצמו, כדי שקידום תקין על אינדקס שגוי ייזקף למנגנון בלבד.

### q3.א.c5 · 2 נק׳ · components

**Teacher's text:** סעיף א: אחרי הלולאה:החזרת מערך המונים המלא

**Collapsed:** 1 checks · credit max 2 / 2

- **q3.א.c5.c1** · credit · binary · origin `planner`
  - החזרת מערך המונים המלא לאחר סיום הלולאה
  - `full` **2** — מוחזר מערך המונים המלא לאחר תום הלולאה
  - `absent` **0** — לא מוחזר מערך המונים המלא, או שההחזרה מתבצעת בתוך הלולאה

## q3.ב — planner

### q3.ב.c0 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: חתימת הפעולה public static void PrintStatistics(int[] arr)

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q3.ב.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה PrintStatistics
  - `full` **0.5** — נכתבה חתימת פעולה תואמת: public static void PrintStatistics(int[] arr)
  - `absent` **0** — החתימה אינה תואמת את הנדרש (שם הפעולה, סוג ההחזרה, מספר או סוג הפרמטרים שונים)

### q3.ב.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: משתנים משמעותיים + קוד קריא

**Collapsed:** 2 checks · credit max 0.5 / 0.5

- **q3.ב.c1.c1** · credit · binary · origin `planner`
  - שמות משתנים משמעותיים
  - `full` **0.25** — שמות המשתנים בקוד משקפים את תפקידם
  - `absent` **0** — שמות המשתנים אינם משמעותיים ואינם קשורים לתפקידם
- **q3.ב.c1.c2** · credit · binary · origin `planner`
  - כתיבת קוד קריא
  - `full` **0.25** — הקוד כתוב בצורה קריאה ומאורגנת
  - `absent` **0** — הקוד אינו קריא או אינו מאורגן

### q3.ב.c2 · 2 נק׳ · components

**Teacher's text:** סעיף ב: קריאה נכונה לפעולה DiceStatistics(arr) ושמירת המערך המוחזר אם יצרו מערך מונים חדש ו/או הריצו את הפעולה DiceStatistics בתוך לולאה תוך העתקה של כל תא , לא להוריד כלום (חוסר יעילות)

**Collapsed:** 3 checks · credit max 2 / 2

- **q3.ב.c2.c1** · credit · binary · origin `planner`
  - קריאה נכונה לפעולה DiceStatistics(arr)
  - `full` **1** — הפעולה DiceStatistics נקראת עם המערך arr כפרמטר
  - `absent` **0** — הפעולה DiceStatistics אינה נקראת עם arr
- **q3.ב.c2.c2** · credit · binary · origin `planner`
  - שמירת המערך המוחזר מהפעולה DiceStatistics
  - `full` **1** — הערך המוחזר מהקריאה לפעולה נשמר במשתנה מערך
  - `absent` **0** — הערך המוחזר מהקריאה אינו נשמר במשתנה
- **q3.ב.c2.n1** · note · note · origin `compiler`
  - כלום (חוסר יעילות
  - `none` **0** — לא רלוונטי
  - `observed` **0** — כלום (חוסר יעילות

**Interpretation notes:**
- ההערה בדבר יצירת מערך מונים חדש או הרצת הפעולה בתוך לולאה תוך העתקה נחשבת הערה שאינה מזכה ואינה נבדקת כרכיב נפרד.

### q3.ב.c3 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב: הגדרת משתנה שלם לשמירת הערך המקסימלי maxCount + _ + אתחול לתא הראשון או לערך מאוד נמוך) (אתחול 1 נקודות)

**Collapsed:** 2 checks · credit max 2 / 2

- **q3.ב.c3.c1** · credit · binary · origin `planner`
  - הגדרת משתנה שלם לשמירת הערך המקסימלי
  - שקילות: שם המשתנה אינו חייב להיות maxCount, ובלבד שתפקידו ברור
  - `full` **1** — הוגדר משתנה שלם המיועד לשמירת הערך המקסימלי
  - `absent` **0** — לא הוגדר משתנה שלם לשמירת הערך המקסימלי
- **q3.ב.c3.c2** · credit · binary · origin `planner`
  - אתחול משתנה הערך המקסימלי
  - `full` **1** — המשתנה אותחל לערך התא הראשון (אינדקס 1) או לערך נמוך מאוד
  - `absent` **0** — המשתנה לא אותחל, או אותחל לערך שאינו מבטיח זיהוי נכון של המקסימום

### q3.ב.c4 · 4 נק׳ · components

**Teacher's text:** סעיף ב: אלגוריתם נכון למציאת הערך המקסימלי (השכיחות הגבוהה ביותר) מתוך מערך המונים (ריצה מאינדקס 1 עד 20).

**Collapsed:** 1 checks · credit max 4 / 4

- **q3.ב.c4.c1** · credit · ladder · origin `planner`
  - אלגוריתם למציאת הערך המקסימלי (השכיחות הגבוהה ביותר) מתוך מערך המונים
  - `full` **4** — הלולאה עוברת על מערך המונים מאינדקס 1 עד 20 ומעדכנת את הערך המקסימלי בכל פעם שנמצא מונה גדול יותר
  - `p1` **2** — הלוגיקה למציאת הערך המקסימלי נכונה, אך הלולאה אינה רצה מאינדקס 1 עד 20
  - `absent` **0** — לא בוצע איתור נכון של הערך המקסימלי במערך המונים

### q3.ב.c5 · 3 נק׳ · components

**Teacher's text:** סעיף ב: לולאה נפרדת הסורקת ומדפיסה את כל האינדקסים שערכם שווה ל-maxCount (תמיכה בריבוי שכיחים) (ריצה מאינדקס 1 עד 20).

**Collapsed:** 1 checks · credit max 3 / 3

- **q3.ב.c5.c1** · credit · ladder · origin `planner`
  - לולאה נפרדת הסורקת ומדפיסה את כל האינדקסים שערכם שווה ל-maxCount
  - `full` **3** — קיימת לולאה נפרדת העוברת מאינדקס 1 עד 20 ומדפיסה את כל האינדקסים שערכם במערך המונים שווה ל-maxCount
  - `p1` **1.5** — הלולאה מדפיסה רק אינדקס אחד שערכו שווה ל-maxCount, ולא את כל האינדקסים שערכם שווה לו
  - `absent` **0** — לא קיימת לולאה נפרדת המדפיסה את האינדקסים שערכם שווה ל-maxCount

### q3.ב.c6 · 3 נק׳ · components

**Teacher's text:** סעיף ב: לולאה הסורקת ומדפיסה את האינדקסים שבהם המונה שווה ל-0 (ערכים שלא הופיעו) (ריצה מאינדקס 1 עד 20).

**Collapsed:** 1 checks · credit max 3 / 3

- **q3.ב.c6.c1** · credit · binary · origin `planner`
  - לולאה הסורקת ומדפיסה את האינדקסים שבהם המונה שווה ל-0
  - `full` **3** — קיימת לולאה העוברת מאינדקס 1 עד 20 ומדפיסה את כל האינדקסים שערכם במערך המונים שווה ל-0
  - `absent` **0** — לא קיימת לולאה המדפיסה את האינדקסים שערכם שווה ל-0

## q4.א — planner

### q4.א.c0 · 1 נק׳ · components

**Teacher's text:** סעיף א: חתימת הפעולה (ללא מילה static!) public double TotalEarnings()

**Collapsed:** 1 checks · credit max 1 / 1

- **q4.א.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה TotalEarnings
  - `full` **1** — הפעולה מוגדרת כ-public double TotalEarnings() ללא המילה static
  - `absent` **0** — הפעולה אינה מוגדרת כ-public double TotalEarnings() ללא static (חתימה שגויה או כוללת static)

### q4.א.c1 · 4 נק׳ · components

**Teacher's text:** סעיף א: החזרת החישוב: return this.seasonsPlayed * this.seasonSalary;

**Collapsed:** 1 checks · credit max 4 / 4

- **q4.א.c1.c1** · credit · ladder · origin `planner`
  - החזרת סך ההכנסות כמכפלת מספר העונות בשכר לעונה
  - שקילות: שימוש ישיר בתכונות באמצעות Get במקום גישה ישירה, שקול
  - `full` **4** — מוחזר ערך השווה למכפלת seasonsPlayed ב-seasonSalary
  - `p1` **2** — מכפלת seasonsPlayed ב-seasonSalary חושבה אך לא הוחזרה כערך הפעולה
  - `absent` **0** — לא מוחזר ערך המבוסס על מכפלת seasonsPlayed ב-seasonSalary

## q4.ב — fallback

> validator messages that sent this scope to repair/fallback:
> - V14: q4.ב.c4.f1 members span charge groups ['q4.ב:once:2aa8e26f', 'q4.ב:once:d754e274']
> - V18: q4.ב.c4.f1 anchor 'q4.ב.c4' is not a candidate of marker 'q4.ב.c7.m1'
> - V18: q4.ב.c4.f1 anchor 'q4.ב.c4' is not a candidate of marker 'q4.ב.c7.m2'

### q4.ב.c0 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: חתימת הפעולה (static!!) public static string[] TopEarners(BasketballPlayer[] arr, double amount)

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q4.ב.c0.c1** · credit · binary · origin `fallback`
  - סעיף ב: חתימת הפעולה (static!!) public static string[] TopEarners(BasketballPlayer[] arr, double amount
  - `full` **0.5** — קיים ותקין
  - `absent` **0** — לא נמצא

### q4.ב.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: משתנים משמעותיים + קוד קריא

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q4.ב.c1.c1** · credit · binary · origin `fallback`
  - סעיף ב: משתנים משמעותיים + קוד קריא
  - `full` **0.5** — קיים ותקין
  - `absent` **0** — לא נמצא

### q4.ב.c2 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ב: משתנה למניית השחקניות שמקיימות את התנאי + איפוס

**Collapsed:** 2 checks · credit max 1 / 1

- **q4.ב.c2.c1** · credit · binary · origin `fallback`
  - סעיף ב: משתנה למניית השחקניות שמקיימות את התנאי
  - `full` **0.5** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c2.c2** · credit · binary · origin `fallback`
  - איפוס
  - `full` **0.5** — קיים ותקין
  - `absent` **0** — לא נמצא

### q4.ב.c3 · 2 נק׳ · components

**Teacher's text:** סעיף ב: לולאה (A) על מערך השחקניות (לספירה נכונה וקידום מונה תקין) for (int i = 0; i < arr.Length; i++)

**Collapsed:** 1 checks · credit max 2 / 2

- **q4.ב.c3.c1** · credit · binary · origin `fallback`
  - סעיף ב: לולאה (A) על מערך השחקניות (לספירה נכונה וקידום מונה תקין
  - `full` **2** — קיים ותקין
  - `absent` **0** — לא נמצא

### q4.ב.c4 · 5 נק׳ · components · fixed

**Teacher's text:** סעיף ב:בתוך הלולאה (A) : בדיקה אם המערך במקום ה- i שונה מ- null (1 נקודות) זימון של פעולה פנימית TotalEarnings עבור המערך במקום ה- i (3 נקודות) (לקנוס פעם אחת אם לא בדקו אם arr[i]!=null , הערה למטה) השוואה אם התוצאה גבוהה מהפרמטר (1 נקודה) קידום המונה (1 נקודה) if (arr[i].TotalEarnings() > amount) count++;

**Collapsed:** 5 checks · credit max 5 / 5

- **q4.ב.c4.c1** · credit · binary · origin `fallback`
  - סעיף ב:בתוך הלולאה (A) : בדיקה אם המערך במקום ה- i שונה מ- null
  - `full` **1** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c4.c2** · credit · binary · origin `fallback`
  - זימון של פעולה פנימית TotalEarnings עבור המערך במקום ה- i
  - `full` **2** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c4.c3** · credit · binary · origin `fallback`
  - פעם אחת אם לא בדקו אם arr[i]!=null , הערה למטה) השוואה אם התוצאה גבוהה מהפרמטר
  - `full` **1** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c4.c4** · credit · binary · origin `fallback`
  - קידום המונה
  - `full` **1** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c4.f1** · fault · fault · origin `fallback` · requires `q4.ב.c4.c3` · group `q4.ב:once:2aa8e26f`
  - טעות שהמחוון מפרט
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — פעם אחת אם לא בדקו אם arr[i]!=null , הערה למטה ← `q4.ב.c4.m1`

### q4.ב.c5 · 3 נק׳ · components

**Teacher's text:** סעיף ב: הקצאת מערך ה-string החדש בדיוק בגודל שנספר (count)

**Collapsed:** 1 checks · credit max 3 / 3

- **q4.ב.c5.c1** · credit · binary · origin `fallback`
  - סעיף ב: הקצאת מערך ה-string החדש בדיוק בגודל שנספר (count
  - `full` **3** — קיים ותקין
  - `absent` **0** — לא נמצא

### q4.ב.c6 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ב: משתנה לאנדקס מערך השמות + איפוס

**Collapsed:** 2 checks · credit max 1 / 1

- **q4.ב.c6.c1** · credit · binary · origin `fallback`
  - סעיף ב: משתנה לאנדקס מערך השמות
  - `full` **0.5** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c6.c2** · credit · binary · origin `fallback`
  - איפוס
  - `full` **0.5** — קיים ותקין
  - `absent` **0** — לא נמצא

### q4.ב.c7 · 5 נק׳ · components · fixed

**Teacher's text:** סעיף ב: לולאה שנייה (B) נכונה (1 נקודה) בדיקה אם המערך במקום ה- i שונה מ- null(1 נקודות), להוריד רק פעם אחת שימוש ב-Getter לקבלת השם arr[i].GetName() (3 נקודות) השמה במערך החדש (1 נקודה) תוך קידום אינדקס נפרד (namesIndex)(1 נקודה) for (int i = 0; i < arr.Length; i++) { if (arr[i]!= null && arr[i].TotalEarnings() > amount) // אם טעו פה,להוריד 3 רק פעם 1 (יש גם זימון בלולאה א { namesArr[namesIndex] = arr[i].GetName(); // שימוש ב-Getter namesIndex++; // קידום האנדקס } }

**Collapsed:** 7 checks · credit max 5 / 5

- **q4.ב.c7.c1** · credit · binary · origin `fallback`
  - סעיף ב: לולאה שנייה (B) נכונה
  - `full` **0.5** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c7.c2** · credit · binary · origin `fallback`
  - בדיקה אם המערך במקום ה- i שונה מ- null
  - `full` **0.5** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c7.c3** · credit · binary · origin `fallback`
  - רק פעם אחת שימוש ב-Getter לקבלת השם arr[i].GetName
  - `full` **2** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c7.c4** · credit · binary · origin `fallback`
  - השמה במערך החדש
  - `full` **1** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c7.c5** · credit · binary · origin `fallback`
  - תוך קידום אינדקס נפרד (namesIndex
  - `full` **1** — קיים ותקין
  - `absent` **0** — לא נמצא
- **q4.ב.c7.f1** · fault · fault · origin `fallback` · group `q4.ב:once:2aa8e26f`
  - טעות שהמחוון מפרט
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — רק פעם אחת ← `q4.ב.c7.m1`
- **q4.ב.c7.f2** · fault · fault · origin `fallback` · group `q4.ב:once:d754e274`
  - טעות שהמחוון מפרט
  - `none` **0** — ללא הטעות הזו
  - `f1` **-3** — אם טעו פה, רק פעם 1 ← `q4.ב.c7.m2`

### q4.ב.c8 · 2 נק׳ · components

**Teacher's text:** סעיף ב: החזרת מערך השמות

**Collapsed:** 1 checks · credit max 2 / 2

- **q4.ב.c8.c1** · credit · binary · origin `fallback`
  - סעיף ב: החזרת מערך השמות
  - `full` **2** — קיים ותקין
  - `absent` **0** — לא נמצא

**Markers and dispositions:**

- `q4.ב.c4.m1` −1 · candidates ['q4.ב.c4'] · fault · «לקנוס פעם אחת אם לא בדקו אם arr[i]!=null , הערה למטה)»
- `q4.ב.c7.m1` −1 · candidates ['q4.ב.c7'] · fault · «להוריד רק פעם אחת»
- `q4.ב.c7.m2` −3 · candidates ['q4.ב.c7'] · fault · «אם טעו פה,להוריד 3 רק פעם 1»

**V19 candidates (telemetry):**
- `q4.ב.c4.f1` requires `q4.ב.c4.c3` — shared tokens ['arr', 'null']

**Telemetry:**
- planner_fallback q4.ב: repair_failed

## q5.א — planner

### q5.א.c0 · 1 נק׳ · components

**Teacher's text:** סעיף א: חתימת הפעולה (ללא מילה static!) public bool IsSimilarWorkshop(Workshop other) כל טעות פה להוריד 1

**Collapsed:** 1 checks · credit max 1 / 1

- **q5.א.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה IsSimilarWorkshop
  - `full` **1** — הפעולה מוגדרת כ-public bool IsSimilarWorkshop(Workshop other), ואינה מוגדרת כ-static
  - `absent` **0** — חתימת הפעולה אינה תואמת: חסר חלק מהחתימה (שם, טיפוס החזרה, טיפוס הפרמטר), או שהפעולה הוגדרה כ-static

### q5.א.c1 · 4 נק׳ · components

**Teacher's text:** סעיף א: החזרת החישוב: return this.name == other.GetName();

**Collapsed:** 2 checks · credit max 4 / 4

- **q5.א.c1.c1** · credit · binary · origin `planner`
  - ביצוע השוואת שוויון בין תכונה של הסדנה הנוכחית לתכונה המקבילה של הסדנה האחרת, והחזרת התוצאה הבוליאנית
  - `full` **2** — מתבצעת השוואת שוויון בין תכונות מקבילות משתי הסדנאות, והתוצאה הבוליאנית מוחזרת מהפעולה
  - `absent` **0** — לא מוחזרת תוצאת השוואה בוליאנית בין הסדנאות
- **q5.א.c1.c2** · credit · binary · origin `planner`
  - ההשוואה מתבצעת בין שמות שתי הסדנאות (name)
  - שקילות: גישה לשם באמצעות this.name וגם באמצעות GetName() תקפה משני הצדדים
  - `full` **2** — ההשוואה מתבצעת על תכונת השם (name) של שתי הסדנאות
  - `absent` **0** — ההשוואה מתבצעת על תכונה שאינה השם

**Interpretation notes:**
- השימוש בגישה ישירה לשדה (this.name) ובפעולת הגישה (GetName()) נחשב שקול, כפי שמופיע בפתרון לדוגמה.

## q5.ב — planner

### q5.ב.c0 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: חתימת הפעולה (לא static!!) public bool HandleNewWorkshop(Workshop ws)

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q5.ב.c0.c1** · credit · binary · origin `planner`
  - כתיבת חתימת הפעולה הנדרשת
  - `full` **0.5** — החתימה תואמת: public bool HandleNewWorkshop(Workshop ws), ואינה מוגדרת כ-static
  - `absent` **0** — החתימה אינה תואמת (שם, טיפוס החזרה או פרמטר שגויים, או הוגדרה כ-static)

### q5.ב.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: משתנים משמעותיים + קוד קריא

**Collapsed:** 2 checks · credit max 0.5 / 0.5

- **q5.ב.c1.c1** · credit · binary · origin `planner`
  - שימוש בשמות משתנים משמעותיים
  - `full` **0.25** — שמות המשתנים בקוד תיאוריים וברורים ומשקפים את תפקידם
  - `absent` **0** — שמות המשתנים אינם משמעותיים (למשל אותיות בודדות או שמות גנריים)
- **q5.ב.c1.c2** · credit · binary · origin `planner`
  - כתיבת קוד קריא
  - `full` **0.25** — הקוד מאורגן, עקבי וברור לקריאה
  - `absent` **0** — הקוד אינו קריא (מבנה מבולגן, חוסר עקביות, הזחה לקויה וכד')

**Interpretation notes:**
- משתנים משמעותיים וקוד קריא נבדקים כשני היבטים נפרדים, כיוון שכל אחד מהם עשוי להתקיים ללא השני.

### q5.ב.c2 · 6 נק׳ · components

**Teacher's text:** סעיף ב: ניהול נכון של לולאת החיפוש (ריצה עד countWorkshops ועצירה במידה ותנאי השילוב מתקיים. אם רצו עד Length ולא בדקו ששונה מ-Null , להוריד 2 אם לא ניהולו נכון את גבולות הלולאה להוריד 1

**Collapsed:** 3 checks · credit max 6 / 6

- **q5.ב.c2.c1** · credit · binary · origin `planner`
  - ריצת לולאת החיפוש עד countWorkshops ולא עד גודל המערך
  - `full` **3** — הלולאה רצה על תחום המדדים 0 עד countWorkshops (ולא עד גודל המערך)
  - `absent` **0** — הלולאה רצה עד גודל המערך (Length) במקום עד countWorkshops
- **q5.ב.c2.c2** · credit · binary · origin `planner`
  - עצירת החיפוש כאשר נמצאה סדנה מתאימה לשילוב
  - `full` **3** — החיפוש נעצר (למשל בעזרת return או דגל עצירה) כאשר נמצאה סדנה דומה שיש בה מקום לכל המשתתפים
  - `absent` **0** — החיפוש אינו נעצר בעת מציאת סדנה מתאימה לשילוב, או נעצר בעיתוי שגוי
- **q5.ב.c2.f1** · fault · fault · origin `planner` · requires `q5.ב.c2.c1`
  - ניהול שגוי של גבולות לולאת החיפוש
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הלולאה רצה עד גודל המערך (Length) במקום עד countWorkshops, ללא בדיקה שהאיבר שונה מ-Null ← `q5.ב.c2.m1`

**Interpretation notes:**
- ניהול הלולאה פוצל לשני רכיבים נפרדים: תחום הריצה של הלולאה, ועצירתה בעת מציאת התאמה, בהתאם לשני המרכיבים שמנתה ההנחיה.
- ההנחיה הכללית 'אם לא ניהולו נכון את גבולות הלולאה' נקראה כחזרה על אותו כשל שתואר במפורש (ריצה עד Length ללא בדיקת Null), ולכן אוחדה עמו.
- ההנחיה הכללית על ניהול שגוי של גבולות הלולאה חוזרת על אותו כשל שתואר במפורש כריצה עד Length ללא בדיקת Null, ולכן אוחדה עמו.

### q5.ב.c3 · 2 נק׳ · components

**Teacher's text:** סעיף ב: זימון נכון של הפעולה מסעיף א' על איבר מהמערך: this.workshops[i].IsSimilarWorkshop(ws)

**Collapsed:** 1 checks · credit max 2 / 2

- **q5.ב.c3.c1** · credit · binary · origin `planner`
  - זימון הפעולה IsSimilarWorkshop מסעיף א' על איבר מהמערך
  - `full` **2** — הפעולה IsSimilarWorkshop מסעיף א' מוזמנת על איבר מהמערך (workshops[i]) עם הסדנה החדשה כפרמטר
  - `absent` **0** — הפעולה מסעיף א' אינה מוזמנת על איבר מהמערך, או שלא נעשה בה שימוש כלל

### q5.ב.c4 · 5 נק׳ · components · fixed

**Teacher's text:** סעיף ב: בדיקת תנאי הקיבולת (קטן או שווה ל-40) ועדכון נכון של התכונה people בעזרת SetPeople ו-GetPeople הבדיקת הקיבולת עצמה 1 נקודה אם לא השתמשו בפעולה הפנימית להוריד 2, אם לא השתמשו באף אחת מהן להוריד 3 אם חישבו נכון את סה"כ ולא עדכנו את התכונה (כמובן ע"י setter) להוריד 2

**Collapsed:** 3 checks · credit max 5 / 5

- **q5.ב.c4.c1** · credit · binary · origin `planner`
  - בדיקת תנאי הקיבולת שסך המשתתפים בשתי הסדנאות אינו עולה על 40
  - `full` **1** — נבדק אם סכום המשתתפים בסדנה הקיימת ובסדנה החדשה אינו עולה על 40
  - `absent` **0** — לא נבדק תנאי הקיבולת בין הסדנה הקיימת לחדשה, או שהתנאי שגוי
- **q5.ב.c4.c2** · credit · binary · origin `planner`
  - עדכון נכון של התכונה people בעזרת הפעולות הפנימיות SetPeople ו-GetPeople
  - `full` **4** — סכום המשתתפים חושב באמצעות GetPeople ועודכן בתכונה people באמצעות SetPeople
  - `absent` **0** — התכונה people לא עודכנה, או עודכנה שלא באמצעות הפעולות הפנימיות Get/Set
- **q5.ב.c4.f1** · fault · fault · origin `planner` · requires `q5.ב.c4.c2`
  - שימוש בפעולות הפנימיות Get/Set לחישוב ועדכון מספר המשתתפים
  - `none` **0** — ללא הטעות הזו
  - `f1` **-2** — נעשה שימוש רק באחת מהפעולות הפנימיות (Get או Set), ולא בשתיהן ← `q5.ב.c4.m1`
  - `f2` **-3** — לא נעשה שימוש כלל בפעולות הפנימיות Get ו-Set (גישה ישירה לתכונה) ← `q5.ב.c4.m2`
  - `f3` **-2** — סכום המשתתפים חושב נכון באמצעות GetPeople, אך התכונה people לא עודכנה באמצעות SetPeople ← `q5.ב.c4.m3`

**Interpretation notes:**
- בדיקת הקיבולת ועדכון התכונה נבדקים כשני רכיבים נפרדים בהתאם לחלוקת הטקסט המקורי לשני חלקים.

### q5.ב.c5 · 3 נק׳ · components

**Teacher's text:** סעיף ב: הוספת הסדנה החדשה למקום ה-countWorkshops וקידום המונה ב-1 במידה ולא בוצע איחוד והמערך אינו מלא

**Collapsed:** 1 checks · credit max 3 / 3

- **q5.ב.c5.c1** · credit · ladder · origin `planner`
  - הוספת הסדנה החדשה למקום הראשון הפנוי וקידום מונה הסדנאות
  - `full` **3** — הסדנה החדשה נוספה למקום ה-countWorkshops במערך והמונה countWorkshops קודם ב-1
  - `p1` **1.5** — הסדנה החדשה נוספה למקום הנכון במערך, אך המונה countWorkshops לא קודם
  - `absent` **0** — הסדנה החדשה לא נוספה למערך כלל

### q5.ב.c6 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ב: החזרת הערכים הבוליאניים הנכונים (true / false) בכל אחד מהתרחישים 1.5 ל-true, 1.5 ל-false

**Collapsed:** 2 checks · credit max 3 / 3

- **q5.ב.c6.c1** · credit · binary · origin `planner`
  - החזרת false בתרחיש שבו המערכת מלאה ולא ניתן להוסיף סדנה חדשה
  - `full` **1.5** — מוחזר false כאשר לא בוצע איחוד, לא בוצעה הוספה, והמערכת מלאה
  - `absent` **0** — לא מוחזר false בתרחיש שהמערכת מלאה, או מוחזר ערך שגוי
- **q5.ב.c6.c2** · credit · binary · origin `planner`
  - החזרת true בתרחישים שבהם בוצע איחוד עם סדנה קיימת או הוספת סדנה חדשה בהצלחה
  - `full` **1.5** — מוחזר true הן כאשר בוצע איחוד עם סדנה דומה והן כאשר נוספה סדנה חדשה בהצלחה
  - `absent` **0** — לא מוחזר true באחד מהתרחישים המצליחים, או מוחזר ערך שגוי

**Interpretation notes:**
- הפיצול בין שני הרכיבים פורש לפי ההקשר: הרכיב שאינו מציין תרחיש במפורש יוחס להחזרת false (מערכת מלאה), והרכיב המזכיר 'ל-true' יוחס להחזרת true (איחוד או הוספה).

**Markers and dispositions:**

- `q5.ב.c2.m1` −2 · candidates ['q5.ב.c2'] · fault · «להוריד 2»
- `q5.ב.c2.m2` −1 · candidates ['q5.ב.c2'] · merged → `q5.ב.c2.m1` — ההנחיה הכללית על ניהול שגוי של גבולות הלולאה חוזרת על אותו כשל שתואר במפורש כריצה עד Length ללא בדיקת Null, ולכן אוחדה עמו. · «אם לא ניהולו נכון את גבולות הלולאה להוריד 1»
- `q5.ב.c4.m1` −2 · candidates ['q5.ב.c4'] · fault · «אם לא השתמשו בפעולה הפנימית להוריד 2»
- `q5.ב.c4.m2` −3 · candidates ['q5.ב.c4'] · fault · «אם לא השתמשו באף אחת מהן להוריד 3»
- `q5.ב.c4.m3` −2 · candidates ['q5.ב.c4'] · fault · «להוריד 2»

## q6 — planner

### q6.c0 · 1 נק׳ · components

**Teacher's text:** חתימת הפעולה (עם המילה static!) כל טעות להוריד 1

**Collapsed:** 1 checks · credit max 1 / 1

- **q6.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה כנדרש, כולל המילה static
  - `full` **1** — הפעולה מוגדרת עם המילה static וחתימה התואמת את הנדרש (public static int[] AnalyzeMechina(int[] studentsMechina))
  - `absent` **0** — חתימת הפעולה שגויה, לרבות היעדר המילה static או פרמטרים/סוג החזרה שאינם תואמים

### q6.c1 · 1 נק׳ · components · fixed

**Teacher's text:** משתנים משמעותיים + קוד קריא

**Collapsed:** 2 checks · credit max 1 / 1

- **q6.c1.c1** · credit · binary · origin `planner`
  - שימוש במשתנים בעלי שמות משמעותיים
  - `full` **0.5** — שמות המשתנים בקוד משקפים את תפקידם
  - `absent` **0** — שמות המשתנים אינם משמעותיים
- **q6.c1.c2** · credit · binary · origin `planner`
  - כתיבת קוד קריא
  - `full` **0.5** — הקוד כתוב בצורה קריאה וברורה
  - `absent` **0** — הקוד אינו קריא

### q6.c2 · 2 נק׳ · components

**Teacher's text:** יצירה של מערך מונים עם הקצאה נכונה (לפחות בגודל 31)

**Collapsed:** 1 checks · credit max 2 / 2

- **q6.c2.c1** · credit · binary · origin `planner`
  - יצירת מערך מונים בהקצאה נכונה
  - `full` **2** — נוצר מערך מונים בגודל 31 לפחות
  - `absent` **0** — לא נוצר מערך מונים בגודל מתאים

### q6.c3 · 1 נק׳ · components

**Teacher's text:** איפוס מערך המונים או הערה שיש איפוס ע"י השפה

**Collapsed:** 1 checks · credit max 1 / 1

- **q6.c3.c1** · credit · binary · origin `planner`
  - איפוס מערך המונים או ציון שהאיפוס נעשה ע"י השפה
  - `full` **1** — מערך המונים אופס בפועל או שצוינה הערה שהשפה מאפסת אותו כברירת מחדל
  - `absent` **0** — אין איפוס של מערך המונים ואין הערה מתאימה

### q6.c4 · 2 נק׳ · components

**Teacher's text:** סריקה נכונה של מערך הקלט לעדכון מונים

**Collapsed:** 2 checks · credit max 2 / 2

- **q6.c4.c1** · credit · binary · origin `planner`
  - מעבר על מערך הקלט
  - `full` **1** — מתבצע מעבר על כל תאי מערך הקלט studentsMechina
  - `absent` **0** — אין מעבר על מערך הקלט
- **q6.c4.c2** · credit · binary · origin `planner`
  - עדכון מונה המכינה המתאימה לכל תלמיד
  - `full` **1** — בכל איטרציה מתעדכן התא במערך המונים באינדקס התואם למספר המכינה של התלמיד
  - `absent` **0** — עדכון המונים אינו מתבצע לפי מספר המכינה של כל תלמיד

**Interpretation notes:**
- הסריקה של מערך הקלט (המכניזם) הופרדה מהעדכון של התא הנכון במערך המונים (היעד), כדי לאפשר זיהוי מקרה שבו נסרק המערך הנכון אך העדכון מתבצע באינדקס שגוי.

### q6.c5 · 4 נק׳ · components

**Teacher's text:** סריקת מערך המונים למציאת המכינה (האינדקס) עם המונה הגבוה ביותר (4 נקודות) ו

**Collapsed:** 1 checks · credit max 4 / 4

- **q6.c5.c1** · credit · ladder · origin `planner`
  - סריקת מערך המונים למציאת המכינה עם מספר הנרשמים הגבוה ביותר
  - `full` **4** — נסרק מערך המונים ונשמרים גם המונה המקסימלי וגם האינדקס (מספר המכינה) המתאים לו
  - `p1` **2** — מזוהה המונה המקסימלי אך האינדקס (מספר המכינה) המתאים לו אינו נשמר בהתאמה נכונה
  - `absent` **0** — לא נמצאה המכינה בעלת מספר הנרשמים הגבוה ביותר

**Interpretation notes:**
- נבחר מצב ביניים קונקרטי שבו המונה המקסימלי מזוהה נכון אך האינדקס המתאים אינו נשמר, כפירוק היחיד הניתן לזיהוי במסגרת דרישה זו.

### q6.c6 · 2 נק׳ · components

**Teacher's text:** הדפסת מספר המכינה בעלת כמות מקסימלית (ולא כמות התלמידים) אם הדפיסו את הכמות להוריד 2 (או 1?)

**Collapsed:** 2 checks · credit max 2 / 2

- **q6.c6.c1** · credit · binary · origin `planner`
  - הדפסת מספר המכינה בעלת כמות התלמידים המקסימלית
  - `full` **2** — מודפס מספר המכינה (האינדקס) שאליה נרשמו הכי הרבה תלמידים
  - `absent` **0** — לא מודפס מספר המכינה בעלת כמות מקסימלית
- **q6.c6.f1** · fault · fault · origin `planner` · requires `q6.c6.c1`
  - הדפסת כמות התלמידים במקום מספר המכינה
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — מודפסת כמות התלמידים שנרשמו למכינה הפופולרית במקום מספרה ← `q6.c6.m1`

### q6.c7 · 4 נק׳ · components · fixed

**Teacher's text:** חישוב גודל מערך היעד: סריקת מערך המונים(1 נק'), ספירת התאים שגדולים מ-0 (1 נקודה), ויצירה והקצאת מערך חדש בגודל count * 2 (2 נקודות)

**Collapsed:** 3 checks · credit max 4 / 4

- **q6.c7.c1** · credit · binary · origin `planner`
  - סריקת מערך המונים לצורך חישוב גודל מערך היעד
  - `full` **1** — מתבצעת סריקה של מערך המונים לצורך קביעת גודל מערך התוצאה
  - `absent` **0** — אין סריקה של מערך המונים לצורך חישוב גודל מערך היעד
- **q6.c7.c2** · credit · binary · origin `planner`
  - ספירת התאים שגדולים מ-0
  - `full` **1** — נספרים תאי מערך המונים שערכם גדול מ-0
  - `absent` **0** — אין ספירה של תאי מערך המונים שערכם גדול מ-0
- **q6.c7.c3** · credit · binary · origin `planner`
  - יצירה והקצאת מערך היעד בגודל count * 2
  - `full` **2** — נוצר מערך חדש בגודל השווה לפעמיים מספר המכינות הפעילות
  - `absent` **0** — לא נוצר מערך בגודל המתאים למספר המכינות הפעילות כפול 2

### q6.c8 · 8 נק׳ · components

**Teacher's text:** בניית מערך התוצאה: מילוי נכון של המערך החדש בזוגות: קודם את result[resIndex] = i ומיד לאחר מכן result[resIndex+1] = counters[i] תוך קידום ידני תקין של אינדקס מערך היעד ב-2 בכל פעם.

**Collapsed:** 3 checks · credit max 8 / 8

- **q6.c8.c1** · credit · binary · origin `planner`
  - כתיבת מספר המכינה בתא הראשון של הזוג
  - `full` **2.75** — בכל זוג נכתב מספר המכינה בתא הראשון של הזוג במערך התוצאה
  - `absent` **0** — מספר המכינה אינו נכתב בתא הראשון של הזוג
- **q6.c8.c2** · credit · binary · origin `planner`
  - כתיבת מספר התלמידים הרשומים למכינה בתא השני של הזוג
  - `full` **2.75** — בכל זוג נכתב מספר התלמידים שנרשמו למכינה מיד לאחר מספר המכינה
  - `absent` **0** — מספר התלמידים אינו נכתב בתא השני של הזוג
- **q6.c8.c3** · credit · binary · origin `planner`
  - קידום אינדקס מערך היעד ב-2 בכל זוג
  - `full` **2.5** — האינדקס במערך התוצאה מתקדם ב-2 לאחר כל זוג שנכתב
  - `absent` **0** — האינדקס במערך התוצאה אינו מתקדם נכון ב-2 לאחר כל זוג

**Interpretation notes:**
- המילוי בזוגות פוצל לשלושה רכיבים עצמאיים — מספר המכינה, מספר התלמידים והתקדמות האינדקס — כדי לאפשר זיהוי מקרה שבו חלק מהם נכון וחלק שגוי.

**Markers and dispositions:**

- `q6.c6.m1` −1 · candidates ['q6.c6'] · fault · «אם הדפיסו את הכמות להוריד 2 (או 1?)»

