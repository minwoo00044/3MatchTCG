using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;

// 전투 엔티티의 소유자입니다. (GDD §2.3)
//
// CharacterSO <-> Actor 런타임 매핑을 여기서만 들고, PuzzleManager는 Actor를 모릅니다.
// 스킬 레시피는 GameActionState의 브로드캐스트를 받은 뒤 GameManager에서 꺼내 옵니다.
// PuzzleManager와 직접 주고받지 않습니다.
public class ActionManager : BaseManager
{
    [Header("ENEMY")]
    [Tooltip("적 NPC 표시 이름")]
    [SerializeField]
    private string enemyName = "Enemy";
    [SerializeField]
    private int enemyMaxHP = 3000;
    [SerializeField]
    private int enemyMaxShield = 0;
    [Tooltip("적의 기본 위협도. 아군을 위협도로 고르는 스킬이 없어 현재는 쓰이지 않습니다")]
    [SerializeField]
    private float enemyBaseThreat = 0f;
    [Tooltip("적 스킬. MVP는 BubbleSO 컨테이너를 재사용합니다 (GDD §4.2)")]
    [SerializeField]
    private BubbleSO enemySkill;

    private Battlefield battlefield;
    private readonly List<PlayerActor> playerActors = new List<PlayerActor>();
    private EnemyActor enemyActor;

    // 버블 -> 시전자 역추적. (GDD §2.3)
    //
    // PuzzleManager도 덱에서 비슷한 표를 만들지만 답하는 질문이 다릅니다(무슨 색이냐 / 누가 쓰냐).
    // 파생을 공유하려면 매니저끼리 참조가 생기므로 각자 자기 표를 만듭니다.
    private readonly Dictionary<BubbleSO, PlayerActor> skillCasters = new Dictionary<BubbleSO, PlayerActor>();

    protected override void Awake()
    {
        base.Awake();
        gameManager.Subscribe(EGameState.Action, HandleOnAction);
    }

    protected override void OnDestroy()
    {
        base.OnDestroy();
        if (gameManager != null)
        {
            gameManager.Unsubscribe(EGameState.Action, HandleOnAction);
        }
    }

    protected override void OnInit()
    {
        base.OnInit();
        BuildBattlefield();

        // GameInitState는 Init 구독자 수만큼 완료 보고를 기다립니다.
        // 여기서 보고하지 않으면 readyCount가 1/2에서 멈춰 게임이 Wait로 넘어가지 못합니다. (AGENT.md §8)
        gameManager.ReceiveCompleteSignal();
    }

    // ===================== 전장 구성 =====================

    private void BuildBattlefield()
    {
        battlefield = new Battlefield();
        playerActors.Clear();
        skillCasters.Clear();

        // 덱의 소유자는 GameManager입니다. 읽는 시점은 Init 브로드캐스트 안으로 한정합니다.
        IReadOnlyList<CharacterSO> characters = gameManager != null ? gameManager.Characters : null;
        if (characters == null)
        {
            Debug.LogWarning("[ActionManager] 덱이 배정되지 않아 플레이어 캐릭터를 세우지 못했습니다.");
        }
        else
        {
            foreach (var character in characters)
            {
                if (character == null) continue;

                PlayerActor actor = new PlayerActor(battlefield, character);
                playerActors.Add(actor);
                RegisterSkills(character, actor);
            }
        }

        enemyActor = new EnemyActor(battlefield, enemyName, enemyMaxHP, enemyMaxShield, enemyBaseThreat, enemySkill);

        Debug.Log($"[ActionManager] 전장 구성 완료. 아군 {playerActors.Count}인, 적 1마리");
    }

