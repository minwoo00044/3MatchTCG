// 전투에서 실제로 일어난 일 1건. 대상 1명 기준입니다.
//
// 스킬 레시피가 "무엇을 하려 했나"라면 이쪽은 "무슨 일이 일어났나"입니다.
// 연출은 이 기록을 재생하며, 재생 시점에 모델을 다시 조회하지 않습니다. (AGENT.md §3)
public class BattleStep
{
    public Actor Caster { get; }
    // 이 기록의 소비자는 연출입니다. 버블 스킬과 적 스킬이 같은 타임라인에 얹히므로
    // 여기도 SkillSO입니다. 버블 고유 정보가 필요하면 그때 캐스팅할 것이 아니라,
    // 필요한 값을 SkillSO로 올릴지부터 다시 봅니다.
    public SkillSO Spec { get; }
    public Actor Target { get; }
    public EBattleEffect Effect { get; }

    // 요청량. 위협도는 이 값으로 쌓입니다 (상한을 넘겨 버려진 힐/실드도 포함 - HANDOFF §7).
    public int Requested { get; }

    // 실제 적용량. 오버킬 초과분과 상한 초과분이 빠진 값이며 화면에 띄울 숫자입니다.
    public int Applied { get; }

    // 적용 직후의 값. 연출 시점에 조회하면 이미 여러 대 더 맞은 뒤라 여기 실어 보냅니다.
    public int HPAfter { get; }
    public int ShieldAfter { get; }

    // 이 타격으로 죽었는가. 이미 죽어 있던 대상은 false입니다.
    public bool Died { get; }

    public BattleStep(Actor caster, SkillSO spec, Actor target, EBattleEffect effect,
                      int requested, int applied, int hpAfter, int shieldAfter, bool died)
    {
        Caster = caster;
        Spec = spec;
        Target = target;
        Effect = effect;
        Requested = requested;
        Applied = applied;
        HPAfter = hpAfter;
        ShieldAfter = shieldAfter;
        Died = died;
    }
}
