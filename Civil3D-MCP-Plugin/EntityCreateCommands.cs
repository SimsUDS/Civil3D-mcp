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
/// definitions can be imported from a source DWG (blockSource).
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

        if (entity is BlockReference blockRef)
        {
          FinishInsert(blockRef, item, transaction, index, warnings);
        }

        created.Add(new Dictionary<string, object?>
        {
          ["index"] = index,
          ["id"] = item["id"]?.GetValue<string>(),
          ["type"] = type == "block" ? "insert" : type,
          ["handle"] = entity.Handle.ToString(),
          ["layer"] = entity.Layer,
        });
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
  /// Imports block definitions that the batch inserts but this drawing lacks,
  /// from blockSource (a .dwg inside the configured import roots). Existing
  /// definitions are never overwritten.
  /// </summary>
  private static List<string> EnsureBlockDefinitions(Database database, Transaction transaction, JsonArray items, string? blockSource)
  {
    var wanted = items
      .OfType<JsonObject>()
      .Where(item => (item["type"]?.GetValue<string>() ?? "").Trim().ToLowerInvariant() is "insert" or "block")
      .Select(item => item["blockName"]?.GetValue<string>())
      .Where(name => !string.IsNullOrWhiteSpace(name))
      .Select(name => name!)
      .Distinct(StringComparer.OrdinalIgnoreCase)
      .ToList();

    var blockTable = (BlockTable)transaction.GetObject(database.BlockTableId, OpenMode.ForRead);
    var missing = wanted.Where(name => !blockTable.Has(name)).ToList();
    if (missing.Count == 0 || string.IsNullOrWhiteSpace(blockSource))
    {
      return new List<string>();
    }

    var path = FileBoundary.ResolveImportPath(blockSource, ".dwg");
    var imported = new List<string>();
    using var source = new Database(false, true);
    source.ReadDwgFile(path, FileOpenMode.OpenForReadAndAllShare, true, "");
    var ids = new ObjectIdCollection();
    using (var sourceTransaction = source.TransactionManager.StartTransaction())
    {
      var sourceTable = (BlockTable)sourceTransaction.GetObject(source.BlockTableId, OpenMode.ForRead);
      foreach (var name in missing)
      {
        if (sourceTable.Has(name))
        {
          ids.Add(sourceTable[name]);
          imported.Add(name);
        }
      }

      sourceTransaction.Commit();
    }

    if (ids.Count > 0)
    {
      var mapping = new IdMapping();
      source.WblockCloneObjects(ids, database.BlockTableId, mapping, DuplicateRecordCloning.Ignore, false);
    }

    return imported;
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
