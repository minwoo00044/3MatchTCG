using System;
using System.Collections.Generic;
using DG.Tweening;
using UnityEngine;

// BattleReceipt를 읽어 연출 타임라인을 조립합니다. (GDD §4.1, §4.5)
//
// **수치를 계산하지 않습니다.** 영수증에 적힌 값을 그대로 뷰에 넘깁니다.
// 재생 시점에 모델을 다시 조회하면 이미 여러 대 더 맞은 뒤라 화면이 미래를 그립니다.
// 재계산이 불가능한 이유는 GDD §4.5에 적혀 있습니다 - RandomActor는 다시 뽑으면 다른 대상입니다.
//
// **타임라인 소유자는 여기 하나입니다.** ActorView들이 각자 재생하면 영수증이 정한 순서가 사라집니다.
// Actor <-> ActorView 짝도 여기가 듭니다. Actor가 자기 뷰를 알면
// GameAction(ScriptableObject)이 Actor를 통해 씬 객체에 닿습니다. (HANDOFF §4)
//
// PuzzleMatrixView가 MoveReceipt에 대해 하는 일과 같은 자리입니다.
public class BattleSequencer : MonoBehaviour
{
    [Header("TIMING")]
    [Tooltip("스킬 1건과 다음 1건 사이의 간격")]
    [SerializeField]
    private float betweenSkills = 0.1f;
    [Tooltip("시전 모션이 끝나고 피격이 뜨기까지의 간격")]
    [SerializeField]
    private float castToHit = 0.05f;

    private readonly Dictionary<Actor, ActorView> viewDict = new Dictionary<Actor, ActorView>();

    // 재생 중인 타임라인. 하나뿐입니다.
    private Sequence running;

    public void Bind(Actor actor, ActorView view)
    {
        if (actor == null || view == null) return;

        // 같은 Actor에 뷰가 둘이면 어느 쪽이 그려지는지가 등록 순서에 달리게 됩니다.
        if (viewDict.ContainsKey(actor))
        {
            Debug.LogWarning("[BattleSequencer] 같은 Actor에 뷰가 두 번 배정됐습니다.");
            return;
        }

        viewDict.Add(actor, view);
        view.SnapGauges(HPRatio(actor), ShieldRatio(actor));
    }

    public void ClearBinds()
    {
        running?.Kill();
        running = null;
        viewDict.Clear();
    }

    // 영수증 한 장을 재생합니다. 완주하면 onComplete가 불립니다.
    //
    // onComplete는 GameActionState의 완수 보고가 걸리는 자리입니다.
    // 여기가 안 불리면 그 상태에서 나가는 길이 사라집니다. (AGENTS.md §8)
    // 그래서 아래 두 경우 모두 반드시 부릅니다 - 재생할 것이 없을 때, 그리고 중간에 끊길 때.
    public void Play(BattleReceipt receipt, Action onComplete)
    {
        // 진행 중인 것이 있으면 Kill이 아니라 Complete로 끊습니다.
        // Kill은 OnComplete를 부르지 않아 완수 보고가 증발합니다. Complete는 최종 상태까지
        // 밀어내므로 화면이 모델과 어긋난 채로 남지도 않습니다.
        //
        // 실제로 끊기는 것은 적 공격 연출뿐입니다. 배치 재생 중에는 GameActionState에
        // 머물러 Wait 틱이 돌지 않으므로 적 공격이 들어올 수 없습니다.
        Sequence previous = running;
        running = null;
        previous?.Complete();

        if (receipt == null || receipt.Steps.Count == 0)
        {
            onComplete?.Invoke();
            return;
        }

        Sequence seq = DOTween.Sequence();

        // 같은 시전자가 같은 스킬로 여러 대상을 친 연속 구간은 한 박자로 묶습니다.
        // 영수증은 대상 1명당 1건이라, 그대로 순차 재생하면 광역 힐 한 방이
        // 세 박자로 늘어집니다. "스킬 1건당 연출 1건"이 GDD §4.5의 표현입니다.
        int i = 0;
        while (i < receipt.Steps.Count)
        {
            int end = i;
            while (end + 1 < receipt.Steps.Count && IsSameSkill(receipt.Steps[end + 1], receipt.Steps[i]))
            {
                end++;
            }

            AppendSkillBeat(seq, receipt.Steps, i, end);
            i = end + 1;
        }

        // 연출이 끝나면 모델 기준으로 스냅합니다. 프레임 스파이크로 게이지 트윈이 통째로
        // 스킵돼도 화면과 모델이 어긋난 채 남지 않습니다. (AGENTS.md §7, §9의 불변식)
        seq.OnComplete(() =>
        {
            running = null;
            ReconcileGauges();
            onComplete?.Invoke();
        });

        running = seq;
    }

