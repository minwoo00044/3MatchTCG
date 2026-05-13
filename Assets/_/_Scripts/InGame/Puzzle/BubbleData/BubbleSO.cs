using System;
using UnityEngine;
[CreateAssetMenu(fileName ="EmptyBubbleData",menuName ="ScriptableObject/BubbleData")]
public class BubbleSO : ScriptableObject
{
  [Header("Module Sector")]
  [SerializeReference]
  public GameAction action;
  [SerializeReference]
  public ActionTarget target;
  public Sprite bubbleImage;
  //연출효과 등등
  [Header("DataParse Sector")]
  public float value;
  public float addPerBubble;
  //그외에 넣어야할 수치 고민중

  public void Excute()
    {
        action.OnExcute(target.FindTarget());
    }
} 