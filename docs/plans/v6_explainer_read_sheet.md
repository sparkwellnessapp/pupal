# Explainer read sheet (§13.4) — blind

80 lines (40 terminals × 2 arms), shuffled. For each line answer three yes/no questions:
- **Faithful** — says nothing the grade and the quotes don't support.
- **Clear** — understood on the first read.
- **Concise** — nothing extraneous.

### 1

**הקריטריון:** בתוך הלולאה על TvShows: בדיקה האם תוכנית מתאימה להדפסה:אינה null ב (2 נקודות) וגם הערוץ שלה תואם את הערוץ המינימלי (ע"י GetChl והשוואתם (2 נקודות) וגם היא באוויר (ע"י GetIsOn ב 2 נקודות) הדפסה של השם של התוכנית (ע"י GetName ב( 2 נקודות)

**ציון:** 6 / 8

**ציטוטים:** «if (arrShows[i].GetIsOn() && arrShows[i].GetChl()==lowestRateChl)» · «arrShows[i].GetChl()==lowestRateChl» · «if (arrShows[i].GetIsOn()» · «CW(arrShows[i].GetName());»

**מה אין:** חיפשתי בדיקת null בתוך הלולאה ובכל הפעולה — אין

> אין בדיקת null בתוך הלולאה, ולכן ירדו 2 נקודות; השוואת GetChl, בדיקת GetIsOn והדפסת GetName נכונות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 2

**הקריטריון:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם הגישה למערך בלי getter להוריד 1

**ציון:** 3 / 3

**ציטוטים:** «for(int i = 0; i < tvRate1.GetArrShows().Length; i++)»

> הלולאה רצה מ-0 עד i < tvRate1.GetArrShows().Length, והגישה למערך נעשית דרך GetArrShows ולכן אין הורדה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 3

**הקריטריון:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם הגישה למערך בלי getter להוריד 1

**ציון:** 2 / 3

**ציטוטים:** «for(int i=0; i<A.Length; i++)» · «A[i].getchl()»

> הלולאה for(int i=0; i<A.Length; i++) עוברת על כל המערך כנדרש, אבל הגישה ל-A.Length ישירה ולא דרך Get, ולכן ירדה נקודה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 4

**הקריטריון:** סעיף א: בתוך הלולאה: חיפוש אחר המספר הנגדי של arr[i]: int target = -arr[i]; bool found = false; for (int j = 0; j < arr.Length && found == false; j++) { if (arr[j] == target) { found = true; } }

**ציון:** 0 / 4

**ציטוטים:** «arr[i] == arr[j] - 1» · «if (arr[i] != 0 && arr[i] == arr[j] - 1)
count++;»

> בלולאה לא נקבע הערך הנגדי של arr[i] ולא מתבצע חיפוש שלו בין איברי המערך, ולכן אין נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 5

**הקריטריון:** התייחסות לתנאי שהאיבר שונה מ-1 ומ-x עצמו  0.5 נק'

**ציון:** 1.5 / 1.5

**ציטוטים:** «וגם לא אחד» · «שהם לא המספר עצמו»

> שני התנאים נכתבו: «וגם לא אחד» לאיבר השונה מ-1, ו-«שהם לא המספר עצמו» לאיבר השונה מ-x, ולכן ניתנו מלוא הנקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 6

**הקריטריון:** סעיף ב: סריקת המערך הפרמטר ומציאת המספרים החיוביים והעתקם למערך הזמני פלוס קידום האנדקס לולאה על המערך הפרמטר 0.5 אם המספר הנוכחי במערך הפרמטר חיובי 2 העתק המספר החיובי למערך העזר 1 קידום האנדקס 1 for (int i = 0; i < arr.Length; i++) { if (arr[i] > 0) // אם המספר חיובי { temp[tempIndex] = arr[i]; // העתקת המספר החיובי למערך העזר tempIndex++;

**ציון:** 2.5 / 4.5

**ציטוטים:** «for (int i=0; i<arr.length; i++)» · «newArr[i] = arr[j];» · «for (int i=0; i<arr.length; i+=2)»

**מה אין:** הבדיקה היא arr[i]<0 (שלילי) ולא חיובי; arr[j]!=0 אינו בדיקת חיוביות

> הלולאה סורקת את arr, אך הבדיקה היא arr[i]<0 (שלילי) ולא חיובי, ולכן ירדו 2 נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 7

**הקריטריון:** בניית מערך התוצאה: מילוי נכון של המערך החדש בזוגות: קודם את result[resIndex] = i ומיד לאחר מכן result[resIndex+1] = counters[i] תוך קידום ידני תקין של אינדקס מערך היעד ב-2 בכל פעם.

**ציון:** 0 / 8

**ציטוטים:** «result[j] = Mecina[i];» · «result[j+1] = i;»

**מה אין:** j לא מקודם בלולאת המילוי

> מערך התוצאה לא מולא: לא נכתבו מספר המכינה והכמות, ו-j לא קודם ב-2 בלולאת המילוי.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 8

**הקריטריון:** סעיף ב: פעולה פנימית בשם PopulateHobbies (סה"כ 16)כותרת הפעולה + טיפוס מוחזר bool

**ציון:** 2 / 2

**ציטוטים:** «Public bool populateHobbies ()» · «Public bool populateHobbies ()»

> הפעולה הוגדרה כ-Public bool populateHobbies, כותרת נכונה וטיפוס מוחזר bool.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 9

**הקריטריון:** סריקת מערך המונים למציאת המכינה (האינדקס) עם המונה הגבוה ביותר (4 נקודות) ו

**ציון:** 2.50 / 4

**ציטוטים:** «if(num>max)» · «mechinaNum = copy[i];»

**מה אין:** אין מערך מונים לסריקה

> אין סריקה של מערך מונים, אבל יש השוואה if(num>max) ושמירת מספר המכינה ב-mechinaNum, ולכן 2.5 נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 10

**הקריטריון:** סעיף ב: העתקה מסודרת של כל איברי מערך העזר חזרה למערך המקורי שנתקבל כפרמטר for (int i = 0; i < arr.Length; i++) arr[i] = temp[i];

**ציון:** 1.00 / 2

**ציטוטים:** «arr[i-1] = save[count];»

> בהעתקה חזרה משתמשים ב-save[-count] ו-arr[i-1], שאינו סדר נכון, ולכן 1 נקודה בלבד.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 11

**הקריטריון:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, בדיקת האם החוג הנוכחי ספורטיבי (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1 כ"א)

**ציון:** 3 / 3

**ציטוטים:** «if(hobbies[i].GetIsSportive())» · «sumSportive += hobbies[i].GetDuration();» · «countSportive++;»

> בתוך הלולאה בדוקה אם החוג ספורטיבי, דקותיו מצטברות ל-sumSportive והמונה countSportive מקודם.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 12

**הקריטריון:** בתוך הלולאה על TvShows: בדיקה אם התא אינו null

**ציון:** 0 / 2

**מה אין:** אין בדיקת null בלולאה על מערך התוכניות

> בלולאה על מערך התוכניות אין בדיקה שהתא אינו null, ולכן אין נקודות על הסעיף.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 13

**הקריטריון:** סעיף א: שורה אחרונה: להחזיר true

**ציון:** 0 / 1

**ציטוטים:** «return mirror»

> בסוף הפעולה לא מוחזר true, ולכן 0 נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 14

**הקריטריון:** סעיף ב: סריקת המערך הפרמטר ומציאת המספרים החיוביים והעתקם למערך הזמני פלוס קידום האנדקס לולאה על המערך הפרמטר 0.5 אם המספר הנוכחי במערך הפרמטר חיובי 2 העתק המספר החיובי למערך העזר 1 קידום האנדקס 1 for (int i = 0; i < arr.Length; i++) { if (arr[i] > 0) // אם המספר חיובי { temp[tempIndex] = arr[i]; // העתקת המספר החיובי למערך העזר tempIndex++;

**ציון:** 3.5 / 4.5

**ציטוטים:** «for ( int i = 0 ; i < arr.Length ; i++)» · «if (arr[i] > 0)» · «arr1[t] = arr[i] ;»

**מה אין:** t אינו מקודם אחרי ההעתקה; רק g++ בענף else

> הלולאה סורקת את המערך וזיהוי המספרים החיוביים נכון, אך t אינו מקודם אחרי ההעתקה למערך העזר.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 15

**הקריטריון:** סעיף ב: יצירת מערך עזר באותו גודל של הפרמטר + משתנה למציין של מערך העזר + אתחול ל-0 int[] temp = new int[arr.Length]; // הקצאת מערך עזר באותו הגודל int tempIndex = 0;

**ציון:** 1.0 / 2

**ציטוטים:** «int[] save = new int[arr.Length/2];» · «int count = 0;» · «int count = 0;»

> נקבע האינדקס count כשהוא מאותחל ל-0, אך לא נוצר מערך עזר באותו גודל, ולכן ניתן רק חצי מהניקוד.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 16

**הקריטריון:** סעיף א: כותרת ותכונות המחלקה Hobby

**ציון:** 4.00 / 4

**ציטוטים:** «Public class Hobby» · «private int durationInMinutes;»

> כל הדרישות בקריטריון מולאו.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 17

**הקריטריון:** סעיף א: החזרת החישוב: return this.seasonsPlayed * this.seasonSalary;

**ציון:** 2.00 / 4

**ציטוטים:** «int total = this.seasonsplayed *» · «return total;»

> הפעולה מחזירה total באמצעות return (2 נקודות), אך לא חושבה מכפלת מספר העונות בשכר לעונה, ולכן ירדו 2 נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 18

**הקריטריון:** סעיף ב: זימון נכון של הפעולה מסעיף א' על איבר מהמערך: this.workshops[i].IsSimilarWorkshop(ws)

**ציון:** 0 / 2

**מה אין:** חיפשתי זימון IsSimilarWorkshop בכל התשובה - אין

> לא זומנה הפעולה IsSimilarWorkshop על איבר מהמערך, כי אין גוף לפעולה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 19

**הקריטריון:** סעיף ב: שמות משתנים משמעותיים וקוד קריא

**ציון:** 0 / 0.5

**מה אין:** שמות כמו arr1, num, num1, L, g, t אינם משמעותיים והקוד מבולבל

> שמות המשתנים arr1, num, num1, L, g, t אינם משמעותיים והקוד מבולבל, ולכן אין נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 20

**הקריטריון:** סריקת מערך המונים למציאת המכינה (האינדקס) עם המונה הגבוה ביותר (4 נקודות) ו

**ציון:** 2.50 / 4

**ציטוטים:** «if(num>max)» · «mechinaNum = copy[i];»

**מה אין:** אין מערך מונים לסריקה

> אין סריקה של מערך מונים, אך השוואה למקסימום ושמירת מספר המכינה קיימות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 21

**הקריטריון:** סעיף ג': פעולה פנימית בשם PrintAverages (סה"כ 16)כותרת הפעולה + void

**ציון:** 0.5 / 1

**ציטוטים:** «printAverages» · «printAverages
{»

> שם הפעולה printAverages נכון, אך הוגדרה ללא void, ולכן ירדו 0.5 נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 22

**הקריטריון:** סעיף ג' בתוך PrintAverages : לולאה על מערך התחביבים מ-0 עד countHobbiesאו לולאה על מערך התחביבים עד hobbies.length ובדיקה בתוך הלולאה אם hobbies[i]!=nullאם עשו לולאה עד length ולא בדקו בפנים שהתא שונה מ-null להוריד 1

**ציון:** 2 / 3

**ציטוטים:** «for(int i=0; i< this.Hobbies.Length; i++)» · «for(int i=0; i< this.Hobbies.Length; i++)»

> הלולאה רצה עד this.Hobbies.Length בלי בדיקה שהתא שונה מ-null, ולכן ירדה נקודה אחת.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 23

**הקריטריון:** סעיף א: בתוך הלולאה: חיפוש אחר המספר הנגדי של arr[i]: int target = -arr[i]; bool found = false; for (int j = 0; j < arr.Length && found == false; j++) { if (arr[j] == target) { found = true; } }

**ציון:** 0 / 4

**ציטוטים:** «arr[i] == arr[j] - 1» · «if (arr[i] != 0 && arr[i] == arr[j] - 1)
count++;»

> לא נקבע הערך הנגדי של arr[i] ולא בוצע חיפוש שלו בין איברי המערך.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 24

**הקריטריון:** סעיף ב:בתוך הלולאה (A) : בדיקה אם המערך במקום ה- i שונה מ- null (1 נקודות) זימון של פעולה פנימית TotalEarnings עבור המערך במקום ה- i (3 נקודות) (לקנוס פעם אחת אם לא בדקו אם arr[i]!=null , הערה למטה) השוואה אם התוצאה גבוהה מהפרמטר (1 נקודה) קידום המונה (1 נקודה) if (arr[i].TotalEarnings() > amount) count++;

**ציון:** 3 / 5

**ציטוטים:** «if (arr [i].TotalEarnings() > amount» · «arr [i].TotalEarnings() > amount» · «Size ++ ;» · «if (arr [i].TotalEarnings() > amount»

**מה אין:** חיפשתי בדיקת null ל-arr[i] בלולאה הראשונה — אין

> אין בדיקת null ל-arr[i] ולכן ירדה נקודה אחת; הזימון, ההשוואה לגדול מ-amount וקידום Size נכונים.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 25

**הקריטריון:** סעיף ב בתוך PopulateHobbies: לפני הלולאה - לבדוק אם המערך מלא, להחזיר false

**ציון:** 0 / 1

**מה אין:** חיפשתי בדיקת מערך מלא לפני הלולאה עם החזרת false – אין; רק count==0 בסוף

> אין לפני הלולאה בדיקה שמחזירה false כשהמערך מלא; בסוף יש רק בדיקת count==0.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 26

**הקריטריון:** הדפסת מספר המכינה בעלת כמות מקסימלית (ולא כמות התלמידים) אם הדפיסו את הכמות להוריד 2 (או 1?)

**ציון:** 0 / 2

**ציטוטים:** «c.w("The mechina with max student: " + i) ;»

> בתשובה אין הדפסה של מספר המכינה בעלת הכמות המקסימלית, ולכן 0; הניכוי על הדפסת כמות לא חל.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 27

**הקריטריון:** סעיף ב: לולאה שנייה (B) נכונה (1 נקודה) בדיקה אם המערך במקום ה- i שונה מ- null(1 נקודות), להוריד רק פעם אחת שימוש ב-Getter לקבלת השם arr[i].GetName() (3 נקודות) השמה במערך החדש (1 נקודה) תוך קידום אינדקס נפרד (namesIndex)(1 נקודה) for (int i = 0; i < arr.Length; i++) { if (arr[i]!= null && arr[i].TotalEarnings() > amount) // אם טעו פה,להוריד 3 רק פעם 1 (יש גם זימון בלולאה א { namesArr[namesIndex] = arr[i].GetName(); // שימוש ב-Getter namesIndex++; // קידום האנדקס } }

**ציון:** 4.5 / 5

**ציטוטים:** «For (inti = 0 ; i < arr.Length ; i++)» · «arr[i] .GetName()» · «players [n] = arr [i] .GetName();» · «n++;» · «if(arr[i] .TotalEarning() > amount)»

**מה אין:** חיפשתי בדיקת null ל-arr[i] בלולאה השנייה — אין

> בלולאה השנייה אין בדיקת null; החיוב על כך כבר נגבה בלולאה הראשונה, ולכן לא ירד שוב. כל שאר הרכיבים תקינים.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 28

**הקריטריון:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, בדיקת האם החוג הנוכחי ספורטיבי (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1 כ"א)

**ציון:** 2 / 3

**ציטוטים:** «if(hobbies[i].getisSportiv()==true)» · «Avgyes += hobbies[i].getdurationIn minutes;»

**מה אין:** אין קידום מונה ספורטיבי בלולאה

> בתוך הלולאה יש בדיקה של isSportive וצבירה לצובר, אך מונה החוגים הספורטיביים לא מקודם.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 29

**הקריטריון:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם הגישה למערך בלי getter להוריד 1

**ציון:** 0 / 3

**ציטוטים:** «int[]arr = new int[tv];»

**מה אין:** הלולאה רצה על מערך int מקומי שאינו מערך התוכניות

> הלולאה רצה על מערך int מקומי ולא על מערך התוכניות, ולכן אין נקודות; הגישה הישירה למערך לא נוכתה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 30

**הקריטריון:** סעיף ב: שמות משתנים משמעותיים וקוד קריא

**ציון:** 0 / 0.5

**מה אין:** שמות כמו arr1, num, num1, L, g, t אינם משמעותיים והקוד מבולבל

> שמות המשתנים arr1, num, num1, L, g, t אינם משמעותיים והקוד קשה לקריאה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 31

**הקריטריון:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה יצירה של עצם חדש מטיפוס Hobby בתא המתאים במערך (hobbies[countHobbies])

**ציון:** 1.50 / 3

**ציטוטים:** «Hobby hobb = new Hobby(name, sportiv, min);»

**מה אין:** העצם נוצר אך לא נשמר במערך

> עצם Hobby נוצר בעזרת new, אך לא נשמר בתא hobbies[countHobbies] — נשמר רק במשתנה מקומי.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 32

**הקריטריון:** סעיף א: שורה אחרונה: להחזיר true

**ציון:** 0 / 1

**ציטוטים:** «return mirror»

> בסוף הפעולה אין החזרת true, ולכן הסעיף לא קיבל נקודה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 33

**הקריטריון:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קידום countHobbies

**ציון:** 1 / 1

**ציטוטים:** «countHobbies++;»

> countHobbies++ מופיע בתוך הלולאה אחרי הוספת התחביב, כנדרש.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 34

**הקריטריון:** סעיף ב: פעולה פנימית בשם PopulateHobbies (סה"כ 16)כותרת הפעולה + טיפוס מוחזר bool

**ציון:** 2 / 2

**ציטוטים:** «Public bool populateHobbies ()» · «Public bool populateHobbies ()»

> הכותרת Public bool populateHobbies () מגדירה פעולה פנימית בשם הנכון עם טיפוס מוחזר bool.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 35

**הקריטריון:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קידום countHobbies

**ציון:** 1 / 1

**ציטוטים:** «countHobbies++;»

> countHobbies מוגדל בתוך הלולאה אחרי הוספת התחביב.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 36

**הקריטריון:** סריקת מערך המונים למציאת המכינה (האינדקס) עם המונה הגבוה ביותר (4 נקודות) ו

**ציון:** 4.00 / 4

**ציטוטים:** «For(int i = 0 ; i < mechina.length ; i++)» · «if (mechina[i] > mechina[max])» · «max = i ;»

> הלולאה על mechina משווה if (mechina[i] > mechina[max]) ושומרת את האינדקס max = i, כלומר את מספר המכינה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 37

**הקריטריון:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קליטה של 3 נתוני התחביב (name, isSportive, minutes)

**ציון:** 3 / 3

**ציטוטים:** «string a = CR();» · «bool b = CR();» · «int c = CR();»

> בתוך הלולאה נקלטו כל 3 הנתונים: שם (string a), ספורטיביות (bool b) ודקות (int c).

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 38

**הקריטריון:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם התחילו מ-1 במקום מ-0 להוריד 0.5 אם ניגשו למערך TvShows בלי Getter להוריד 1 אם טעו בגבול העליון של הלולאה להוריד 0.5

**ציון:** 3 / 3

**ציטוטים:** «For (int i = 0; i < rates.GetArrShows.Length; i++)»

> לולאה על מערך התוכניות מתחילה מ-0 וחוזרת עד קטן ממש מ-Length, כנדרש.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 39

**הקריטריון:** הדפסת מספר המכינה בעלת כמות מקסימלית (ולא כמות התלמידים) אם הדפיסו את הכמות להוריד 2 (או 1?)

**ציון:** 0 / 2

**ציטוטים:** «c.w("The mechina with max student: " + i) ;»

> לא נכתבה הדפסה של מספר המכינה בעלת הכמות המקסימלית, ולכן אין נקודות על הסעיף.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 40

**הקריטריון:** שמות משתנים משמעותיים וקוד קריא

**ציון:** 0.5 / 0.5

**ציטוטים:** «bool mirror = true;»

> שמות כמו mirror ו-arr מבטאים את תפקידם, והקוד קריא.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 41

**הקריטריון:** סעיף ב: סריקת המערך הפרמטר ומציאת המספרים החיוביים והעתקם למערך הזמני פלוס קידום האנדקס לולאה על המערך הפרמטר 0.5 אם המספר הנוכחי במערך הפרמטר חיובי 2 העתק המספר החיובי למערך העזר 1 קידום האנדקס 1 for (int i = 0; i < arr.Length; i++) { if (arr[i] > 0) // אם המספר חיובי { temp[tempIndex] = arr[i]; // העתקת המספר החיובי למערך העזר tempIndex++;

**ציון:** 3.5 / 4.5

**ציטוטים:** «for ( int i = 0 ; i < arr.Length ; i++)» · «if (arr[i] > 0)» · «arr1[t] = arr[i] ;»

**מה אין:** t אינו מקודם אחרי ההעתקה; רק g++ בענף else

> הלולאה, הבדיקה arr[i] > 0 וההעתקה arr1[t] = arr[i] קיימות, אך t אינו מקודם אחרי ההעתקה, ולכן ירדו 1.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 42

**הקריטריון:** בתוך הלולאה על TvShows: בדיקה האם תוכנית מתאימה להדפסה:אינה null ב (2 נקודות) וגם הערוץ שלה תואם את הערוץ המינימלי (ע"י GetChl והשוואתם (2 נקודות) וגם היא באוויר (ע"י GetIsOn ב 2 נקודות) הדפסה של השם של התוכנית (ע"י GetName ב( 2 נקודות)

**ציון:** 6 / 8

**ציטוטים:** «if (arrShows[i].GetIsOn() && arrShows[i].GetChl()==lowestRateChl)» · «arrShows[i].GetChl()==lowestRateChl» · «if (arrShows[i].GetIsOn()» · «CW(arrShows[i].GetName());»

**מה אין:** חיפשתי בדיקת null בתוך הלולאה ובכל הפעולה — אין

> בדיקת null לא נכתבה בלולאה, אך GetChl, GetIsOn ו-GetName נקראו כנדרש, ולכן ירדו 2 נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 43

**הקריטריון:** התייחסות לתנאי שהאיבר שונה מ-1 ומ-x עצמו  0.5 נק'

**ציון:** 1.5 / 1.5

**ציטוטים:** «וגם לא אחד» · «שהם לא המספר עצמו»

> התשובה ציינה שהמחלק צריך להיות שונה מ-1 («וגם לא אחד») ומ-x עצמו («שהם לא המספר עצמו»).

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 44

**הקריטריון:** סעיף ב:בתוך הלולאה (A) : בדיקה אם המערך במקום ה- i שונה מ- null (1 נקודות) זימון של פעולה פנימית TotalEarnings עבור המערך במקום ה- i (3 נקודות) (לקנוס פעם אחת אם לא בדקו אם arr[i]!=null , הערה למטה) השוואה אם התוצאה גבוהה מהפרמטר (1 נקודה) קידום המונה (1 נקודה) if (arr[i].TotalEarnings() > amount) count++;

**ציון:** 3 / 5

**ציטוטים:** «if (arr [i].TotalEarnings() > amount» · «arr [i].TotalEarnings() > amount» · «Size ++ ;» · «if (arr [i].TotalEarnings() > amount»

**מה אין:** חיפשתי בדיקת null ל-arr[i] בלולאה הראשונה — אין

> TotalEarnings מזומנת והשוואה ל-amount נכונה, אך חסרה בדיקת null ל-arr[i] בלולאה הראשונה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 45

**הקריטריון:** סעיף א: שורה אחרונה: להחזיר true

**ציון:** 0 / 1

**ציטוטים:** «return true;»

> בסוף הפעולה לא מוחזר true, ולכן אין נקודה על הסעיף.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 46

**הקריטריון:** סעיף ב: משתנים משמעותיים + קוד קריא

**ציון:** 0 / 0.5

**מה אין:** שמות לא עקביים, קוד מבולגן ולא קריא (workshop/workShops, g)

> שמות המשתנים לא עקביים (workshop/workShops, g) והקוד לא קריא, ולכן אין נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 47

**הקריטריון:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם הגישה למערך בלי getter להוריד 1

**ציון:** 0 / 3

**ציטוטים:** «int[]arr = new int[tv];»

**מה אין:** הלולאה רצה על מערך int מקומי שאינו מערך התוכניות

> הלולאה רצה על מערך int מקומי ולא על מערך התוכניות arrShows, ולכן אפס נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 48

**הקריטריון:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, בדיקת האם החוג הנוכחי ספורטיבי (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1 כ"א)

**ציון:** 3 / 3

**ציטוטים:** «if(hobbies[i].GetIsSportive())» · «sumSportive += hobbies[i].GetDuration();» · «countSportive++;»

> בתוך הלולאה נבדק GetIsSportive(), הדקות נצברות ב-sumSportive והמונה countSportive מקודם.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 49

**הקריטריון:** סעיף ב: סריקת המערך הפרמטר ומציאת המספרים החיוביים והעתקם למערך הזמני פלוס קידום האנדקס לולאה על המערך הפרמטר 0.5 אם המספר הנוכחי במערך הפרמטר חיובי 2 העתק המספר החיובי למערך העזר 1 קידום האנדקס 1 for (int i = 0; i < arr.Length; i++) { if (arr[i] > 0) // אם המספר חיובי { temp[tempIndex] = arr[i]; // העתקת המספר החיובי למערך העזר tempIndex++;

**ציון:** 2.5 / 4.5

**ציטוטים:** «for (int i=0; i<arr.length; i++)» · «newArr[i] = arr[j];» · «for (int i=0; i<arr.length; i+=2)»

**מה אין:** הבדיקה היא arr[i]<0 (שלילי) ולא חיובי; arr[j]!=0 אינו בדיקת חיוביות

> הלולאה, ההעתקה newArr[i] = arr[j] וקידום המציין קיימים, אך הבדיקה היא arr[i]<0 (שלילי) ולא חיובי, ולכן ירדו 2 נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 50

**הקריטריון:** סעיף ג': פעולה פנימית בשם PrintAverages (סה"כ 16)כותרת הפעולה + void

**ציון:** 0.5 / 1

**ציטוטים:** «printAverages» · «printAverages
{»

> הפעולה נקראת printAverages, אך הכותרת אינה void, ולכן ניתנה חצי נקודה בלבד.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 51

**הקריטריון:** בתוך הלולאה על TvShows: בדיקה אם התא אינו null

**ציון:** 0 / 2

**מה אין:** חיפשתי בדיקת null בלולאה על התוכניות ובכל הפעולה — אין

> אין בדיקה שהתא אינו null, לא בלולאה ולא בשאר הפעולה, ולכן אין נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 52

**הקריטריון:** סעיף ב: יצירת מערך עזר באותו גודל של הפרמטר + משתנה למציין של מערך העזר + אתחול ל-0 int[] temp = new int[arr.Length]; // הקצאת מערך עזר באותו הגודל int tempIndex = 0;

**ציון:** 1.0 / 2

**ציטוטים:** «int[] save = new int[arr.Length/2];» · «int count = 0;» · «int count = 0;»

> מערך עזר לא נוצר; רק משתנה count מאותחל ל-0 כמציין, ולכן 1 נקודה בלבד.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 53

**הקריטריון:** סעיף ב: לולאה שנייה (B) נכונה (1 נקודה) בדיקה אם המערך במקום ה- i שונה מ- null(1 נקודות), להוריד רק פעם אחת שימוש ב-Getter לקבלת השם arr[i].GetName() (3 נקודות) השמה במערך החדש (1 נקודה) תוך קידום אינדקס נפרד (namesIndex)(1 נקודה) for (int i = 0; i < arr.Length; i++) { if (arr[i]!= null && arr[i].TotalEarnings() > amount) // אם טעו פה,להוריד 3 רק פעם 1 (יש גם זימון בלולאה א { namesArr[namesIndex] = arr[i].GetName(); // שימוש ב-Getter namesIndex++; // קידום האנדקס } }

**ציון:** 4.5 / 5

**ציטוטים:** «For (inti = 0 ; i < arr.Length ; i++)» · «arr[i] .GetName()» · «players [n] = arr [i] .GetName();» · «n++;» · «if(arr[i] .TotalEarning() > amount)»

**מה אין:** חיפשתי בדיקת null ל-arr[i] בלולאה השנייה — אין

> GetName() מזומנת נכון והשמה במערך עם קידום אינדקס תקין; בדיקת null בלולאה השנייה כבר נוכתה בלולאה הראשונה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 54

**הקריטריון:** סעיף ב: זימון נכון של הפעולה מסעיף א' על איבר מהמערך: this.workshops[i].IsSimilarWorkshop(ws)

**ציון:** 0 / 2

**מה אין:** חיפשתי זימון IsSimilarWorkshop בכל התשובה - אין

> הפעולה IsSimilarWorkshop מסעיף א' לא זומנה בתשובה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 55

**הקריטריון:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם הגישה למערך בלי getter להוריד 1

**ציון:** 3 / 3

**ציטוטים:** «for(int i = 0; i < tvRate1.GetArrShows().Length; i++)»

> הלולאה עוברת על כל תאי המערך מ-0 עד Length-1 בעזרת GetArrShows().

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 56

**הקריטריון:** בתוך הלולאה על TvShows: בדיקה אם התא אינו null

**ציון:** 0 / 2

**מה אין:** אין בדיקת null בלולאה על מערך התוכניות

> אין בדיקת null בלולאה על מערך התוכניות, ולכן לא ניתנו נקודות על הסעיף.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 57

**הקריטריון:** סעיף ג' בתוך PrintAverages : מחוץ ללולאה,בדיקה האם המונה של התחביבים הלא-הספורטיבים שונה מאפס (1)אם לא מנעו חלוקה באפס להוריד 1חישוב הממוצע והדפסה (1) (אם טעו בחישוב מתמטי להוריד 0.5)אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)

**ציון:** 0 / 2

**ציטוטים:** «cw("the non spotiv Avg is: " + AvgNS);» · «double AvgNS = totaldurationNS / counterNS;»

**מה אין:** חיפשתי בדיקת מונה שונה מאפס לפני החישוב - אין

> לא נבדק אם counterNS שונה מאפס לפני חישוב הממוצע, ולא הודפס ממוצע החוגים הלא ספורטיביים.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 58

**הקריטריון:** בתוך הלולאה על מערך הצוברים: בדיקה האם התא מתאים לערוץ הנוכחי של TvShow בתוך מערך הצוברים גדול מאפס (כלומר יש שימוש בערוץ זה) - לא להוריד, לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום - סה"כ 2 נקודות

**ציון:** 3 / 3

**ציטוטים:** «if(chRate[i] < chRate[minRate])»

> כל הדרישות בקריטריון מולאו.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 59

**הקריטריון:** סעיף א: שורה אחרונה: להחזיר true

**ציון:** 0 / 1

**ציטוטים:** «return true;»

> בסוף הפעולה לא מוחזר true.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 60

**הקריטריון:** סעיף ב בתוך PopulateHobbies: לפני הלולאה - לבדוק אם המערך מלא, להחזיר false

**ציון:** 0 / 1

**מה אין:** חיפשתי בדיקת מערך מלא לפני הלולאה עם החזרת false – אין; רק count==0 בסוף

> חסרה בדיקה לפני הלולאה אם המערך מלא מראש עם החזרת false.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 61

**הקריטריון:** בתוך הלולאה על TvShows: בדיקה אם התא אינו null

**ציון:** 0 / 2

**מה אין:** חיפשתי בדיקת null בלולאה על התוכניות ובכל הפעולה — אין

> אין בדיקה אם התא במערך התוכניות אינו null, ולכן לא זוכו 2 הנקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 62

**הקריטריון:** סעיף א: חתימת הפעולה (ללא מילה static!) public bool IsSimilarWorkshop(Workshop other) כל טעות פה להוריד 1

**ציון:** 1 / 1

**ציטוטים:** «Public bool IsSimilarWorkShop (workShop other)»

> החתימה נכונה: הפעולה פנימית (ללא static), מחזירה bool, מקבלת Workshop, אך שם הפעולה כתוב IsSimilarWorkShop במקום IsSimilarWorkshop.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 63

**הקריטריון:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה יצירה של עצם חדש מטיפוס Hobby בתא המתאים במערך (hobbies[countHobbies])

**ציון:** 1.50 / 3

**ציטוטים:** «Hobby hobb = new Hobby(name, sportiv, min);»

**מה אין:** העצם נוצר אך לא נשמר במערך

> נוצר עצם חדש Hobby hobb = new Hobby(name, sportiv, min), אך הוא לא נשמר בתא של hobbies; לכן ניתנה חצי מהנקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 64

**הקריטריון:** בניית מערך התוצאה: מילוי נכון של המערך החדש בזוגות: קודם את result[resIndex] = i ומיד לאחר מכן result[resIndex+1] = counters[i] תוך קידום ידני תקין של אינדקס מערך היעד ב-2 בכל פעם.

**ציון:** 0 / 8

**ציטוטים:** «result[j] = Mecina[i];» · «result[j+1] = i;»

**מה אין:** j לא מקודם בלולאת המילוי

> לא נכתבו מספר המכינה וכמות התלמידים בזוגות למערך היעד, ולא קודם אינדקס j בלולאת המילוי.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 65

**הקריטריון:** סעיף ב: העתקה מסודרת של כל איברי מערך העזר חזרה למערך המקורי שנתקבל כפרמטר for (int i = 0; i < arr.Length; i++) arr[i] = temp[i];

**ציון:** 1.00 / 2

**ציטוטים:** «arr[i-1] = save[count];»

> קיימת לולאת העתקה חזרה, אך arr[i-1] = save[count] אינה מעתיקה לפי הסדר, ולכן ניתנה חצי מהנקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 66

**הקריטריון:** ניקוד טבלת מעקב סה"כ 12 נקודות: 17 תאים  0.7 כל תא

**ציון:** 12 / 12

**ציטוטים:** «| 4 | t | 3 | 6 | t |  |»

> כל 17 התאים בטבלת המעקב מולאו נכון, כולל השורה האחרונה: arr[i]=3, התנאי T והערך המוחזר true.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 67

**הקריטריון:** סעיף ג' בתוך PrintAverages : מחוץ ללולאה,בדיקה האם המונה של התחביבים הלא-הספורטיבים שונה מאפס (1)אם לא מנעו חלוקה באפס להוריד 1חישוב הממוצע והדפסה (1) (אם טעו בחישוב מתמטי להוריד 0.5)אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)

**ציון:** 0 / 2

**ציטוטים:** «cw("the non spotiv Avg is: " + AvgNS);» · «double AvgNS = totaldurationNS / counterNS;»

**מה אין:** חיפשתי בדיקת מונה שונה מאפס לפני החישוב - אין

> אחרי הלולאה אין בדיקה שמונה הלא ספורטיביים שונה מאפס, וגם לא חושב או הודפס ממוצע, ולכן 0.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 68

**הקריטריון:** סעיף א: חתימת הפעולה (ללא מילה static!) public bool IsSimilarWorkshop(Workshop other) כל טעות פה להוריד 1

**ציון:** 1 / 1

**ציטוטים:** «Public bool IsSimilarWorkShop (workShop other)»

> החתימה נכונה: פעולה פנימית ללא static, מחזירה bool ומקבלת פרמטר אחד מטיפוס Workshop; הבדלי אותיות גדולות/קטנות בשמות אינם פוגעים.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 69

**הקריטריון:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם הגישה למערך בלי getter להוריד 1

**ציון:** 2 / 3

**ציטוטים:** «for(int i=0; i<A.Length; i++)» · «A[i].getchl()»

> הלולאה עוברת על כל תאי המערך מ-0 עד A.Length, אך הגישה למערך ישירה בלי GetArrShows, ולכן ירדה נקודה אחת.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 70

**הקריטריון:** סעיף ג' בתוך PrintAverages : לולאה על מערך התחביבים מ-0 עד countHobbiesאו לולאה על מערך התחביבים עד hobbies.length ובדיקה בתוך הלולאה אם hobbies[i]!=nullאם עשו לולאה עד length ולא בדקו בפנים שהתא שונה מ-null להוריד 1

**ציון:** 2 / 3

**ציטוטים:** «for(int i=0; i< this.Hobbies.Length; i++)» · «for(int i=0; i< this.Hobbies.Length; i++)»

> הלולאה רצה עד this.Hobbies.Length ללא בדיקה שהתא שונה מ-null בתוכה, ולכן ירדה נקודה אחת.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 71

**הקריטריון:** בתוך הלולאה על מערך הצוברים: בדיקה האם התא מתאים לערוץ הנוכחי של TvShow בתוך מערך הצוברים גדול מאפס (כלומר יש שימוש בערוץ זה) - לא להוריד, לכתוב הערהוהאם סה"כ הדירוגים קטן מהמינימום - סה"כ 2 נקודות

**ציון:** 3 / 3

**ציטוטים:** «if(chRate[i] < chRate[minRate])»

> בדיקה השוואת הדירוג של הערוץ הנוכחי לדירוג המינימלי קיימת.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 72

**הקריטריון:** סעיף א: כותרת ותכונות המחלקה Hobby

**ציון:** 4.00 / 4

**ציטוטים:** «Public class Hobby» · «private int durationInMinutes;»

> הכותרת Public class Hobby ושלוש התכונות, כולל int durationInMinutes, מוגדרות בטיפוסים המתאימים.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 73

**הקריטריון:** ניקוד טבלת מעקב סה"כ 12 נקודות: 17 תאים  0.7 כל תא

**ציון:** 12 / 12

**ציטוטים:** «| 4 | t | 3 | 6 | t |  |»

> כל 17 התאים בטבלת המעקב מלאים בנכון, כולל הערכים של המשתנים, התנאי, וערך ההחזרה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 74

**הקריטריון:** סעיף ב בתוך PopulateHobbies: בתוך הלולאה קליטה של 3 נתוני התחביב (name, isSportive, minutes)

**ציון:** 3 / 3

**ציטוטים:** «string a = CR();» · «bool b = CR();» · «int c = CR();»

> בתוך הלולאה נקלטו שלושת הנתונים: שם ב-string a, ספורטיביות ב-bool b ודקות ב-int c.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 75

**הקריטריון:** סריקת מערך המונים למציאת המכינה (האינדקס) עם המונה הגבוה ביותר (4 נקודות) ו

**ציון:** 4.00 / 4

**ציטוטים:** «For(int i = 0 ; i < mechina.length ; i++)» · «if (mechina[i] > mechina[max])» · «max = i ;»

> מערך המונים נסרק, המקסימום נמצא בהשוואה if (mechina[i] > mechina[max]) והאינדקס נשמר ב-max = i.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 76

**הקריטריון:** סעיף ג' בתוך PrintAverages : בתוך הלולאה, בדיקת האם החוג הנוכחי ספורטיבי (1)+ צבירה של הדקות שלו (1)+ קידום המונה שלו (1 כ"א)

**ציון:** 2 / 3

**ציטוטים:** «if(hobbies[i].getisSportiv()==true)» · «Avgyes += hobbies[i].getdurationIn minutes;»

**מה אין:** אין קידום מונה ספורטיבי בלולאה

> נבדק hobbies[i].getisSportiv()==true והדקות נצברו ב-Avgyes, אך מונה הספורטיביים לא קודם.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 77

**הקריטריון:** שמות משתנים משמעותיים וקוד קריא

**ציון:** 0.5 / 0.5

**ציטוטים:** «bool mirror = true;»

> שמות המשתנים mirror, i, g משמעותיים והקוד קריא.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 78

**הקריטריון:** סעיף א: החזרת החישוב: return this.seasonsPlayed * this.seasonSalary;

**ציון:** 2.00 / 4

**ציטוטים:** «int total = this.seasonsplayed *» · «return total;»

> המכפלה של seasonsPlayed בseasonSalary לא מחושבת בפעולה, אך התוצאה מוחזרת ב-return total.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 79

**הקריטריון:** סעיף ב: משתנים משמעותיים + קוד קריא

**ציון:** 0 / 0.5

**מה אין:** שמות לא עקביים, קוד מבולגן ולא קריא (workshop/workShops, g)

> השמות לא עקביים (workshop/workShops) ומשתנה בשם g אינו משמעותי, והקוד מבולגן, ולכן אין נקודות.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

### 80

**הקריטריון:** הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ- length של מערך ה -TvShowsאם התחילו מ-1 במקום מ-0 להוריד 0.5 אם ניגשו למערך TvShows בלי Getter להוריד 1 אם טעו בגבול העליון של הלולאה להוריד 0.5

**ציון:** 3 / 3

**ציטוטים:** «For (int i = 0; i < rates.GetArrShows.Length; i++)»

> הלולאה על rates.GetArrShows.Length רצה מ-0 עד length ממש וניגשת למערך דרך Getter, ולכן אין הורדה.

faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no

---
Strata drawn (seed 6): {'full': 10, 'partial': 10, 'zero': 10, 'deduction': 10}. The arm key is in a separate file.
