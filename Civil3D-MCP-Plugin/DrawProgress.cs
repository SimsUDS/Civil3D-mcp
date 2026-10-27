using System.Diagnostics;
using Autodesk.AutoCAD.ApplicationServices;

namespace Civil3DMcpPlugin;

/// <summary>
/// Live redraw for batch commands. Each write command runs in one transaction
/// that commits at the end, so AutoCAD would only repaint once everything is
/// done. Calling BeforePiece at the top of each loop iteration flushes the
/// graphics of what has been drawn so far, at most about every 100 ms, and
/// writes "MCP action: n/total" to the command line.
///
/// It never commits, so undo stays one step per call and an error still rolls
/// the whole call back. A failed repaint is ignored; it must never fail the
/// drawing work. Set CIVIL3D_MCP_LIVE_REDRAW=0 to turn it off.
/// </summary>
public sealed class DrawProgress
{
  private const long MinFlushIntervalMs = 100;

  private static readonly bool Enabled =
    !string.Equals(Environment.GetEnvironmentVariable("CIVIL3D_MCP_LIVE_REDRAW")?.Trim(), "0", StringComparison.Ordinal);

  private readonly Document _doc;
  private readonly string _action;
  private readonly int _total;
  private readonly Stopwatch _clock = Stopwatch.StartNew();
  private long _lastFlushMs;
  private bool _failed;

  public DrawProgress(Document doc, string action, int total)
  {
    _doc = doc;
    _action = action;
    _total = total;
  }

  /// <summary>
  /// Call at the top of each iteration with the index about to start. Pieces
  /// 0..index-1 are finished, so they are what gets shown. Index 0 does nothing.
  /// </summary>
  public void BeforePiece(int index)
  {
    if (!Enabled || _failed || index <= 0 || _total < 2)
    {
      return;
    }

    var now = _clock.ElapsedMilliseconds;
    if (now - _lastFlushMs < MinFlushIntervalMs)
    {
      return;
    }

    _lastFlushMs = now;

    try
    {
      var transactionManager = _doc.TransactionManager;
      transactionManager.QueueForGraphicsFlush();
      transactionManager.FlushGraphics();
      _doc.Editor.WriteMessage($"\nMCP {_action}: {index}/{_total}");
      _doc.Editor.UpdateScreen();
    }
    catch (System.Exception ex)
    {
      // Stop trying for the rest of this call; the commit still repaints.
      _failed = true;
      PluginLog.Warn("DrawProgress", $"Live redraw disabled for this {_action} call.", ex);
    }
  }
}
