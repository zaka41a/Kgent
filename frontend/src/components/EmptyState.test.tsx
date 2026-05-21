import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EmptyState from "./EmptyState";

describe("EmptyState", () => {
  it("renders the suggestion prompts", () => {
    render(<EmptyState onSuggest={() => {}} />);
    expect(screen.getByText(/how can i help/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /trace the path of a single user request/i }),
    ).toBeInTheDocument();
  });

  it("calls onSuggest with the picked prompt", async () => {
    const user = userEvent.setup();
    const onSuggest = vi.fn();
    render(<EmptyState onSuggest={onSuggest} />);

    await user.click(
      screen.getByRole("button", { name: /trace the path of a single user request/i }),
    );
    expect(onSuggest).toHaveBeenCalledWith(
      "Trace the path of a single user request through the system",
    );
  });
});
