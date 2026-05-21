import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../lib/api", () => ({
  listConversations: vi.fn().mockResolvedValue([]),
  deleteConversation: vi.fn(),
}));

import Sidebar from "./Sidebar";
import type { StoreInfo } from "../lib/api";

const info: StoreInfo = {
  count: 598,
  store_path: "/x",
  store_kind: "ChromaStore",
  default_provider: "ollama",
  default_model: "mistral",
  active_repo: "/Users/me/Projects/StoreZ",
  document_count: 130,
  has_graph: false,
};

const baseProps = {
  info,
  activeConvId: null,
  conversationsRefresh: 0,
  onSelectConversation: () => {},
  onNewChat: () => {},
  onOpenSettings: () => {},
  onOpenIngest: () => {},
  onError: () => {},
};

describe("Sidebar", () => {
  it("shows the active repo, document and chunk counts, and the default model", () => {
    render(<Sidebar {...baseProps} />);
    expect(screen.getByText(/Projects\/StoreZ/)).toBeInTheDocument();
    expect(screen.getByText(/130 documents/)).toBeInTheDocument();
    expect(screen.getByText(/598 chunks/)).toBeInTheDocument();
    expect(screen.getByText("mistral")).toBeInTheDocument();
    expect(screen.getByText("ChromaStore")).toBeInTheDocument();
  });

  it("falls back to a placeholder when no repository is indexed", () => {
    render(<Sidebar {...baseProps} info={{ ...info, active_repo: null, document_count: 0 }} />);
    expect(screen.getByText(/no repository indexed/i)).toBeInTheDocument();
  });

  it("shows the graph badge only when has_graph is true", () => {
    const { rerender } = render(<Sidebar {...baseProps} />);
    expect(screen.queryByText(/\+ graph/)).toBeNull();
    rerender(<Sidebar {...baseProps} info={{ ...info, has_graph: true }} />);
    expect(screen.getByText(/\+ graph/)).toBeInTheDocument();
  });

  it("wires the New chat, Add repository and Settings buttons", async () => {
    const user = userEvent.setup();
    const onNewChat = vi.fn();
    const onOpenIngest = vi.fn();
    const onOpenSettings = vi.fn();
    render(
      <Sidebar
        {...baseProps}
        onNewChat={onNewChat}
        onOpenIngest={onOpenIngest}
        onOpenSettings={onOpenSettings}
      />,
    );
    await user.click(screen.getByRole("button", { name: /new chat/i }));
    await user.click(screen.getByRole("button", { name: /add repository/i }));
    await user.click(screen.getByRole("button", { name: /settings/i }));
    expect(onNewChat).toHaveBeenCalledOnce();
    expect(onOpenIngest).toHaveBeenCalledOnce();
    expect(onOpenSettings).toHaveBeenCalledOnce();
  });
});
