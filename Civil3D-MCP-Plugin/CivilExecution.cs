using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.Civil.ApplicationServices;
using App = Autodesk.AutoCAD.ApplicationServices.Application;

namespace Civil3DMcpPlugin;

public static class CivilExecution
{
  private static readonly SemaphoreSlim HostExecutionGate = new(1, 1);

  public static async Task<T> ExecuteAsync<T>(Func<Document, CivilDocument, Database, Transaction, T> action, bool write)
  {
    return await ExecuteSerializedAsync(async () =>
    {
      T? result = default;
      Exception? capturedException = null;

      await App.DocumentManager.ExecuteInCommandContextAsync(async _ =>
      {
        try
        {
          var doc = App.DocumentManager.MdiActiveDocument ?? throw new JsonRpcDispatchException("CIVIL3D.NO_DRAWING", "No active drawing is open in Civil 3D.");
          EnsureExpectedDrawing(doc);
          var civilDoc = CivilApplication.ActiveDocument ?? throw new JsonRpcDispatchException("CIVIL3D.NO_DRAWING", "No active Civil 3D document is available.");
          var database = doc.Database;

          using var documentLock = doc.LockDocument();
          // Started from the document's transaction manager so DrawProgress can
          // flush graphics mid-transaction (live redraw during batch commands).
          using var transaction = doc.TransactionManager.StartTransaction();

          result = action(doc, civilDoc, database, transaction);

          if (write)
          {
            transaction.Commit();
          }
        }
        catch (Exception ex)
        {
          capturedException = ex;
        }

        await Task.CompletedTask;
      }, null);

      if (capturedException != null)
      {
        throw capturedException;
      }

      return result!;
    });
  }

  public static async Task<T> ExecuteInCommandContextAsync<T>(Func<Task<T>> action)
  {
    return await ExecuteSerializedAsync(async () =>
    {
      T? result = default;
      Exception? capturedException = null;

      await App.DocumentManager.ExecuteInCommandContextAsync(async _ =>
      {
        try
        {
          EnsureExpectedDrawing(App.DocumentManager.MdiActiveDocument);
          result = await action();
        }
        catch (Exception ex)
        {
          capturedException = ex;
        }
      }, null);

      if (capturedException != null)
      {
        throw capturedException;
      }

      return result!;
    });
  }

  /// <summary>
  /// Refuses the operation when the request is bound to a drawing (expectDrawing, or a background job's
  /// drawing) and a different drawing is active now. Nothing has been changed when this throws.
  /// </summary>
  private static void EnsureExpectedDrawing(Document? doc)
  {
    var expected = PluginRuntime.GetExpectedDrawingIdentity();
    if (string.IsNullOrWhiteSpace(expected)) return;
    var active = PluginRuntime.GetDrawingIdentity(doc);
    if (!string.Equals(expected, active, StringComparison.OrdinalIgnoreCase))
    {
      throw new JsonRpcDispatchException(
        "CIVIL3D.CONFLICT",
        $"This request is for '{expected}' but the active drawing is '{active ?? "none"}'. No drawing changes were made. Switch with civil3d_drawing action=activate.");
    }
  }

  public static Task<T> ReadAsync<T>(Func<Document, CivilDocument, Database, Transaction, T> action)
  {
    return ExecuteAsync(action, false);
  }

  public static Task<T> WriteAsync<T>(Func<Document, CivilDocument, Database, Transaction, T> action)
  {
    return ExecuteAsync(action, true);
  }

  private static async Task<T> ExecuteSerializedAsync<T>(Func<Task<T>> action)
  {
    var cancellationToken = PluginRuntime.GetCurrentRequestCancellationToken();
    PluginRuntime.QueueHostOperation();
    var started = false;

    try
    {
      await HostExecutionGate.WaitAsync(cancellationToken);
      started = true;
      PluginRuntime.StartHostOperation();
      cancellationToken.ThrowIfCancellationRequested();
      return await action();
    }
    finally
    {
      if (started)
      {
        PluginRuntime.CompleteHostOperation();
        HostExecutionGate.Release();
      }
      else
      {
        PluginRuntime.CancelQueuedHostOperation();
      }
    }
  }
}
