=== PAGE 1 ===
שאלה 1
public class Hobby
{
    private string hobbyName;
    private bool isSportive;
    private int durationInMinutes;

    public Hobby(string hobbyName, bool isSportive, int minutes)
    {
        this.hobbyName = hobbyName;
        this.isSportive = isSportive;
        durationInMinutes = minutes;
    }
}

ב.
public class School Hobbies
{
    public bool PopulateHobbies()
    {
        int count=0; // סופר כמה פעמים עדכן משתנה (אם לא עדכן נחזיר fake)
        for(int i=0; i<hobbies.Length; i++)
        {
            if(hobbies[i] != null)
            {
                Console.Write("Do you want to create another hobby?");
                Char answer = Char.Parse(Console.ReadLine());
                if(answer!='n' && answer!='N')
                {
                    CW("Enter the hobby name:");
                    string hobbyname = Console.ReadLine();

                    CW("Enter if the hobby is sportive: ");
                    bool isSportive = bool.Parse(Console.ReadLine());

=== PAGE 2 ===
                    CW("The duration in minutes: ");
                    int duration = int.Parse(Console.ReadLine());

                    hobbies[i] = new Hobby(hobbyName,isSportive,duration);
                    countHobbies++;
                    count++;
                }
            }
        }
    }
        if(count==0)
            return false;

        return true;
}

ג.
public Void PrintAverages()
{
    int countSport=0; int sumSport=0;
    int countNonSport=0; int sumNonSport=0;

    for(int i=0; i<hobbies.Length; i++)
    {
        if(hobbies[i] != null)
        {
            if(hobbies[i].GetIsSportive())
            {
                count Sport++;
                sumSport += hobbies[i].GetDurationInMinutes;
            }
            else
            {
                countNonSport++;
                sumNonSport += hobbies[i].GetDurationInMinutes;
            }
        }
    }

=== PAGE 3 ===
    CW("The average for sportive is {0}",(double)sumSport/countSport);
    CW("The average for non sportive is {0}",(double)sumNonSport/countNonSport);
}

=== PAGE 4 ===
שאלה 2 
public class TvShow
{
    private string name;
    private int rate;
    private int chl;
    private bool isOn;

    public TvShow(string name, int channel)
    {
        this.name = name;
        rate = 0;
        this.chl = channel;
        isOn = true;
    }

    public Void UpdateRate(int numViewers)
    {
        for(int i=0; i<numViewers; i++)
        {
            CW("Enter your rate: ");
            int rate = int.Parse(Console.ReadLine());
            this.rate += rate;
        }
    }
}

=== PAGE 5 ===
ג.
public static Void PrintLowRatingChannel(TVRate tvRate)
{
    int chl = LowestRateChannel(tvRate);

    TVShow[] arr = tvRate.GetArrShows();

    for(int i=0; i<arr.Length; i++)
    {
        if(arr[i].GetChl() == chl && arr[i].GetIsOn)
            CW(arr[i].GetName());
    }
}

=== PAGE 6 ===
ד.
public static int LowestRateChannel(TVRate tvRate)
{
    int[] arr = new int[101];

    TvShow[]arrShow = TVRate.GetArrShows();

    for(int i=0; i<arr.Length; i++)
        arr[i] = 0;

    For(int i=0; i<arrShow.Length; i++)
    {
        int channel = arrShow[i].GetChl();
        arr[channel] += arrShow[i].GetRate();
    }

    int minRate = int.MaxValue;
    int minChl = 0;

    for(int i=1; i<arr.Length; i++)
    {
        if(arr[i] < minRate)
        {
            minRate = arr[i];
            minChl = i;
        }
    }

    return minChl;
}
