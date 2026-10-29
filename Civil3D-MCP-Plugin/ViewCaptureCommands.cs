using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text.Json.Nodes;
using App = Autodesk.AutoCAD.ApplicationServices.Application;

namespace Civil3DMcpPlugin;

/// <summary>
/// captureView: optionally zooms the active drawing to a window (plan view),
/// waits so online map tiles (GEOMAP, e.g. Bing aerial) can load, then saves
/// what the drawing view shows as a PNG and reports the world extents of the
/// image, so pixels map to drawing coordinates.
/// mode "screen" (default) copies the drawing view's pixels from the screen,
/// so it includes the online map; the Civil 3D window must be visible and not
/// covered. mode "render" uses Document.CapturePreviewImage (may leave out
/// the online map).
/// map: "aerial" | "road" | "hybrid" | "off" runs GEOMAP first (needs the
/// drawing geolocated and the user signed in to Autodesk); mapAfter runs it
/// again after the capture (e.g. "off").
/// </summary>
public static class ViewCaptureCommands
{
  [StructLayout(LayoutKind.Sequential)]
  private struct RECT { public int Left, Top, Right, Bottom; }

  [StructLayout(LayoutKind.Sequential)]
  private struct POINT { public int X, Y; }

  private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

  [DllImport("user32.dll")] private static extern bool GetClientRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] private static extern bool ClientToScreen(IntPtr hWnd, ref POINT point);
  [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr parent, EnumWindowsProc callback, IntPtr lParam);

  public static async Task<object?> CaptureViewAsync(JsonObject? parameters)
  {
    var outFile = PluginRuntime.GetOptionalString(parameters, "outFile");
    if (string.IsNullOrWhiteSpace(outFile))
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "captureView requires outFile (a .png path).");
    }

    var overwrite = PluginRuntime.GetOptionalBool(parameters, "overwrite") ?? true;
    var path = FileBoundary.ResolveExportPath(outFile, overwrite, ".png");
    var mode = (PluginRuntime.GetOptionalString(parameters, "mode") ?? "screen").Trim().ToLowerInvariant();
    if (mode is not ("screen" or "render"))
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "captureView mode must be 'screen' or 'render'.");
    }

    var waitMs = Math.Clamp(PluginRuntime.GetOptionalInt(parameters, "waitMs") ?? 3000, 0, 20000);
    var renderWidth = Math.Clamp(PluginRuntime.GetOptionalInt(parameters, "width") ?? 1600, 200, 4000);
    var window = PluginRuntime.GetParameter(parameters, "window") as JsonObject;
    var pad = window?["pad"]?.GetValue<double>() ?? 0.0;
    var map = MapOption(PluginRuntime.GetOptionalString(parameters, "map"), "map");
    var mapAfter = MapOption(PluginRuntime.GetOptionalString(parameters, "mapAfter"), "mapAfter");

    return await CivilExecution.ExecuteInCommandContextAsync<object?>(async () =>
    {
      var doc = App.DocumentManager.MdiActiveDocument
        ?? throw new JsonRpcDispatchException("CIVIL3D.NO_DRAWING", "No active drawing is open in Civil 3D.");
      var editor = doc.Editor;
      var mapStatus = new List<string>();
      if (map is not null)
      {
        mapStatus.Add(await SetMapAsync(editor, map));
      }

      if (window is not null)
      {
        var minX = Required(window, "minX");
        var minY = Required(window, "minY");
        var maxX = Required(window, "maxX");
        var maxY = Required(window, "maxY");
        if (maxX <= minX || maxY <= minY)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "captureView window needs maxX > minX and maxY > minY.");
        }

        using (doc.LockDocument())
        {
          using var view = editor.GetCurrentView();
          var aspect = view.Height > 0 ? view.Width / view.Height : 1.0;
          var width = maxX - minX + 2 * pad;
          var height = maxY - minY + 2 * pad;
          if (width / height > aspect)
          {
            height = width / aspect;
          }
          else
          {
            width = height * aspect;
          }

          view.ViewDirection = Vector3d.ZAxis;
          view.Target = Point3d.Origin;
          view.ViewTwist = 0;
          view.CenterPoint = new Point2d((minX + maxX) / 2, (minY + maxY) / 2);
          view.Width = width;
          view.Height = height;
          editor.SetCurrentView(view);
        }

        editor.UpdateScreen();
      }

      // Let AutoCAD repaint and fetch online map tiles before capturing.
      if (waitMs > 0)
      {
        await Task.Delay(waitMs);
      }

      double cx, cy, viewWidth, viewHeight, twist;
      bool planView;
      using (doc.LockDocument())
      {
        using var current = editor.GetCurrentView();
        planView = current.ViewDirection.IsParallelTo(Vector3d.ZAxis);
        twist = current.ViewTwist;
        cx = current.Target.X + current.CenterPoint.X;
        cy = current.Target.Y + current.CenterPoint.Y;
        viewWidth = current.Width;
        viewHeight = current.Height;
      }

      var extents = new Dictionary<string, object?>
      {
        ["minX"] = Math.Round(cx - viewWidth / 2, 4),
        ["minY"] = Math.Round(cy - viewHeight / 2, 4),
        ["maxX"] = Math.Round(cx + viewWidth / 2, 4),
        ["maxY"] = Math.Round(cy + viewHeight / 2, 4),
      };

      int pixelWidth, pixelHeight;
      string source;
      if (mode == "render")
      {
        pixelWidth = renderWidth;
        pixelHeight = Math.Max(1, (int)Math.Round(renderWidth * viewHeight / viewWidth));
        using var bitmap = doc.CapturePreviewImage((uint)pixelWidth, (uint)pixelHeight);
        bitmap.Save(path, ImageFormat.Png);
        source = "CapturePreviewImage";
      }
      else
      {
        var (rect, how) = FindViewRect(doc.Window.Handle, viewWidth / viewHeight);
        pixelWidth = rect.Right - rect.Left;
        pixelHeight = rect.Bottom - rect.Top;
        if (pixelWidth <= 0 || pixelHeight <= 0)
        {
          throw new JsonRpcDispatchException("CIVIL3D.HOST_ERROR", "The drawing view has no visible area to capture (is Civil 3D minimized?).");
        }

        using var bitmap = new Bitmap(pixelWidth, pixelHeight, PixelFormat.Format24bppRgb);
        using (var graphics = Graphics.FromImage(bitmap))
        {
          graphics.CopyFromScreen(rect.Left, rect.Top, 0, 0, new Size(pixelWidth, pixelHeight));
        }

        bitmap.Save(path, ImageFormat.Png);
        source = how;
      }

      if (mapAfter is not null)
      {
        mapStatus.Add(await SetMapAsync(editor, mapAfter));
      }

      return new Dictionary<string, object?>
      {
        ["outFile"] = path,
        ["map"] = mapStatus,
        ["mode"] = mode,
        ["source"] = source,
        ["pixelWidth"] = pixelWidth,
        ["pixelHeight"] = pixelHeight,
        ["extents"] = extents,
        ["feetPerPixel"] = Math.Round(viewWidth / pixelWidth, 5),
        ["planView"] = planView,
        ["viewTwistDeg"] = Math.Round(twist * 180 / Math.PI, 4),
        ["note"] = planView && Math.Abs(twist) < 1e-9
          ? "Pixel (0,0) is the top-left corner = (minX, maxY)."
          : "View is twisted or not plan; extents are approximate.",
      };
    });
  }

  /// <summary>
  /// The drawing view is a child window of the document window. Pick the
  /// largest visible descendant whose client aspect matches the view's
  /// width/height; fall back to the document window's client area.
  /// </summary>
  private static (RECT Rect, string How) FindViewRect(IntPtr documentWindow, double viewAspect)
  {
    RECT best = default;
    long bestArea = 0;
    EnumChildWindows(documentWindow, (child, _) =>
    {
      if (!IsWindowVisible(child) || !GetClientRect(child, out var client))
      {
        return true;
      }

      var w = client.Right - client.Left;
      var h = client.Bottom - client.Top;
      if (w < 50 || h < 50)
      {
        return true;
      }

      var aspect = (double)w / h;
      if (Math.Abs(aspect - viewAspect) / viewAspect > 0.01)
      {
        return true;
      }

      long area = (long)w * h;
      if (area > bestArea)
      {
        var origin = new POINT { X = 0, Y = 0 };
        ClientToScreen(child, ref origin);
        best = new RECT { Left = origin.X, Top = origin.Y, Right = origin.X + w, Bottom = origin.Y + h };
        bestArea = area;
      }

      return true;
    }, IntPtr.Zero);

    if (bestArea > 0)
    {
      return (best, "screen: drawing view window");
    }

    GetClientRect(documentWindow, out var docClient);
    var docOrigin = new POINT { X = 0, Y = 0 };
    ClientToScreen(documentWindow, ref docOrigin);
    return (new RECT
    {
      Left = docOrigin.X,
      Top = docOrigin.Y,
      Right = docOrigin.X + docClient.Right - docClient.Left,
      Bottom = docOrigin.Y + docClient.Bottom - docClient.Top,
    }, "screen: document window (view window not found; extents may not line up)");
  }

  /// <summary>
  /// geolocateDrawing: gives the drawing a geographic location (what GEOMAP and
  /// GEOMAPIMAGE need) from a coordinate system code, by default the Civil 3D
  /// drawing settings' zone (e.g. CA83-VF). Grid coordinates, design point =
  /// reference point = the given point or the middle of the drawing extents,
  /// north = +Y, unity scale. Reports and keeps an existing location unless
  /// overwrite is true.
  /// </summary>
  public static Task<object?> GeolocateDrawingAsync(JsonObject? parameters)
  {
    var overwrite = PluginRuntime.GetOptionalBool(parameters, "overwrite") ?? false;
    var requestedCode = PluginRuntime.GetOptionalString(parameters, "coordinateSystem");
    var pointNode = PluginRuntime.GetParameter(parameters, "point") as JsonObject;

    return CivilExecution.WriteAsync<object?>((doc, civilDoc, database, transaction) =>
    {
      var existingId = ObjectId.Null;
      try
      {
        existingId = database.GeoDataObject;
      }
      catch (Autodesk.AutoCAD.Runtime.Exception)
      {
        existingId = ObjectId.Null;
      }

      if (!existingId.IsNull && !overwrite)
      {
        var current = (GeoLocationData)transaction.GetObject(existingId, OpenMode.ForRead);
        return new Dictionary<string, object?>
        {
          ["changed"] = false,
          ["alreadyGeolocated"] = true,
          ["coordinateSystem"] = current.CoordinateSystem,
          ["designPoint"] = new Dictionary<string, object?> { ["x"] = current.DesignPoint.X, ["y"] = current.DesignPoint.Y },
          ["note"] = "Drawing already has a geographic location; pass overwrite=true to replace it.",
        };
      }

      var code = string.IsNullOrWhiteSpace(requestedCode)
        ? civilDoc.Settings.DrawingSettings.UnitZoneSettings.CoordinateSystemCode
        : requestedCode.Trim();
      if (string.IsNullOrWhiteSpace(code))
      {
        throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "No coordinate system: pass coordinateSystem or set the zone in Drawing Settings.");
      }

      Point3d point;
      if (pointNode is not null)
      {
        point = new Point3d(Required(pointNode, "x"), Required(pointNode, "y"), 0);
      }
      else
      {
        var min = database.Extmin;
        var max = database.Extmax;
        point = new Point3d((min.X + max.X) / 2, (min.Y + max.Y) / 2, 0);
      }

      if (!existingId.IsNull)
      {
        var old = transaction.GetObject(existingId, OpenMode.ForWrite);
        old.Erase();
      }

      var geo = new GeoLocationData
      {
        BlockTableRecordId = SymbolUtilityServices.GetBlockModelSpaceId(database),
      };
      geo.PostToDb();
      geo.CoordinateSystem = code;
      geo.TypeOfCoordinates = TypeOfCoordinates.CoordinateTypeGrid;
      geo.HorizontalUnits = database.Insunits;
      geo.VerticalUnits = database.Insunits;
      geo.DesignPoint = point;
      geo.ReferencePoint = point;
      geo.NorthDirectionVector = Vector2d.YAxis;
      geo.ScaleEstimationMethod = ScaleEstimationMethod.ScaleEstMethodUnity;

      return new Dictionary<string, object?>
      {
        ["changed"] = true,
        ["replacedExisting"] = !existingId.IsNull,
        ["coordinateSystem"] = code,
        ["designPoint"] = new Dictionary<string, object?> { ["x"] = Math.Round(point.X, 4), ["y"] = Math.Round(point.Y, 4) },
        ["horizontalUnits"] = database.Insunits.ToString(),
      };
    });
  }

  private static string? MapOption(string? value, string name)
  {
    if (string.IsNullOrWhiteSpace(value))
    {
      return null;
    }

    var option = value.Trim().ToLowerInvariant();
    if (option is not ("aerial" or "road" or "hybrid" or "off"))
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"captureView {name} must be aerial, road, hybrid or off.");
    }

    return option;
  }

  /// <summary>Runs GEOMAP with the option; reports instead of failing so the capture still happens.</summary>
  private static async Task<string> SetMapAsync(Editor editor, string option)
  {
    var keyword = option switch
    {
      "aerial" => "_Aerial",
      "road" => "_Road",
      "hybrid" => "_Hybrid",
      _ => "_Off",
    };

    try
    {
      await editor.CommandAsync("_.GEOMAP", keyword);
      return $"GEOMAP {option}: done";
    }
    catch (System.Exception ex)
    {
      return $"GEOMAP {option} failed: {ex.Message} (is the drawing geolocated and are you signed in to Autodesk?)";
    }
  }

  private static double Required(JsonObject window, string name) =>
    window[name]?.GetValue<double>() ?? throw new JsonRpcDispatchException(
      "CIVIL3D.INVALID_INPUT", $"captureView window needs {name}.");
}
