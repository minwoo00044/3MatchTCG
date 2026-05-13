using UnityEngine;

public class BaseManager : MonoBehaviour
{
    protected GameManager gameManager;
    protected bool isFreeze;
    void Awake()
    {
        gameManager.OnInit+=Init;
    }
    void Start()
    {
        
    }
    // Update is called once per frame
    public virtual void Init()
    {
        
    }
    public virtual void OnUpdate()
    {
        
    }
}
