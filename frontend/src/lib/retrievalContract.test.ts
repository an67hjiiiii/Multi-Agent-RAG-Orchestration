import { describe, expect, it } from "vitest";
import {
  createOwnerScopedRetrievalQuery,
  filterOwnerScopedSources,
  type SourceMetadataView,
} from "./retrievalContract";

describe("owner-scoped retrieval contract", () => {
  it("builds the shared query shape without a client owner identifier", () => {
    const query = createOwnerScopedRetrievalQuery({
      request: "  What is retained? ",
      taskId: " task-1 ",
      topK: 5,
      contextTokenLimit: 2048,
    });

    expect(query).toEqual({
      request: "What is retained?",
      task_id: "task-1",
      top_k: 5,
      context_token_limit: 2048,
    });
    expect(Object.keys(query)).not.toContain("owner_id");
  });

  it("rejects empty requests and invalid positive limits", () => {
    expect(() => createOwnerScopedRetrievalQuery({ request: "   " })).toThrow("request must not be empty");
    expect(() => createOwnerScopedRetrievalQuery({ request: "question", topK: 0 })).toThrow("topK");
    expect(() => createOwnerScopedRetrievalQuery({ request: "question", contextTokenLimit: 1.5 })).toThrow("contextTokenLimit");
  });

  it("filters only the already owner-scoped sources by metadata", () => {
    const sources: SourceMetadataView[] = [
      { sourceId: "source-a", sourceName: "Guide.md", sourceType: "knowledge", sourceFormat: "md" },
      { sourceId: "source-b", sourceName: "Notes.txt", sourceType: "knowledge", sourceFormat: "txt" },
      { sourceId: "source-c", sourceName: "Report.pdf", sourceType: "archive", sourceFormat: "pdf" },
    ];

    expect(filterOwnerScopedSources(sources, { sourceFormats: [" MD ", "pdf"] }).map((item) => item.sourceId))
      .toEqual(["source-a", "source-c"]);
    expect(filterOwnerScopedSources(sources, { sourceTypes: ["knowledge"], sourceIds: ["source-b"] }))
      .toEqual([sources[1]]);
  });
});
