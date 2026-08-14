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
    [Tooltip("적 스킬. 보드에 없는 스킬이므로 SkillSO입니다 (GDD §4.2)")]
    [SerializeField]
    private SkillSO enemySkill;
    [Tooltip("적 공격 주기(초). 유효 전투 시간 기준이며 연출 중에는 흐르지 않습니다 (GDD §4.2)")]
    [SerializeField]
    private float enemyAttackInterval = 3f;

    [Header("DEBUG")]
    [Tooltip("전투 시계와 적 공격을 로그로 확인합니다. 화면이 생기면 제거할 임시 수단입니다")]
    [SerializeField]
    private bool logBattleTick = true;

    private Battlefield battlefield;
    private readonly List<PlayerActor> playerActors = new List<PlayerActor>();
    private EnemyActor enemyActor;

    // 적의 공격 주기를 세는 쪽. 실행은 이 매니저가 합니다.
    private EnemyController enemyController;

    // 시계 로그를 마지막으로 찍은 GameTime. 매 프레임 찍으면 로그가 흐름을 덮습니다. (AGENT.md §9)
    private float lastTickLogTime;

    // 버블 -> 시전자 역추적. (GDD §2.3)
    //
    // PuzzleManager도 덱에서 비슷한 표를 만들지만 답하는 질문이 다릅니다(무슨 색이냐 / 누가 쓰냐).
    // 파생을 공유하려면 매니저끼리 참조가 생기므로 각자 자기 표를 만듭니다.
    private readonly Dictionary<BubbleSO, PlayerActor> skillCasters = new Dictionary<BubbleSO, PlayerActor>();

    protected override void Awake()
    {
        base.Awake();
        gameManager.Subscribe(EGameState.Action, HandleOnAction);

        // Wait 구간에서만 열리는 틱입니다. BaseManager가 거는 OnUpdate(전 구간)와 다릅니다.
        // 적 타이머와 GameTime은 이쪽에만 매달아야 Time Freeze가 성립합니다. (GDD §4.2)
        gameManager.OnWaitTick += HandleWaitTick;
    }

    protected override void OnDestroy()
    {
        base.OnDestroy();
        if (gameManager != null)
        {
            gameManager.Unsubscribe(EGameState.Action, HandleOnAction);
            gameManager.OnWaitTick -= HandleWaitTick;
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
                actor.OnDeath += HandleActorDeath;
            }
        }

        enemyActor = new EnemyActor(battlefield, enemyName, enemyMaxHP, enemyMaxShield, enemyBaseThreat, enemySkill);
        enemyActor.OnDeath += HandleActorDeath;

        enemyController = new EnemyController(enemyAttackInterval);

        // 스킬 배선 검사는 부팅 시 한 번만 합니다. 실행 시점에 찍으면 적은 주기마다,
        // 버블은 터질 때마다 반복됩니다. (AGENT.md §9)
        ValidateSkill(enemySkill, "적 스킬");
        foreach (var skill in skillCasters.Keys) ValidateSkill(skill, "버블 스킬");

        Debug.Log($"[ActionManager] 전장 구성 완료. 아군 {playerActors.Count}인, 적 1마리");
    }

    // 배선이 덜 된 스킬은 실행 시점에 아무 일도 일으키지 않고 조용히 지나갑니다.
    // ExecuteSkill이 amount <= 0에서 먼저 return하므로 액션·타깃 미배정 경고에도 닿지 못합니다.
    // 실제로 적 스킬(E_0)이 전부 빈 채로 오래 지나갔고, 발동 로그를 붙이고서야 드러났습니다.
    //
    // 그래서 "무엇이 비었나"를 부팅 시점에 한 줄로 말하게 합니다. 값을 나열하는 로그가 아니라
    // "이 스킬은 실행돼도 아무 일이 없다"는 불변식 위반을 찍는 것입니다. (AGENT.md §9)
    private void ValidateSkill(SkillSO skill, string label)
    {
        if (skill == null)
        {
            Debug.LogWarning($"[ActionManager] {label}이(가) 배정되지 않았습니다.");
            return;
        }

        string name = string.IsNullOrEmpty(skill.SOName) ? skill.name : skill.SOName;
        List<string> missing = new List<string>();

        if (skill.action == null) missing.Add("action");
        if (skill.target == null) missing.Add("target");
        if (skill.value <= 0f) missing.Add("value");

        if (missing.Count == 0) return;

        Debug.LogWarning($"[ActionManager] {label} {name}: {string.Join(", ", missing)} 미배정. " +
                         "실행돼도 아무 일도 일어나지 않습니다.");
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

        // 최종 수치 = value * matchCount * chainWeight (GDD §4.6)
        //
        // 여기서 정수로 확정합니다. Actor의 HP/실드가 int인 이유는, float로 두면
        // "0.0001 남아 안 죽은 적"이 생기고 그 판정이 타깃 필터와 승패까지 번지기 때문입니다.
        int amount = Mathf.RoundToInt(spec.value * recipe.MatchCount * spec.GetChainWeight(recipe.ChainIndex));

        ExecuteSkill(caster, spec, amount, battle);
    }

    // 스킬 1건이 실제로 발동하는 유일한 지점입니다.
    //
    // 플레이어와 적이 갈라지는 것은 여기까지 오는 길(시전자를 어떻게 찾는가, 수치를 어떻게 세는가)
    // 뿐이고, 타깃 검색·적용·기록·위협도는 완전히 같습니다. 적 공격용 실행 함수를 따로 만들면
    // 경로가 둘이 되고, 이후 규칙이 하나만 고쳐질 때 한쪽이 조용히 틀려집니다. (AGENT.md §5)
    //
    // 인자가 BubbleSO가 아니라 SkillSO인 것이 이 경계의 선언입니다.
    // **여기부터는 퍼즐 개념이 없습니다.** 연쇄 차수도 매치 개수도 이미 amount에 녹아 끝났고,
    // 이 아래에서 다시 꺼내 쓸 수 없어야 합니다.
    private void ExecuteSkill(Actor caster, SkillSO spec, int amount, BattleReceipt battle)
    {
        if (caster == null || spec == null || amount <= 0) return;

        if (spec.action == null || spec.target == null)
        {
            Debug.LogWarning($"[ActionManager] {spec.SOName}에 액션 또는 타깃이 배정되지 않았습니다.");
            return;
        }

        Actor[] targets = spec.target.FindTarget(caster);
        if (targets.Length == 0) return;

        int before = battle.Steps.Count;
        spec.action.OnExecute(new SkillContext(caster, spec, targets, amount, battle));

        AccumulateThreat(caster, spec, battle, before);
    }

    // ===================== 적 공격 =====================

    // GameWaitState.OnUpdate()가 연 틱입니다. 이 구간 밖에서는 호출되지 않으므로
    // 퍼즐 연쇄 연출과 스킬 실행 동안 시계가 완전히 멈춥니다. (GDD §4.2 Time Freeze)
    private void HandleWaitTick(float delta)
    {
        if (battlefield == null || enemyController == null) return;

        // 유효 전투 시간을 전진시키는 유일한 지점입니다. 적 타이머와 위협도 10초 윈도우가
        // 같은 시계를 봐야 "연출로 번 시간"이 양쪽에 똑같이 적용됩니다. (GDD §4.2)
        battlefield.GameTime += delta;
        LogGameTime();

        if (!enemyController.Tick(delta)) return;

        ExecuteEnemyAttack();
    }

    // 시계가 흐르는지, 그리고 연출 중에 멈추는지를 눈으로 보기 위한 임시 로그입니다.
    // 화면에 전투가 보이기 시작하면 제거합니다. (AGENT.md §9)
    //
    // 1초에 한 줄로 묶습니다. 매 프레임 찍으면 초당 수십 줄이라 다른 로그가 묻히고,
    // 무엇보다 "연출 중 멈춤"을 확인하려면 줄 간격이 곧 신호인데 그게 안 보입니다.
    private void LogGameTime()
    {
        if (!logBattleTick) return;
        if (battlefield.GameTime - lastTickLogTime < 1f) return;

        lastTickLogTime = battlefield.GameTime;
        Debug.Log($"[ActionManager] GameTime {battlefield.GameTime:F1}s");
    }

    private void ExecuteEnemyAttack()
    {
        if (enemyActor == null || enemyActor.IsDead) return;

        SkillSO skill = enemyActor.Skill;
        if (skill == null) return; // 배선 경고는 BuildBattlefield에서 한 번만 찍습니다.

        // 적 공격은 버블 매치가 없으므로 최종 데미지 = value 고정입니다.
        // matchCount와 chainWeight를 곱하지 않습니다. (GDD §4.2)
        int amount = Mathf.RoundToInt(skill.value);

        // 발동 자체를 먼저 찍습니다. 아래 영수증 로그는 대상이 없거나 빗나가면 아무것도 남기지 않아,
        // "적이 안 때린 것"과 "때렸는데 대상이 없던 것"을 구별할 수 없습니다. (AGENT.md §9)
        LogEnemyAttack();

        // 발동 시점에 수치를 영수증으로 선확정하고, 연출은 나중에 그 기록을 재생합니다. (GDD §4.2)
        // 플레이어 배치와 섞이지 않도록 이 공격 한 건만 담은 영수증을 만듭니다.
        // 배치가 다르면 연출 타임라인도 다르므로 한 장에 이어붙이면 순서가 뭉갭니다.
        BattleReceipt battle = new BattleReceipt();
        ExecuteSkill(enemyActor, skill, amount, battle);
        ReportBattleReceipt(battle);

        // 여기서 상태를 전이시키지 않습니다. GameWaitState에서 나가는 길은 플레이어 스왑이며,
        // 적 공격은 연출로도 흐름을 끊지 않습니다. 승패만 예외인데 그 전이는
        // HandleActorDeath가 예약하고 GameWaitState가 확인합니다. (GDD §4.2, §4.4)
    }

    // 적이 누구를 때리는지만 봐서는 HighestThreatEnemy가 정렬을 하는지, 그냥 명단 첫 번째를
    // 집는지 구별할 수 없습니다. 탱커가 계속 맞으면 두 경우의 결과가 같기 때문입니다.
    // 그래서 후보 전원의 총 위협도를 함께 찍습니다. 화면이 생기면 제거합니다. (AGENT.md §9)
    private void LogEnemyAttack()
    {
        if (!logBattleTick) return;

        StringBuilder sb = new StringBuilder();
        sb.Append($"[ActionManager] 적 공격 발동 (GameTime {battlefield.GameTime:F1}s, 주기 {enemyAttackInterval}s) 위협도");

        // 적 기준의 "적군"이 곧 아군 진영입니다. 상대 판정은 반드시 이 경로로 합니다. (AGENT.md §5)
        foreach (var actor in battlefield.EnemiesOf(enemyActor))
        {
            sb.Append($" {actor}={actor.GetTotalThreat(battlefield.GameTime):F0}");
        }
        Debug.Log(sb.ToString());
    }

    // ===================== 승패 판정 =====================

    // 전장을 소유한 쪽이 판정합니다. 다만 전이는 하지 않고 예약만 합니다 —
    // 사망 시점에 곧바로 전이하면 진행 중인 연출 시퀀스가 남고 뷰가 누수됩니다. (GDD §4.4, AGENT.md §9)
    private void HandleActorDeath(Actor actor)
    {
        if (actor == null || gameManager == null) return;

        if (actor.Team == ETeam.Enemy)
        {
            // MVP는 적 1마리입니다. 여러 마리가 되면 여기를 생존 수 판정으로 바꿉니다. (GDD §4.2)
            gameManager.RequestGameEnd(EGameResult.Victory);
            return;
        }

        // 패배 조건은 3인 중 2명 사망, 즉 생존자 1명 이하입니다. (GDD §4.4)
        if (AliveAllyCount() <= 1)
        {
            gameManager.RequestGameEnd(EGameResult.Defeat);
        }
    }

    private int AliveAllyCount()
    {
        int ret = 0;
        foreach (var actor in playerActors)
        {
            if (!actor.IsDead) ret++;
        }
        return ret;
    }

    // 위협도는 실제 적용량이 아니라 "부여량" 기준입니다. 상한을 넘겨 버려진 힐/실드도 셉니다.
    // 탱커가 방어 행위를 계속하는 한 어그로를 유지하는 게 의도입니다. (HANDOFF §7)
    //
    // 대상 수만큼 합산합니다. 광역 힐은 1인 힐보다 총량이 크므로 어그로도 그만큼 끌립니다. (GDD §4.1)
    // 방금 적힌 기록에서 요청량을 걷어오므로, 액션이 무엇을 했든 셈이 어긋나지 않습니다.
    private void AccumulateThreat(Actor caster, SkillSO spec, BattleReceipt battle, int fromIndex)
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
