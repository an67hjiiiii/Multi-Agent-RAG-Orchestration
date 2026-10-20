import { describe, expect, it } from "vitest";
import {
  mapEvidencePackageCitations,
  mapEvidenceToCitations,
  resolveCitationIds,
} from "./evidenceCitation";

const evidence = [
  {
    evidence_id: "evidence-1",
    text: "First source chunk",
    provenance: { source_id: "source-a", chunk_id: "chunk-1", locator: "page:1" },
  },
  {
    evidence_id: "evidence-2",
    text: "Second source chunk",
    provenance: { source_id: "source-b", chunk_id: "chunk-4", locator: null },
  },
];

describe("evidence citation mapping", () => {
  it("maps EvidencePackage entries to source and locator projections", () => {
    expect(mapEvidencePackageCitations({ evidence })).toEqual([
      { citationId: "evidence-1", sourceId: "source-a", chunkId: "chunk-1", locator: "page:1" },
      { citationId: "evidence-2", sourceId: "source-b", chunkId: "chunk-4", locator: null },
    ]);
  });

  it("deduplicates citation IDs and ignores malformed provenance", () => {
    expect(mapEvidenceToCitations([
      ...evidence,
      { evidence_id: " evidence-1 ", text: "duplicate", provenance: { source_id: "source-c", chunk_id: "chunk-9" } },
      { evidence_id: "", text: "invalid", provenance: { source_id: "source-c", chunk_id: "chunk-9" } },
    ]).length).toBe(2);
  });

  it("separates valid locators from unknown citation IDs", () => {
    expect(resolveCitationIds(["evidence-2", "missing", "evidence-2"], evidence)).toEqual({
      valid: [{ citationId: "evidence-2", sourceId: "source-b", chunkId: "chunk-4", locator: null }],
      invalid: ["missing"],
    });
  });
});
