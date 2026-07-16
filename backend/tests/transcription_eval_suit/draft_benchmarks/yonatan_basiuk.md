=== Q1.א ===
public class Hobby
{
    private string hobbyName; // הגדרת תכונות
    private bool isSportive;
    private int durationInMinutes;

    public Hobby(string hobbyName, bool isSportive, int minutes)
    {
        this.hobbyName = hobbyName;
        this.isSportive = isSportive;
        this.durationInMinutes = Minutes;
    }
}

=== Q1.ב ===
public class schoolHobbies
{
    public bool populateHobbies()
    {
        int string num = ""; bool isSportive = true; int duration = 0;

        if (this.countHobbies == this.hobbies.Length)
            return false; // בדיקה אם מלא

        Console.Write("Do you want to create another hobby?");
        char answer = char.Parse(Console.ReadLine());

        for(int i = this.countHobbies; (i < this.hobbies.Length)
            && (answer != "N") && (answer != "n"); i++)
        {
            if (this.hobbies[i] == null)
            {
                CW("enter name: ")
                name = CR();

                CW("enter true if sportive and false
                if not: ");
                isSportive = bool.Parse(CR());

                CW("enter duration(minutes): ");
                duration = int.Parse(CR());

                this.hobbies[i] = new Hobby(name,
                isSportive, duration); // יצירת תחביב חדש
            }

            CW("Do you want to create another
            another hobby?");
            char answer = char.Parse(CR());
        }

        return true;
    }
}
=== Q1.ג ===
public void printAverages()
{
    double sumSportive = 0;
    double int sumNoSportive = 0;
    int count = 0;
    int count1 = 0;

    for(int i = 0; i < this.hobbies.Length; i++)
    {
        if (this.hobbies[i].GetisSportive())
        {
            sumSportive += this.hobbies[i].GetdurationInMinutes
            count ++
        }
        else
        {
            sumNoSportive += this.hobbies[i].GetdurationInMinutes;
            count1++;
        }
    }

    CW("the average ua sportive is: " + sumSportive / count);
    CW("the average ua NotSportiv is: " + sumSportive / count);

=== Q2.א ===
public class TVshow
{
    public TVshow(String name, int channel)
    {
        this.name = name;
        this.chl = channel;
        this.rate = 0;
        this.isOn = true;
    }

    public void updateRate(int numViewers)
    {
        int rate = 0;
        for(int i = 0; i < numViewers; i++)
        {
            this.rate +=
            CW("enter rating: ");
            int rate = int.Parse(CR());
            this.rate += rate;
        }
    }
}

=== Q2.ב ===
 // TVshow() arrShows

public static int LowestRateChannel(TVRate tvRate)
{
    int[] chRate = new int[101]

    for(int i = 0; i < chRate.Length; i++) / chRate[i] = 0;

    for(int i = 0; i < tvRate.Length; i++)
    {
        if(tvRate.GetarrShows()[i] != null)
        {
            chRate[tvRate[i].Getch()] += tvRate[i].Getrate();
        }
    }

    int minRate = chRate[0];

    for(int i = 0; i < chRate.Length; i++)
    {
        if(chRate[i] < chRate[minRate])
        {
            minRate = i;
        }
    }

    return minRate;
}

=== Q2.ג ===
public static void PrintLowRatingchannel(tVRate tvRate1)
{
    int channel = LowestRateChannel(tvRate1);

    for(int i = 0; i < tvRate1.GetArrShows().Length; i++)
    {
        if(tvRate1.GetArrShows()[i] != null)
        {
            if((tvRate1.GetArrShows()[i].GetChl() == channel)
            && (tvRate1.GetArrShows()[i].GetIsOn() == true))
            {
                CW(tvRate1.GetArrShows()[i].GetName());
            }
        }
    }
}
