using System;
using System.Collections.Generic;
using UnityEngine;

// 전투 엔티티(플레이어 캐릭터 3인 + 적 NPC)의 모델입니다. (GDD §4.1)
//
// MonoBehaviour가 아닙니다. GameAction/ActionTarget이 ScriptableObject에서 Actor 배열을
// 다루므로, Actor가 씬 객체가 되면 SO가 씬을 참조하게 됩니다. (AGENT.md §1)
//
// 스탯 변경은 즉시 반영하고 값을 실은 이벤트를 발화합니다. 연출은 그 값을 나중에 소비합니다.
public abstract class Actor
{
    // 위협도 누적 윈도우. (GDD §4.1 - 최근 10초 유효 전투 시간)
    //
    // MonoBehaviour가 아니라 [SerializeField]로 뺄 수 없어 const로 둡니다. (AGENT.md §10 예외)
    // 튜닝 대상이 되면 ActionManager가 주입하는 형태로 옮깁니다.
    private const float ThreatWindow = 10f;

    // 자기가 선 전장. ActionTarget이 시전자만 받고도 명단에 닿는 통로입니다. (GDD §4.3)
    public Battlefield Field { get; private set; }

    public ETeam Team { get; private set; }
    public int MaxHP { get; private set; }
    public int CurrentHP { get; private set; }
    public int MaxShield { get; private set; }
    public int Shield { get; private set; }
    public float BaseThreat { get; private set; }
    public bool IsDead { get; private set; }

    // LowestHPAlly와 LowestHPEnemy가 같은 질문을 합니다. 답하는 함수는 여기 하나만 둡니다. (AGENT.md §5)
    public float HPRatio => MaxHP > 0 ? (float)CurrentHP / MaxHP : 0f;

    // 발화 시점의 값을 인자에 실어 보냅니다.
    // UI는 이 이벤트를 영수증 타임라인으로 지연 소비하므로(GDD §4.1), 구독자가 발화 뒤에
    // CurrentHP를 다시 조회하면 이미 여러 번 더 맞은 뒤의 값을 읽게 됩니다. (AGENT.md §3)
    public event Action<Actor, int, int> OnHPChanged;     // (actor, delta, hpAfter)
    public event Action<Actor, int, int> OnShieldChanged; // (actor, delta, shieldAfter)
    public event Action<Actor> OnDeath;

    // (발생 시각, 누적량). 시각은 GameTime이며 Time.time이 아닙니다. (HANDOFF §5 - 시계가 둘이다)
    // gameTime은 단조 증가하므로 큐의 앞쪽이 항상 가장 오래된 항목입니다.
    private readonly Queue<(float time, float amount)> threatLog = new Queue<(float time, float amount)>();

    protected Actor(Battlefield field, ETeam team, int maxHP, int maxShield, float baseThreat)
    {
        // 명단에 오르지 않은 Actor는 어떤 타깃 검색에도 잡히지 않습니다.
        // 등록을 잊는 실수를 원천에서 막으려고 생성자에서 직접 올립니다.
        Field = field;
        field?.Register(this);

        Team = team;
        MaxHP = maxHP;
        CurrentHP = maxHP;
        MaxShield = maxShield;
        // 실드는 0에서 시작합니다. 흡수막은 DefenseAction으로 부여받는 것이고
        // maxShield는 그 상한입니다. 방어막을 쌓는 행위 자체에 퍼즐 조작의 의미를 두기 위함입니다.
        // (GDD §4.1에 초기값 명시가 없어 확인받은 사항 - GDD 반영 제안 대기)
        Shield = 0;
        BaseThreat = baseThreat;
        IsDead = false;
    }

    // ===================== 팀 판정 =====================
    //
    // 타겟팅은 모두 "시전자 상대 기준"입니다. (GDD §4.3)
    // ETeam 값을 직접 비교하면(예: target.Team == ETeam.Player) 플레이어 시전에서는 통과하고
    // 적 NPC 시전에서만 틀리는 코드가 됩니다. 상대 판정은 반드시 이 두 함수로만 합니다. (AGENT.md §5)

    public bool IsAllyOf(Actor other) => other != null && Team == other.Team;
    public bool IsEnemyOf(Actor other) => other != null && Team != other.Team;

    // ===================== 스탯 변경 =====================

    // 실드 우선 차감, 초과분만 HP. 반환값은 "실제로 깎인 양"(오버킬 초과분 제외)입니다.
    // 위협도에 쌓을 값은 이 반환값이 아니라 요청량(amount)입니다. AddThreat 주석 참고.
    public int TakeDamage(int amount)
    {
        if (IsDead || amount <= 0) return 0;

        int absorbed = Mathf.Min(Shield, amount);
        if (absorbed > 0)
        {
            Shield -= absorbed;
            OnShieldChanged?.Invoke(this, -absorbed, Shield);
        }

        int toHP = amount - absorbed;
        if (toHP <= 0) return absorbed;

        int before = CurrentHP;
        CurrentHP = Mathf.Max(0, CurrentHP - toHP);
        int lost = before - CurrentHP;
        OnHPChanged?.Invoke(this, -lost, CurrentHP);

        // 수치는 즉시 확정하고 사망 이벤트도 즉시 발화합니다.
        // 승패 "상태 전이"만 연출 완주 뒤로 미룹니다. (GDD §4.4 - 오버킬 방지)
        if (CurrentHP == 0)
        {
            IsDead = true;
            OnDeath?.Invoke(this);
        }

        return absorbed + lost;
    }

    // 죽은 대상은 회복되지 않습니다. 부활 메커니즘은 없습니다. (GDD §3.2.1)
    public int Heal(int amount)
    {
        if (IsDead || amount <= 0) return 0;

        int before = CurrentHP;
        CurrentHP = Mathf.Min(MaxHP, CurrentHP + amount);
        int healed = CurrentHP - before;
        if (healed > 0) OnHPChanged?.Invoke(this, healed, CurrentHP);

        return healed;
    }

    public int AddShield(int amount)
    {
        if (IsDead || amount <= 0) return 0;

        int before = Shield;
        Shield = Mathf.Min(MaxShield, Shield + amount);
        int added = Shield - before;
        if (added > 0) OnShieldChanged?.Invoke(this, added, Shield);

        return added;
    }

    // ===================== 위협도 =====================

    // amount는 threatMultiplier가 이미 곱해진 값입니다. 배수 곱셈은 ActionManager 책임입니다.
    //
    // 또한 "실제 적용량"이 아니라 "부여량" 기준입니다. 상한을 넘겨 버려진 힐/실드도 위협도로 칩니다.
    // 탱커가 방어 행위를 계속하는 한 어그로를 유지하는 것이 의도에 맞다고 판단했습니다.
    // (HANDOFF §7 - 기획자 확정 대기 중인 가정)
    public void AddThreat(float amount, float gameTime)
    {
        if (IsDead || amount <= 0f) return;

        PruneThreatLog(gameTime);
        threatLog.Enqueue((gameTime, amount));
    }

    // 총 위협도 = BaseThreat + 최근 10초 누적 (GDD §4.1)
    // 누적분만 만료되므로 BaseThreat 아래로는 내려가지 않습니다.
    public float GetTotalThreat(float gameTime)
    {
        PruneThreatLog(gameTime);

        float sum = 0f;
        foreach (var entry in threatLog) sum += entry.amount;

        return BaseThreat + sum;
    }

    private void PruneThreatLog(float gameTime)
    {
        float expireBefore = gameTime - ThreatWindow;
        while (threatLog.Count > 0 && threatLog.Peek().time <= expireBefore)
        {
            threatLog.Dequeue();
        }
    }
}
