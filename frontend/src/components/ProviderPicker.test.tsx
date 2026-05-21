import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProviderPicker from "./ProviderPicker";
import type { ProviderInfo } from "../lib/api";

const providers: ProviderInfo[] = [
  { name: "ollama", available: true, models: ["mistral", "llama3"] },
  { name: "openai", available: false, models: ["gpt-4o"] },
];

describe("ProviderPicker", () => {
  it("shows the current provider label and the selected model on the trigger", () => {
    render(
      <ProviderPicker
        providers={providers}
        selectedProvider="ollama"
        selectedModel="mistral"
        onChange={() => {}}
        onOpenSettings={() => {}}
      />,
    );
    expect(screen.getByText("Ollama")).toBeInTheDocument();
    expect(screen.getByText("mistral")).toBeInTheDocument();
  });

  it("opens the dropdown and calls onChange when picking a model from an available provider", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ProviderPicker
        providers={providers}
        selectedProvider="ollama"
        selectedModel="mistral"
        onChange={onChange}
        onOpenSettings={() => {}}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Ollama/i }));
    await user.click(screen.getByRole("button", { name: "llama3" }));
    expect(onChange).toHaveBeenCalledWith("ollama", "llama3");
  });

  it("flags an unavailable provider and disables its model buttons", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ProviderPicker
        providers={providers}
        selectedProvider="ollama"
        selectedModel="mistral"
        onChange={onChange}
        onOpenSettings={() => {}}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Ollama/i }));
    expect(screen.getByText(/no key/i)).toBeInTheDocument();
    const gpt = screen.getByRole("button", { name: "gpt-4o" });
    expect(gpt).toBeDisabled();
    await user.click(gpt);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("opens settings from the Manage API keys footer", async () => {
    const user = userEvent.setup();
    const onOpenSettings = vi.fn();
    render(
      <ProviderPicker
        providers={providers}
        selectedProvider="ollama"
        selectedModel="mistral"
        onChange={() => {}}
        onOpenSettings={onOpenSettings}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Ollama/i }));
    await user.click(screen.getByRole("button", { name: /manage api keys/i }));
    expect(onOpenSettings).toHaveBeenCalled();
  });
});
