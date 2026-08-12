using System;
using UnityEngine;
[CreateAssetMenu(fileName = "EmptyBubbleData", menuName = "ScriptableObject/BubbleData")]
public class BubbleSO : ScriptableObject
{
  [Header("Name")]
  public String SOName;
  [Header("Module Sector")]
  [SerializeReference]
  public GameAction action;
  [SerializeReference]
  public ActionTarget target;
  public Sprite bubbleImage;
  public Color bubbleColor;
  //연출효과 등등
  [Header("Spawn Sector")]
  [Tooltip("소속 캐릭터에게 배정된 지분 안에서 이 스킬 버블이 뽑힐 상대 가중치 (GDD §3.2 2단계 추첨)")]
  public float spawnWeight = 1f;
  [Header("DataParse Sector")]
  [Tooltip("1버블당 기본 수치. 최종 수치 = value * matchCount * chainWeight (GDD §4.6)")]
  public float value;
  [Tooltip("연쇄 차수별 배율. index 0 = 1차 연쇄. 비어 있거나 범위를 넘으면 1.0 (마지막 값 유지)")]
  public float[] chainWeights;
  //그외에 넣어야할 수치 고민중

  // 연쇄 배율을 묻는 곳이 여러 군데 생기므로 답하는 함수는 여기 하나만 둡니다. (AGENT.md §5)
  // chainIndex는 1-based입니다.
  public float GetChainWeight(int chainIndex)
  {
    if (chainWeights == null || chainWeights.Length == 0) return 1f;
    int i = Mathf.Clamp(chainIndex - 1, 0, chainWeights.Length - 1);
    return chainWeights[i];
  }

  public void Excute(Actor caster)
  {
    action.OnExcute(target.FindTarget(caster));
  }
}
