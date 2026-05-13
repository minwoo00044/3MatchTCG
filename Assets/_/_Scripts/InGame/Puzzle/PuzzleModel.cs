public class PuzzleModel
{
    private Bubble[][] bubbles;
    public int Size{get; private set;}
    public void SetBubbles(int size)
    {
        Size = size;
        bubbles = new Bubble[size][];
        for(int i = 0; i < size; i++)
        {
            bubbles[i] = new Bubble[size];
        }
    }
}