using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using System.Globalization;
using System.Text.Json.Nodes;

namespace Civil3DMcpPlugin;

/// <summary>
/// Generic AutoCAD entity tools: read everything in an area, copy or move
/// entities, edit text and attributes, adjust line endpoints, and erase.
/// Built for template-driven drafting where existing blocks, lines, text and
/// leaders are copied and edited rather than drawn from scratch.
/// </summary>
public static class EntityCommands
{
  private const int DefaultQueryLimit = 500;
  private const int MaxQueryLimit = 5000;
  private const int MaxVerticesPerEntity = 100;

  // ---------------------------------------------------------------- query

  public static Task<object?> QueryEntitiesAsync(JsonObject? parameters)
  {
    var spaceName = PluginRuntime.GetOptionalString(parameters, "space");
    var window = ReadWindow(parameters?["window"]);
    var crossing = PluginRuntime.GetOptionalBool(parameters, "crossing") ?? true;
    var layers = ReadStringSet(parameters?["layers"]);
    var types = ReadStringSet(parameters?["types"]);
    var limit = Math.Clamp(PluginRuntime.GetOptionalInt(parameters, "limit") ?? DefaultQueryLimit, 1, MaxQueryLimit);
    var includeGeometry = PluginRuntime.GetOptionalBool(parameters, "includeGeometry") ?? true;

    return CivilExecution.ReadAsync<object?>((doc, civilDoc, database, transaction) =>
    {
      var space = ResolveSpace(database, transaction, spaceName, OpenMode.ForRead);
      var results = new List<Dictionary<string, object?>>();
      var countsByType = new SortedDictionary<string, int>(StringComparer.OrdinalIgnoreCase);
      var matched = 0;

      foreach (ObjectId id in space.Record)
      {
        if (transaction.GetObject(id, OpenMode.ForRead, false) is not Entity entity)
        {
          continue;
        }

        if (!MatchesFilters(entity, window, crossing, layers, types))
        {
          continue;
        }

        matched++;
        var typeName = TypeName(entity);
        countsByType[typeName] = countsByType.TryGetValue(typeName, out var count) ? count + 1 : 1;

        if (results.Count < limit)
        {
          results.Add(Describe(entity, transaction, includeGeometry));
        }
      }

      return new Dictionary<string, object?>
      {
        ["space"] = space.Name,
        ["layouts"] = ListLayoutNames(database, transaction),
        ["matched"] = matched,
        ["returned"] = results.Count,
        ["truncated"] = matched > results.Count,
        ["countsByType"] = countsByType,
        ["entities"] = results,
      };
    });
  }

  // ----------------------------------------------------------- copy / move

