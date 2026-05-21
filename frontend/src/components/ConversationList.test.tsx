import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../lib/api", () => ({
  listConversations: vi.fn(),
  deleteConversation: vi.fn(),
}));

import ConversationList from "./ConversationList";
import { listConversations, deleteConversation } from "../lib/api";

const mockedList = vi.mocked(listConversations);
const mockedDelete = vi.mocked(deleteConversation);

beforeEach(() => {
  mockedList.mockReset();
  mockedDelete.mockReset();
});

const conv = (id: string, title: string) => ({
  id,
  title,
  repo_path: null,
  provider: null,
  model: null,
  created_at: "",
  updated_at: "",
});

describe("ConversationList", () => {
  it("renders the conversations returned by the API", async () => {
    mockedList.mockResolvedValueOnce([
      conv("a", "First chat"),
      conv("b", "Second chat"),
    ]);

    render(
      <ConversationList activeId="a" onSelect={() => {}} refreshKey={0} onError={() => {}} />,
    );

    expect(await screen.findByText("First chat")).toBeInTheDocument();
    expect(screen.getByText("Second chat")).toBeInTheDocument();
  });

  it("shows the empty placeholder when there is no history", async () => {
    mockedList.mockResolvedValueOnce([]);
    render(
      <ConversationList activeId={null} onSelect={() => {}} refreshKey={0} onError={() => {}} />,
    );
    expect(await screen.findByText(/no previous conversations/i)).toBeInTheDocument();
  });

  it("calls onError when the API rejects", async () => {
    mockedList.mockRejectedValueOnce(new Error("backend down"));
    const onError = vi.fn();
    render(
      <ConversationList activeId={null} onSelect={() => {}} refreshKey={0} onError={onError} />,
    );
    await waitFor(() => expect(onError).toHaveBeenCalledWith("backend down"));
  });

  it("removes a conversation from the list after the delete API succeeds", async () => {
    mockedList.mockResolvedValueOnce([
      conv("a", "Keep me"),
      conv("b", "Drop me"),
    ]);
    mockedDelete.mockResolvedValueOnce(undefined);

    const user = userEvent.setup();
    render(
      <ConversationList activeId="a" onSelect={() => {}} refreshKey={0} onError={() => {}} />,
    );

    await screen.findByText("Drop me");
    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    await user.click(deleteButtons[1]);

    await waitFor(() => expect(screen.queryByText("Drop me")).toBeNull());
    expect(mockedDelete).toHaveBeenCalledWith("b");
    expect(screen.getByText("Keep me")).toBeInTheDocument();
  });
});
