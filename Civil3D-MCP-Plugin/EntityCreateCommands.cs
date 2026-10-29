using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using System.Text.Json.Nodes;

namespace Civil3DMcpPlugin;

/// <summary>
/// createEntities: draws new entities in one transaction, so a whole batch
/// (hundreds of blocks and polylines) runs as one call and one approval.
/// Item types: insert (block reference, with rotation, scale, dynamic
/// properties and attributes), polyline (per-vertex bulge for true arcs),
/// circle, arc, line and text. Missing layers are created. Missing block
/// definitions are imported from blockSource: a .dwg, or a folder of
/// one-block drawings named after the blocks.
/// </summary>
public static partial class EntityCommands
{
  public static Task<object?> CreateEntitiesAsync(JsonObject? parameters)
  {
    if (PluginRuntime.GetParameter(parameters, "creates") is not JsonArray items || items.Count == 0)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", "createEntities requires a non-empty creates array.");
    }

    var blockSource = PluginRuntime.GetOptionalString(parameters, "blockSource");
    var defaultSpace = PluginRuntime.GetOptionalString(parameters, "space");

    return CivilExecution.WriteAsync<object?>((doc, civilDoc, database, transaction) =>
    {
      var imported = EnsureBlockDefinitions(database, transaction, items, blockSource);
      var created = new List<Dictionary<string, object?>>();
      var warnings = new List<string>();
      var progress = new DrawProgress(doc, "create", items.Count);
      var spaces = new Dictionary<string, SpaceInfo>(StringComparer.OrdinalIgnoreCase);

      for (var index = 0; index < items.Count; index++)
      {
        progress.BeforePiece(index);
        if (items[index] is not JsonObject item)
        {
          throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Create {index}: must be an object.");
        }

        var spaceName = item["space"]?.GetValue<string>() ?? defaultSpace ?? "model";
        if (!spaces.TryGetValue(spaceName, out var space))
        {
          space = ResolveSpace(database, transaction, spaceName, OpenMode.ForWrite);
          spaces[spaceName] = space;
        }

        var type = (item["type"]?.GetValue<string>() ?? "").Trim().ToLowerInvariant();
        Entity entity = type switch
        {
          "insert" or "block" => MakeInsert(database, transaction, item, index),
          "polyline" => MakePolyline(item, index),
          "circle" => new Circle(P3(RequirePoint(item, "center", index)), Vector3d.ZAxis, RequirePositive(item, "radius", index)),
          "arc" => new Arc(
            P3(RequirePoint(item, "center", index)),
            RequirePositive(item, "radius", index),
            Deg(item, "startAngleDeg", index),
            Deg(item, "endAngleDeg", index)),
          "line" => new Line(P3(RequirePoint(item, "start", index)), P3(RequirePoint(item, "end", index))),
          "text" => MakeText(item, index),
          _ => throw new JsonRpcDispatchException(
            "CIVIL3D.INVALID_INPUT",
            $"Create {index}: type must be insert, polyline, circle, arc, line or text (got '{type}')."),
        };

        var layer = item["layer"]?.GetValue<string>();
        if (!string.IsNullOrWhiteSpace(layer))
        {
          entity.LayerId = AcadCommands.EnsureLayer(database, transaction, layer.Trim());
        }

        if (item["colorIndex"] is JsonNode colorNode)
        {
          entity.ColorIndex = colorNode.GetValue<int>();
        }

        var linetype = item["linetype"]?.GetValue<string>();
        if (!string.IsNullOrWhiteSpace(linetype))
        {
          entity.LinetypeId = GetLinetypeId(database, transaction, linetype, index);
        }

        space.Record.AppendEntity(entity);
        transaction.AddNewlyCreatedDBObject(entity, true);

        List<string>? pieces = null;
        if (entity is BlockReference blockRef)
        {
          FinishInsert(blockRef, item, transaction, index, warnings);
          if (item["explode"]?.GetValue<bool>() == true)
          {
            pieces = ExplodeInsert(blockRef, item, space.Record, transaction, index, warnings);
          }
        }

        var entry = new Dictionary<string, object?>
        {
          ["index"] = index,
          ["id"] = item["id"]?.GetValue<string>(),
          ["type"] = type == "block" ? "insert" : type,
          ["handle"] = pieces is { Count: > 0 } ? pieces[0] : entity.Handle.ToString(),
          ["layer"] = entity.Layer,
        };
        if (pieces is not null)
        {
          entry["pieceHandles"] = pieces;
        }

        created.Add(entry);
      }

      return new Dictionary<string, object?>
      {
        ["created"] = created,
        ["count"] = created.Count,
        ["importedBlocks"] = imported,
        ["warnings"] = warnings,
      };
    });
  }

  private static BlockReference MakeInsert(Database database, Transaction transaction, JsonObject item, int index)
  {
    var name = item["blockName"]?.GetValue<string>();
    if (string.IsNullOrWhiteSpace(name))
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Create {index}: insert needs blockName.");
    }

    var blockTable = (BlockTable)transaction.GetObject(database.BlockTableId, OpenMode.ForRead);
    if (!blockTable.Has(name))
    {
      throw new JsonRpcDispatchException(
        "CIVIL3D.OBJECT_NOT_FOUND",
        $"Create {index}: block '{name}' is not defined in this drawing. Pass blockSource (a .dwg that has it) to import it.");
    }

    var position = RequirePoint(item, "position", index);
    var blockRef = new BlockReference(P3(position), blockTable[name])
    {
      Rotation = (item["rotationDeg"]?.GetValue<double>() ?? 0.0) * Math.PI / 180.0,
    };

    var scale = item["scale"]?.GetValue<double>() ?? 1.0;
    if (scale <= 0)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Create {index}: scale must be positive.");
    }

    blockRef.ScaleFactors = new Scale3d(scale);
    return blockRef;
  }

  /// <summary>
  /// After the reference is in the drawing: add attribute references from the
  /// definition (constant ones excluded), then apply dynamic properties, then
  /// attribute values, like the edit action does.
  /// </summary>
  private static void FinishInsert(BlockReference blockRef, JsonObject item, Transaction transaction, int index, List<string> warnings)
  {
    var definition = (BlockTableRecord)transaction.GetObject(blockRef.BlockTableRecord, OpenMode.ForRead);
    if (definition.HasAttributeDefinitions)
    {
      foreach (var id in definition)
      {
        if (transaction.GetObject(id, OpenMode.ForRead) is not AttributeDefinition attDef || attDef.Constant)
        {
          continue;
        }

        var attRef = new AttributeReference();
        attRef.SetAttributeFromBlock(attDef, blockRef.BlockTransform);
        attRef.TextString = attDef.TextString;
        blockRef.AttributeCollection.AppendAttribute(attRef);
        transaction.AddNewlyCreatedDBObject(attRef, true);
      }
    }

    if (item["dynamicProperties"] is JsonObject dynamic && dynamic.Count > 0)
    {
      if (!blockRef.IsDynamicBlock)
      {
        warnings.Add($"Create {index}: block '{item["blockName"]}' is not dynamic; dynamicProperties ignored.");
      }
      else
      {
        foreach (var name in SetDynamicProperties(blockRef, dynamic, index))
        {
          warnings.Add($"Create {index}: dynamic property '{name}' not found.");
        }
      }
    }

    if (item["attributes"] is JsonObject attributes && attributes.Count > 0)
    {
      foreach (var tag in SetAttributes(blockRef, attributes, transaction))
      {
        warnings.Add($"Create {index}: attribute '{tag}' not found.");
      }
    }
  }

  /// <summary>
  /// Explodes a just-inserted block into its pieces (like EXPLODE; attribute
  /// definitions are dropped). Pieces on layer 0 take the insert's layer and
  /// ByBlock color becomes ByLayer, like BURST. With clipLength, every piece is
  /// trimmed at that distance from the insertion point along the insert's
  /// rotation: lines and straight polyline segments are cut there, other pieces
  /// whose middle lies past it are dropped. The reference itself is erased.
  /// </summary>
  private static List<string> ExplodeInsert(
    BlockReference blockRef, JsonObject item, BlockTableRecord space, Transaction transaction, int index, List<string> warnings)
  {
    double? clip = item["clipLength"]?.GetValue<double>();
    if (clip is <= 0)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Create {index}: clipLength must be positive.");
    }

    var origin = blockRef.Position;
    var along = new Vector3d(Math.Cos(blockRef.Rotation), Math.Sin(blockRef.Rotation), 0);
    double X(Point3d point) => (point - origin).DotProduct(along);

    var parts = new DBObjectCollection();
    blockRef.Explode(parts);
    var handles = new List<string>();
    var cutArcs = false;
    foreach (DBObject part in parts)
    {
      if (part is not Entity piece || part is AttributeDefinition)
      {
        part.Dispose();
        continue;
      }

      var keep = clip is double length ? ClipPiece(piece, X, length, ref cutArcs) : piece;
      if (keep is null)
      {
        piece.Dispose();
        continue;
      }

      if (string.Equals(piece.Layer, "0", StringComparison.OrdinalIgnoreCase))
      {
        keep.LayerId = blockRef.LayerId;
      }

      if (keep.ColorIndex == 0)
      {
        keep.ColorIndex = 256;
      }

      space.AppendEntity(keep);
      transaction.AddNewlyCreatedDBObject(keep, true);
      handles.Add(keep.Handle.ToString());
      if (!ReferenceEquals(keep, piece))
      {
        piece.Dispose();
      }
    }

    blockRef.Erase();
    if (cutArcs)
    {
      warnings.Add($"Create {index}: clipLength cut through a polyline arc segment; that segment was ended with a straight line.");
    }

    return handles;
  }

  private static Entity? ClipPiece(Entity piece, Func<Point3d, double> x, double length, ref bool cutArcs)
  {
    switch (piece)
    {
      case Line line:
      {
        var a = x(line.StartPoint);
        var b = x(line.EndPoint);
        if (a > length && b > length)
        {
          return null;
        }

        if (a <= length && b <= length)
        {
          return line;
        }

        var cut = line.StartPoint + (line.EndPoint - line.StartPoint) * ((length - a) / (b - a));
        if (a > length)
        {
          line.StartPoint = cut;
        }
        else
        {
          line.EndPoint = cut;
        }

        return line;
      }

      case Polyline polyline:
        return ClipPolyline(polyline, x, length, ref cutArcs);

      default:
      {
        try
        {
          var bounds = piece.GeometricExtents;
          var middle = bounds.MinPoint + (bounds.MaxPoint - bounds.MinPoint) * 0.5;
          return x(middle) > length ? null : piece;
        }
        catch (Autodesk.AutoCAD.Runtime.Exception)
        {
          return piece;
        }
      }
    }
  }

  /// <summary>Keeps the first run of the polyline that lies at or before the cut, ending exactly on it.</summary>
  private static Polyline? ClipPolyline(Polyline polyline, Func<Point3d, double> x, double length, ref bool cutArcs)
  {
    var count = polyline.NumberOfVertices;
    if (polyline.Closed)
    {
      return x(polyline.GeometricExtents.MaxPoint) <= length ? polyline : null;
    }

    var result = new Polyline();
    var k = 0;
    var started = false;
    for (var i = 0; i < count; i++)
    {
      var p = polyline.GetPoint3dAt(i);
      var xp = x(p);
      var inside = xp <= length;
      var bulge = i < count - 1 ? polyline.GetBulgeAt(i) : 0.0;
      if (inside)
      {
        result.AddVertexAt(k++, new Point2d(p.X, p.Y), bulge, polyline.GetStartWidthAt(i), polyline.GetEndWidthAt(i));
        started = true;
      }

      if (i == count - 1)
      {
        break;
      }

      var q = polyline.GetPoint3dAt(i + 1);
      var xq = x(q);
      if (inside == (xq <= length))
      {
        continue;
      }

      if (Math.Abs(bulge) > 1e-9)
      {
        cutArcs = true;
      }

      var c = p + (q - p) * ((length - xp) / (xq - xp));
      if (inside)
      {
        result.SetBulgeAt(k - 1, 0);
        result.AddVertexAt(k++, new Point2d(c.X, c.Y), 0, 0, 0);
        break;
      }

      if (!started)
      {
        result.AddVertexAt(k++, new Point2d(c.X, c.Y), 0, 0, 0);
        started = true;
      }
    }

    if (result.NumberOfVertices < 2)
    {
      result.Dispose();
      return null;
    }

    result.SetPropertiesFrom(polyline);
    result.Elevation = polyline.Elevation;
    result.Normal = polyline.Normal;
    return result;
  }

  private static Polyline MakePolyline(JsonObject item, int index)
  {
    if (item["points"] is not JsonArray points || points.Count < 2)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Create {index}: polyline needs at least 2 points.");
    }

    var polyline = new Polyline();
    for (var i = 0; i < points.Count; i++)
    {
      var point = ReadPoint(points[i]) ?? throw new JsonRpcDispatchException(
        "CIVIL3D.INVALID_INPUT", $"Create {index}: points[{i}] needs numeric x and y.");
      // Bulge of the segment that STARTS at this vertex: tan(sweep/4), positive = counterclockwise.
      var bulge = points[i]?["bulge"]?.GetValue<double>() ?? 0.0;
      polyline.AddVertexAt(i, point, bulge, 0, 0);
    }

    polyline.Closed = item["closed"]?.GetValue<bool>() ?? false;
    return polyline;
  }

  private static DBText MakeText(JsonObject item, int index)
  {
    var value = item["text"]?.GetValue<string>();
    if (string.IsNullOrEmpty(value))
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Create {index}: text needs text.");
    }

    return new DBText
    {
      Position = P3(RequirePoint(item, "position", index)),
      TextString = value,
      Height = item["height"]?.GetValue<double>() ?? 1.0,
      Rotation = (item["rotationDeg"]?.GetValue<double>() ?? 0.0) * Math.PI / 180.0,
    };
  }

  /// <summary>
  /// Makes sure every block the batch inserts is defined before anything is
  /// drawn. Missing definitions come from blockSource, which is either:
  /// - a .dwg that holds the blocks as definitions (e.g. a finished drawing or
  ///   a symbols library), or a one-block file named after the block; or
  /// - a folder of one-block drawings (e.g. "C:\civ3dmcp\TOPO LW"): block
  ///   NAME comes from "NAME.dwg" in that folder.
  /// A one-block file is inserted as a whole drawing, like INSERT with a file.
  /// Existing definitions are never overwritten. Every path is checked against
  /// the import roots. Fails before drawing anything if a block is still missing.
  /// </summary>
  private static List<string> EnsureBlockDefinitions(Database database, Transaction transaction, JsonArray items, string? blockSource)
  {
    var wanted = items
      .OfType<JsonObject>()
      .Where(item => (item["type"]?.GetValue<string>() ?? "").Trim().ToLowerInvariant() is "insert" or "block")
      .Select(item => item["blockName"]?.GetValue<string>())
      .Where(name => !string.IsNullOrWhiteSpace(name))
      .Select(name => name!.Trim())
      .Distinct(StringComparer.OrdinalIgnoreCase)
      .ToList();

    var blockTable = (BlockTable)transaction.GetObject(database.BlockTableId, OpenMode.ForRead);
    var missing = wanted.Where(name => !blockTable.Has(name)).ToList();
    var imported = new List<string>();
    if (missing.Count == 0)
    {
      return imported;
    }

    if (string.IsNullOrWhiteSpace(blockSource))
    {
      throw new JsonRpcDispatchException(
        "CIVIL3D.OBJECT_NOT_FOUND",
        $"Blocks not defined in this drawing: {string.Join(", ", missing)}. Pass blockSource (a .dwg or a folder of block .dwg files) to import them.");
    }

    var isFile = string.Equals(Path.GetExtension(blockSource.Trim()), ".dwg", StringComparison.OrdinalIgnoreCase);
    var stillMissing = new List<string>();

    if (isFile)
    {
      var path = FileBoundary.ResolveImportPath(blockSource.Trim(), ".dwg");
      var fileName = Path.GetFileNameWithoutExtension(path);
      using var source = OpenSource(path);
      var fromTable = CloneDefinitions(database, source, missing);
      imported.AddRange(fromTable);
      foreach (var name in missing.Where(name => !fromTable.Contains(name, StringComparer.OrdinalIgnoreCase)))
      {
        if (string.Equals(name, fileName, StringComparison.OrdinalIgnoreCase))
        {
          database.Insert(name, source, true);
          imported.Add($"{name} (file)");
        }
        else
        {
          stillMissing.Add(name);
        }
      }
    }
    else
    {
      var folder = blockSource.Trim().TrimEnd('\\', '/');
      var invalid = Path.GetInvalidFileNameChars();
      foreach (var name in missing)
      {
        if (name.IndexOfAny(invalid) >= 0)
        {
          stillMissing.Add(name);
          continue;
        }

        string path;
        try
        {
          path = FileBoundary.ResolveImportPath(Path.Combine(folder, name + ".dwg"), ".dwg");
        }
        catch (JsonRpcDispatchException error) when (error.Code == "CIVIL3D.OBJECT_NOT_FOUND")
        {
          stillMissing.Add(name);
          continue;
        }

        using var source = OpenSource(path);
        if (CloneDefinitions(database, source, new List<string> { name }).Count == 1)
        {
          imported.Add(name);
        }
        else
        {
          database.Insert(name, source, true);
          imported.Add($"{name} (file)");
        }
      }
    }

    if (stillMissing.Count > 0)
    {
      throw new JsonRpcDispatchException(
        "CIVIL3D.OBJECT_NOT_FOUND",
        $"Blocks not found in this drawing or in blockSource '{blockSource}': {string.Join(", ", stillMissing)}." +
        (isFile ? "" : " Each needs a file named <block name>.dwg in that folder."));
    }

    return imported;
  }

  private static Database OpenSource(string path)
  {
    var source = new Database(false, true);
    try
    {
      source.ReadDwgFile(path, FileOpenMode.OpenForReadAndAllShare, true, "");
      source.CloseInput(true);
      return source;
    }
    catch
    {
      source.Dispose();
      throw;
    }
  }

  /// <summary>Copies the named definitions that the source's block table has; returns the names copied.</summary>
  private static List<string> CloneDefinitions(Database database, Database source, List<string> names)
  {
    var ids = new ObjectIdCollection();
    var found = new List<string>();
    using (var sourceTransaction = source.TransactionManager.StartTransaction())
    {
      var sourceTable = (BlockTable)sourceTransaction.GetObject(source.BlockTableId, OpenMode.ForRead);
      foreach (var name in names)
      {
        if (sourceTable.Has(name))
        {
          ids.Add(sourceTable[name]);
          found.Add(name);
        }
      }

      sourceTransaction.Commit();
    }

    if (ids.Count > 0)
    {
      source.WblockCloneObjects(ids, database.BlockTableId, new IdMapping(), DuplicateRecordCloning.Ignore, false);
    }

    return found;
  }

  private static Point2d RequirePoint(JsonObject item, string name, int index) =>
    ReadPoint(item[name]) ?? throw new JsonRpcDispatchException(
      "CIVIL3D.INVALID_INPUT", $"Create {index}: {name} needs numeric x and y.");

  private static double RequirePositive(JsonObject item, string name, int index)
  {
    var value = item[name]?.GetValue<double>();
    if (value is not > 0)
    {
      throw new JsonRpcDispatchException("CIVIL3D.INVALID_INPUT", $"Create {index}: {name} must be a positive number.");
    }

    return value.Value;
  }

  private static double Deg(JsonObject item, string name, int index)
  {
    var value = item[name]?.GetValue<double>() ?? throw new JsonRpcDispatchException(
      "CIVIL3D.INVALID_INPUT", $"Create {index}: {name} is required.");
    return value * Math.PI / 180.0;
  }

  private static Point3d P3(Point2d point) => new(point.X, point.Y, 0);
}