  public static Task<object?> CopyEntitiesAsync(JsonObject? parameters)
  {
    if (PluginRuntime.GetParameter(parameters, "operations") is not JsonArray operations || operations.Count == 0)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "copyEntities requires a non-empty operations array.");
    }

    return CivilExecution.WriteAsync<object?>((doc, civilDoc, database, transaction) =>
    {
      var results = new List<Dictionary<string, object?>>();
      var progress = new DrawProgress(doc, "copy", operations.Count);

      for (var index = 0; index < operations.Count; index++)
      {
        progress.BeforePiece(index);
        if (operations[index] is not JsonObject operation)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Operation {index} must be an object.");
        }

        var mode = (operation["mode"]?.GetValue<string>() ?? "copy").Trim().ToLowerInvariant();
        if (mode != "copy" && mode != "move")
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Operation {index}: mode must be 'copy' or 'move'.");
        }

        var dx = operation["dx"]?.GetValue<double>() ?? 0.0;
        var dy = operation["dy"]?.GetValue<double>() ?? 0.0;
        var sourceSpaceName = operation["space"]?.GetValue<string>();
        var targetSpaceName = operation["targetSpace"]?.GetValue<string>();

        var sourceSpace = ResolveSpace(database, transaction, sourceSpaceName, OpenMode.ForRead);
        var ids = SelectIds(database, transaction, sourceSpace, operation, index);
        if (ids.Count == 0)
        {
          throw new JsonRpcDispatchException("CIVIL3D.NOT_FOUND", $"Operation {index} selected no entities.");
        }

        var displacement = Matrix3d.Displacement(new Vector3d(dx, dy, 0));
        var mirrorX = operation["mirrorX"]?.GetValue<double>();
        var handleMap = new Dictionary<string, string>();

        if (mode == "move")
        {
          if (!string.IsNullOrWhiteSpace(targetSpaceName))
          {
            throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Operation {index}: targetSpace is only supported for copy.");
          }

          foreach (ObjectId id in ids)
          {
            var entity = (Entity)transaction.GetObject(id, OpenMode.ForWrite);
            entity.TransformBy(displacement);
            if (mirrorX is { } mx)
            {
              MirrorReadable(entity, mx, transaction);
            }
            var handle = CivilObjectUtils.GetHandle(entity);
            handleMap[handle] = handle;
          }
        }
        else
        {
          var targetSpace = string.IsNullOrWhiteSpace(targetSpaceName)
            ? sourceSpace
            : ResolveSpace(database, transaction, targetSpaceName, OpenMode.ForRead);

          var mapping = new IdMapping();
          database.DeepCloneObjects(ids, targetSpace.Record.ObjectId, mapping, false);

          foreach (IdPair pair in mapping)
          {
            if (!pair.IsPrimary || !pair.IsCloned || !ids.Contains(pair.Key))
            {
              continue;
            }

            var clone = (Entity)transaction.GetObject(pair.Value, OpenMode.ForWrite);
            clone.TransformBy(displacement);
            if (mirrorX is { } mx)
            {
              MirrorReadable(clone, mx, transaction);
            }
            handleMap[pair.Key.Handle.ToString()] = clone.Handle.ToString();
          }
        }

        results.Add(new Dictionary<string, object?>
        {
          ["index"] = index,
          ["mode"] = mode,
          ["count"] = handleMap.Count,
          ["dx"] = dx,
          ["dy"] = dy,
          ["mirrorX"] = mirrorX,
          ["handles"] = handleMap,
        });
      }

      return new Dictionary<string, object?>
      {
        ["operations"] = results,
      };
    });
  }

  // ------------------------------------------------------------------ edit

  public static Task<object?> EditEntitiesAsync(JsonObject? parameters)
  {
    if (PluginRuntime.GetParameter(parameters, "edits") is not JsonArray edits || edits.Count == 0)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "editEntities requires a non-empty edits array.");
    }

    return CivilExecution.WriteAsync<object?>((doc, civilDoc, database, transaction) =>
    {
      var results = new List<Dictionary<string, object?>>();
      var progress = new DrawProgress(doc, "edit", edits.Count);

      for (var index = 0; index < edits.Count; index++)
      {
        progress.BeforePiece(index);
        if (edits[index] is not JsonObject edit)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index} must be an object.");
        }

        var handle = edit["handle"]?.GetValue<string>()
          ?? throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index} is missing handle.");
        var entity = (Entity)transaction.GetObject(GetIdFromHandle(database, handle), OpenMode.ForWrite);
        var changed = new List<string>();

        var text = edit["text"]?.GetValue<string>();
        if (text != null)
        {
          SetText(entity, text, transaction, index);
          changed.Add("text");
        }

        // Dynamic properties first: changing a visibility state can rebuild the
        // anonymous block, so attribute values are written after it.
        if (edit["dynamicProperties"] is JsonObject dynamicProperties && dynamicProperties.Count > 0)
        {
          if (entity is not BlockReference dynamicRef || !dynamicRef.IsDynamicBlock)
          {
            throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: dynamicProperties can only be set on dynamic block references.");
          }

          var missingProperties = SetDynamicProperties(dynamicRef, dynamicProperties, index);
          if (missingProperties.Count > 0)
          {
            throw new JsonRpcDispatchException("CIVIL3D.NOT_FOUND", $"Edit {index}: dynamic properties not found: {string.Join(", ", missingProperties)}. Available: {string.Join(", ", DynamicPropertyNames(dynamicRef))}.");
          }

          changed.Add("dynamicProperties");
        }

        if (edit["attributes"] is JsonObject attributes && attributes.Count > 0)
        {
          if (entity is not BlockReference blockRef)
          {
            throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: attributes can only be set on block references.");
          }

          var missing = SetAttributes(blockRef, attributes, transaction);
          if (missing.Count > 0)
          {
            throw new JsonRpcDispatchException("CIVIL3D.NOT_FOUND", $"Edit {index}: attribute tags not found: {string.Join(", ", missing)}.");
          }

          changed.Add("attributes");
        }

        var start = ReadPoint(edit["start"]);
        var end = ReadPoint(edit["end"]);
        if (start != null || end != null)
        {
          if (entity is not Line line)
          {
            throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: start/end can only be set on lines.");
          }

          if (start is { } s)
          {
            line.StartPoint = new Point3d(s.X, s.Y, line.StartPoint.Z);
            changed.Add("start");
          }

          if (end is { } e)
          {
            line.EndPoint = new Point3d(e.X, e.Y, line.EndPoint.Z);
            changed.Add("end");
          }
        }

        var xLine1 = ReadPoint(edit["xLine1"]);
        var xLine2 = ReadPoint(edit["xLine2"]);
        var dimLine = ReadPoint(edit["dimLine"]);
        if (xLine1 != null || xLine2 != null || dimLine != null)
        {
          SetDimensionPoints(entity, xLine1, xLine2, dimLine, index);
          changed.Add("dimensionPoints");
        }

        // Applied after dimension points, which reset text to its default spot.
        var textPosition = ReadPoint(edit["textPosition"]);
        if (textPosition is { } tp)
        {
          if (entity is not Dimension dimensionForText)
          {
            throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: textPosition can only be set on dimensions.");
          }

          dimensionForText.TextPosition = new Point3d(tp.X, tp.Y, dimensionForText.TextPosition.Z);
          dimensionForText.UsingDefaultTextPosition = false;
          dimensionForText.RecomputeDimensionBlock(true);
          changed.Add("textPosition");
        }

        if (edit["vertices"] is JsonArray vertexNodes)
        {
          var vertices = vertexNodes.Select(node => ReadPoint(node)
            ?? throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: every vertex needs x and y.")).ToList();
          SetVertices(entity, vertices, index);
          changed.Add("vertices");
        }

        var closed = edit["closed"]?.GetValue<bool>();
        if (closed != null)
        {
          if (entity is not Polyline closable)
          {
            throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: closed applies to LWPOLYLINEs only.");
          }

          closable.Closed = closed.Value;
          changed.Add("closed");
        }

        // Circles and arcs: center, radius, and for arcs the start/end angles
        // (degrees CCW from +X, the arc runs CCW from start to end).
        var center = ReadPoint(edit["center"]);
        var radius = edit["radius"]?.GetValue<double>();
        var startAngleDeg = edit["startAngleDeg"]?.GetValue<double>();
        var endAngleDeg = edit["endAngleDeg"]?.GetValue<double>();
        if (center != null || radius != null)
        {
          if (radius is { } rad && rad <= 0)
          {
            throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: radius must be greater than 0.");
          }

          switch (entity)
          {
            case Circle editedCircle:
              if (center is { } cc)
              {
                editedCircle.Center = new Point3d(cc.X, cc.Y, editedCircle.Center.Z);
              }

              if (radius is { } cr)
              {
                editedCircle.Radius = cr;
              }

              break;
            case Arc editedArc:
              if (center is { } ac)
              {
                editedArc.Center = new Point3d(ac.X, ac.Y, editedArc.Center.Z);
              }

              if (radius is { } ar)
              {
                editedArc.Radius = ar;
              }

              break;
            default:
              throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: center/radius can only be set on circles and arcs.");
          }

          if (center != null)
          {
            changed.Add("center");
          }

          if (radius != null)
          {
            changed.Add("radius");
          }
        }

        if (startAngleDeg != null || endAngleDeg != null)
        {
          if (entity is not Arc angledArc)
          {
            throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: startAngleDeg/endAngleDeg can only be set on arcs.");
          }

          if (startAngleDeg is { } sa)
          {
            angledArc.StartAngle = NormalizeRadians(sa * Math.PI / 180.0);
            changed.Add("startAngleDeg");
          }

          if (endAngleDeg is { } ea)
          {
            angledArc.EndAngle = NormalizeRadians(ea * Math.PI / 180.0);
            changed.Add("endAngleDeg");
          }
        }

        // Rotation about the entity's own insertion point, in degrees CCW.
        var rotationDeg = edit["rotationDeg"]?.GetValue<double>();
        if (rotationDeg != null)
        {
          var radians = rotationDeg.Value * Math.PI / 180.0;
          switch (entity)
          {
            case BlockReference rotatedBlock:
              rotatedBlock.Rotation = radians;
              break;
            case DBText rotatedText:
              rotatedText.Rotation = radians;
              break;
            case MText rotatedMText:
              rotatedMText.Rotation = radians;
              break;
            default:
              throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: rotationDeg can only be set on block references, text and MText.");
          }

          changed.Add("rotationDeg");
        }

        var colorIndex = edit["colorIndex"]?.GetValue<int>();
        if (colorIndex != null)
        {
          if (colorIndex < 0 || colorIndex > 256)
          {
            throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: colorIndex must be 0-256 (0 = ByBlock, 256 = ByLayer).");
          }

          entity.ColorIndex = colorIndex.Value;
          changed.Add("colorIndex");
        }

        var linetype = edit["linetype"]?.GetValue<string>();
        if (!string.IsNullOrWhiteSpace(linetype))
        {
          entity.LinetypeId = GetLinetypeId(database, transaction, linetype, index);
          changed.Add("linetype");
        }

        var layer = edit["layer"]?.GetValue<string>();
        if (!string.IsNullOrWhiteSpace(layer))
        {
          entity.LayerId = LookupUtils.GetLayerId(database, transaction, layer);
          changed.Add("layer");
        }

        if (changed.Count == 0)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index} has nothing to change.");
        }

        results.Add(new Dictionary<string, object?>
        {
          ["index"] = index,
          ["handle"] = handle,
          ["type"] = TypeName(entity),
          ["changed"] = changed,
        });
      }

      return new Dictionary<string, object?>
      {
        ["edits"] = results,
      };
    });
  }

  // ----------------------------------------------------------------- erase

  public static Task<object?> EraseEntitiesAsync(JsonObject? parameters)
  {
    var handles = ReadStringList(PluginRuntime.GetParameter(parameters, "handles") as JsonNode);
    if (handles.Count == 0)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "eraseEntities requires a non-empty handles array.");
    }

    return CivilExecution.WriteAsync<object?>((doc, civilDoc, database, transaction) =>
    {
      var erased = new List<string>();
      var progress = new DrawProgress(doc, "erase", handles.Count);
      foreach (var handle in handles)
      {
        progress.BeforePiece(erased.Count);
        var entity = (Entity)transaction.GetObject(GetIdFromHandle(database, handle), OpenMode.ForWrite);
        entity.Erase();
        erased.Add(handle);
      }

      return new Dictionary<string, object?>
      {
        ["erased"] = erased,
        ["count"] = erased.Count,
      };
    });
  }

  // ----------------------------------------------------------------- hatch

  /// <summary>
  /// Creates hatches like HATCH > Select objects: closed LWPOLYLINEs and circles
  /// become the boundary objects (associative, so the hatch follows later edits).
  /// Open polylines or explicit vertex loops fall back to vertex-built loops
  /// (open ones closed with a straight segment, non-associative). Pattern, scale,
  /// angle, style, layer and color can be copied from an existing hatch ("like").
  /// </summary>
  public static Task<object?> CreateHatchesAsync(JsonObject? parameters)
  {
    if (PluginRuntime.GetParameter(parameters, "hatches") is not JsonArray specs || specs.Count == 0)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "createHatches requires a non-empty hatches array.");
    }

    return CivilExecution.WriteAsync<object?>((doc, civilDoc, database, transaction) =>
    {
      var created = new List<Dictionary<string, object?>>();
      var progress = new DrawProgress(doc, "hatch", specs.Count);
      for (var index = 0; index < specs.Count; index++)
      {
        progress.BeforePiece(index);
        if (specs[index] is not JsonObject spec)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Hatch {index}: must be an object.");
        }

        // Like HATCH > Select objects: closed polylines and circles are used as
        // the boundary objects themselves (associative, the hatch follows them).
        // Only when a boundary is not a closed curve, or explicit loops are given,
        // are loops built from vertices instead (non-associative).
        var loops = new List<(Point2dCollection Points, DoubleCollection Bulges)>();
        var boundaryIds = new List<(ObjectId Id, string Handle)>();
        var allClosed = true;
        foreach (var handle in ReadStringList(spec["boundaries"]))
        {
          var id = GetIdFromHandle(database, handle);
          var boundary = transaction.GetObject(id, OpenMode.ForRead);
          boundaryIds.Add((id, handle));
          allClosed &= boundary is Circle || (boundary is Polyline closedPolyline && closedPolyline.Closed);
          loops.Add(LoopFromEntity(boundary, index, handle));
        }

        if (spec["loops"] is JsonArray rawLoops)
        {
          for (var l = 0; l < rawLoops.Count; l++)
          {
            var points = new List<Point2d>();
            if (rawLoops[l] is JsonArray rawPoints)
            {
              foreach (var rawPoint in rawPoints)
              {
                points.Add(ReadPoint(rawPoint) ?? throw new JsonRpcDispatchException(
                  "CIVIL3D.INVALID_INPUT", $"Hatch {index}: loops[{l}] has a point without numeric x and y."));
              }
            }

            if (points.Count < 3)
            {
              throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Hatch {index}: loops[{l}] needs at least 3 points.");
            }

            loops.Add(CloseLoop(points, points.Select(_ => 0.0).ToList(), true));
          }
        }

        var wantAssociative = PluginRuntime.GetOptionalBool(spec, "associative") ?? true;
        var useObjects = wantAssociative && allClosed && boundaryIds.Count > 0 && spec["loops"] is not JsonArray;

        if (loops.Count == 0)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Hatch {index}: needs boundaries and/or loops.");
        }

        Hatch? like = null;
        var likeHandle = PluginRuntime.GetOptionalString(spec, "like");
        if (!string.IsNullOrWhiteSpace(likeHandle))
        {
          like = transaction.GetObject(GetIdFromHandle(database, likeHandle), OpenMode.ForRead) as Hatch
            ?? throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Hatch {index}: 'like' handle {likeHandle} is not a hatch.");
        }

        var space = ResolveSpace(database, transaction, PluginRuntime.GetOptionalString(spec, "space"), OpenMode.ForWrite);
        var pattern = PluginRuntime.GetOptionalString(spec, "pattern") ?? like?.PatternName ?? "ANSI31";
        var patternType = like != null && pattern.Equals(like.PatternName, StringComparison.OrdinalIgnoreCase)
          ? like.PatternType
          : HatchPatternType.PreDefined;
        var angleDeg = PluginRuntime.GetOptionalDouble(spec, "angleDeg");
        var angle = angleDeg.HasValue ? angleDeg.Value * Math.PI / 180.0 : like?.PatternAngle ?? 0.0;
        var scale = PluginRuntime.GetOptionalDouble(spec, "scale") ?? like?.PatternScale ?? 1.0;
        if (scale <= 0)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Hatch {index}: scale must be positive.");
        }

        var colorIndex = PluginRuntime.GetOptionalInt(spec, "colorIndex");
        if (colorIndex != null && (colorIndex < 0 || colorIndex > 256))
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Hatch {index}: colorIndex must be 0-256 (0 = ByBlock, 256 = ByLayer).");
        }

        // Canonical order: pattern first, then scale and angle (re-applying the
        // pattern so they take effect), then loops, then evaluate, then the
        // display properties. Every step reports its own failure.
        var hatch = new Hatch();
        hatch.SetDatabaseDefaults(database);
        space.Record.AppendEntity(hatch);
        transaction.AddNewlyCreatedDBObject(hatch, true);

        Step(index, $"set pattern {patternType} {pattern}", () => hatch.SetHatchPattern(patternType, pattern));
        Step(index, $"set scale {scale}", () => hatch.PatternScale = scale);
        Step(index, $"set angle {angle}", () => hatch.PatternAngle = angle);
        Step(index, "re-apply pattern", () => hatch.SetHatchPattern(hatch.PatternType, hatch.PatternName));
        // Island style goes on before any loop: changing it after EvaluateHatch
        // and evaluating again fails with eInvalidInput.
        if (like != null && hatch.HatchStyle != like.HatchStyle)
        {
          Step(index, $"copy hatch style {like.HatchStyle}", () => hatch.HatchStyle = like.HatchStyle);
        }

        if (useObjects)
        {
          Step(index, "set associative", () => hatch.Associative = true);
          foreach (var (id, handle) in boundaryIds)
          {
            Step(index, $"append boundary {handle}", () => hatch.AppendLoop(HatchLoopTypes.Default, new ObjectIdCollection(new[] { id })));
          }
        }
        else
        {
          Step(index, "set non-associative", () => hatch.Associative = false);
          for (var l = 0; l < loops.Count; l++)
          {
            var (points, bulges) = loops[l];
            AppendPolylineLoop(hatch, points, bulges, index, l);
          }
        }

        Step(index, "evaluate hatch", () => hatch.EvaluateHatch(true));

        if (like != null)
        {
          Step(index, "copy layer", () => hatch.Layer = like.Layer);
          Step(index, "copy color", () => hatch.Color = like.Color);
          Step(index, "copy linetype", () => hatch.LinetypeId = like.LinetypeId);
          Step(index, "copy lineweight", () => hatch.LineWeight = like.LineWeight);
        }

        var layer = PluginRuntime.GetOptionalString(spec, "layer");
        if (!string.IsNullOrWhiteSpace(layer))
        {
          Step(index, $"set layer {layer}", () => hatch.Layer = layer);
        }

        if (colorIndex != null)
        {
          hatch.ColorIndex = colorIndex.Value;
        }
        created.Add(new Dictionary<string, object?>
        {
          ["index"] = index,
          ["handle"] = hatch.Handle.ToString(),
          ["pattern"] = hatch.PatternName,
          ["scale"] = R(hatch.PatternScale),
          ["angleDeg"] = R(hatch.PatternAngle * 180.0 / Math.PI),
          ["loops"] = loops.Count,
          ["associative"] = hatch.Associative,
          ["layer"] = hatch.Layer,
        });
      }

      return new Dictionary<string, object?>
      {
        ["hatches"] = created,
        ["count"] = created.Count,
      };
    });
  }

  /// <summary>
  /// Appends a polyline loop. AutoCAD versions differ on whether the closing
  /// vertex may repeat the first one, so try with it and fall back to without.
  /// </summary>
  private static void AppendPolylineLoop(Hatch hatch, Point2dCollection points, DoubleCollection bulges, int index, int loop)
  {
    try
    {
      hatch.AppendLoop(HatchLoopTypes.Polyline, points, bulges);
      return;
    }
    catch (Autodesk.AutoCAD.Runtime.Exception)
    {
      // fall through: retry without the repeated closing vertex
    }

    var open = new Point2dCollection();
    var openBulges = new DoubleCollection();
    for (var i = 0; i < points.Count - 1; i++)
    {
      open.Add(points[i]);
      openBulges.Add(bulges[i]);
    }

    Step(index, $"append loop {loop} ({open.Count} vertices)", () => hatch.AppendLoop(HatchLoopTypes.Polyline, open, openBulges));
  }

  private static void Step(int index, string what, Action action)
  {
    try
    {
      action();
    }
    catch (Autodesk.AutoCAD.Runtime.Exception ex)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Hatch {index}: {what} failed: {ex.ErrorStatus}.");
    }
    catch (System.Exception ex) when (ex is not JsonRpcDispatchException)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Hatch {index}: {what} failed: {ex.GetType().Name}: {ex.Message}");
    }
  }

  private static (Point2dCollection Points, DoubleCollection Bulges) LoopFromEntity(DBObject entity, int index, string handle)
  {
    switch (entity)
    {
      case Polyline polyline:
      {
        var points = new List<Point2d>();
        var bulges = new List<double>();
        for (var i = 0; i < polyline.NumberOfVertices; i++)
        {
          points.Add(polyline.GetPoint2dAt(i));
          bulges.Add(polyline.GetBulgeAt(i));
        }

        if (points.Count < 2)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Hatch {index}: boundary {handle} has fewer than 2 vertices.");
        }

        return CloseLoop(points, bulges, polyline.Closed);
      }
      case Circle circle:
      {
        var c = circle.Center;
        var r = circle.Radius;
        return CloseLoop(
          new List<Point2d> { new(c.X + r, c.Y), new(c.X - r, c.Y) },
          new List<double> { 1.0, 1.0 },
          true);
      }
      default:
        throw new JsonRpcDispatchException(
          "CIVIL3D.INVALID_INPUT",
          $"Hatch {index}: boundary {handle} is a {entity.GetType().Name}; use LWPOLYLINEs or circles, or give explicit loops.");
    }
  }

  /// <summary>
  /// Builds an explicitly closed hatch polyline loop. bulges[k] is the bulge of
  /// the segment from points[k] to points[k + 1]; the last one is the closing
  /// segment when closed is true (straight otherwise). A duplicate closing
  /// vertex is folded in, so a polyline drawn back onto its start works too.
  /// </summary>
  private static (Point2dCollection Points, DoubleCollection Bulges) CloseLoop(List<Point2d> points, List<double> bulges, bool closed)
  {
    if (points.Count > 2 && points[0].GetDistanceTo(points[^1]) < 1e-6)
    {
      points.RemoveAt(points.Count - 1);
      bulges.RemoveAt(bulges.Count - 1);
      closed = true;
    }

    if (!closed)
    {
      bulges[^1] = 0.0;
    }

    var outPoints = new Point2dCollection();
    var outBulges = new DoubleCollection();
    for (var i = 0; i < points.Count; i++)
    {
      outPoints.Add(points[i]);
      outBulges.Add(bulges[i]);
    }

    outPoints.Add(points[0]);
    outBulges.Add(0.0);
    return (outPoints, outBulges);
  }

  // --------------------------------------------------------------- helpers

  private sealed record SpaceInfo(string Name, BlockTableRecord Record);

  private readonly record struct Window(double MinX, double MinY, double MaxX, double MaxY);

  private static SpaceInfo ResolveSpace(Database database, Transaction transaction, string? spaceName, OpenMode openMode)
  {
    if (string.IsNullOrWhiteSpace(spaceName) || spaceName.Equals("model", StringComparison.OrdinalIgnoreCase))
    {
      var blockTable = (BlockTable)transaction.GetObject(database.BlockTableId, OpenMode.ForRead);
      var record = (BlockTableRecord)transaction.GetObject(blockTable[BlockTableRecord.ModelSpace], openMode);
      return new SpaceInfo("Model", record);
    }

    var layouts = (DBDictionary)transaction.GetObject(database.LayoutDictionaryId, OpenMode.ForRead);
    foreach (DBDictionaryEntry entry in layouts)
    {
      if (!entry.Key.Equals(spaceName, StringComparison.OrdinalIgnoreCase))
      {
        continue;
      }

      var layout = (Layout)transaction.GetObject(entry.Value, OpenMode.ForRead);
      var record = (BlockTableRecord)transaction.GetObject(layout.BlockTableRecordId, openMode);
      return new SpaceInfo(layout.LayoutName, record);
    }

    throw new JsonRpcDispatchException(
      "CIVIL3D.NOT_FOUND",
      $"Space '{spaceName}' not found. Use 'model' or one of: {string.Join(", ", ListLayoutNames(database, transaction))}.");
  }

  private static List<string> ListLayoutNames(Database database, Transaction transaction)
  {
    var names = new List<(int Order, string Name)>();
    var layouts = (DBDictionary)transaction.GetObject(database.LayoutDictionaryId, OpenMode.ForRead);
    foreach (DBDictionaryEntry entry in layouts)
    {
      var layout = (Layout)transaction.GetObject(entry.Value, OpenMode.ForRead);
      names.Add((layout.TabOrder, layout.LayoutName));
    }

    return names.OrderBy(n => n.Order).Select(n => n.Name).ToList();
  }

  private static ObjectIdCollection SelectIds(Database database, Transaction transaction, SpaceInfo space, JsonObject operation, int index)
  {
    var ids = new ObjectIdCollection();
    var handles = ReadStringList(operation["handles"]);
    var window = ReadWindow(operation["window"]);

    if (handles.Count == 0 && window == null)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Operation {index} needs handles or a window.");
    }

    foreach (var handle in handles)
    {
      var id = GetIdFromHandle(database, handle);
      if (!ids.Contains(id))
      {
        ids.Add(id);
      }
    }

    if (window != null)
    {
      var crossing = operation["crossing"]?.GetValue<bool>() ?? false;
      var layers = ReadStringSet(operation["layers"]);
      var types = ReadStringSet(operation["types"]);
      foreach (ObjectId id in space.Record)
      {
        if (ids.Contains(id))
        {
          continue;
        }

        if (transaction.GetObject(id, OpenMode.ForRead, false) is Entity entity &&
            MatchesFilters(entity, window, crossing, layers, types))
        {
          ids.Add(id);
        }
      }
    }

    return ids;
  }

  private static bool MatchesFilters(Entity entity, Window? window, bool crossing, HashSet<string>? layers, HashSet<string>? types)
  {
    if (layers != null && !layers.Contains(entity.Layer))
    {
      return false;
    }

    if (types != null && !types.Contains(TypeName(entity)))
    {
      return false;
    }

    if (window is not { } w)
    {
      return true;
    }

    var extents = TryGetExtents(entity);
    if (extents is not { } e)
    {
      return false;
    }

    if (crossing)
    {
      return e.MaxPoint.X >= w.MinX && e.MinPoint.X <= w.MaxX &&
             e.MaxPoint.Y >= w.MinY && e.MinPoint.Y <= w.MaxY;
    }

    return e.MinPoint.X >= w.MinX && e.MaxPoint.X <= w.MaxX &&
           e.MinPoint.Y >= w.MinY && e.MaxPoint.Y <= w.MaxY;
  }

  private static Extents3d? TryGetExtents(Entity entity)
  {
    try
    {
      return entity.GeometricExtents;
    }
    catch
    {
      return null;
    }
  }

  private static ObjectId GetIdFromHandle(Database database, string handle)
  {
    long value;
    try
    {
      value = Convert.ToInt64(handle.Trim(), 16);
    }
    catch (Exception)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"'{handle}' is not a valid hexadecimal handle.");
    }

    if (!database.TryGetObjectId(new Handle(value), out var id) || id.IsNull || id.IsErased)
    {
      throw new JsonRpcDispatchException("CIVIL3D.NOT_FOUND", $"No entity found for handle '{handle}'.");
    }

    return id;
  }

  private static string TypeName(Entity entity)
  {
    try
    {
      var dxf = entity.GetRXClass().DxfName;
      if (!string.IsNullOrWhiteSpace(dxf))
      {
        return dxf;
      }
    }
    catch
    {
      // fall through to the managed type name
    }

    return entity.GetType().Name;
  }

  private static Dictionary<string, object?> Describe(Entity entity, Transaction transaction, bool includeGeometry)
  {
    var info = new Dictionary<string, object?>
    {
      ["handle"] = CivilObjectUtils.GetHandle(entity),
      ["type"] = TypeName(entity),
      ["layer"] = entity.Layer,
    };

    if (entity.ColorIndex != 256)
    {
      info["colorIndex"] = entity.ColorIndex;
    }

    if (!string.Equals(entity.Linetype, "BYLAYER", StringComparison.OrdinalIgnoreCase))
    {
      info["linetype"] = entity.Linetype;
    }

    if (TryGetExtents(entity) is { } extents)
    {
      info["extents"] = new Dictionary<string, object?>
      {
        ["min"] = P(extents.MinPoint),
        ["max"] = P(extents.MaxPoint),
      };
    }

    switch (entity)
    {
      case Line line:
        if (includeGeometry)
        {
          info["start"] = P(line.StartPoint);
          info["end"] = P(line.EndPoint);
          info["length"] = R(line.Length);
        }
        break;

      case Polyline polyline:
        info["closed"] = polyline.Closed;
        info["vertexCount"] = polyline.NumberOfVertices;
        if (includeGeometry)
        {
          var vertices = new List<object>();
          for (var i = 0; i < Math.Min(polyline.NumberOfVertices, MaxVerticesPerEntity); i++)
          {
            vertices.Add(P(polyline.GetPoint2dAt(i)));
          }
          info["vertices"] = vertices;
        }
        break;

      case Circle circle:
        info["center"] = P(circle.Center);
        info["radius"] = R(circle.Radius);
        break;

      case Arc arc:
        info["center"] = P(arc.Center);
        info["radius"] = R(arc.Radius);
        info["startAngleDeg"] = R(arc.StartAngle * 180.0 / Math.PI);
        info["endAngleDeg"] = R(arc.EndAngle * 180.0 / Math.PI);
        break;

      case DBText text:
        info["text"] = text.TextString;
        info["position"] = P(text.Position);
        info["height"] = R(text.Height);
        info["rotationDeg"] = R(text.Rotation * 180.0 / Math.PI);
        info["style"] = text.TextStyleName;
        break;

      case MText mtext:
        info["text"] = mtext.Text;
        info["contents"] = mtext.Contents;
        info["location"] = P(mtext.Location);
        info["height"] = R(mtext.TextHeight);
        info["width"] = R(mtext.Width);
        info["rotationDeg"] = R(mtext.Rotation * 180.0 / Math.PI);
        info["style"] = mtext.TextStyleName;
        break;

      case MLeader mleader:
        DescribeMLeader(mleader, info, includeGeometry);
        break;

      case Leader leader:
        if (includeGeometry)
        {
          var vertices = new List<object>();
          for (var i = 0; i < Math.Min(leader.NumVertices, MaxVerticesPerEntity); i++)
          {
            vertices.Add(P(leader.VertexAt(i)));
          }
          info["vertices"] = vertices;
        }
        if (!leader.Annotation.IsNull)
        {
          info["annotationHandle"] = leader.Annotation.Handle.ToString();
        }
        break;

      case Dimension dimension:
        info["measurement"] = R(dimension.Measurement);
        info["dimensionText"] = dimension.DimensionText;
        info["textPosition"] = P(dimension.TextPosition);
        if (includeGeometry && dimension is RotatedDimension rd)
        {
          info["xLine1"] = P(rd.XLine1Point);
          info["xLine2"] = P(rd.XLine2Point);
          info["dimLine"] = P(rd.DimLinePoint);
          info["rotationDeg"] = R(rd.Rotation * 180.0 / Math.PI);
        }
        else if (includeGeometry && dimension is AlignedDimension ad)
        {
          info["xLine1"] = P(ad.XLine1Point);
          info["xLine2"] = P(ad.XLine2Point);
          info["dimLine"] = P(ad.DimLinePoint);
        }
        break;

      case BlockReference blockRef:
        DescribeBlockReference(blockRef, transaction, info);
        break;
    }

    return info;
  }

  private static void DescribeBlockReference(BlockReference blockRef, Transaction transaction, Dictionary<string, object?> info)
  {
    var name = blockRef.Name;
    try
    {
      if (blockRef.IsDynamicBlock)
      {
        var dynamicRecord = (BlockTableRecord)transaction.GetObject(blockRef.DynamicBlockTableRecord, OpenMode.ForRead);
        info["anonymousName"] = name;
        name = dynamicRecord.Name;
        info["dynamic"] = true;

        var dynamicProperties = new Dictionary<string, object?>();
        foreach (var property in EditableDynamicProperties(blockRef))
        {
          dynamicProperties.TryAdd(property.PropertyName, DynamicValueForJson(property.Value));
        }

        if (dynamicProperties.Count > 0)
        {
          info["dynamicProperties"] = dynamicProperties;
        }
      }
    }
    catch
    {
      // keep the plain block name
    }

    info["blockName"] = name;
    info["position"] = P(blockRef.Position);
    info["rotationDeg"] = R(blockRef.Rotation * 180.0 / Math.PI);

    var scale = blockRef.ScaleFactors;
    if (Math.Abs(scale.X - 1) > 1e-9 || Math.Abs(scale.Y - 1) > 1e-9 || Math.Abs(scale.Z - 1) > 1e-9)
    {
      info["scale"] = new Dictionary<string, object?> { ["x"] = R(scale.X), ["y"] = R(scale.Y), ["z"] = R(scale.Z) };
    }

    var attributes = new Dictionary<string, object?>();
    foreach (ObjectId attributeId in blockRef.AttributeCollection)
    {
      if (transaction.GetObject(attributeId, OpenMode.ForRead, false) is AttributeReference attribute)
      {
        attributes[attribute.Tag] = attribute.IsMTextAttribute ? attribute.MTextAttribute.Text : attribute.TextString;
      }
    }

    if (attributes.Count > 0)
    {
      info["attributes"] = attributes;
    }
  }

  private static void DescribeMLeader(MLeader mleader, Dictionary<string, object?> info, bool includeGeometry)
  {
    try
    {
      if (mleader.ContentType == ContentType.MTextContent && mleader.MText is { } mtext)
      {
        info["text"] = mtext.Text;
        info["contents"] = mtext.Contents;
        info["textLocation"] = P(mtext.Location);
      }
      else if (mleader.ContentType == ContentType.BlockContent)
      {
        info["contentBlock"] = true;
      }
    }
    catch
    {
      // content not readable; leave it out
    }

    if (!includeGeometry)
    {
      return;
    }

    try
    {
      var lines = new List<object>();
      foreach (int leaderIndex in mleader.GetLeaderIndexes())
      {
        foreach (int lineIndex in mleader.GetLeaderLineIndexes(leaderIndex))
        {
          var vertices = new List<object>();
          var count = mleader.VerticesCount(lineIndex);
          for (var i = 0; i < Math.Min(count, MaxVerticesPerEntity); i++)
          {
            vertices.Add(P(mleader.GetVertex(lineIndex, i)));
          }
          lines.Add(vertices);
        }
      }

      if (lines.Count > 0)
      {
        info["leaderLines"] = lines;
      }
    }
    catch
    {
      // leader geometry not readable; leave it out
    }
  }

  private static void SetText(Entity entity, string text, Transaction transaction, int index)
  {
    switch (entity)
    {
      case AttributeReference attribute:
        if (attribute.IsMTextAttribute)
        {
          var mtextAttribute = attribute.MTextAttribute;
          mtextAttribute.Contents = text;
          attribute.MTextAttribute = mtextAttribute;
          attribute.UpdateMTextAttribute();
        }
        else
        {
          attribute.TextString = text;
        }
        break;

      case DBText dbText:
        dbText.TextString = text;
        break;

      case MText mtext:
        mtext.Contents = text;
        break;

      case MLeader mleader:
        if (mleader.ContentType != ContentType.MTextContent || mleader.MText == null)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: this multileader has no text content.");
        }

        var content = mleader.MText;
        content.Contents = text;
        mleader.MText = content;
        break;

      case Dimension dimension:
        dimension.DimensionText = text;
        break;

      default:
        throw new JsonRpcDispatchException(
          "CIVIL3D.INVALID_INPUT",
          $"Edit {index}: text cannot be set on a {TypeName(entity)}. Use attributes for block references.");
    }
  }

  private static IEnumerable<DynamicBlockReferenceProperty> EditableDynamicProperties(BlockReference blockRef)
  {
    foreach (DynamicBlockReferenceProperty property in blockRef.DynamicBlockReferencePropertyCollection)
    {
      if (!property.ReadOnly && !string.Equals(property.PropertyName, "Origin", StringComparison.OrdinalIgnoreCase))
      {
        yield return property;
      }
    }
  }

  private static IEnumerable<string> DynamicPropertyNames(BlockReference blockRef) =>
    EditableDynamicProperties(blockRef).Select(property => property.PropertyName).Distinct();

  private static object? DynamicValueForJson(object? value) => value switch
  {
    null => null,
    string s => s,
    double d => R(d),
    short or int or long or float => Convert.ToDouble(value, CultureInfo.InvariantCulture),
    _ => Convert.ToString(value, CultureInfo.InvariantCulture),
  };

  private static List<string> SetDynamicProperties(BlockReference blockRef, JsonObject values, int index)
  {
    var missing = new List<string>();
    foreach (var (name, node) in values)
    {
      if (node == null)
      {
        continue;
      }

      var raw = node is JsonValue jsonValue && jsonValue.TryGetValue<string>(out var s)
        ? s
        : node.ToJsonString();

      var property = EditableDynamicProperties(blockRef)
        .FirstOrDefault(p => string.Equals(p.PropertyName, name, StringComparison.OrdinalIgnoreCase));
      if (property == null)
      {
        missing.Add(name);
        continue;
      }

      var allowed = property.GetAllowedValues();
      object newValue;
      if (allowed != null && allowed.Length > 0)
      {
        var hasNumber = double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var number);
        var match = allowed.FirstOrDefault(a =>
          string.Equals(Convert.ToString(a, CultureInfo.InvariantCulture), raw, StringComparison.OrdinalIgnoreCase)
          || (hasNumber && a is double or short or int && Math.Abs(Convert.ToDouble(a, CultureInfo.InvariantCulture) - number) < 1e-9));
        if (match == null)
        {
          var options = string.Join(", ", allowed.Select(a => Convert.ToString(a, CultureInfo.InvariantCulture)));
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: '{raw}' is not an allowed value for {property.PropertyName}. Allowed: {options}.");
        }

        newValue = match;
      }
      else
      {
        try
        {
          newValue = property.Value switch
          {
            double => double.Parse(raw, NumberStyles.Float, CultureInfo.InvariantCulture),
            short => short.Parse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture),
            int => int.Parse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture),
            _ => raw,
          };
        }
        catch (FormatException)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: '{raw}' is not a valid value for {property.PropertyName}.");
        }
      }

      property.Value = newValue;
    }

    return missing;
  }

  private static List<string> SetAttributes(BlockReference blockRef, JsonObject values, Transaction transaction)
  {
    var pending = values
      .Where(pair => pair.Value != null)
      .ToDictionary(pair => pair.Key, pair => pair.Value!.GetValue<string>(), StringComparer.OrdinalIgnoreCase);

    foreach (ObjectId attributeId in blockRef.AttributeCollection)
    {
      if (transaction.GetObject(attributeId, OpenMode.ForWrite, false) is not AttributeReference attribute)
      {
        continue;
      }

      if (!pending.TryGetValue(attribute.Tag, out var value))
      {
        continue;
      }

      if (attribute.IsMTextAttribute)
      {
        var mtext = attribute.MTextAttribute;
        mtext.Contents = value;
        attribute.MTextAttribute = mtext;
        attribute.UpdateMTextAttribute();
      }
      else
      {
        attribute.TextString = value;
      }

      pending.Remove(attribute.Tag);
    }

    return pending.Keys.ToList();
  }

  /// <summary>
  /// Mirrors an entity across the vertical line x = mirrorX while keeping text
  /// readable (like MIRROR with MIRRTEXT = 0): text anchors are mirrored and
  /// left/right justification is swapped instead of reversing the characters.
  /// </summary>
  private static void MirrorReadable(Entity entity, double mirrorX, Transaction transaction)
  {
    var mirror = Matrix3d.Mirroring(new Line3d(new Point3d(mirrorX, 0, 0), new Point3d(mirrorX, 1, 0)));
    Point3d Mir(Point3d p) => new(2 * mirrorX - p.X, p.Y, p.Z);

    switch (entity)
    {
      case AttributeReference:
        // Owned by a block reference; handled with its block.
        return;

      case DBText text:
        var textState = TextState.Capture(text);
        textState.Apply(text, Mir);
        return;

      case MText mtext:
        mtext.Location = Mir(mtext.Location);
        mtext.Rotation = -mtext.Rotation;
        mtext.Attachment = SwapAttachment(mtext.Attachment);
        return;

      case BlockReference blockRef:
        var attributeStates = new List<(AttributeReference Attribute, TextState State)>();
        foreach (ObjectId attributeId in blockRef.AttributeCollection)
        {
          if (transaction.GetObject(attributeId, OpenMode.ForWrite, false) is AttributeReference attribute && !attribute.IsMTextAttribute)
          {
            attributeStates.Add((attribute, TextState.Capture(attribute)));
          }
        }

        blockRef.TransformBy(mirror);
        foreach (var (attribute, state) in attributeStates)
        {
          attribute.IsMirroredInX = false;
          attribute.IsMirroredInY = false;
          state.Apply(attribute, Mir);
        }
        return;

      case RotatedDimension rotated:
        rotated.XLine1Point = Mir(rotated.XLine1Point);
        rotated.XLine2Point = Mir(rotated.XLine2Point);
        rotated.DimLinePoint = Mir(rotated.DimLinePoint);
        rotated.Rotation = Math.PI - rotated.Rotation;
        if (!rotated.UsingDefaultTextPosition)
        {
          rotated.TextPosition = Mir(rotated.TextPosition);
        }
        rotated.RecomputeDimensionBlock(true);
        return;

      case AlignedDimension aligned:
        aligned.XLine1Point = Mir(aligned.XLine1Point);
        aligned.XLine2Point = Mir(aligned.XLine2Point);
        aligned.DimLinePoint = Mir(aligned.DimLinePoint);
        if (!aligned.UsingDefaultTextPosition)
        {
          aligned.TextPosition = Mir(aligned.TextPosition);
        }
        aligned.RecomputeDimensionBlock(true);
        return;

      case Dimension dimension:
        dimension.TransformBy(mirror);
        dimension.RecomputeDimensionBlock(true);
        return;

      default:
        entity.TransformBy(mirror);
        return;
    }
  }

  private sealed record TextState(Point3d Anchor, TextHorizontalMode Horizontal, TextVerticalMode Vertical, double Rotation)
  {
    public static TextState Capture(DBText text)
    {
      var usesPosition = text.HorizontalMode == TextHorizontalMode.TextLeft && text.VerticalMode == TextVerticalMode.TextBase;
      return new TextState(usesPosition ? text.Position : text.AlignmentPoint, text.HorizontalMode, text.VerticalMode, text.Rotation);
    }

    public void Apply(DBText text, Func<Point3d, Point3d> mirrorPoint)
    {
      var horizontal = Horizontal switch
      {
        TextHorizontalMode.TextLeft => TextHorizontalMode.TextRight,
        TextHorizontalMode.TextRight => TextHorizontalMode.TextLeft,
        _ => Horizontal,
      };

      var anchor = mirrorPoint(Anchor);
      text.IsMirroredInX = false;
      text.IsMirroredInY = false;
      text.Rotation = -Rotation;
      text.HorizontalMode = horizontal;
      text.VerticalMode = Vertical;

      if (horizontal == TextHorizontalMode.TextLeft && Vertical == TextVerticalMode.TextBase)
      {
        text.Position = anchor;
      }
      else
      {
        text.AlignmentPoint = anchor;
      }

      text.AdjustAlignment(text.Database);
    }
  }

  private static AttachmentPoint SwapAttachment(AttachmentPoint attachment) => attachment switch
  {
    AttachmentPoint.TopLeft => AttachmentPoint.TopRight,
    AttachmentPoint.TopRight => AttachmentPoint.TopLeft,
    AttachmentPoint.MiddleLeft => AttachmentPoint.MiddleRight,
    AttachmentPoint.MiddleRight => AttachmentPoint.MiddleLeft,
    AttachmentPoint.BottomLeft => AttachmentPoint.BottomRight,
    AttachmentPoint.BottomRight => AttachmentPoint.BottomLeft,
    _ => attachment,
  };

  private static void SetVertices(Entity entity, List<Point2d> vertices, int index)
  {
    if (vertices.Count < 2)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: vertices needs at least two points.");
    }

    switch (entity)
    {
      case Polyline polyline:
        for (var i = 0; i < vertices.Count; i++)
        {
          if (i < polyline.NumberOfVertices)
          {
            polyline.SetPointAt(i, vertices[i]);
          }
          else
          {
            polyline.AddVertexAt(i, vertices[i], 0, 0, 0);
          }
        }

        while (polyline.NumberOfVertices > vertices.Count)
        {
          polyline.RemoveVertexAt(polyline.NumberOfVertices - 1);
        }
        break;

      case Leader leader:
        var z = leader.NumVertices > 0 ? leader.VertexAt(0).Z : 0;
        for (var i = 0; i < vertices.Count; i++)
        {
          var point = new Point3d(vertices[i].X, vertices[i].Y, z);
          if (i < leader.NumVertices)
          {
            leader.SetVertexAt(i, point);
          }
          else
          {
            leader.AppendVertex(point);
          }
        }

        while (leader.NumVertices > vertices.Count)
        {
          leader.RemoveLastVertex();
        }
        break;

      case Line line:
        if (vertices.Count != 2)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: a line takes exactly two vertices.");
        }

        line.StartPoint = new Point3d(vertices[0].X, vertices[0].Y, line.StartPoint.Z);
        line.EndPoint = new Point3d(vertices[1].X, vertices[1].Y, line.EndPoint.Z);
        break;

      default:
        throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: vertices can be set on lines, polylines and leaders, not {TypeName(entity)}.");
    }
  }

  private static void SetDimensionPoints(Entity entity, Point2d? xLine1, Point2d? xLine2, Point2d? dimLine, int index)
  {
    static Point3d To3d(Point2d p, Point3d current) => new(p.X, p.Y, current.Z);

    switch (entity)
    {
      case RotatedDimension rotated:
        // A user-placed text position pins the dimension line to the text
        // (DIMTMOVE 0), which makes dimLine edits no-ops and stretches the
        // dimension back to the old text spot. Reset to the default position.
        rotated.UsingDefaultTextPosition = true;
        if (xLine1 is { } a) rotated.XLine1Point = To3d(a, rotated.XLine1Point);
        if (xLine2 is { } b) rotated.XLine2Point = To3d(b, rotated.XLine2Point);
        if (dimLine is { } c) rotated.DimLinePoint = To3d(c, rotated.DimLinePoint);
        rotated.RecomputeDimensionBlock(true);
        break;

      case AlignedDimension aligned:
        aligned.UsingDefaultTextPosition = true;
        if (xLine1 is { } d) aligned.XLine1Point = To3d(d, aligned.XLine1Point);
        if (xLine2 is { } e) aligned.XLine2Point = To3d(e, aligned.XLine2Point);
        if (dimLine is { } f) aligned.DimLinePoint = To3d(f, aligned.DimLinePoint);
        aligned.RecomputeDimensionBlock(true);
        break;

      default:
        throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Edit {index}: xLine1/xLine2/dimLine can only be set on linear (rotated or aligned) dimensions, not {TypeName(entity)}.");
    }
  }

  private static ObjectId GetLinetypeId(Database database, Transaction transaction, string name, int index)
  {
    var linetypes = (LinetypeTable)transaction.GetObject(database.LinetypeTableId, OpenMode.ForRead);
    if (linetypes.Has(name))
    {
      return linetypes[name];
    }

    throw new JsonRpcDispatchException("CIVIL3D.NOT_FOUND", $"Edit {index}: linetype '{name}' is not loaded in this drawing.");
  }

  private static Window? ReadWindow(JsonNode? node)
  {
    if (node is not JsonObject window)
    {
      return null;
    }

    var minX = window["minX"]?.GetValue<double>();
    var minY = window["minY"]?.GetValue<double>();
    var maxX = window["maxX"]?.GetValue<double>();
    var maxY = window["maxY"]?.GetValue<double>();
    if (minX == null || minY == null || maxX == null || maxY == null)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "window requires minX, minY, maxX and maxY.");
    }

    return new Window(
      Math.Min(minX.Value, maxX.Value),
      Math.Min(minY.Value, maxY.Value),
      Math.Max(minX.Value, maxX.Value),
      Math.Max(minY.Value, maxY.Value));
  }

  private static double NormalizeRadians(double radians)
  {
    var full = 2.0 * Math.PI;
    var value = radians % full;
    return value < 0 ? value + full : value;
  }

  private static Point2d? ReadPoint(JsonNode? node)
  {
    if (node is not JsonObject point)
    {
      return null;
    }

    var x = point["x"]?.GetValue<double>() ?? throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "Point is missing x.");
    var y = point["y"]?.GetValue<double>() ?? throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "Point is missing y.");
    return new Point2d(x, y);
  }

  private static List<string> ReadStringList(JsonNode? node)
  {
    var list = new List<string>();
    if (node is JsonArray array)
    {
      foreach (var item in array)
      {
        var value = item?.GetValue<string>();
        if (!string.IsNullOrWhiteSpace(value))
        {
          list.Add(value.Trim());
        }
      }
    }

    return list;
  }

  private static HashSet<string>? ReadStringSet(JsonNode? node)
  {
    var list = ReadStringList(node);
    return list.Count == 0 ? null : new HashSet<string>(list, StringComparer.OrdinalIgnoreCase);
  }

  private static double R(double value) => Math.Round(value, 4);

  private static Dictionary<string, object?> P(Point3d point) => new() { ["x"] = R(point.X), ["y"] = R(point.Y) };

  private static Dictionary<string, object?> P(Point2d point) => new() { ["x"] = R(point.X), ["y"] = R(point.Y) };
}
