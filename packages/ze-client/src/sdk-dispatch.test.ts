import { beforeEach, describe, expect, it, vi } from "vitest";

const { getNewsSettings } = vi.hoisted(() => ({
  getNewsSettings: vi.fn(),
}));

vi.mock("./generated/sdk.gen", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./generated/sdk.gen")>();
  return {
    ...actual,
    getNewsSettings,
  };
});

import { invokeSdkOperation, loadPluginOperation } from "./sdk-dispatch";

describe("sdk-dispatch", () => {
  beforeEach(() => {
    getNewsSettings.mockReset();
  });

  it("throws for unknown operation", async () => {
    await expect(invokeSdkOperation("missingOp")).rejects.toThrow("Unknown SDK operation");
  });

  it("returns PluginPageResponse from sdk function", async () => {
    getNewsSettings.mockResolvedValue({ data: { title: "News", tree: [] } });
    const result = await loadPluginOperation("getNewsSettings");
    expect(result).toEqual({ title: "News", tree: [] });
  });

  it("throws when sdk returns error", async () => {
    getNewsSettings.mockResolvedValue({ error: { message: "fail" } });
    await expect(invokeSdkOperation("getNewsSettings")).rejects.toThrow("SDK operation failed");
  });

  it("throws when response is not PluginPageResponse", async () => {
    getNewsSettings.mockResolvedValue({ data: { foo: "bar" } });
    await expect(loadPluginOperation("getNewsSettings")).rejects.toThrow(
      "did not return PluginPageResponse",
    );
  });
});
