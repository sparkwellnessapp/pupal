# bagrut_899371 — plan/v6 render

- plan_hash `4b6447f8db75645c…` · config_hash `8401b943980225ea…` · pack `computer_science@v1`
- stage 1 `plan-compiler/v2.0+stage1-v6.0` · 61 criteria · 109 checks
- scope origins: q1.א.1=compiled, q1.א.2=planner, q1.ב.1=planner, q1.ב.2=planner, q2.א=planner, q2.ב=planner, q3.א=planner, q3.ב=planner, q4.א=planner, q4.ב=repaired, q5.א=repaired, q5.ב=planner, q6=planner

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

- **q1.א.2.c0.c1** · credit · binary · origin `planner`
  - הבנת הבדיקה של "מחלק ללא שארית"
  - `full` **1.5** — מצוין שהבדיקה בוחנת האם x מתחלק באיבר ללא שארית, כלומר שהאיבר הוא מחלק של x
  - `absent` **0** — אין התייחסות לכך שהבדיקה בוחנת חלוקה ללא שארית של x באיבר

### q1.א.2.c1 · 1.5 נק׳ · components · fixed

**Teacher's text:** התייחסות לתנאי שהאיבר שונה מ-1 ומ-x עצמו  0.5 נק'

**Collapsed:** 2 checks · credit max 1.5 / 1.5

- **q1.א.2.c1.c1** · credit · binary · origin `planner`
  - התייחסות לתנאי שהאיבר שונה מ-1
  - `full` **0.5** — מצוין שהאיבר הנבדק צריך להיות שונה מ-1
  - `absent` **0** — אין התייחסות לכך שהאיבר צריך להיות שונה מ-1
- **q1.א.2.c1.c2** · credit · binary · origin `planner`
  - התייחסות לתנאי שהאיבר שונה מ-x עצמו
  - `full` **1** — מצוין שהאיבר הנבדק צריך להיות שונה מ-x עצמו
  - `absent` **0** — אין התייחסות לכך שהאיבר צריך להיות שונה מ-x עצמו

## q1.ב.1 — planner

### q1.ב.1.c0 · 6 נק׳ · components

**Teacher's text:** ניקוד: 6 נקודות

**Collapsed:** 1 checks · credit max 6 / 6

- **q1.ב.1.c0.c1** · credit · ladder · origin `planner`
  - ציון הערך המוחזר מהפעולה What(arr)B
  - `full` **6** — הערך המוחזר שנכתב הוא 76, בהתאם לסכימת הערכים במערך שעבורם check(arr,i) מתקיים
  - `p1` **3** — הודגמה סכימה של הערכים שעבורם check(arr,i) מתקיים, לפי הסדר הנכון, אך התוצאה הסופית שגויה עקב טעות חישוב
  - `absent` **0** — הערך המוחזר שנכתב שונה מ-76 ואינו תואם לסכימת הערכים שעבורם check(arr,i) מתקיים

## q1.ב.2 — planner

### q1.ב.2.c0 · 2 נק׳ · components

**Teacher's text:** זיהוי שמדובר בפעולת סכימה של איברי המערך – 2 נק'

**Collapsed:** 1 checks · credit max 2 / 2

- **q1.ב.2.c0.c1** · credit · binary · origin `planner`
  - זיהוי שמדובר בפעולת סכימה של איברי המערך
  - `full` **2** — זוהה שהפעולה מחשבת ומחזירה סכום של איברים מתוך המערך
  - `absent` **0** — לא זוהה שמדובר בפעולת סכימה של איברי המערך

### q1.ב.2.c1 · 2 נק׳ · components

**Teacher's text:** הגדרה נכונה של תנאי הסכימה (איברים שיש להם מחלק אחר במערך) 2  נק'

**Collapsed:** 1 checks · credit max 2 / 2

- **q1.ב.2.c1.c1** · credit · ladder · origin `planner`
  - הגדרה נכונה של תנאי הסכימה (איברים שיש להם מחלק אחר במערך)
  - `full` **2** — הוגדר שהאיברים הנסכמים הם אלו שיש להם לפחות מחלק אחד הנמצא בתוך המערך עצמו, פרט ל-1 ולמספר עצמו
  - `p1` **1** — הוגדר שהאיברים הנסכמים הם אלו שיש להם מחלק, אך לא צוין שהמחלק חייב להימצא בתוך המערך עצמו
  - `absent` **0** — לא הוגדר תנאי הסכימה כלל, או שהתנאי שהוגדר אינו קשור למחלקים בתוך המערך

## q2.א — planner

### q2.א.c0 · 1 נק׳ · components

**Teacher's text:** סעיף א: חתימת הפעולה public static bool IsMirror(int[] arr)

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.א.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה IsMirror
  - שקילות: שם הפרמטר עצמו יכול להיות שונה מ-arr, כל עוד הסוג והתפקיד תואמים
  - `full` **1** — הפעולה מוגדרת עם החתימה public static bool IsMirror(int[] arr), כולל שם, סוג החזרה ופרמטר מהסוג הנכון
  - `absent` **0** — החתימה חסרה או שונה מהנדרש (שם הפעולה, סוג ההחזרה או סוג הפרמטר אינם תואמים)

### q2.א.c1 · 0.5 נק׳ · components

**Teacher's text:** שמות משתנים משמעותיים וקוד קריא

**Collapsed:** 2 checks · credit max 0.5 / 0.5

- **q2.א.c1.c1** · credit · binary · origin `planner`
  - שימוש בשמות משתנים משמעותיים
  - `full` **0.25** — שמות המשתנים בקוד משקפים את תפקידם (למשל target, found)
  - `absent` **0** — שמות המשתנים אינם משקפים את תפקידם (למשל שמות גנריים כמו a, x1)
- **q2.א.c1.c2** · credit · binary · origin `planner`
  - כתיבת קוד קריא
  - `full` **0.25** — מבנה הקוד מסודר וברור לקריאה
  - `absent` **0** — מבנה הקוד אינו מסודר וקשה לקריאה

### q2.א.c2 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף א: בדיקה האם המערך לא באורך זוגי, להחזיר false (if נק' 1, החזרת false נקודה 1) if (arr.Length % 2 != 0) return false;

**Collapsed:** 2 checks · credit max 2 / 2

- **q2.א.c2.c1** · credit · binary · origin `planner`
  - בדיקה האם אורך המערך אינו זוגי
  - שקילות: בדיקה שקולה כגון arr.Length % 2 == 1 תקפה
  - `full` **1** — קיימת בדיקה מפורשת האם אורך המערך אי-זוגי, למשל if (arr.Length % 2 != 0)
  - `absent` **0** — אין בדיקה של זוגיות אורך המערך
- **q2.א.c2.c2** · credit · binary · origin `planner`
  - החזרת false כאשר אורך המערך אינו זוגי
  - `full` **1** — כאשר אורך המערך אי-זוגי מוחזר false
  - `absent` **0** — לא מוחזר false כאשר אורך המערך אי-זוגי

### q2.א.c3 · 1.5 נק׳ · components

**Teacher's text:** סעיף א: לולאה על המערך for (int i = 0; i < arr.Length; i++)

**Collapsed:** 1 checks · credit max 1.5 / 1.5

- **q2.א.c3.c1** · credit · binary · origin `planner`
  - לולאה העוברת על כל איברי המערך
  - שקילות: לולאת while או foreach השקולה במעבר על כל האיברים תקפה
  - `full` **1.5** — קיימת לולאה שעוברת על כל איברי המערך מתחילתו ועד סופו
  - `absent` **0** — אין לולאה שעוברת על כל איברי המערך

### q2.א.c4 · 4 נק׳ · components

**Teacher's text:** סעיף א: בתוך הלולאה: חיפוש אחר המספר הנגדי של arr[i]: int target = -arr[i]; bool found = false; for (int j = 0; j < arr.Length && found == false; j++) { if (arr[j] == target) { found = true; } }

