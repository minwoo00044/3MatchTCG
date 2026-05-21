using System.Collections.Generic;
using UnityEngine;

public class PuzzleMatrixView : MonoBehaviour
{
    private Dictionary<Bubble,PuzzleView> dataViewDict = new Dictionary<Bubble, PuzzleView>();
    public void DrawingAllMatrix()
    {
        Debug.Log("drawStart");
        foreach(var pair in dataViewDict)
        {
            int x = pair.Key.Pos.x * 1;
            int y = pair.Key.Pos.y * 1;

            pair.Value.transform.SetPositionAndRotation(new Vector2(x,y),transform.rotation);
            pair.Value.gameObject.SetActive(true);
        }
    }
    public void RegistBubble(Bubble data, PuzzleView view)
    {
        dataViewDict.Add(data,view);
    }
    public void RemoveView(Bubble data)
    {
        dataViewDict.Remove(data);
    }

}