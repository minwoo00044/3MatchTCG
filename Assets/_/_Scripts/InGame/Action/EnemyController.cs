// 적이 "지금 공격한다"를 결정하는 곳입니다. (GDD §4.2)
//
// 결정만 하고 실행은 하지 않습니다. 타깃 선정·적용·기록·위협도는 플레이어 스킬과 전부 같으므로
// ActionManager의 기존 경로를 그대로 탑니다. 적을 별도 매니저로 빼면 Battlefield 소유권이
// 갈리고 스킬 실행 경로가 둘이 되는데, 스킬은 멱등이 아니라 그중 하나가 이중 적용이 됩니다.
// 플레이어와 다른 것은 발동 계기(이벤트 / 시간)와 수치 공식뿐입니다. (AGENT.md §5)
//
// MonoBehaviour가 아닙니다. Model 층이며 Unity API를 쓰지 않습니다. (AGENT.md §1)
// Time.deltaTime을 스스로 읽지 않고 인자로 받는 것이 핵심입니다 — 프레임 시간을 직접 읽으면
// Time Freeze 구간에서도 타이머가 돌아 §4.2가 깨집니다. 시계의 주인은 호출하는 쪽입니다.
public class EnemyController
{
    private readonly float interval;
    private float elapsed;

    public EnemyController(float interval)
    {
        this.interval = interval;
    }

    // delta는 유효 전투 시간(GameTime)의 증분입니다. Time.time 기준이 아닙니다. (HANDOFF §5)
    // 이번 틱에 공격을 발동해야 하면 true를 반환합니다.
    public bool Tick(float delta)
    {
        if (interval <= 0f || delta <= 0f) return false;

        elapsed += delta;
        if (elapsed < interval) return false;

        // 0으로 초기화하지 않고 주기만큼만 뺍니다. 프레임 경계와 주기가 딱 맞아떨어지는 일은
        // 없으므로 매번 나머지를 버리면 실측 주기가 설정값보다 느려지고, 그 오차가 전투 내내
        // 누적됩니다. 3초 주기가 체감 3.02초가 되면 밸런스 검증이 흔들립니다.
        elapsed -= interval;

        // 한 틱에 여러 번 터뜨리지는 않습니다. 밀린 만큼 몰아치면 프레임 스파이크가 곧
        // 피해량이 되고, [9]에서 붙을 피격 연출의 시간축도 겹칩니다.
        // 초과분은 다음 틱으로 넘겨 한 프레임에 한 대씩 빠져나가게 합니다.
        if (elapsed > interval) elapsed = interval;

        return true;
    }
}