**Collapsed:** 2 checks · credit max 4 / 4

- **q2.א.c4.c1** · credit · binary · origin `planner`
  - חישוב המספר הנגדי של האיבר הנוכחי
  - שקילות: חישוב שקול כגון 0 - arr[i] תקף
  - `full` **2** — מחושב ונשמר הערך הנגדי של arr[i], כגון target = -arr[i]
  - `absent` **0** — לא מחושב הערך הנגדי של האיבר הנוכחי
- **q2.א.c4.c2** · credit · binary · origin `planner`
  - חיפוש המספר הנגדי במערך וסימון האם נמצא
  - שקילות: עצירה מוקדמת באמצעות break במקום דגל found שקולה
  - `full` **2** — קיימת לולאה פנימית העוברת על המערך ובודקת עבור כל איבר האם הוא שווה לערך המבוקש, ומסמנת זאת (למשל באמצעות found)
  - `absent` **0** — אין לולאה פנימית שמחפשת את הערך המבוקש במערך ומסמנת האם נמצא

**Interpretation notes:**
- רכיב החיפוש נבדק במונחי עצמו גם כאשר הערך המבוקש שגוי, שכן הטעות בחישוב הערך המבוקש כבר מחויבת ברכיב הנפרד.

### q2.א.c5 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף א: מחוץ ללואה אם לא מצאנו את המספר הנגדי (1 נקודה) להחזיר false (1 נקודה)

**Collapsed:** 2 checks · credit max 2 / 2

- **q2.א.c5.c1** · credit · binary · origin `planner`
  - בדיקה מחוץ ללולאה האם המספר הנגדי לא נמצא
  - `full` **1** — קיימת בדיקה מחוץ ללולאה הפנימית האם found נשאר false, כלומר המספר הנגדי לא נמצא
  - `absent` **0** — אין בדיקה מחוץ ללולאה האם המספר הנגדי לא נמצא
- **q2.א.c5.c2** · credit · binary · origin `planner`
  - החזרת false כאשר המספר הנגדי לא נמצא
  - `full` **1** — כאשר המספר הנגדי לא נמצא מוחזר false
  - `absent` **0** — לא מוחזר false כאשר המספר הנגדי לא נמצא

### q2.א.c6 · 1 נק׳ · components

**Teacher's text:** סעיף א: שורה אחרונה: להחזיר true

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.א.c6.c1** · credit · binary · origin `planner`
  - החזרת true בסיום הפעולה
  - `full` **1** — לאחר שהלולאה הראשית הסתיימה בהצלחה מוחזר true
  - `absent` **0** — לא מוחזר true בסיום הבדיקות

## q2.ב — planner

### q2.ב.c0 · 1 נק׳ · components

**Teacher's text:** סעיף ב: חתימת הפעולה public static void ArrangeMirror(int[] arr)

**Collapsed:** 1 checks · credit max 1 / 1

- **q2.ב.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה public static void ArrangeMirror(int[] arr)
  - `full` **1** — הפעולה מוגדרת עם החתימה public static void ArrangeMirror(int[] arr)
  - `absent` **0** — חתימת הפעולה חסרה או שגויה

### q2.ב.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: שמות משתנים משמעותיים וקוד קריא

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q2.ב.c1.c1** · credit · binary · origin `planner`
  - שמות משתנים משמעותיים וקוד קריא
  - `full` **0.5** — שמות המשתנים בקוד משמעותיים והקוד כתוב באופן קריא
  - `absent` **0** — שמות המשתנים אינם משמעותיים או הקוד אינו קריא

### q2.ב.c2 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב: יצירת מערך עזר באותו גודל של הפרמטר + משתנה למציין של מערך העזר + אתחול ל-0 int[] temp = new int[arr.Length]; // הקצאת מערך עזר באותו הגודל int tempIndex = 0;

**Collapsed:** 3 checks · credit max 2 / 2

- **q2.ב.c2.c1** · credit · binary · origin `planner`
  - יצירת מערך עזר באותו גודל של הפרמטר
  - `full` **1** — נוצר מערך עזר בגודל השווה לגודל המערך שהתקבל כפרמטר
  - `absent` **0** — לא נוצר מערך עזר, או שנוצר בגודל שאינו תואם את הפרמטר
- **q2.ב.c2.c2** · credit · binary · origin `planner`
  - משתנה למציין של מערך העזר
  - `full` **0.5** — הוגדר משתנה נפרד המשמש כמציין/אינדקס למערך העזר
  - `absent` **0** — לא הוגדר משתנה נפרד לאינדקס של מערך העזר
- **q2.ב.c2.c3** · credit · binary · origin `planner`
  - אתחול משתנה האינדקס לאפס
  - `full` **0.5** — משתנה האינדקס של מערך העזר אותחל לאפס
  - `absent` **0** — משתנה האינדקס של מערך העזר לא אותחל לאפס

### q2.ב.c3 · 4.5 נק׳ · components · fixed

**Teacher's text:** סעיף ב: סריקת המערך הפרמטר ומציאת המספרים החיוביים והעתקם למערך הזמני פלוס קידום האנדקס לולאה על המערך הפרמטר 0.5 אם המספר הנוכחי במערך הפרמטר חיובי 2 העתק המספר החיובי למערך העזר 1 קידום האנדקס 1 for (int i = 0; i < arr.Length; i++) { if (arr[i] > 0) // אם המספר חיובי { temp[tempIndex] = arr[i]; // העתקת המספר החיובי למערך העזר tempIndex++;

**Collapsed:** 4 checks · credit max 4.5 / 4.5

- **q2.ב.c3.c1** · credit · binary · origin `planner`
  - לולאה הסורקת את כל איברי המערך שהתקבל כפרמטר
  - `full` **0.5** — קיימת לולאה שעוברת על כל איברי המערך הפרמטר
  - `absent` **0** — אין לולאה שסורקת את כל איברי המערך הפרמטר
- **q2.ב.c3.c2** · credit · binary · origin `planner`
  - בדיקה אם המספר הנוכחי במערך הפרמטר חיובי
  - `full` **2** — בתוך הלולאה נבדק אם האיבר הנוכחי במערך הפרמטר חיובי
  - `absent` **0** — אין בדיקה אם האיבר הנוכחי חיובי
- **q2.ב.c3.c3** · credit · binary · origin `planner`
  - העתקת המספר החיובי למערך העזר
  - `full` **1** — המספר החיובי מועתק למערך העזר
  - `absent` **0** — המספר החיובי אינו מועתק למערך העזר
- **q2.ב.c3.c4** · credit · binary · origin `planner`
  - קידום האנדקס של מערך העזר
  - `full` **1** — האינדקס של מערך העזר מתקדם בעת ההעתקה
  - `absent` **0** — האינדקס של מערך העזר לא מתקדם בעת ההעתקה

### q2.ב.c4 · 3 נק׳ · components

**Teacher's text:** סעיף ב: בתוך הלולאה: אופציה 1: מניחים שהמערך פרמטר הוא מערך מראה (כפי שכתוב בשאלה) ופשוט מבצעים: temp[tempIndex] = -arr[i]; tempIndex++; אופציה 2: מציאת המספר הנגדי המתאים (ע"י עוד לולאה) והשמתו בצמוד למספר שנמצא (באינדקס העוקב). bool found = false; for (int j = 0; j < arr.Length && found == false ; j++) { if (arr[j] == -arr[i]) { temp[tempIndex] = arr[j]; // העתקת המספר השלילי מיד לאחר החיובי tempIndex++; found = true; // מצאנו את הנגדי היחיד, יוצאים מהלולאה הפנימית } }

**Collapsed:** 1 checks · credit max 3 / 3

