import { describe, it, expect, beforeEach } from "vitest";
import {
  loadTheme,
  saveTheme,
  loadSidebarOpen,
  saveSidebarOpen,
  loadSelection,
  saveSelection,
  loadActiveConv,
  saveActiveConv,
} from "./storage";

describe("theme storage", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to dark when nothing is stored", () => {
    expect(loadTheme()).toBe("dark");
  });

  it("round-trips a saved theme", () => {
    saveTheme("light");
    expect(loadTheme()).toBe("light");
  });
});

describe("sidebar storage", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to open", () => {
    expect(loadSidebarOpen()).toBe(true);
  });

  it("round-trips the collapsed state", () => {
    saveSidebarOpen(false);
    expect(loadSidebarOpen()).toBe(false);
  });
});

describe("provider selection storage", () => {
  beforeEach(() => localStorage.clear());

  it("returns null when nothing is stored", () => {
    expect(loadSelection()).toBeNull();
  });

  it("round-trips a provider selection", () => {
    saveSelection({ provider: "ollama", model: "mistral" });
    expect(loadSelection()).toEqual({ provider: "ollama", model: "mistral" });
  });
});

describe("active conversation storage", () => {
  beforeEach(() => localStorage.clear());

  it("returns null when nothing is stored", () => {
    expect(loadActiveConv()).toBeNull();
  });

  it("round-trips an active conversation id", () => {
    saveActiveConv("conv-123");
    expect(loadActiveConv()).toBe("conv-123");
  });

  it("clears the stored id when saving null", () => {
    saveActiveConv("conv-123");
    saveActiveConv(null);
    expect(loadActiveConv()).toBeNull();
  });
});
