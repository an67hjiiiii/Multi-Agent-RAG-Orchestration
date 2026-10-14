import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ConversationWorkspace from "./ConversationWorkspace";

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
});
