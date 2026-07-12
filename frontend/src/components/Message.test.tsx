import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Message, { type ChatMessage } from "./Message";

const assistant = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  role: "assistant",
  content: "Hello there",
  ...overrides,
});

describe("Message", () => {

  it("renders markdown content for an assistant reply", () => {
    render(<Message message={assistant({ content: "**bold** word" })} />);
    expect(screen.getByText("bold").tagName).toBe("STRONG");
  });

  it("shows the typing dots when an assistant reply is pending without content", () => {
    const { container } = render(
      <Message message={assistant({ content: "", pending: true })} />,
    );
    expect(container.querySelector(".dot-pulse")).not.toBeNull();
  });

  it("renders an error message in the error color", () => {
    render(<Message message={assistant({ content: "boom", error: true })} />);
    const node = screen.getByText("boom");
    expect(node.className).toMatch(/text-red-400/);
  });

  it("copies the message content to the clipboard when Copy is clicked", async () => {
    const user = userEvent.setup();
    render(<Message message={assistant({ content: "answer" })} />);

    await user.click(screen.getByRole("button", { name: /^copy$/i }));
    const clipboard = await navigator.clipboard.readText();
    expect(clipboard).toBe("answer");
    expect(await screen.findByText(/copied/i)).toBeInTheDocument();
  });

  it("shows Regenerate only when both showRegenerate and onRegenerate are provided", async () => {
    const user = userEvent.setup();
    const onRegenerate = vi.fn();
    const { rerender } = render(
      <Message message={assistant()} showRegenerate onRegenerate={onRegenerate} />,
    );
    await user.click(screen.getByRole("button", { name: /regenerate/i }));
    expect(onRegenerate).toHaveBeenCalledOnce();

    rerender(<Message message={assistant()} onRegenerate={onRegenerate} />);
    expect(screen.queryByRole("button", { name: /regenerate/i })).toBeNull();
  });

  it("lists retrieved source chunks in a collapsible details block", () => {
    render(
      <Message
        message={assistant({
          context: [
            { doc_path: "graph.py", kind: "code", index: 0, text: "snippet text" },
          ],
        })}
      />,
    );
    expect(screen.getByText(/1 source\b/i)).toBeInTheDocument();
    expect(screen.getByText(/graph\.py/)).toBeInTheDocument();
    expect(screen.getByText(/snippet text/)).toBeInTheDocument();
  });

  it("does not show the action row for user messages", () => {
    render(<Message message={{ role: "user", content: "ping" }} />);
    expect(screen.queryByRole("button", { name: /^copy$/i })).toBeNull();
  });
});
