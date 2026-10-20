/**
 * Citation mapping adapter for the shared Evidence/Provenance contract.
 * The generic input keeps the backend model authoritative: this module does
 * not redeclare EvidencePackage or create a second source of truth.
 */
export interface EvidenceCitationMapping {
  citationId: string;
  sourceId: string;
  chunkId: string;
  locator?: string | null;
}

type EvidenceWithProvenance = {
  evidence_id: string;
  provenance: {
    source_id: string;
    chunk_id: string;
    locator?: string | null;
  };
};

export interface CitationResolution {
  valid: EvidenceCitationMapping[];
  invalid: string[];
}

function toMapping(evidence: EvidenceWithProvenance): EvidenceCitationMapping | null {
  const citationId = evidence.evidence_id.trim();
  const sourceId = evidence.provenance.source_id.trim();
  const chunkId = evidence.provenance.chunk_id.trim();
  if (!citationId || !sourceId || !chunkId) return null;
  return {
    citationId,
    sourceId,
    chunkId,
    locator: evidence.provenance.locator?.trim() || null,
  };
}

/** Map an EvidencePackage.evidence collection to display-safe citation data. */
export function mapEvidenceToCitations<T extends EvidenceWithProvenance>(
  evidence: readonly T[],
): EvidenceCitationMapping[] {
  const seen = new Set<string>();
  const mappings: EvidenceCitationMapping[] = [];
  for (const item of evidence) {
    const mapping = toMapping(item);
    if (!mapping || seen.has(mapping.citationId)) continue;
    seen.add(mapping.citationId);
    mappings.push(mapping);
  }
  return mappings;
}

export function mapEvidencePackageCitations<T extends EvidenceWithProvenance>(
  evidencePackage: { evidence: readonly T[] },
): EvidenceCitationMapping[] {
  return mapEvidenceToCitations(evidencePackage.evidence);
}

/** Keep valid citation locators and expose unknown IDs as an explicit warning. */
export function resolveCitationIds<T extends EvidenceWithProvenance>(
  citationIds: readonly string[],
  evidence: readonly T[],
): CitationResolution {
  const mappings = mapEvidenceToCitations(evidence);
  const byId = new Map(mappings.map((mapping) => [mapping.citationId, mapping]));
  const valid: EvidenceCitationMapping[] = [];
  const invalid: string[] = [];
  const seen = new Set<string>();

  for (const rawId of citationIds) {
    const id = rawId.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    const mapping = byId.get(id);
    if (mapping) valid.push(mapping);
    else invalid.push(id);
  }
  return { valid, invalid };
}
