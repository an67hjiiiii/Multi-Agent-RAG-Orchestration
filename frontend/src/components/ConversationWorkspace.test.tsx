import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ConversationWorkspace from "./ConversationWorkspace";

afterEach(() => cleanup());

describe("ConversationWorkspace", () => {
  it("renders the workspace shell, result slot, and question integration point", async () => {
    const onSubmitQuestion = vi.fn();
    render(
      <ConversationWorkspace
        userEmail="viet@example.com"
        result={<p>Result slot</p>}
        onSubmitQuestion={onSubmitQuestion}
      />,
    );

    expect(screen.getByRole("heading", { name: "Workspace" })).toBeTruthy();
    expect(screen.getByText("Result slot")).toBeTruthy();

    const question = screen.getByLabelText("Question");
    await userEvent.type(question, "What is in my corpus?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(onSubmitQuestion).toHaveBeenCalledWith("What is in my corpus?");
  });

  it("preserves the pending question and blocks duplicate submits while loading", async () => {
    let resolveRequest!: () => void;
    const onSubmitQuestion = vi.fn(() => new Promise<void>((resolve) => {
      resolveRequest = resolve;
    }));
    render(
      <ConversationWorkspace
        pendingQuestion="Saved question"
        onSubmitQuestion={onSubmitQuestion}
      />,
    );

    const question = screen.getByLabelText("Question");
    expect(question).toHaveProperty("value", "Saved question");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(onSubmitQuestion).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Sending…" })).toHaveProperty("disabled", true);
    expect(question).toHaveProperty("disabled", true);
    expect(screen.getByRole("status")).toHaveProperty("textContent", "Question pendingSaved question");

    resolveRequest();
    expect(await screen.findByRole("button", { name: "Send" })).toHaveProperty("disabled", false);
    expect(question).toHaveProperty("value", "Saved question");
  });
});
