using UnityEngine;

public class BaseManager : MonoBehaviour
{
    [SerializeField]
    protected GameManager gameManager;
    protected bool isFreeze;
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
        
    }
}