- **q2.ב.c4.c1** · credit · binary · origin `planner`
  - השמת המספר השלילי הנגדי בצמוד למספר החיובי במערך העזר
  - שקילות: מותר להניח שהמערך פרמטר הוא מערך מראה ולהשמיא את הנגדי ישירות (-arr[i]), וכן מותר לחפש את המספר הנגדי בלולאה נוספת ולהשמיאו — שתי הדרכים שקולות
  - `full` **3** — המספר השלילי הנגדי למספר החיובי מושם במערך העזר מיד לאחר המספר החיובי
  - `absent` **0** — המספר השלילי הנגדי אינו מושם במערך העזר בצמוד למספר החיובי

### q2.ב.c5 · 2 נק׳ · components

**Teacher's text:** סעיף ב: העתקה מסודרת של כל איברי מערך העזר חזרה למערך המקורי שנתקבל כפרמטר for (int i = 0; i < arr.Length; i++) arr[i] = temp[i];

**Collapsed:** 1 checks · credit max 2 / 2

- **q2.ב.c5.c1** · credit · binary · origin `planner`
  - העתקה מסודרת של איברי מערך העזר חזרה למערך המקורי
  - `full` **2** — כל איברי מערך העזר מועתקים בסדרם בחזרה למערך שהתקבל כפרמטר
  - `absent` **0** — איברי מערך העזר אינם מועתקים בחזרה למערך הפרמטר, או מועתקים בסדר שגוי

## q3.א — planner

### q3.א.c0 · 0.5 נק׳ · components

**Teacher's text:** סעיף א: חתימת הפעולה public static int[] DiceStatistics(int[] arr)

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q3.א.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה
  - `full` **0.5** — הפעולה מוגדרת בדיוק כ- public static int[] DiceStatistics(int[] arr)
  - `absent` **0** — חתימת הפעולה אינה תואמת את החתימה הנדרשת

### q3.א.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף א: משתנים משמעותיים + קוד קריא

**Collapsed:** 2 checks · credit max 0.5 / 0.5

- **q3.א.c1.c1** · credit · binary · origin `planner`
  - בחירת שמות משתנים משמעותיים
  - `full` **0.25** — שמות המשתנים בקוד מבטאים את תפקידם
  - `absent` **0** — שמות המשתנים אינם משמעותיים או אינם מבטאים את תפקידם
- **q3.א.c1.c2** · credit · binary · origin `planner`
  - כתיבת קוד קריא
  - `full` **0.25** — הקוד כתוב בצורה מסודרת וקריאה
  - `absent` **0** — הקוד אינו קריא או אינו מסודר

### q3.א.c2 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף א: הגדרה והקצאה נכונה של מערך המונים בגודל 21 + איפוס מערך מונים

**Collapsed:** 2 checks · credit max 2 / 2

- **q3.א.c2.c1** · credit · binary · origin `planner`
  - הגדרה והקצאה נכונה של מערך המונים בגודל 21
  - `full` **1** — מוגדר ומוקצה מערך מונים בגודל 21 (אינדקסים 0 עד 20)
  - `absent` **0** — מערך המונים אינו מוגדר או אינו מוקצה בגודל הנכון
- **q3.א.c2.c2** · credit · binary · origin `planner`
  - איפוס מערך מונים
  - שקילות: איפוס במובלע באמצעות ברירת המחדל של השפה, שממלאת מערך מספרים חדש באפסים, נחשב מספק גם ללא איפוס מפורש בלולאה
  - `full` **1** — מערך המונים מאופס בכל תאיו לפני תחילת הספירה
  - `absent` **0** — מערך המונים אינו מאופס

### q3.א.c3 · 2 נק׳ · components

**Teacher's text:** סעיף א: לולאה הסורקת את מערך הקלט

**Collapsed:** 2 checks · credit max 2 / 2

- **q3.א.c3.c1** · credit · binary · origin `planner`
  - לולאה העוברת על כל איברי המערך
  - `full` **1** — קיימת לולאה העוברת על כל איברי המערך מתחילתו ועד סופו
  - `absent` **0** — אין לולאה הסורקת את איברי המערך
- **q3.א.c3.c2** · credit · binary · origin `planner`
  - סריקת מערך הקלט arr
  - `full` **1** — הלולאה סורקת את מערך הקלט arr שהתקבל כפרמטר
  - `absent` **0** — הלולאה סורקת מערך שאינו מערך הקלט arr

### q3.א.c4 · 3 נק׳ · components

**Teacher's text:** סעיף א: בתוך הלולאה, קידום תקין של המונה המתאים int diceValue = arr[i]; // תוצאת ההטלה -ערך בין 1 ל-20 counts[diceValue]++; // קידום המונה באינדקס המתאים אם עשו לולאה פנימית ועדכנו את מערך הונים רק כש- arr[i] == למונה של הלולאה הפנימית , לא להוריד כלום (לא ביקשנו פתרון עם מערך מונים)

**Collapsed:** 3 checks · credit max 3 / 3

- **q3.א.c4.c1** · credit · binary · origin `planner`
  - קידום (הגדלה) של מונה בתוך הלולאה
  - `full` **1.5** — בתוך הלולאה מתבצעת הגדלה של מונה במערך המונים
  - `absent` **0** — אין הגדלה של מונה בתוך הלולאה
- **q3.א.c4.c2** · credit · binary · origin `planner`
  - עדכון המונה באינדקס המתאים לערך ההטלה הנוכחית
  - `full` **1.5** — מתעדכן המונה באינדקס השווה לערך ההטלה הנוכחית (למשל counts[arr[i]])
  - `absent` **0** — מתעדכן מונה באינדקס שאינו תואם את ערך ההטלה הנוכחית
