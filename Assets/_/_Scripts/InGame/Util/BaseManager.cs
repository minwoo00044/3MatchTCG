using UnityEngine;

public class BaseManager : MonoBehaviour
{
    [SerializeField]
    protected GameManager gameManager;
    private bool isFreeze;

    public bool IsFreeze { get => isFreeze; set => isFreeze = value; }

    protected virtual void Awake()
    {
        gameManager.OnInit+=OnInit;
        gameManager.OnUpdate+=OnUpdate;
    }
    void Start()
    {
        
    }
    // Update is called once per frame
    protected virtual void OnInit()
    {
        Debug.Log($"{this} init");
    }
    protected virtual void OnUpdate()
    {
        if(!isFreeze) return;
    }
}
