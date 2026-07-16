=== PAGE 1 ===
שאלה 1 
א.

Public class Hobby
{
    private string hobbyName;
    private bool isSportive;
    private int durationInMinutes; \\ 1-60

    public Hobby (string hobbyName ,bool isSportive ,int minutes)
    {
        this.hobbyName = hobbyName;
        this.isSportive = isSportive;
        this.minutes = minutes;
    }
}

=== PAGE 2 ===
שאלה 1 
ב.
Public bool populateHobbies ()
{
    bool added = false;
    bool going = true;

    for (int i=0; i< this.hobbies.Length; i++)
    {
        cw("do u want to create another hobby?");  // אם מאושר להמשיך
        string answear = CR();
        if(answear == "n" || answear == "N")
            going = false;

        if((this.hobbies[i] == null) && (going == true))  // אישור להמשיך/מקום פנוי
        {
            added = true;   // אפשר להכניס
            cw("enter bobbyName , if its sportive and it duration");
            string a = CR();
            bool b = CR();
            int c = CR();
            this.hobbies[i] = new Hobby(a,b,c); // יצירת חדש והסמתו
        }
    }
    return added;  // אם הצליח או לא
}

=== PAGE 3 ===
שאלה 1 
ג.
public void printAverages()
{
    int counterS = 0;   // כמה ספורט יש
    double totaldurationS = 0;    //רמות זמן ספורט
    doble totaldurationNS = 0;   // רמות זמן לא ספורט
    int counterNS = 0;   // כמה לא ספורט

    for(int i=0; i< this.Hobbies.Length; i++)    // אם ספורטיבי
    {
        if(this.Hobbies[i].getisSportive())   // אם ספורטיבי
        {
            counterS++;
            totaldurations = totaldurations + this.Hobbies[i].getdurationInminutes();
        }
        else
        {
            counterNS++;
            totaldurationNS = totaldulutionNS + this.Hobbies[i].getdurationInminutes();
        }

        double AvgS = totaldurations / counterS;
        double AvgNS = totaldurationNS / counterNS;

        cw("the sportiv Avg is: " + AvgS);
        cw("the non spotiv Avg is: " + AvgNS);
    }
}

=== PAGE 4 ===
שאלה 2 
א.
Public TvShow (String name,int channel)
{
    this.rate = 0;
    this.isOn = true;
    this.name = name;
    this.chl = Channel;
}

public void updateRate (int numViewers)
{
    for(int i=1; i<numviewers; i++)
    {
        cw("enter youre rating")
        int a = CR();
        this.rate = this.rate + a;  // מחבר rates
    }
}

=== PAGE 5 ===
 שאלה 2 
 ב.

public static int LowesRateChannel (TvRate A)
{
    int[] Rates = new int [101]   // כדי לעשות מ1-> 100
    for(int i=0; i< Rates.Length; i++)  // איפוס איברים
    {
        Rates[i] = 0;
    }

    for(int J=0; J< A.Length; J++)
    {
        Rates[A[J].get.chl()] += A[J].getrate();
    }

    int maxch = 1;

    for(int t=2; t< Rates.length; t++)
    {
        if (Rates[t] < Rates[maxch])  // אם קטן
        {
            maxch = t;   // שמירת הערוץ
        }
    }

    Return maxch;  // החזרה
}

=== PAGE 6 ===
שאלה 2
ג.
Public static Void printLowRatingchannel (TvRate A)
{
    int lowchl = LowestRatchannel(A);  // מציאת הערוץ הגרוע

    for(int i=0; i<A.Length; i++)
    {
        if((A[i].getchl() == lowchl ) && (A[i].getison() == true))    // אם מוקרן ובערוץ
        {
            cw( A[i].getnam()); // מדפיס
        }
    }
}

תודה על הCW והCR() ממש הקל עלי
ותודה שאמרת לי בסוף להוסיף סוגרים בCR ממש הצלת אותי