=== PAGE 1 ===
שאלה 1 
א.

public class Hobby
{
    private string hobbyName;
    private bool isSportive;
    private int durationInMinutes;

    public Hobby (string hobbyName, bool isSportive, int minutes)
    {
        this.hobbyName = hobbyName; // פעולה בונה
        this.isSportive = isSportive;
        this.durationInMinutes = minutes;
    }








}

=== PAGE 2 ===
שאלה 1 
ב.
public class SchoolHobbies
{
    public bool PopulateHobbies()
    {
        if(countHobbies == hobbies.Length)
            return false;

        else
        {
            char add = y;

            While ((countHobbies < hobbies.Length) && add != n && add != N)
            {
                CW("enter hobby name:");
                string name = CR();
                CW("enter is the hobby sportive:");
                bool sportive = bool.Parse(CR());
                CW("enter the hobby's duration in mins:");
                int duration = int.Parse(CR());

                hobbies(countHobbies) = new Hobby(name, sportive, duration);
                countHobbies++;
                CW("do you want to create another hobby?");
                add = char.Parse(CR());
            }
        }

        return true; // גם לא הוחזר בהתחלה
                                  // false אז מקבלת והוחזר true.
    }
}

=== PAGE 3 ===
שאלה 1 
ג.

public void PrintAverages()
{
    int sumSportive = 0;  int countSportive = 0;
    int sumNotS = 0;   int countNotS = 0;
    

    for(int i=0; i < countHobbies; i++)
    {
        if(hobbies[i].GetIsSportive())
        {
            sumSportive += hobbies[i].GetDuration();
            countSportive++;
        }
        else
        {
            sumNotS += hobbies[i].GetDuration();
            countNotS++;
        }
    }

    double averageSportive = (double)(sumSportive) / countSportive;
    double averageNotS = (double)(sumNotS) / countNotS;

    CW("average time of sportive hobbies is:");
    CW(averageSportive + "minutes");

    CW("average time of not sportive hobbies is {0} minutes", averageNotS);
}

=== PAGE 4 ===
שאלה 2 
א.
public class TvShow
{
    public TvShow (string name, int channel) // פעולה בונה
    {
        this.name = name;
        this.chl = channel;
        this.rate = 0;
        this.isOn = true;
    }

    Public void UpdateRate (int numViewers)
    {
        For (int i = 0; i < numViewers; i++)
        {
            CW("enter your rate For the TV Show:");
            int ViewerRate = int.Parse(CR());

            SetRate(GetRate() + viewerRate);
            // שינוי דירוג התוכנית למה שהיה פלוס הדירוג החדש.
        }
    }
}

=== PAGE 5 ===
שאלה 2
ב.
Public Static int LowestRateChannel (TVRate rates)
{
    int[] chlRates = new int[100]; // מערך צבירה חדש

    for(int i = 0; i < chlRates.Length; i++) // איפוס המערך
    {
        chlRates[i] = 0;
    }

    For (int i = 0; i < rates.GetArrShows.Length; i++) // מילוי המערך
    {
        chlRates[arrShows[i].GetChl()] += arrShows[i].GetRate();
    }

    int lowestRate = int.MaxValue;
    int chlNum = -1;

    For(int i = 1; i <= 100; i++) // מציאת והדפסת מספר הערוץ עם הדירוג בנמוך ביותר
    {
        if (chlRate[i] < lowestRate)
        {
            lowestRate = chlRate[i];
            chlNum = i;
        }
    }
    return chlNum;
    
}

=== PAGE 6 ===
שאלה 2 
ג.
Public Static void PrintLowRatingChannel(TVRate rates)
{
    int lowestRateChl = LowestRateChannel(rates);

    TVShow[] arrShows = new TVShow[rates.GetArrShows().Length];
    arrShows = rates.GetArrShows(); // השמאת מערכים

    for(int i = 0; i < rates.GetArrShows().Length; i++)
    {
        if (arrShows[i].GetIsOn() && arrShows[i].GetChl()==lowestRateChl)
            CW(arrShows[i].GetName());
    }
}
