using DG.Tweening;
using UnityEngine;
using UnityEngine.UI;

// 캐릭터 하나의 표현. (GDD §4.1)
//
// **언제 보여줄지 모릅니다.** 받은 값을 그릴 뿐이고, 모델(Actor)을 조회하지 않습니다.
// 조회하기 시작하면 연출 시점에는 이미 여러 대 더 맞은 뒤라 화면이 미래를 그립니다. (AGENT.md §3)
// 순서를 아는 것은 BattleSequencer 하나뿐입니다.
//
// 연출 내용(모션·시간·스프라이트)은 아직 기획이 없습니다. 지금은 구조 검증이 목적이라
// 최소한으로 둡니다 - 사각 스프라이트, HP바, 실드 게이지, 뜨는 숫자.
// 코스메틱이라 기획이 오면 이 클래스 안만 갈아끼우면 됩니다. (HANDOFF §4)
public class ActorView : MonoBehaviour
{
    [Header("VIEW")]
    [SerializeField]
    private SpriteRenderer body;
    [SerializeField]
    private Image hpFill;
    [SerializeField]
    private Image shieldFill;
    [SerializeField]
    private Text nameText;
    [Tooltip("피격·회복 수치가 떠오를 위치. 비우면 이 오브젝트 위치를 씁니다")]
    [SerializeField]
    private Transform popupAnchor;
    [Tooltip("수치 표시 프리팹. 비우면 숫자를 띄우지 않습니다")]
    [SerializeField]
    private Text popupPrefab;

    // TMP가 아니라 레거시 UI.Text입니다. TMP는 TMP Essentials를 임포트해야 쓸 수 있어
    // 구조 검증을 시작하는 데 설치 절차가 하나 끼어듭니다. 연출 기획이 오면 이 클래스 안에서
    // 갈아끼우면 되므로 지금은 의존을 늘리지 않습니다. (AGENT.md §0 - 예외 사유)

    [Header("TWEEN")]
    [Tooltip("시전 시 앞으로 내미는 거리")]
    [SerializeField]
    private float castOffset = 0.3f;
    [SerializeField]
    private float castDuration = 0.12f;
    [Tooltip("피격 시 흔들리는 세기")]
    [SerializeField]
    private float hitShake = 0.15f;
    [SerializeField]
    private float hitDuration = 0.18f;
    [SerializeField]
    private float gaugeDuration = 0.2f;
    [SerializeField]
    private float popupRise = 0.6f;
    [SerializeField]
    private float popupDuration = 0.6f;
    [SerializeField]
    private float deathDuration = 0.3f;

    [Header("COLOR")]
    [SerializeField]
    private Color damageColor = new Color(1f, 0.35f, 0.35f);
    [SerializeField]
    private Color healColor = new Color(0.4f, 1f, 0.5f);
    [SerializeField]
    private Color shieldColor = new Color(0.5f, 0.8f, 1f);

    // 시전 모션이 돌아올 기준 위치. 트윈 생성 전에 확정해야 합니다. (AGENT.md §7)
    private Vector3 homePos;

    // 자기 트윈만 죽입니다. 시퀀서의 타임라인은 건드리지 않습니다.
    private Tween bodyTween;
    private Tween hpTween;
    private Tween shieldTween;

    // 시전 방향. 아군은 오른쪽(적 쪽), 적은 왼쪽을 향합니다.
    private int facing = 1;

    public void Init(string displayName, Color mainColor, bool facingRight)
    {
        homePos = transform.position;
        facing = facingRight ? 1 : -1;

        if (body != null) body.color = mainColor;
        if (nameText != null) nameText.text = displayName;
    }

    // 게이지는 즉시 값이 아니라 "이 값까지 흐르게" 합니다.
    // 채우는 비율만 받습니다. 최대치를 나누는 계산조차 여기서 하지 않는 이유는
    // 뷰가 규칙을 판단하지 않기 때문입니다. (AGENT.md §1)
    public void SetHP(float ratio)
    {
        if (hpFill == null) return;

        hpTween?.Kill();
        hpTween = hpFill.DOFillAmount(Mathf.Clamp01(ratio), gaugeDuration);
    }

