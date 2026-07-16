=== Q1.א ===
Public class Hobby
{
    private string hobbyName;
    private bool isSportive;
    private int durationInMinutes;
    
    public Hobby(string hobbyName, bool isSportive, int minutes)
    {
        this.hobbyName = hobbyName;
        this.isSportive = isSportive;
        this.minutes = durationInMinutes;
    }

=== Q1.ב ===
public bool pupulatHobbies()
{
    bool t = true;
    bool f = false;

    for(int i=0; i<this.hobbies.length; i++)
    {
        cw("do u want to crate
        string a = CR();
        if(a=="n" || a=="N")
        {
            t = false;
        }

        if((this.hobbies[i]==null) && (t==true))
        {
            f = true;
            rw("enter your hobby");

            string name = CR();
            bool sportiv = CR();
            int min = int.parce(CR());
            Hobby hobb = new Hobby(name, sportiv, min);
        }
    }

    return f;
}

=== Q1.ג ===
printAverages
{
    double Avgyes = 0;
    double Avgno = 0;

    For(int i=0; i<hobbies.length; i++)
    {
        if(hobbies[i].getisSportiv()==true)
        {
            Avgyes += hobbies[i].getdurationIn minutes;
        }
        else
        {
            Avgno += hobbies[i].get durationIn minutes;
        }
    }

    cw("Avg sportiv= {0}, Avg not sportiv={1}", Avgyes, Avgno);

=== Q2.א ===
public class TvShow
{
    private string name;
    private int rate;
    private int chl;
    private bool isOn;

    public Tv Show(string name, int channel)
    {
        this.name = name;
        this.channel = chl;
        this.rate=0;
        this.isOn=true;
    }

    public void updateRate(int numViewers)
    {
        int sum=0

        for(int i=1; i<=numViewers; i++)
        {
            CW("how your rate?");
            int rateOfThisViewer = int.parse(CR());
            sum+=rateOfThisViewer;
        }

        this.rate=sum;
    }

=== Q2.ב ===
public static string LowestRateChannel(TV rate tv)
{
    int[] arr = int[tv]

    string min1 = " "; int min = arr[0].getrate();

    for(int i=1; i<arr.Length; i++)
    {
        if(min>arr[i].getrate)
        {
            min = arr[i].getrate();
            min1 = arr[i].getName();
        }
    }

    return min1
}  

=== Q2.ג ===
public static void printLowChannel(TVRate[] tv)
{
    int[]arr = new int[tv];

    For(int i=0; i<arr.Length; i++)
    {
        if(LowestRateChannel == arr[i].getName())
        {
            if(get isOn==true)
            {
                CW(getName());
            }
        }
    }
}
