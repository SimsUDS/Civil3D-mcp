import { afterEach, describe, expect, it } from "vitest";
import { getPinnedDrawing, setPinnedDrawing, withPinnedDrawing } from "../src/utils/ConnectionManager.js";
import { DRAWING_RUNTIME_DOMAIN_DEFINITION } from "../src/tools/domains/drawingRuntimeDomain.js";
import { hasApprovalRisk } from "../src/tools/approvalPolicy.js";

const PIN = "C:\\jobs\\TD2558860\\TD2558860 OH Template 2024.dwg";

describe("drawing pin", () => {
  afterEach(() => setPinnedDrawing(null));

  it("leaves requests alone while unpinned", () => {
    expect(getPinnedDrawing()).toBeNull();
    expect(withPinnedDrawing("applyEntityJob", { jobFile: "x.json" })).toEqual({ jobFile: "x.json" });
  });

  it("binds every request to the pinned drawing", () => {
    setPinnedDrawing(PIN);
    expect(withPinnedDrawing("applyEntityJob", { jobFile: "x.json" })).toEqual({ jobFile: "x.json", expectDrawing: PIN });
    expect(withPinnedDrawing("getDrawingInfo", undefined)).toEqual({ expectDrawing: PIN });
  });

  it("never binds health, the document list, the switch or a new drawing", () => {
    setPinnedDrawing(PIN);
    for (const command of ["getCivil3DHealth", "listDocuments", "activateDocument", "newDrawing"]) {
      expect(withPinnedDrawing(command, { a: 1 })).toEqual({ a: 1 });
    }
  });

  it("keeps an explicit expectDrawing", () => {
    setPinnedDrawing(PIN);
    expect(withPinnedDrawing("queryEntities", { expectDrawing: "other.dwg" })).toEqual({ expectDrawing: "other.dwg" });
  });

  it("unpin clears the pin", async () => {
    setPinnedDrawing(PIN);
    const result = await DRAWING_RUNTIME_DOMAIN_DEFINITION.actions.unpin.execute({ action: "unpin" } as never);
    expect(result).toEqual({ unpinned: PIN, pinned: null });
    expect(getPinnedDrawing()).toBeNull();
  });
});

describe("document actions", () => {
  const { actions } = DRAWING_RUNTIME_DOMAIN_DEFINITION;

  it("activate requires a drawing name", () => {
    expect(actions.activate.inputSchema.safeParse({ action: "activate" }).success).toBe(false);
    expect(actions.activate.inputSchema.safeParse({ action: "activate", drawing: "TD2558860" }).success).toBe(true);
  });

  it("switching tabs and listing them need no approval token", () => {
    for (const name of ["activate", "list_documents", "unpin"] as const) {
      const a = actions[name];
      expect(hasApprovalRisk({ action: a.action, capabilities: a.capabilities, safeForRetry: a.safeForRetry } as never)).toBe(false);
    }
  });
});
