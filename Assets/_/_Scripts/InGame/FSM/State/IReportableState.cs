public interface IReportableState
{
    void ReceiveCompleteSignal();
    void OnAllTasksComplete();
}