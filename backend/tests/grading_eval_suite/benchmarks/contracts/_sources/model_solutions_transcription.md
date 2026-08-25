# MODEL SOLUTIONS — transcription for ratification (H1-A2 input)

**Source:** 7 owner-supplied screenshots of the teacher's model solutions (IDE render).
**Transcriber:** Claude · **Ratifier:** Noam (check against the images — this is teacher material; the bar is accuracy, not blindness).
**Mapping:** q1.א ← image7 · q1.ב ← image1 · q1.ג ← image2 · q2.א ← images 3+4 (two methods, one scope) · q2.ב ← image5 · q2.ג ← image6.

**Transcription conventions applied (ratify these too):**
- **T-1** IDE chrome excluded: the "0/1 references" CodeLens lines are editor furniture, not solution content.
- **T-2** RTL comment normalization: Hebrew comments are transcribed in logical reading order with parentheses/apostrophes placed logically (the screenshots' mixed-direction rendering scrambles them visually). Code is byte-faithful; comments are meaning-faithful.
- **T-3** Hebrew comment spellings were flagged ⟨?⟩ where uncertain; all were resolved during ratification (one corrected in-review, the rest confirmed).

**Status: RATIFIED — Noam, 2026-08-25.** One in-review correction applied (the `minChannel` comment); all other content confirmed 100% accurate against the source images.

---

## q1.א — example_solution (image 7)

```csharp
internal class Hobby
{
    // תכונות
    private string hobbyName;        // שם התחביב
    private bool isSportive;         // האם התחביב ספורטיבי
    private int durationInMinutes;   // משך הפעילות בדקות (1-60)

    // פעולה בונה
    public Hobby(string hobbyName, bool isSportive, int minutes)
    {
        this.hobbyName = hobbyName;
        this.isSportive = isSportive;
        if (minutes >= 0 && minutes <= 60)
            this.durationInMinutes = minutes;
        // אם לא בדקתם טווח 0-60 גם בסדר
    }
}
```

## q1.ב — example_solution (image 1)

```csharp
// סעיף ב'
public bool PopulateHobbies()
{
    // אם המערך מלא מראש
    if (countHobbies == hobbies.Length)
        return false;

    bool addedAtLeastOne = false;
    string answer = "Y";

    while (countHobbies < hobbies.Length && answer != "N" && answer != "n")
    {
        Console.WriteLine("Enter hobby name:");
        string name = Console.ReadLine();

        Console.WriteLine("Is the hobby sportive? (true/false):");
        bool isSportive = bool.Parse(Console.ReadLine());

        Console.WriteLine("Enter duration in minutes (1-60):");
        int minutes = int.Parse(Console.ReadLine());

        // יצירת אובייקט חדש והוספה לתא הפנוי הראשון
        hobbies[countHobbies] = new Hobby(name, isSportive, minutes);
        countHobbies++;            // מקדמים את המונה מס' העצמים המלאים
        addedAtLeastOne = true;

        if (countHobbies < hobbies.Length)
        {
            Console.WriteLine("Do you want to create another hobby? (Y/N)");
            answer = Console.ReadLine();
        }
    }

    return addedAtLeastOne;
}
```

## q1.ג — example_solution (image 2)

```csharp
// סעיף ג'
public void PrintAverages()
{
    int sportSum = 0, sportCount = 0;
    int nonSportSum = 0, nonSportCount = 0;

    for (int i = 0; i < countHobbies; i++)
    {
        if (hobbies[i].GetIsSportive())
        {
            sportSum += hobbies[i].GetDurationInMinutes();
            sportCount++;
        }
        else
        {
            nonSportSum += hobbies[i].GetDurationInMinutes();
            nonSportCount++;
        }
    }

    if (sportCount > 0)
        Console.WriteLine("Average duration of sportive hobbies: " +
                          (double)sportSum / sportCount);
    else
        Console.WriteLine("No sportive hobbies (0).");

    if (nonSportCount > 0)
        Console.WriteLine("Average duration of non-sportive hobbies: " +
                          (double)nonSportSum / nonSportCount);
    else
        Console.WriteLine("No non-sportive hobbies (0).");
}
```

## q2.א — example_solution (images 3 + 4, concatenated)

```csharp
// פעולה בונה לפי סעיף א'
// מתקבלים name ו-channel
// קובעים rate = 0 , isOn = true
public TvShow(string name, int channel)
{
    this.name = name;
    this.chl = channel;
    this.rate = 0;
    this.isOn = true;
}

// פעולה לניהול קליטת דירוג הצופים (סעיף א)
// מקבלת מספר צופים
// קולטת דירוגים עבור כ"א מהצופים ומוסיפה את הדירוג שנקלט לדירוג הקיים
public void UpdateRate(int numViewers)
{
    int viewerRate;

    for (int i = 1; i <= numViewers; i++)
    {
        Console.WriteLine("Enter rating for viewer " + i + ":");
        viewerRate = int.Parse(Console.ReadLine());
        rate += viewerRate;
    }
}
```

## q2.ב — example_solution (image 5)

```csharp
//Q2 - start
// שאלה 2 סעיף ב
public static int LowestRateChannel(TvRate tr)
{
    TvShow[] arrTvShows = tr.GetArrShows();

    // מערך צוברים לדירוג ערוצים (אינדקס 1-100)
    int[] sumRates = new int[101];      //

    // איפוס כל התאים ל-0
    for (int i = 0; i < sumRates.Length; i++)
        sumRates[i] = 0;

    // צבירת דירוגים לכל ערוץ
    for (int i = 0; i < arrTvShows.Length; i++)
    {
        if (arrTvShows[i] != null)
        {
            int channel = arrTvShows[i].GetChl();
            sumRates[channel] += arrTvShows[i].GetRate();
        }
    }

    // מציאת הערוץ בעל הדירוג הנמוך ביותר
    int minRate = int.MaxValue;   // כל ערך יהיה נמוך מזה
    int minChannel = -1;          // מניחים שקיים 1 ורק 1 ערוץ קיים בעל דירוג מינימלי ולכן הערך הזה יוחלף

    for (int chl = 1; chl <= 100; chl++)
    {
        // ערוץ שנעשה בו שימוש (יש לו דירוג שנצבר)
        if (   sumRates[chl] > 0     // קיים דירוג כלשהו לערוץ הזה
            && sumRates[chl] < minRate)
        {
            minRate = sumRates[chl];
            minChannel = chl;
        }
    }

    return minChannel;
}
```

## q2.ג — example_solution (image 6)

```csharp
// שאלה 2 סעיף ג
public static void PrintLowRatingChannel(TvRate tr)
{
    int lowChannel = LowestRateChannel(tr);
    TvShow[] arr = tr.GetArrShows();

    for (int i = 0; i < arr.Length; i++)
    {
        if (arr[i] != null && arr[i].GetChl() == lowChannel && arr[i].GetIsOn())
        {
            Console.WriteLine(arr[i].GetName());
        }
    }
}
```
