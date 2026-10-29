using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Runtime;
using App = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: ExtensionApplication(typeof(Civil3DMcpPlugin.PluginEntry))]
[assembly: CommandClass(typeof(Civil3DMcpPlugin.PluginEntry))]

namespace Civil3DMcpPlugin;

public sealed class PluginEntry : IExtensionApplication
{
  public void Initialize()
  {
    try
    {
      PluginRuntime.StartServer();
      PluginLog.Info("PluginEntry", $"Civil3D MCP plugin initialized on port {PluginRuntime.Port}. Log file: {PluginLog.LogFilePath}");
      WriteMessage($"Civil3D MCP plugin initialized on port {PluginRuntime.Port}.");
    }
    catch (System.Exception ex)
    {
      PluginLog.Error("PluginEntry", "Plugin failed to initialize", ex);
      WriteMessage($"Civil3D MCP plugin failed to initialize: {ex.Message}");
    }
  }

  public void Terminate()
  {
    try
    {
      PluginRuntime.StopServer();
      PluginLog.Info("PluginEntry", "Civil3D MCP plugin terminated cleanly.");
    }
    catch (System.Exception ex)
    {
      PluginLog.Error("PluginEntry", "Error during plugin termination", ex);
    }
  }

  [CommandMethod("C3DMCPSTART")]
  public void StartCommand()
  {
    PluginRuntime.StartServer();
    WriteMessage($"Civil3D MCP listener started on port {PluginRuntime.Port}.");
  }

  /// <summary>Moves the listener to a chosen port, e.g. 8081 for a Civil 3D
  /// that should be reached by a second (read-only) MCP server.</summary>
  [CommandMethod("C3DMCPPORT")]
  public void PortCommand()
  {
    var doc = App.DocumentManager.MdiActiveDocument;
    if (doc == null) return;
    var options = new Autodesk.AutoCAD.EditorInput.PromptIntegerOptions($"\nMCP listener port (now {PluginRuntime.Port}): ")
    {
      AllowNone = false,
      LowerLimit = 1024,
      UpperLimit = 65535,
      UseDefaultValue = true,
      DefaultValue = PluginRuntime.Port,
    };
    var result = doc.Editor.GetInteger(options);
    if (result.Status != Autodesk.AutoCAD.EditorInput.PromptStatus.OK) return;

    var previous = PluginRuntime.Port;
    PluginRuntime.StopServer();
    try
    {
      PluginRuntime.StartServer(result.Value);
      WriteMessage($"Civil3D MCP listener now on port {PluginRuntime.Port}.");
    }
    catch (System.Exception ex)
    {
      WriteMessage($"Could not use port {result.Value}: {ex.Message} Going back to port {previous}.");
      try { PluginRuntime.StartServer(previous); }
      catch (System.Exception restartError) { WriteMessage($"Listener could not restart: {restartError.Message} Run C3DMCPSTART."); }
    }
  }

  [CommandMethod("C3DMCPSTOP")]
  public void StopCommand()
  {
    PluginRuntime.StopServer();
    WriteMessage("Civil3D MCP listener stopped.");
  }

  [CommandMethod("C3DMCPSTATUS")]
  public void StatusCommand()
  {
    var status = PluginRuntime.GetStatus();
    WriteMessage($"Civil3D MCP listener running: {status.IsRunning}; port: {status.Port}; pending: {status.QueueDepth}; active: {status.OperationInProgress}; current: {status.CurrentOperation ?? "<none>"}");
  }

  private static void WriteMessage(string message)
  {
    var doc = App.DocumentManager.MdiActiveDocument;
    doc?.Editor.WriteMessage($"\n{message}");
  }
}