    private void RegisterSkills(CharacterSO character, PlayerActor actor)
    {
        if (character.skills == null) return;

        foreach (var skill in character.skills)
        {
            if (skill == null) continue;

            // 한 버블이 두 캐릭터에 걸려 있으면 시전자가 뽑기 나름이 됩니다.
            if (skillCasters.ContainsKey(skill))
            {
                Debug.LogWarning($"[ActionManager] {skill.SOName}이(가) 캐릭터 둘 이상에 배정돼 있습니다.");
                continue;
            }
            skillCasters.Add(skill, actor);
        }
    }

    // ===================== 시전자 역추적 =====================

    // 레시피는 버블 스펙만 들고 옵니다. 누가 쓴 스킬인지는 여기서 되짚습니다. (GDD §2.3)
    //
    // 시전자를 못 찾는 두 경우를 구별해야 합니다.
    //   - 소속 캐릭터가 죽었다  -> 스킬 무효. 다른 아군이 대신 쓰지 않는다 (GDD §3.2.1)
    //   - 소속 캐릭터가 없다    -> 공용 버블. 생존 아군 중 BaseThreat 최고가 쓴다 (GDD §3.3)
    // 둘을 뭉뚱그리면 죽은 캐릭터의 버블이 남의 손을 빌려 계속 발동합니다.
    private bool TryResolveCaster(BubbleSO spec, out Actor caster)
    {
        caster = null;
        if (spec == null) return false;

        if (skillCasters.TryGetValue(spec, out PlayerActor owner))
        {
            // 사망 무효 판정은 작성 시점이 아니라 실행 시점에 합니다.
            // 연쇄 중간에 죽어도 그 이후 스킬이 정확히 걸러집니다. (GDD §3.2.1)
            if (owner.IsDead) return false;

            caster = owner;
            return true;
        }

        caster = HighestBaseThreatAlly();
        return caster != null;
    }

    private Actor HighestBaseThreatAlly()
    {
        PlayerActor found = null;
        foreach (var actor in playerActors)
        {
            if (actor.IsDead) continue;
            if (found == null || actor.BaseThreat > found.BaseThreat) found = actor;
        }
        return found;
    }

    // ===================== 스킬 해석 =====================

    // GameActionState가 이 상태에 들어오며 브로드캐스트한 뒤 호출됩니다.
    private void HandleOnAction()
    {
        MoveReceipt receipt = gameManager.ConsumeMoveReceipt();
        List<SkillRecipe> recipes = BuildSkillRecipes(receipt);

        // 수치는 여기서 전부 확정됩니다. 연출은 나중에 이 기록을 재생할 뿐입니다. (GDD §4.1, §4.5)
        BattleReceipt battle = new BattleReceipt();
        foreach (var recipe in recipes)
        {
            ExecuteRecipe(recipe, battle);
        }

        // 연출 담당이 생기면 이 영수증을 재생합니다. 지금은 소비자가 없어 내역만 찍습니다.
        ReportBattleReceipt(battle);

        gameManager.ReceiveCompleteSignal();
    }

    // 퍼즐 영수증을 실행 순서대로 늘어놓은 스킬 목록으로 옮깁니다. (GDD §4.5)
    //
    // 퍼즐은 "무슨 버블이 몇 차에 몇 개 터졌나"까지만 적습니다.
    // 덩어리 1개 = 스킬 1건이라는 판정도, 차수와 개수를 세는 것도 여기서 합니다.
    private List<SkillRecipe> BuildSkillRecipes(MoveReceipt receipt)
    {
        List<SkillRecipe> ret = new List<SkillRecipe>();
        if (receipt == null) return ret;

        for (int i = 0; i < receipt.ChainSteps.Count; i++)
        {
            // 연쇄 차수는 1-based입니다.
            int chainIndex = i + 1;
            List<SkillRecipe> ofStep = new List<SkillRecipe>();

            foreach (var group in receipt.ChainSteps[i].MatchGroups)
            {
                if (group.Spec == null) continue;
                ofStep.Add(new SkillRecipe(group.Spec, group.Cells.Count, chainIndex));
            }

            // 선(先)배치 실행 규칙 - 증폭/버프를 이 차수의 가장 앞으로 당깁니다. (GDD §4.5)
            //
            // 정렬 범위는 이번 차수뿐입니다. 앞선 차수로 소급되면 이미 발동이 끝난 스킬의
            // 수치가 뒤늦게 바뀝니다. OrderBy는 안정 정렬이라 나머지 순서는 보존됩니다.
            if (ofStep.Count > 1)
            {
                ofStep = ofStep
                    .OrderByDescending(r => r.Spec.action != null && r.Spec.action.IsPreemptive)
                    .ToList();
            }

            ret.AddRange(ofStep);
        }

        return ret;
    }