    private static bool IsSameSkill(BattleStep a, BattleStep b)
    {
        return a.Caster == b.Caster && a.Spec == b.Spec;
    }

    private void AppendSkillBeat(Sequence seq, List<BattleStep> steps, int from, int to)
    {
        BattleStep head = steps[from];

        // 시전 모션 먼저. 시전자 뷰가 없으면(적 뷰 미배치 등) 건너뛰되 박자는 유지합니다.
        ActorView casterView = FindView(head.Caster);
        if (casterView != null) seq.Append(casterView.PlayCast());
        else seq.AppendInterval(castToHit);

        seq.AppendInterval(castToHit);

        // 이 박자의 대상들은 동시에 맞습니다.
        for (int i = from; i <= to; i++)
        {
            AppendTarget(seq, steps[i], i == from);
        }

        seq.AppendInterval(betweenSkills);
    }

    private void AppendTarget(Sequence seq, BattleStep step, bool isFirst)
    {
        ActorView view = FindView(step.Target);
        if (view == null) return;

        // 첫 대상은 Append로 시간을 잡고, 나머지는 Join으로 같은 시점에 붙입니다.
        Tween hit = view.PlayHit(step.Effect, step.Applied);
        if (isFirst) seq.Append(hit);
        else seq.Join(hit);

        // 게이지는 영수증에 적힌 "적용 직후" 값으로 갑니다. 모델을 다시 읽지 않습니다.
        //
        // MaxHP/MaxShield는 조회합니다. 전투 중 변하지 않는 값이라 시점 문제가 없습니다.
        // 변하는 값(CurrentHP, Shield)만 영수증에 실려 옵니다. (AGENTS.md §3)
        int maxHP = step.Target.MaxHP;
        int maxShield = step.Target.MaxShield;

        seq.JoinCallback(() =>
        {
            view.SetHP(maxHP > 0 ? (float)step.HPAfter / maxHP : 0f);
            view.SetShield(maxShield > 0 ? (float)step.ShieldAfter / maxShield : 0f);
        });

        // 이 타격으로 죽었으면 그 자리에서 쓰러집니다.
        // 이미 죽어 있던 대상은 step.Died가 false라 두 번 쓰러지지 않습니다.
        if (step.Died) seq.Join(view.PlayDeath());
    }

    private ActorView FindView(Actor actor)
    {
        if (actor == null) return null;
        return viewDict.TryGetValue(actor, out ActorView view) ? view : null;
    }

    // 재생이 끝난 뒤에는 모델이 진실입니다. 이 시점 조회는 안전합니다. (AGENTS.md §7)
    private void ReconcileGauges()
    {
        foreach (var pair in viewDict)
        {
            pair.Value.SnapGauges(HPRatio(pair.Key), ShieldRatio(pair.Key));
        }
    }

    private static float HPRatio(Actor actor) => actor.MaxHP > 0 ? (float)actor.CurrentHP / actor.MaxHP : 0f;
    private static float ShieldRatio(Actor actor) => actor.MaxShield > 0 ? (float)actor.Shield / actor.MaxShield : 0f;
}
