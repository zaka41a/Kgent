import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InputBox from "./InputBox";

describe("InputBox", () => {
  it("calls onSubmit with the trimmed value and clears the field", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<InputBox onSubmit={onSubmit} />);

    const textarea = screen.getByPlaceholderText(/ask anything/i);
    await user.type(textarea, "   hello world   ");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(onSubmit).toHaveBeenCalledWith("hello world");
    expect(textarea).toHaveValue("");
  });

  it("submits on Enter and inserts a newline on Shift+Enter", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<InputBox onSubmit={onSubmit} />);

    const textarea = screen.getByPlaceholderText(/ask anything/i);
    await user.type(textarea, "line1{Shift>}{Enter}{/Shift}line2");
    expect(onSubmit).not.toHaveBeenCalled();
    expect(textarea).toHaveValue("line1\nline2");

    await user.type(textarea, "{Enter}");
    expect(onSubmit).toHaveBeenCalledWith("line1\nline2");
  });

  it("does not submit when the input is empty or only whitespace", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<InputBox onSubmit={onSubmit} />);

    const button = screen.getByRole("button", { name: /send/i });
    expect(button).toBeDisabled();

    await user.type(screen.getByPlaceholderText(/ask anything/i), "   ");
    expect(button).toBeDisabled();
    await user.keyboard("{Enter}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does not submit when disabled", () => {
    const onSubmit = vi.fn();
    render(<InputBox onSubmit={onSubmit} disabled />);

    const textarea = screen.getByPlaceholderText(/ask anything/i);
    expect(textarea).toBeDisabled();
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });
});