    // ===================== 스킬 실행 =====================

    private void ExecuteRecipe(SkillRecipe recipe, BattleReceipt battle)
    {
        if (recipe == null || recipe.Spec == null) return;
        BubbleSO spec = recipe.Spec;

        // 소속 캐릭터가 죽었으면 여기서 걸러집니다. 버블은 이미 터졌고 효과만 없습니다. (GDD §3.2.1)
        if (!TryResolveCaster(spec, out Actor caster)) return;

        if (spec.action == null || spec.target == null)
        {
            Debug.LogWarning($"[ActionManager] {spec.SOName}에 액션 또는 타깃이 배정되지 않았습니다.");
            return;
        }

        Actor[] targets = spec.target.FindTarget(caster);
        if (targets.Length == 0) return;

        // 최종 수치 = value * matchCount * chainWeight (GDD §4.6)
        //
        // 여기서 정수로 확정합니다. Actor의 HP/실드가 int인 이유는, float로 두면
        // "0.0001 남아 안 죽은 적"이 생기고 그 판정이 타깃 필터와 승패까지 번지기 때문입니다.
        int amount = Mathf.RoundToInt(spec.value * recipe.MatchCount * spec.GetChainWeight(recipe.ChainIndex));
        if (amount <= 0) return;

        int before = battle.Steps.Count;
        spec.action.OnExecute(new SkillContext(caster, spec, targets, amount, battle));

        AccumulateThreat(caster, spec, battle, before);
    }

    // 위협도는 실제 적용량이 아니라 "부여량" 기준입니다. 상한을 넘겨 버려진 힐/실드도 셉니다.
    // 탱커가 방어 행위를 계속하는 한 어그로를 유지하는 게 의도입니다. (HANDOFF §7)
    //
    // 대상 수만큼 합산합니다. 광역 힐은 1인 힐보다 총량이 크므로 어그로도 그만큼 끌립니다. (GDD §4.1)
    // 방금 적힌 기록에서 요청량을 걷어오므로, 액션이 무엇을 했든 셈이 어긋나지 않습니다.
    private void AccumulateThreat(Actor caster, BubbleSO spec, BattleReceipt battle, int fromIndex)
    {
        int requested = 0;
        for (int i = fromIndex; i < battle.Steps.Count; i++)
        {
            requested += battle.Steps[i].Requested;
        }
        if (requested <= 0) return;

        caster.AddThreat(requested * spec.threatMultiplier, battlefield.GameTime);
    }

    // 전투 결과 확인용 임시 로그입니다. 연출이 이 영수증을 소비하기 시작하면 제거합니다. (AGENT.md §9)
    private void ReportBattleReceipt(BattleReceipt battle)
    {
        if (battle.Steps.Count == 0) return;

        StringBuilder sb = new StringBuilder();
        sb.Append($"[ActionManager] 전투 {battle.Steps.Count}건");
        foreach (var step in battle.Steps)
        {
            sb.Append($"\n  {step.Caster} -{step.Spec.SOName}-> {step.Target} " +
                      $"{step.Effect} {step.Applied}(요청 {step.Requested}) " +
                      $"HP {step.HPAfter}/{step.Target.MaxHP} 실드 {step.ShieldAfter}");
            if (step.Died) sb.Append(" [사망]");
        }
        Debug.Log(sb.ToString());
    }
}