    public void SetShield(float ratio)
    {
        if (shieldFill == null) return;

        shieldTween?.Kill();
        shieldTween = shieldFill.DOFillAmount(Mathf.Clamp01(ratio), gaugeDuration);
    }

    // 즉시 반영. 전장 구성 직후처럼 연출 없이 맞춰야 할 때 씁니다.
    public void SnapGauges(float hpRatio, float shieldRatio)
    {
        hpTween?.Kill();
        shieldTween?.Kill();

        if (hpFill != null) hpFill.fillAmount = Mathf.Clamp01(hpRatio);
        if (shieldFill != null) shieldFill.fillAmount = Mathf.Clamp01(shieldRatio);
    }

    // 스킬을 쓰는 쪽 모션. 앞으로 내밀었다 돌아옵니다.
    public Tween PlayCast()
    {
        bodyTween?.Kill();

        // 시작값은 트윈 "생성 전"에 확정합니다. OnStart 안에서 잡으면 이미 늦습니다. (AGENT.md §7)
        transform.position = homePos;

        Sequence seq = DOTween.Sequence();
        seq.Append(transform.DOMoveX(homePos.x + castOffset * facing, castDuration));
        seq.Append(transform.DOMoveX(homePos.x, castDuration));

        bodyTween = seq;
        return seq;
    }

    // 맞는 쪽 모션. 흔들리고 숫자가 뜹니다.
    public Tween PlayHit(EBattleEffect effect, int applied)
    {
        Sequence seq = DOTween.Sequence();

        // 실제 적용량이 0이면 흔들지 않습니다. 실드가 다 막았거나 만피에 회복이 들어간 경우인데,
        // 화면이 "맞았다"고 말하면 거짓말이 됩니다. 숫자는 여전히 띄웁니다(0으로).
        if (effect == EBattleEffect.Damage && applied > 0)
        {
            seq.Join(transform.DOShakePosition(hitDuration, hitShake, 20, 90f, false, true));
        }

        ShowPopup(seq, effect, applied);
        return seq;
    }

    public Tween PlayDeath()
    {
        bodyTween?.Kill();

        Sequence seq = DOTween.Sequence();
        if (body != null) seq.Join(body.DOFade(0.25f, deathDuration));
        seq.Join(transform.DORotate(new Vector3(0f, 0f, 90f * facing), deathDuration));

        bodyTween = seq;
        return seq;
    }

    private void ShowPopup(Sequence seq, EBattleEffect effect, int applied)
    {
        if (popupPrefab == null) return;

        Transform anchor = popupAnchor != null ? popupAnchor : transform;

        // 풀링하지 않습니다. 수치 표시는 연출 기획이 오면 통째로 갈릴 자리이고,
        // 지금 풀을 붙이면 반납 주체가 하나 더 늘어납니다. (AGENT.md §4)
        Text popup = Instantiate(popupPrefab, anchor);
        popup.text = effect == EBattleEffect.Damage ? $"-{applied}" : $"+{applied}";
        popup.color = ResolvePopupColor(effect);

        // 로컬 좌표로 띄웁니다. 캔버스가 월드든 스크린이든 같은 코드가 돕니다.
        Transform t = popup.transform;
        t.localPosition = Vector3.zero;

        seq.Join(t.DOLocalMoveY(popupRise, popupDuration));
        seq.Join(popup.DOFade(0f, popupDuration).OnComplete(() =>
        {
            if (popup != null) Destroy(popup.gameObject);
        }));
    }

    private Color ResolvePopupColor(EBattleEffect effect)
    {
        switch (effect)
        {
            case EBattleEffect.Heal: return healColor;
            case EBattleEffect.Shield: return shieldColor;
            default: return damageColor;
        }
    }

    private void OnDestroy()
    {
        // 대상이 Destroy되면 DOTween이 알아서 죽이지만, 씬 전환 중 순서에 기대지 않습니다.
        bodyTween?.Kill();
        hpTween?.Kill();
        shieldTween?.Kill();
    }
}
