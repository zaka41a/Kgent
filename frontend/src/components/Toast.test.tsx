import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ToastContainer from "./Toast";

describe("ToastContainer", () => {
  it("renders each toast message", () => {
    render(
      <ToastContainer
        toasts={[{ id: 1, kind: "success", message: "Settings saved" }]}
        onDismiss={() => {}}
      />,
    );
    expect(screen.getByText("Settings saved")).toBeInTheDocument();
  });

  it("renders nothing when there are no toasts", () => {
    const { container } = render(
      <ToastContainer toasts={[]} onDismiss={() => {}} />,
    );
    expect(container.querySelectorAll("div").length).toBe(1);
  });
});