- **q3.א.c4.n1** · note · note · origin `compiler`
  - כלום (לא ביקשנו פתרון עם מערך מונים
  - `none` **0** — לא רלוונטי
  - `observed` **0** — כלום (לא ביקשנו פתרון עם מערך מונים

**Interpretation notes:**
- פתרון המבצע לולאה פנימית לאיתור ההתאמה במקום גישה ישירה לפי האינדקס, ומעדכן את המונה בהתאם, נחשב שקול ואינו נפגע.

### q3.א.c5 · 2 נק׳ · components

**Teacher's text:** סעיף א: אחרי הלולאה:החזרת מערך המונים המלא

**Collapsed:** 1 checks · credit max 2 / 2

- **q3.א.c5.c1** · credit · binary · origin `planner`
  - החזרת מערך המונים המלא לאחר סיום הלולאה
  - `full` **2** — הפעולה מחזירה את מערך המונים המלא לאחר סיום הלולאה
  - `absent` **0** — הפעולה אינה מחזירה את מערך המונים המלא, או שההחזרה מתבצעת בתוך הלולאה

## q3.ב — planner

### q3.ב.c0 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: חתימת הפעולה public static void PrintStatistics(int[] arr)

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q3.ב.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה PrintStatistics
  - `full` **0.5** — הפעולה מוגדרת כ-public static void PrintStatistics(int[] arr) בדיוק כנדרש
  - `absent` **0** — חתימת הפעולה אינה תואמת את הנדרש (שם הפעולה, טיפוס ההחזרה או הפרמטר שגויים)

### q3.ב.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: משתנים משמעותיים + קוד קריא

**Collapsed:** 2 checks · credit max 0.5 / 0.5

- **q3.ב.c1.c1** · credit · binary · origin `planner`
  - שימוש בשמות משתנים משמעותיים
  - `full` **0.25** — שמות המשתנים בקוד משקפים את תפקידם
  - `absent` **0** — שמות המשתנים אינם משמעותיים ואינם משקפים את תפקידם
- **q3.ב.c1.c2** · credit · binary · origin `planner`
  - כתיבת קוד קריא
  - `full` **0.25** — הקוד כתוב בצורה קריאה וברורה
  - `absent` **0** — הקוד אינו קריא או אינו ברור

### q3.ב.c2 · 2 נק׳ · components

**Teacher's text:** סעיף ב: קריאה נכונה לפעולה DiceStatistics(arr) ושמירת המערך המוחזר אם יצרו מערך מונים חדש ו/או הריצו את הפעולה DiceStatistics בתוך לולאה תוך העתקה של כל תא , לא להוריד כלום (חוסר יעילות)

**Collapsed:** 3 checks · credit max 2 / 2

- **q3.ב.c2.c1** · credit · binary · origin `planner`
  - קריאה נכונה לפעולה DiceStatistics(arr)
  - `full` **1** — הפעולה DiceStatistics נקראת עם הפרמטר arr המתקבל בפעולה
  - `absent` **0** — הפעולה DiceStatistics אינה נקראת כנדרש
- **q3.ב.c2.c2** · credit · binary · origin `planner`
  - שמירת המערך המוחזר מהפעולה DiceStatistics
  - `full` **1** — הערך המוחזר מהפעולה DiceStatistics נשמר במשתנה מערך
  - `absent` **0** — הערך המוחזר מהפעולה DiceStatistics אינו נשמר
- **q3.ב.c2.n1** · note · note · origin `compiler`
  - כלום (חוסר יעילות
  - `none` **0** — לא רלוונטי
  - `observed` **0** — כלום (חוסר יעילות

**Interpretation notes:**
- יצירת מערך מונים חדש או הרצת DiceStatistics בתוך לולאה עם העתקת כל תא אינה נפגעת, כפי שצוין בהערה הנפרדת שאינה נבדקת כאן.

### q3.ב.c3 · 2 נק׳ · components · fixed

**Teacher's text:** סעיף ב: הגדרת משתנה שלם לשמירת הערך המקסימלי maxCount + _ + אתחול לתא הראשון או לערך מאוד נמוך) (אתחול 1 נקודות)

**Collapsed:** 2 checks · credit max 2 / 2

- **q3.ב.c3.c1** · credit · binary · origin `planner`
  - הגדרת משתנה שלם לשמירת הערך המקסימלי maxCount
  - `full` **1** — מוגדר משתנה שלם המיועד לשמירת הערך המקסימלי (למשל maxCount)
  - `absent` **0** — לא הוגדר משתנה שלם לשמירת הערך המקסימלי
- **q3.ב.c3.c2** · credit · binary · origin `planner`
  - אתחול המשתנה maxCount לתא הראשון או לערך נמוך מאוד
  - `full` **1** — המשתנה מאותחל לערך התא הראשון במערך המונים או לערך נמוך מאוד
  - `absent` **0** — המשתנה אינו מאותחל לתא הראשון ולא לערך נמוך מאוד

### q3.ב.c4 · 4 נק׳ · components

**Teacher's text:** סעיף ב: אלגוריתם נכון למציאת הערך המקסימלי (השכיחות הגבוהה ביותר) מתוך מערך המונים (ריצה מאינדקס 1 עד 20).

**Collapsed:** 1 checks · credit max 4 / 4

- **q3.ב.c4.c1** · credit · ladder · origin `planner`
  - אלגוריתם למציאת הערך המקסימלי מתוך מערך המונים
  - `full` **4** — לולאה עוברת על מערך המונים מאינדקס 1 עד 20 ומעדכנת את הערך המקסימלי בהתאם לערכים שנסרקים
  - `p1` **2** — האלגוריתם מוצא נכון את הערך המקסימלי, אך הלולאה רצה מטווח שגוי (למשל כוללת את תא 0 או מחסירה את תא 20)
  - `absent` **0** — לא קיים אלגוריתם למציאת הערך המקסימלי מתוך מערך המונים

### q3.ב.c5 · 3 נק׳ · components

**Teacher's text:** סעיף ב: לולאה נפרדת הסורקת ומדפיסה את כל האינדקסים שערכם שווה ל-maxCount (תמיכה בריבוי שכיחים) (ריצה מאינדקס 1 עד 20).

**Collapsed:** 1 checks · credit max 3 / 3

- **q3.ב.c5.c1** · credit · ladder · origin `planner`
  - לולאה נפרדת המדפיסה את כל האינדקסים ששכיחותם שווה לערך המקסימלי
  - `full` **3** — לולאה נפרדת עוברת על מערך המונים מאינדקס 1 עד 20 ומדפיסה את כל האינדקסים שערכם שווה ל-maxCount, כולל מקרה של כמה ערכים שכיחים בו-זמנית
  - `p1` **1.5** — הלולאה מדפיסה רק את האינדקס הראשון ששווה ל-maxCount, ואינה תומכת בהדפסת כל הערכים השכיחים
  - `absent` **0** — לא קיימת לולאה נפרדת המדפיסה את האינדקסים ששווים ל-maxCount

### q3.ב.c6 · 3 נק׳ · components

**Teacher's text:** סעיף ב: לולאה הסורקת ומדפיסה את האינדקסים שבהם המונה שווה ל-0 (ערכים שלא הופיעו) (ריצה מאינדקס 1 עד 20).

**Collapsed:** 1 checks · credit max 3 / 3

- **q3.ב.c6.c1** · credit · ladder · origin `planner`
  - לולאה המדפיסה את האינדקסים שבהם המונה שווה ל-0
  - `full` **3** — לולאה עוברת על מערך המונים מאינדקס 1 עד 20 ומדפיסה את כל האינדקסים שערכם 0
  - `p1` **1.5** — הלולאה מדפיסה את הערכים שלא הופיעו, אך רצה מטווח שגוי (למשל כוללת את תא 0 או מחסירה את תא 20)
  - `absent` **0** — לא קיימת לולאה המדפיסה את האינדקסים שערכם 0

## q4.א — planner

### q4.א.c0 · 1 נק׳ · components

**Teacher's text:** סעיף א: חתימת הפעולה (ללא מילה static!) public double TotalEarnings()

**Collapsed:** 1 checks · credit max 1 / 1

- **q4.א.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה TotalEarnings
  - `full` **1** — הפעולה מוגדרת כ-public double TotalEarnings() ללא המילה static
  - `absent` **0** — החתימה שגויה: טיפוס ההחזרה, שם הפעולה או הנגישות אינם תואמים, או שנוספה המילה static

**Interpretation notes:**
- החתימה נבדקת כמכלול אחד, בהתאם לניסוח המורה שהדגישה את היעדר המילה static כחלק מהחתימה.

### q4.א.c1 · 4 נק׳ · components

**Teacher's text:** סעיף א: החזרת החישוב: return this.seasonsPlayed * this.seasonSalary;

**Collapsed:** 2 checks · credit max 4 / 4

- **q4.א.c1.c1** · credit · binary · origin `planner`
  - חישוב מכפלת מספר העונות בשכר לעונה
  - שקילות: שימוש בפעולות ה-Get של התכונות במקום גישה ישירה לשדות נחשב שקול
  - `full` **2** — מבוצעת מכפלה בין seasonsPlayed לבין seasonSalary
  - `absent` **0** — אין חישוב מכפלה בין שני השדות
- **q4.א.c1.c2** · credit · binary · origin `planner`
  - החזרת תוצאת החישוב
  - `full` **2** — תוצאת המכפלה מוחזרת באמצעות return
  - `absent` **0** — התוצאה אינה מוחזרת מהפעולה

## q4.ב — repaired

> validator messages that sent this scope to repair/fallback:
> - V14: q4.ב.c7.f1 members span charge groups ['q4.ב:once:2aa8e26f', 'q4.ב:once:d754e274']

### q4.ב.c0 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: חתימת הפעולה (static!!) public static string[] TopEarners(BasketballPlayer[] arr, double amount)

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q4.ב.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה TopEarners
  - שקילות: שמות הפרמטרים עצמם (arr, amount) יכולים להיות שונים כל עוד סוגיהם וסדרם תואמים
  - `full` **0.5** — חתימת הפעולה תואמת בדיוק: public static string[] TopEarners(BasketballPlayer[] arr, double amount)
  - `absent` **0** — חתימת הפעולה אינה תואמת (סוג מוחזר, שם הפעולה, סוג/סדר הפרמטרים או static חסרים או שגויים)

### q4.ב.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: משתנים משמעותיים + קוד קריא

**Collapsed:** 2 checks · credit max 0.5 / 0.5

- **q4.ב.c1.c1** · credit · binary · origin `planner`
  - משתנים משמעותיים
  - `full` **0.25** — שמות המשתנים בקוד משקפים בבירור את תפקידם
  - `absent` **0** — שמות המשתנים אינם משמעותיים ואינם משקפים את תפקידם
- **q4.ב.c1.c2** · credit · binary · origin `planner`
  - קוד קריא
  - `full` **0.25** — הקוד כתוב בצורה קריאה ומאורגנת
  - `absent` **0** — הקוד אינו קריא או אינו מאורגן

**Interpretation notes:**
- פוצל התנאי 'משתנים משמעותיים + קוד קריא' לשני מרכיבים נפרדים, משום שכל אחד מהם עשוי להתקיים בלי השני.

### q4.ב.c2 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ב: משתנה למניית השחקניות שמקיימות את התנאי + איפוס

**Collapsed:** 2 checks · credit max 1 / 1

- **q4.ב.c2.c1** · credit · binary · origin `planner`
  - משתנה למניית השחקניות שמקיימות את התנאי
  - `full` **0.5** — קיים משתנה המונה את מספר השחקניות המקיימות את התנאי
  - `absent` **0** — אין משתנה למניית השחקניות המקיימות את התנאי
- **q4.ב.c2.c2** · credit · binary · origin `planner`
  - איפוס משתנה המונה
  - `full` **0.5** — משתנה המונה מאותחל לערך אפס
  - `absent` **0** — משתנה המונה אינו מאותחל לאפס

### q4.ב.c3 · 2 נק׳ · components

**Teacher's text:** סעיף ב: לולאה (A) על מערך השחקניות (לספירה נכונה וקידום מונה תקין) for (int i = 0; i < arr.Length; i++)

**Collapsed:** 1 checks · credit max 2 / 2

- **q4.ב.c3.c1** · credit · binary · origin `planner`
  - לולאה (A) על מערך השחקניות
  - `full` **2** — קיימת לולאה העוברת על כל איברי מערך השחקניות מהאיבר הראשון ועד האחרון
  - `absent` **0** — אין לולאה נכונה העוברת על כל מערך השחקניות

### q4.ב.c4 · 5 נק׳ · components · fixed

**Teacher's text:** סעיף ב:בתוך הלולאה (A) : בדיקה אם המערך במקום ה- i שונה מ- null (1 נקודות) זימון של פעולה פנימית TotalEarnings עבור המערך במקום ה- i (3 נקודות) (לקנוס פעם אחת אם לא בדקו אם arr[i]!=null , הערה למטה) השוואה אם התוצאה גבוהה מהפרמטר (1 נקודה) קידום המונה (1 נקודה) if (arr[i].TotalEarnings() > amount) count++;

**Collapsed:** 5 checks · credit max 5 / 5

- **q4.ב.c4.c1** · credit · binary · origin `planner`
  - בדיקה אם המערך במקום ה-i שונה מ-null
  - `full` **1** — בלולאה קיימת בדיקה שהאיבר arr[i] שונה מ-null לפני הגישה אליו
  - `absent` **0** — אין בדיקה שהאיבר arr[i] שונה מ-null
- **q4.ב.c4.c2** · credit · binary · origin `planner`
  - זימון של פעולה פנימית TotalEarnings עבור המערך במקום ה-i
  - `full` **2** — מתבצע זימון לפעולה TotalEarnings על arr[i] לקבלת סך הכנסותיה
  - `absent` **0** — אין זימון לפעולה TotalEarnings על השחקנית
- **q4.ב.c4.c3** · credit · binary · origin `planner`
  - השוואה אם התוצאה גבוהה מהפרמטר
  - `full` **1** — תוצאת TotalEarnings מושווית לפרמטר amount באמצעות תנאי גדול מ
  - `absent` **0** — אין השוואה בין תוצאת TotalEarnings לפרמטר amount
- **q4.ב.c4.c4** · credit · binary · origin `planner`
  - קידום המונה
  - `full` **1** — המונה מוגדל כאשר מתקיים התנאי
  - `absent` **0** — המונה אינו מתקדם כאשר מתקיים התנאי
- **q4.ב.c4.f1** · fault · fault · origin `planner` · requires `q4.ב.c4.c1` · group `q4.ב:once:2aa8e26f`
  - היעדר בדיקה שהאיבר arr[i] שונה מ-null בלולאה הראשונה
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — לא בוצעה בדיקה שהאיבר arr[i] שונה מ-null בלולאה הראשונה ← `q4.ב.c4.m1`

### q4.ב.c5 · 3 נק׳ · components

**Teacher's text:** סעיף ב: הקצאת מערך ה-string החדש בדיוק בגודל שנספר (count)

**Collapsed:** 1 checks · credit max 3 / 3

- **q4.ב.c5.c1** · credit · ladder · origin `planner`
  - הקצאת מערך ה-string החדש בגודל שנספר
  - `full` **3** — מוקצה מערך מחרוזות חדש בגודל השווה בדיוק למספר השחקניות שנספרו (count)
  - `p1` **1.5** — מוקצה מערך מחרוזות חדש אך בגודל שאינו תואם למספר השחקניות שנספר (count)
  - `absent` **0** — לא מוקצה מערך מחרוזות חדש בגודל count

**Interpretation notes:**
- הוגדר מצב ביניים שבו מוקצה מערך אך לא בגודל count, כדי לאפשר זיהוי הקצאה חלקית.

### q4.ב.c6 · 1 נק׳ · components · fixed

**Teacher's text:** סעיף ב: משתנה לאנדקס מערך השמות + איפוס

**Collapsed:** 2 checks · credit max 1 / 1

- **q4.ב.c6.c1** · credit · binary · origin `planner`
  - משתנה לאנדקס מערך השמות
  - `full` **0.5** — קיים משתנה נפרד המשמש כאינדקס למערך השמות (namesIndex)
  - `absent` **0** — אין משתנה נפרד לאינדקס מערך השמות
- **q4.ב.c6.c2** · credit · binary · origin `planner`
  - איפוס משתנה האינדקס
  - `full` **0.5** — משתנה האינדקס מאותחל לערך אפס
  - `absent` **0** — משתנה האינדקס אינו מאותחל לאפס

### q4.ב.c7 · 5 נק׳ · components · fixed

**Teacher's text:** סעיף ב: לולאה שנייה (B) נכונה (1 נקודה) בדיקה אם המערך במקום ה- i שונה מ- null(1 נקודות), להוריד רק פעם אחת שימוש ב-Getter לקבלת השם arr[i].GetName() (3 נקודות) השמה במערך החדש (1 נקודה) תוך קידום אינדקס נפרד (namesIndex)(1 נקודה) for (int i = 0; i < arr.Length; i++) { if (arr[i]!= null && arr[i].TotalEarnings() > amount) // אם טעו פה,להוריד 3 רק פעם 1 (יש גם זימון בלולאה א { namesArr[namesIndex] = arr[i].GetName(); // שימוש ב-Getter namesIndex++; // קידום האנדקס } }

**Collapsed:** 7 checks · credit max 5 / 5

- **q4.ב.c7.c1** · credit · binary · origin `planner`
  - לולאה שנייה (B) נכונה
  - `full` **0.5** — קיימת לולאה שנייה העוברת על כל איברי מערך השחקניות
  - `absent` **0** — אין לולאה שנייה נכונה העוברת על מערך השחקניות
- **q4.ב.c7.c2** · credit · binary · origin `planner`
  - בדיקה אם המערך במקום ה-i שונה מ-null (לולאה שנייה)
  - `full` **0.5** — בלולאה השנייה קיימת בדיקה שהאיבר arr[i] שונה מ-null
  - `absent` **0** — אין בדיקה שהאיבר arr[i] שונה מ-null בלולאה השנייה
- **q4.ב.c7.c3** · credit · binary · origin `planner`
  - שימוש ב-Getter לקבלת השם
  - `full` **2** — שם השחקנית מתקבל באמצעות שימוש ב-Getter (GetName)
  - `absent` **0** — אין שימוש ב-Getter לקבלת שם השחקנית
- **q4.ב.c7.c4** · credit · binary · origin `planner`
  - השמה במערך החדש
  - `full` **1** — השם המתקבל מושם במערך המחרוזות החדש באינדקס המתאים
  - `absent` **0** — אין השמה של השם למערך החדש
- **q4.ב.c7.c5** · credit · binary · origin `planner`
  - קידום אינדקס נפרד (namesIndex)
  - `full` **1** — אינדקס namesIndex מתקדם בנפרד מהאינדקס i בכל השמה
  - `absent` **0** — אינדקס namesIndex אינו מתקדם או אינו נפרד מהאינדקס i
- **q4.ב.c7.f1** · fault · fault · origin `planner` · requires `q4.ב.c7.c2` · group `q4.ב:once:2aa8e26f`
  - היעדר בדיקה שהאיבר arr[i] שונה מ-null בלולאה השנייה
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — לא בוצעה בדיקה שהאיבר arr[i] שונה מ-null בלולאה השנייה ← `q4.ב.c7.m1`
- **q4.ב.c7.f2** · fault · fault · origin `planner` · requires `q4.ב.c7.c1` · group `q4.ב:once:d754e274`
  - התנאי בלולאה השנייה אינו משחזר נכון את תנאי הסינון שבלולאה הראשונה (arr[i]!=null וההשוואה ל-amount)
  - `none` **0** — ללא הטעות הזו
  - `f1` **-3** — תנאי הסינון בלולאה השנייה שגוי או אינו תואם לתנאי שבלולאה הראשונה ← `q4.ב.c7.m2`

### q4.ב.c8 · 2 נק׳ · components

**Teacher's text:** סעיף ב: החזרת מערך השמות

**Collapsed:** 1 checks · credit max 2 / 2

- **q4.ב.c8.c1** · credit · binary · origin `planner`
  - החזרת מערך השמות
  - `full` **2** — הפעולה מחזירה את מערך השמות שנבנה
  - `absent` **0** — הפעולה אינה מחזירה את מערך השמות

**Markers and dispositions:**

- `q4.ב.c4.m1` −1 · candidates ['q4.ב.c4'] · fault · «לקנוס פעם אחת אם לא בדקו אם arr[i]!=null , הערה למטה)»
- `q4.ב.c7.m1` −1 · candidates ['q4.ב.c7'] · fault · «להוריד רק פעם אחת»
- `q4.ב.c7.m2` −3 · candidates ['q4.ב.c7'] · fault · «אם טעו פה,להוריד 3 רק פעם 1»

**V19 candidates (telemetry):**
- `q4.ב.c4.f1` requires `q4.ב.c4.c1` — shared tokens ['null']

## q5.א — repaired

> validator messages that sent this scope to repair/fallback:
> - terminal 'q5.א.c1' was not planned

### q5.א.c0 · 1 נק׳ · components

**Teacher's text:** סעיף א: חתימת הפעולה (ללא מילה static!) public bool IsSimilarWorkshop(Workshop other) כל טעות פה להוריד 1

**Collapsed:** 1 checks · credit max 1 / 1

- **q5.א.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה IsSimilarWorkshop
  - `full` **1** — הפעולה מוגדרת כ-public bool IsSimilarWorkshop(Workshop other) ללא המילה static
  - `absent` **0** — חתימת הפעולה שגויה: חסר public, סוג החזרה אינו bool, שם הפעולה או הפרמטר אינם תואמים, או שנוספה המילה static

### q5.א.c1 · 4 נק׳ · components

**Teacher's text:** סעיף א: החזרת החישוב: return this.name == other.GetName();

**Collapsed:** 1 checks · credit max 4 / 4

- **q5.א.c1.c1** · credit · binary · origin `planner`
  - החזרת תוצאת ההשוואה בין שם הסדנה הנוכחית לשם הסדנה האחרת
  - שקילות: גישה לשם הסדנה האחרת דרך תכונה ישירה במקום קריאה לפעולת ה-Get שקולה, בהינתן ששתי הסדנאות מאותה מחלקה
  - `full` **4** — הפעולה מחזירה true אם שם הסדנה הנוכחית שווה לשם הסדנה האחרת, ואחרת מחזירה false
  - `absent` **0** — הפעולה אינה מחזירה השוואה נכונה בין שמות שתי הסדנאות

## q5.ב — planner

### q5.ב.c0 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: חתימת הפעולה (לא static!!) public bool HandleNewWorkshop(Workshop ws)

**Collapsed:** 1 checks · credit max 0.5 / 0.5

- **q5.ב.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה הציבורית (לא static) בשם HandleNewWorkshop המקבלת פרמטר מטיפוס Workshop ומחזירה bool
  - `full` **0.5** — הפעולה מוגדרת כ-public bool HandleNewWorkshop(Workshop ws) ואינה מסומנת static
  - `absent` **0** — חתימת הפעולה שגויה: מסומנת static, שם/פרמטר/סוג החזרה שונים מהנדרש

### q5.ב.c1 · 0.5 נק׳ · components

**Teacher's text:** סעיף ב: משתנים משמעותיים + קוד קריא

**Collapsed:** 2 checks · credit max 0.5 / 0.5

- **q5.ב.c1.c1** · credit · binary · origin `planner`
  - שימוש בשמות משתנים משמעותיים
  - `full` **0.25** — שמות המשתנים בקוד משקפים את תפקידם באופן משמעותי
  - `absent` **0** — שמות המשתנים אינם משמעותיים
- **q5.ב.c1.c2** · credit · binary · origin `planner`
  - כתיבת קוד קריא
  - `full` **0.25** — הקוד מאורגן וקריא
  - `absent` **0** — הקוד אינו קריא או אינו מאורגן

### q5.ב.c2 · 6 נק׳ · components

**Teacher's text:** סעיף ב: ניהול נכון של לולאת החיפוש (ריצה עד countWorkshops ועצירה במידה ותנאי השילוב מתקיים. אם רצו עד Length ולא בדקו ששונה מ-Null , להוריד 2 אם לא ניהולו נכון את גבולות הלולאה להוריד 1

**Collapsed:** 3 checks · credit max 6 / 6

- **q5.ב.c2.c1** · credit · binary · origin `planner`
  - הגבלת הלולאה לריצה עד countWorkshops ולא עד גודל המערך
  - שקילות: ריצה עד countWorkshops-1 באמצעות תנאי <= שקולה
  - `full` **3** — הלולאה רצה על פני הסדנאות הקיימות בפועל, מאינדקס 0 עד countWorkshops (לא כולל)
  - `absent` **0** — הלולאה אינה מוגבלת לרוץ עד countWorkshops
- **q5.ב.c2.c2** · credit · binary · origin `planner`
  - עצירת החיפוש כאשר תנאי השילוב מתקיים
  - `full` **3** — החיפוש נעצר (למשל באמצעות return או דגל עצירה) ברגע שנמצאה סדנה מתאימה לשילוב
  - `absent` **0** — החיפוש אינו נעצר כשנמצאה סדנה מתאימה וממשיך לבדוק סדנאות נוספות ללא צורך
- **q5.ב.c2.f1** · fault · fault · origin `planner` · requires `q5.ב.c2.c1`
  - ניהול שגוי של גבול הלולאה בחיפוש הסדנה הדומה
  - `none` **0** — ללא הטעות הזו
  - `f1` **-2** — הלולאה רצה עד גודל המערך (Length) במקום עד countWorkshops, ולא נבדק שהאיבר שונה מ-null ← `q5.ב.c2.m1`
  - `f2` **-1** — גבולות הלולאה לא נוהלו כנדרש, מסיבה אחרת שאינה ריצה עד Length ← `q5.ב.c2.m2`

**Interpretation notes:**
- הביטוי הכללי בדבר ניהול שגוי של גבולות הלולאה פורש כמתייחס לגבול העליון של הלולאה, בנפרד מהמקרה הספציפי של ריצה עד Length.

### q5.ב.c3 · 2 נק׳ · components

**Teacher's text:** סעיף ב: זימון נכון של הפעולה מסעיף א' על איבר מהמערך: this.workshops[i].IsSimilarWorkshop(ws)

**Collapsed:** 1 checks · credit max 2 / 2

- **q5.ב.c3.c1** · credit · binary · origin `planner`
  - קריאה לפעולה IsSimilarWorkshop מסעיף א' על איבר מהמערך, בהשוואה לסדנה החדשה
  - `full` **2** — הפעולה IsSimilarWorkshop נקראת על איבר מהמערך workshops[i] עם הסדנה החדשה כפרמטר
  - `absent` **0** — הפעולה IsSimilarWorkshop לא נקראת על איבר מהמערך, או נקראה באופן שגוי

### q5.ב.c4 · 5 נק׳ · components · fixed

**Teacher's text:** סעיף ב: בדיקת תנאי הקיבולת (קטן או שווה ל-40) ועדכון נכון של התכונה people בעזרת SetPeople ו-GetPeople הבדיקת הקיבולת עצמה 1 נקודה אם לא השתמשו בפעולה הפנימית להוריד 2, אם לא השתמשו באף אחת מהן להוריד 3 אם חישבו נכון את סה"כ ולא עדכנו את התכונה (כמובן ע"י setter) להוריד 2

**Collapsed:** 4 checks · credit max 5 / 5

- **q5.ב.c4.c1** · credit · binary · origin `planner`
  - בדיקת תנאי הקיבולת: סך המשתתפים בסדנה הקיימת ובסדנה החדשה אינו עולה על 40
  - `full` **1** — מתבצעת בדיקה שסכום המשתתפים בסדנה הקיימת ובסדנה החדשה אינו עולה על 40
  - `absent` **0** — לא מתבצעת בדיקה של תנאי הקיבולת
- **q5.ב.c4.c2** · credit · binary · origin `planner`
  - עדכון נכון של התכונה people בעזרת הפעולות הפנימיות SetPeople ו-GetPeople
  - `full` **4** — הסכום המעודכן מחושב באמצעות GetPeople משתי הסדנאות, והתכונה people בסדנה הקיימת מעודכנת באמצעות SetPeople
  - `absent` **0** — התכונה people אינה מעודכנת בעזרת הפעולות הפנימיות GetPeople/SetPeople
- **q5.ב.c4.f1** · fault · fault · origin `planner` · requires `q5.ב.c4.c2`
  - אי שימוש בפעולות הפנימיות Get/Set לבדיקת הקיבולת ולעדכון התכונה
  - `none` **0** — ללא הטעות הזו
  - `f1` **-2** — נעשה שימוש בפעולה פנימית אחת בלבד מבין Get/Set, ובשנייה לא נעשה שימוש ← `q5.ב.c4.m1`
  - `f2` **-3** — לא נעשה שימוש בשום פעולה פנימית, לא ב-Get ולא ב-Set ← `q5.ב.c4.m2`
- **q5.ב.c4.f2** · fault · fault · origin `planner` · requires `q5.ב.c4.c2`
  - אי עדכון התכונה people לאחר חישוב נכון של הסכום
  - `none` **0** — ללא הטעות הזו
  - `f1` **-2** — הסכום חושב נכון אך התכונה people לא עודכנה בעזרת setter ← `q5.ב.c4.m3`

### q5.ב.c5 · 3 נק׳ · components

**Teacher's text:** סעיף ב: הוספת הסדנה החדשה למקום ה-countWorkshops וקידום המונה ב-1 במידה ולא בוצע איחוד והמערך אינו מלא

**Collapsed:** 2 checks · credit max 3 / 3

- **q5.ב.c5.c1** · credit · binary · origin `planner`
  - הוספת הסדנה החדשה למקום ה-countWorkshops (המקום הראשון הפנוי)
  - `full` **1.5** — הסדנה החדשה מוכנסת למערך workshops באינדקס countWorkshops
  - `absent` **0** — הסדנה החדשה לא מוכנסת למקום הנכון במערך
- **q5.ב.c5.c2** · credit · binary · origin `planner`
  - קידום המונה countWorkshops באחד לאחר ההוספה
  - `full` **1.5** — לאחר ההוספה, countWorkshops מוגדל באחד
  - `absent` **0** — countWorkshops לא מתעדכן לאחר ההוספה

**Interpretation notes:**
- ההוספה וקידום המונה נדרשים רק כאשר לא בוצע איחוד עם סדנה קיימת והמערך אינו מלא.

### q5.ב.c6 · 3 נק׳ · components · fixed

**Teacher's text:** סעיף ב: החזרת הערכים הבוליאניים הנכונים (true / false) בכל אחד מהתרחישים 1.5 ל-true, 1.5 ל-false

**Collapsed:** 2 checks · credit max 3 / 3

- **q5.ב.c6.c1** · credit · binary · origin `planner`
  - החזרת false בתרחיש שבו המערך מלא ולא ניתן להוסיף סדנה חדשה
  - `full` **1.5** — כאשר המערך מלא ולא בוצע איחוד, הפעולה מחזירה false
  - `absent` **0** — בתרחיש שהמערך מלא, הפעולה אינה מחזירה false
- **q5.ב.c6.c2** · credit · binary · origin `planner`
  - החזרת true בתרחישים שבהם הפעולה מצליחה (איחוד עם סדנה קיימת או הוספת סדנה חדשה)
  - `full` **1.5** — בתרחיש איחוד מוצלח או הוספה מוצלחת, הפעולה מחזירה true
  - `absent` **0** — בתרחיש הצלחה, הפעולה אינה מחזירה true

**Interpretation notes:**
- חלוקת הבדיקה לפי true/false מבוססת על ההנחה שהניקוד מתייחס בנפרד לתרחישי ההצלחה (true) ולתרחיש המערך המלא (false).

**Markers and dispositions:**

- `q5.ב.c2.m1` −2 · candidates ['q5.ב.c2'] · fault · «להוריד 2»
- `q5.ב.c2.m2` −1 · candidates ['q5.ב.c2'] · fault · «אם לא ניהולו נכון את גבולות הלולאה להוריד 1»
- `q5.ב.c4.m1` −2 · candidates ['q5.ב.c4'] · fault · «אם לא השתמשו בפעולה הפנימית להוריד 2»
- `q5.ב.c4.m2` −3 · candidates ['q5.ב.c4'] · fault · «אם לא השתמשו באף אחת מהן להוריד 3»
- `q5.ב.c4.m3` −2 · candidates ['q5.ב.c4'] · fault · «להוריד 2»

## q6 — planner

### q6.c0 · 1 נק׳ · components

**Teacher's text:** חתימת הפעולה (עם המילה static!) כל טעות להוריד 1

**Collapsed:** 1 checks · credit max 1 / 1

- **q6.c0.c1** · credit · binary · origin `planner`
  - חתימת הפעולה עם המילה static, שם הפעולה, סוג ההחזרה וסוג הפרמטר התואמים לנדרש
  - `full` **1** — החתימה כוללת את המילה static, שם הפעולה AnalyzeMechina, סוג ההחזרה int[] וסוג הפרמטר int[] כנדרש
  - `absent` **0** — החתימה חסרה את המילה static, או שאחד ממרכיביה (שם הפעולה, סוג ההחזרה, סוג הפרמטר) שגוי

### q6.c1 · 1 נק׳ · components · fixed

**Teacher's text:** משתנים משמעותיים + קוד קריא

**Collapsed:** 2 checks · credit max 1 / 1

- **q6.c1.c1** · credit · binary · origin `planner`
  - משתנים משמעותיים
  - `full` **0.5** — שמות המשתנים תיאוריים וברורים בהתאם לתפקידם
  - `absent` **0** — שמות המשתנים אינם משמעותיים (כגון אותיות בודדות ללא הקשר)
- **q6.c1.c2** · credit · binary · origin `planner`
  - קוד קריא
  - `full` **0.5** — הקוד מאורגן, ברור וקריא, כולל הזחות עקביות
  - `absent` **0** — הקוד אינו קריא או אינו מאורגן

### q6.c2 · 2 נק׳ · components

**Teacher's text:** יצירה של מערך מונים עם הקצאה נכונה (לפחות בגודל 31)

**Collapsed:** 1 checks · credit max 2 / 2

- **q6.c2.c1** · credit · ladder · origin `planner`
  - יצירה של מערך מונים עם הקצאה נכונה
  - `full` **2** — נוצר מערך מונים בגודל 31 לפחות
  - `p1` **1** — נוצר מערך מונים אך בגודל קטן מ-31
  - `absent` **0** — לא נוצר מערך מונים, או שנוצר בגודל קטן מ-31

### q6.c3 · 1 נק׳ · components

**Teacher's text:** איפוס מערך המונים או הערה שיש איפוס ע"י השפה

**Collapsed:** 1 checks · credit max 1 / 1

- **q6.c3.c1** · credit · binary · origin `planner`
  - איפוס מערך המונים או ציון שהשפה מאפסת אותו
  - `full` **1** — מערך המונים אופס במפורש בלולאה, או שצוינה הערה כי השפה מאפסת מערכים כברירת מחדל
  - `absent` **0** — אין איפוס מפורש של מערך המונים ואין הערה על איפוס אוטומטי

### q6.c4 · 2 נק׳ · components

**Teacher's text:** סריקה נכונה של מערך הקלט לעדכון מונים

**Collapsed:** 2 checks · credit max 2 / 2

- **q6.c4.c1** · credit · binary · origin `planner`
  - סריקת מערך הקלט על פני כל התלמידים
  - `full` **1** — בוצעה לולאה העוברת על כל תאי מערך הקלט
  - `absent` **0** — לא בוצעה סריקה של מערך הקלט
- **q6.c4.c2** · credit · binary · origin `planner`
  - עדכון מונה המכינה בהתאם למספר שנרשם בכל תא
  - `full` **1** — מונה המכינה המתאימה למספר שנרשם בתא מוגדל בכל איטרציה
  - `absent` **0** — המונים אינם מעודכנים בהתאם למספרי המכינות שנרשמו

**Interpretation notes:**
- הסריקה של הקלט ועדכון המונים נבדקים כשני מרכיבים נפרדים, כדי לזכות מנגנון סריקה תקין גם כשהעדכון עצמו שגוי.

### q6.c5 · 4 נק׳ · components

**Teacher's text:** סריקת מערך המונים למציאת המכינה (האינדקס) עם המונה הגבוה ביותר (4 נקודות) ו

**Collapsed:** 2 checks · credit max 4 / 4

- **q6.c5.c1** · credit · binary · origin `planner`
  - סריקת מערך המונים על פני כל המכינות
  - `full` **2** — בוצעה לולאה העוברת על כל תאי מערך המונים (מכינה 1 עד 30)
  - `absent` **0** — לא בוצעה סריקה של מערך המונים
- **q6.c5.c2** · credit · binary · origin `planner`
  - עדכון האינדקס של המכינה בעלת המונה הגבוה ביותר
  - `full` **2** — נשמר האינדקס (מספר המכינה) שבו נמצא המונה הגבוה ביותר שנמצא עד כה בסריקה
  - `absent` **0** — לא נשמר או לא מתעדכן האינדקס של המכינה בעלת המונה המקסימלי

### q6.c6 · 2 נק׳ · components

**Teacher's text:** הדפסת מספר המכינה בעלת כמות מקסימלית (ולא כמות התלמידים) אם הדפיסו את הכמות להוריד 2 (או 1?)

**Collapsed:** 2 checks · credit max 2 / 2

- **q6.c6.c1** · credit · binary · origin `planner`
  - הדפסת מספר המכינה בעלת כמות התלמידים הגבוהה ביותר
  - `full` **2** — מודפס מספר המכינה שאליה נרשמו הכי הרבה תלמידים
  - `absent` **0** — לא מודפס מספר המכינה בעלת הכמות המקסימלית
- **q6.c6.f1** · fault · fault · origin `planner` · requires `q6.c6.c1`
  - הדפסת כמות התלמידים במקום מספר המכינה
  - `none` **0** — ללא הטעות הזו
  - `f1` **-1** — הודפסה כמות התלמידים שנרשמו במקום מספר המכינה בעלת הכמות הגבוהה ביותר ← `q6.c6.m1`

### q6.c7 · 4 נק׳ · components · fixed

**Teacher's text:** חישוב גודל מערך היעד: סריקת מערך המונים(1 נק'), ספירת התאים שגדולים מ-0 (1 נקודה), ויצירה והקצאת מערך חדש בגודל count * 2 (2 נקודות)

**Collapsed:** 3 checks · credit max 4 / 4

- **q6.c7.c1** · credit · binary · origin `planner`
  - סריקת מערך המונים לצורך חישוב גודל מערך היעד
  - `full` **1** — בוצעה סריקה של מערך המונים לצורך חישוב גודל מערך היעד
  - `absent` **0** — לא בוצעה סריקה של מערך המונים לצורך חישוב הגודל
- **q6.c7.c2** · credit · binary · origin `planner`
  - ספירת התאים שגדולים מ-0
  - `full` **1** — נספרו התאים במערך המונים שערכם גדול מ-0
  - `absent` **0** — לא נספרו התאים שערכם גדול מ-0
- **q6.c7.c3** · credit · binary · origin `planner`
  - יצירה והקצאת מערך חדש בגודל count * 2
  - `full` **2** — נוצר מערך חדש בגודל השווה לפעמיים מספר המכינות הפעילות
  - `absent` **0** — לא נוצר מערך בגודל הנכון (פעמיים מספר המכינות הפעילות)

### q6.c8 · 8 נק׳ · components

**Teacher's text:** בניית מערך התוצאה: מילוי נכון של המערך החדש בזוגות: קודם את result[resIndex] = i ומיד לאחר מכן result[resIndex+1] = counters[i] תוך קידום ידני תקין של אינדקס מערך היעד ב-2 בכל פעם.

**Collapsed:** 2 checks · credit max 8 / 8

- **q6.c8.c1** · credit · binary · origin `planner`
  - מילוי נכון של המערך החדש בזוגות: מספר המכינה ומספר התלמידים שנרשמו אליה
  - `full` **4** — בכל זוג נכתב תחילה מספר המכינה (i) ומיד לאחריו מספר התלמידים שנרשמו אליה (counters[i])
  - `absent` **0** — הזוגות במערך התוצאה אינם כוללים את מספר המכינה ומספר התלמידים הנכונים, או שסדרם הפוך
- **q6.c8.c2** · credit · binary · origin `planner`
  - קידום ידני תקין של אינדקס מערך היעד ב-2 בכל פעם
  - `full` **4** — האינדקס במערך התוצאה מתקדם ב-2 לאחר כתיבת כל זוג
  - `absent` **0** — האינדקס אינו מתקדם ב-2 בין הזוגות (למשל מתקדם ב-1 או לא מתקדם כלל)

**Markers and dispositions:**

- `q6.c6.m1` −1 · candidates ['q6.c6'] · fault · «אם הדפיסו את הכמות להוריד 2 (או 1?)»

