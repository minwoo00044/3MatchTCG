using System.Collections.Generic;
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
    private Actor ResolveCaster(BubbleSO spec)
    {
        if (spec != null && skillCasters.TryGetValue(spec, out PlayerActor caster) && !caster.IsDead)
        {
            return caster;
        }

        // 소속 캐릭터가 없는 공용 버블(T_O)은 생존 아군 중 BaseThreat가 가장 높은 캐릭터가 씁니다. (GDD §3.3)
        // 시전자가 이미 죽은 경우에도 같은 규칙으로 넘깁니다 - 스킬 무효화 판정은 실행 단계의 몫입니다.
        return HighestBaseThreatAlly();
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

    // ===================== 스킬 처리 =====================

    // GameActionState가 이 상태에 들어오며 브로드캐스트한 뒤 호출됩니다.
    private void HandleOnAction()
    {
        IReadOnlyList<SkillRecipe> recipes = gameManager.ConsumeSkillRecipes();

        foreach (var recipe in recipes)
        {
            ExecuteRecipe(recipe);
        }

        gameManager.ReceiveCompleteSignal();
    }

    // 5a 단계에서는 타깃 선정까지만 합니다. 수치 적용은 GameAction 3종을 구현하는 다음 단계입니다.
    private void ExecuteRecipe(SkillRecipe recipe)
    {
        if (recipe == null || recipe.Spec == null) return;

        Actor caster = ResolveCaster(recipe.Spec);
        if (caster == null)
        {
            // 아군이 전멸했다는 뜻입니다. 승패 판정이 붙으면 여기까지 오지 않습니다([8]).
            Debug.LogWarning($"[ActionManager] {recipe.Spec.SOName}의 시전자를 찾지 못했습니다.");
            return;
        }

        if (recipe.Spec.target == null)
        {
            Debug.LogWarning($"[ActionManager] {recipe.Spec.SOName}에 타깃이 배정되지 않았습니다.");
            return;
        }

        Actor[] targets = recipe.Spec.target.FindTarget(caster);

        // 타깃 선정이 맞는지 확인하는 임시 로그입니다.
        // 수치가 실제로 들어가기 시작하면 이 로그는 제거합니다. (AGENT.md §9)
        StringBuilder sb = new StringBuilder();
        sb.Append($"[ActionManager] chain {recipe.ChainIndex} / {caster} -> {recipe.Spec.SOName} (x{recipe.MatchCount}) => ");
        if (targets.Length == 0) sb.Append("대상 없음");
        else
        {
            for (int i = 0; i < targets.Length; i++)
            {
                if (i > 0) sb.Append(", ");
                sb.Append($"{targets[i]}({targets[i].CurrentHP}/{targets[i].MaxHP})");
            }
        }
        Debug.Log(sb.ToString());
    }
}
