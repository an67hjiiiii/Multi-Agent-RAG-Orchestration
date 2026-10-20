import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AnswerCitationView } from "./AnswerCitationView";

afterEach(() => cleanup());

describe("AnswerCitationView", () => {
  it("shows a pending state while a run is processing", () => {
    render(<AnswerCitationView status="RUNNING" />);

    expect(screen.getByText("Processing", { exact: true })).toBeTruthy();
    expect(screen.getByText("Processing your question…")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Answer and citations" }).getAttribute("aria-busy")).toBe("true");
  });

  it("shows a completed answer with source and locator details", () => {
    render(
      <AnswerCitationView
        status="COMPLETED"
        answer="The source describes an owner-scoped retrieval boundary."
        citations={[{ id: "evidence-1", source: "contract.md", locator: "chunk-2" }]}
      />,
    );

    expect(screen.getByText("The source describes an owner-scoped retrieval boundary.")).toBeTruthy();
    expect(screen.getByText("evidence-1")).toBeTruthy();
    expect(screen.getByText("contract.md")).toBeTruthy();
    expect(screen.getByText("chunk-2")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Answer and citations" }).getAttribute("aria-busy")).toBe("false");
  });

  it("shows partial answers and missing information", () => {
    render(
      <AnswerCitationView
        status="PARTIAL"
        answer="The available evidence covers the first requirement."
        missingInformation={["The second requirement is not documented."]}
      />,
    );

    expect(screen.getByText("Partial", { exact: true })).toBeTruthy();
    expect(screen.getByText("Missing information")).toBeTruthy();
    expect(screen.getByText("The second requirement is not documented.")).toBeTruthy();
  });

  it("shows an explicit no-evidence state", () => {
    render(<AnswerCitationView status="NO_EVIDENCE" />);

    expect(screen.getByText("No evidence", { exact: true })).toBeTruthy();
    expect(screen.getByText("No evidence was found for this question.")).toBeTruthy();
  });

  it("shows the server error for a failed run", () => {
    render(<AnswerCitationView status="FAILED" error="The local worker is unavailable." />);

    expect(screen.getByText("Failed", { exact: true })).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("The local worker is unavailable.");
  });
});
