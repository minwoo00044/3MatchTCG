using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

// 퍼즐 연출이 전부 끝난 뒤 스킬을 일괄 실행하는 구간입니다. (GDD §4.5)
//
// 흐름: GameWaitState -> (스왑) -> GamePuzzleActionState -> [여기] -> GameWaitState
//
// 스킬 실행을 DOTween 시퀀스 내부가 아니라 전용 상태로 뺀 이유는 두 가지입니다.
// 하나는 전투 흐름의 주도권을 GameManager가 갖게 하기 위함이고,
// 다른 하나는 캐릭터 공격 모션 같은 스킬 연출을 놓을 시간축을 확보하기 위함입니다.
//
// 클래스 이름 주의: AutoInsertStates()가 "{Owner}{State}State"로 찾습니다.
// GameManager -> "Game", EGameState.Action -> GameActionState. (AGENT.md §2)
public class GameActionState : BaseState<EGameState, GameManager>, IBroadcastableState, IReportableState
{
    private Action _cachedBroadCastAction;
    private int readyCount = 0;
    private int totalTargetCount = 0;

    public GameActionState(BaseStateMachine<EGameState, GameManager> machine) : base(machine)
    {
    }

    public void InjectBroadCastTask(Action targetAction)
    {
        _cachedBroadCastAction = targetAction;
    }

    public override void OnEnter()
    {
        readyCount = 0;
        var owner = machine.Owner;
        totalTargetCount = owner != null ? owner.GetSubscriberCount(EGameState.Action) : 0;

        // 구독자(ActionManager)는 이 브로드캐스트를 받고 GameManager에서 레시피를 꺼내 갑니다.
        _cachedBroadCastAction?.Invoke();

        // 아직 아무도 구독하지 않는 동안([5] 이전)에는 레시피가 그대로 남습니다.
        // 조용히 버리면 레시피 작성이 맞는지 확인할 방법이 없어 내역을 찍고 비웁니다.
        // ActionManager가 붙으면 이 분기는 더 이상 타지 않습니다.
        if (totalTargetCount == 0)
        {
            ReportUnconsumedRecipes(owner);
            OnAllTasksComplete();
        }
    }

    public void ReceiveCompleteSignal()
    {
        readyCount++;
        if (readyCount >= totalTargetCount) OnAllTasksComplete();
    }

    public void OnAllTasksComplete()
    {
        machine.ChangeState(EGameState.Wait);
    }

    public override void OnExit()
    {
        // 불변식: 이 상태를 나갈 때 제출된 레시피는 남아 있으면 안 된다.
        // 남아 있다는 건 하달됐지만 아무도 가져가지 않았다는 뜻입니다. (AGENT.md §9)
        var owner = machine.Owner;
        if (owner == null) return;

        int leaked = owner.PeekSkillRecipeCount();
        if (leaked > 0)
        {
            Debug.LogWarning($"[GameActionState] 소비되지 않은 스킬 레시피 {leaked}건이 남은 채 상태를 벗어납니다.");
            owner.ConsumeSkillRecipes();
        }
    }

    public override void OnUpdate()
    {
    }

    private void ReportUnconsumedRecipes(GameManager owner)
    {
        IReadOnlyList<SkillRecipe> recipes = owner.ConsumeSkillRecipes();
        if (recipes.Count == 0) return;

        StringBuilder sb = new StringBuilder();
        sb.Append($"[GameActionState] 하달 대상이 없어 스킬 레시피 {recipes.Count}건을 실행하지 못했습니다.");
        foreach (var recipe in recipes)
        {
            string specName = recipe.Spec != null ? recipe.Spec.SOName : "(null)";
            sb.Append($"\n  chain {recipe.ChainIndex} / {specName} / matchCount {recipe.MatchCount}");
        }
        Debug.LogWarning(sb.ToString());
    }
}
