using System.Collections.Generic;
using System.Text.RegularExpressions;
using DG.Tweening;
using UnityEngine;
using UnityEngine.UI;

// 캐릭터 하나의 표현. (GDD §4.1)
//
// **언제 보여줄지 모릅니다.** 받은 값을 그릴 뿐이고, 모델(Actor)을 조회하지 않습니다.
// 조회하기 시작하면 연출 시점에는 이미 여러 대 더 맞은 뒤라 화면이 미래를 그립니다. (AGENTS.md §3)
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
    // 갈아끼우면 되므로 지금은 의존을 늘리지 않습니다. (AGENTS.md §0 - 예외 사유)

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

    [Header("SPRITE ANIMATION")]
    // 프레임 애니메이션은 Animator로 재생합니다 - AGENTS.md §7(연출은 DOTween)의 예외입니다.
    // 사유: 스프라이트 파이프라인(SpriteAnimationPipeline)이 캐릭터마다 클립과 AnimatorController를
    // 만들어 두었고(상태 = Idle/Hit/Skill1~3/Dead), 프레임별 표시 시간(완급)까지 클립에 들어 있습니다.
    // DOTween으로 같은 재생기를 다시 만들면 클립 해석이 두 벌이 됩니다(§5).
    // 역할은 나눕니다 - Animator는 "어떤 그림을 몇 프레임째 보여 줄지"만, "언제 틀지"는 지금처럼
    // BattleSequencer의 DOTween 타임라인이 정합니다(아래 PlayState는 시퀀스 콜백에서만 불립니다).
    [Tooltip("프레임 애니메이션을 재생할 Animator. 비우면 body에 붙여 씁니다")]
    [SerializeField]
    private Animator animator;
    [Tooltip("스프라이트 캐릭터의 배율. 캐릭터 간 키 차이는 시트에 이미 들어 있어 모두 같은 값을 씁니다")]
    [SerializeField]
    private float spriteScale = 0.4f;
    [Tooltip("스프라이트 캐릭터: 시전 시작부터 대상이 맞기까지의 시간")]
    [SerializeField]
    private float castImpactTime = 0.35f;

    [Header("COLOR")]
    [SerializeField]
    private Color damageColor = new Color(1f, 0.35f, 0.35f);
    [SerializeField]
    private Color healColor = new Color(0.4f, 1f, 0.5f);
    [SerializeField]
    private Color shieldColor = new Color(0.5f, 0.8f, 1f);

    // 시전 모션이 돌아올 기준 위치. 트윈 생성 전에 확정해야 합니다. (AGENTS.md §7)
    private Vector3 homePos;

    // 자기 트윈만 죽입니다. 시퀀서의 타임라인은 건드리지 않습니다.
    private Tween bodyTween;
    private Tween hpTween;
    private Tween shieldTween;

    // 시전 방향. 아군은 오른쪽(적 쪽), 적은 왼쪽을 향합니다.
    private int facing = 1;

    // 스프라이트 캐릭터면 true. 아니면 예전 사각형 + DOTween 모션 그대로입니다.
    private bool animated;
    // 상태 이름 -> 클립 길이(초). 끝나고 Idle로 돌아갈 시점을 계산하는 데만 씁니다.
    private readonly Dictionary<string, float> clipLengths = new Dictionary<string, float>();
    private Tween idleReturn;
    // 쓰러진 뒤에는 어떤 동작도 틀지 않습니다. Dead 클립의 마지막 장면(누운 자세)이 끝까지 남아야 합니다.
    // 죽은 대상이 다시 맞는 경로는 지금 없지만, 생기면 Hit 클립이 시체를 일으켜 세웁니다(직접 강제 피격으로 확인).
    private bool isDown;

    // 파이프라인 클립 이름: {캐릭터}_{액션}_v{N}. 상태 이름 = 액션 (SpriteAnimationPipeline.LinkController)
    private static readonly Regex ClipAction = new Regex(@"_(Idle|Hit|Skill[1-9]|Dead)_v[0-9]+$");

    public void Init(string displayName, Color mainColor, bool facingRight, RuntimeAnimatorController look = null)
    {
        homePos = transform.position;
        facing = facingRight ? 1 : -1;

        if (nameText != null) nameText.text = displayName;

        if (look != null && body != null)
        {
            // 스프라이트 캐릭터는 그림 자체가 색이라 칠하지 않습니다. 보는 방향도 시트에 구워져 있습니다
            // (적은 파이프라인이 좌우 반전해 저장) - 여기서 뒤집지 않습니다.
            animated = true;
            body.color = Color.white;
            body.transform.localScale = Vector3.one * spriteScale;
            if (animator == null) animator = body.GetComponent<Animator>();
            if (animator == null) animator = body.gameObject.AddComponent<Animator>();
            animator.runtimeAnimatorController = look;

            clipLengths.Clear();
            foreach (AnimationClip clip in look.animationClips)
            {
                Match m = ClipAction.Match(clip.name);
                if (m.Success) clipLengths[m.Groups[1].Value] = clip.length;
            }
            return;
        }

        if (body != null) body.color = mainColor;
    }

    // 한 동작을 처음부터 틀고, 끝나면 Idle로 돌아갑니다(Dead는 마지막 장면에 머뭅니다).
    // 없는 상태(예: 적의 Skill2)는 Skill1로 대신합니다.
    private void PlayState(string state, bool returnToIdle = true)
    {
        if (animator == null) return;

        if (isDown) return;
        if (!animator.HasState(0, Animator.StringToHash(state)))
        {
            if (!state.StartsWith("Skill") || !animator.HasState(0, Animator.StringToHash("Skill1"))) return;
            state = "Skill1";
        }

        idleReturn?.Kill();
        animator.Play(state, 0, 0f);

        if (returnToIdle && clipLengths.TryGetValue(state, out float length))
        {
            idleReturn = DOVirtual.DelayedCall(length, () =>
            {
                if (animator != null) animator.Play("Idle", 0, 0f);
            });
        }
    }

    // 게이지는 즉시 값이 아니라 "이 값까지 흐르게" 합니다.
    // 채우는 비율만 받습니다. 최대치를 나누는 계산조차 여기서 하지 않는 이유는
    // 뷰가 규칙을 판단하지 않기 때문입니다. (AGENTS.md §1)
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
    // skillNumber: 이 스킬이 캐릭터의 몇 번째 스킬인지(1부터) - 스프라이트 캐릭터가 틀 Skill 클립.
    public Tween PlayCast(int skillNumber = 1)
    {
        bodyTween?.Kill();

        if (animated)
        {
            // 돌진·휘두르기는 클립에 그려져 있어 위치를 움직이지 않습니다.
            // 반환하는 트윈 길이 = 타격 시점까지. 클립의 나머지(복귀 자세)는 다음 박자와 겹쳐 흘러갑니다.
            Sequence cast = DOTween.Sequence();
            cast.AppendCallback(() => PlayState($"Skill{skillNumber}"));
            cast.AppendInterval(castImpactTime);
            bodyTween = cast;
            return cast;
        }

        // 시작값은 트윈 "생성 전"에 확정합니다. OnStart 안에서 잡으면 이미 늦습니다. (AGENTS.md §7)
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
            if (animated)
            {
                seq.AppendCallback(() => PlayState("Hit"));
                seq.AppendInterval(hitDuration);
            }
            else
            {
                seq.Join(transform.DOShakePosition(hitDuration, hitShake, 20, 90f, false, true));
            }
        }

        ShowPopup(seq, effect, applied);
        return seq;
    }

    public Tween PlayDeath()
    {
        bodyTween?.Kill();

        Sequence seq = DOTween.Sequence();

        if (animated)
        {
            // 쓰러지는 모습은 Dead 클립에 있고, 마지막 장면(누운 자세)에 머뭅니다. 흐리게·눕히기는 하지 않습니다.
            seq.AppendCallback(() =>
            {
                PlayState("Dead", returnToIdle: false);
                isDown = true;
            });
            seq.AppendInterval(deathDuration);
            bodyTween = seq;
            return seq;
        }

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
        // 지금 풀을 붙이면 반납 주체가 하나 더 늘어납니다. (AGENTS.md §4)
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
        idleReturn?.Kill();
    }
}
