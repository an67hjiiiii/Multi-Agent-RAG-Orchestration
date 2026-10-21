/**
 * Frontend boundary for the shared RetrievalQuery contract.
 *
 * Ownership is resolved by the authenticated server session. There is
 * deliberately no owner id in this request or in the metadata projection.
 * Source metadata is filtered only after it has been returned in that
 * owner-scoped context; this module does not invent a retrieval endpoint.
 */
export interface OwnerScopedRetrievalQuery {
  request: string;
  task_id?: string;
  top_k?: number;
  context_token_limit?: number;
}

export interface RetrievalQueryInput {
  request: string;
  taskId?: string;
  topK?: number;
  contextTokenLimit?: number;
}

export interface SourceMetadataView {
  sourceId: string;
  sourceName: string;
  sourceType?: string | null;
  sourceFormat?: string | null;
}

export interface SourceMetadataFilter {
  sourceIds?: readonly string[];
  sourceTypes?: readonly string[];
  sourceFormats?: readonly string[];
}

function validatePositiveInteger(value: number | undefined, field: string): number | undefined {
  if (value === undefined) return undefined;
  if (!Number.isInteger(value) || value < 1) {
    throw new RangeError(`${field} must be a positive integer`);
  }
  return value;
}

/** Build the shared query shape without accepting a client-supplied owner. */
export function createOwnerScopedRetrievalQuery(input: RetrievalQueryInput): OwnerScopedRetrievalQuery {
  const request = input.request.trim();
  if (!request) throw new TypeError("request must not be empty");

  const taskId = input.taskId?.trim();
  const query: OwnerScopedRetrievalQuery = { request };
  if (taskId) query.task_id = taskId;
  const topK = validatePositiveInteger(input.topK, "topK");
  if (topK !== undefined) query.top_k = topK;
  const contextTokenLimit = validatePositiveInteger(input.contextTokenLimit, "contextTokenLimit");
  if (contextTokenLimit !== undefined) query.context_token_limit = contextTokenLimit;
  return query;
}

function normalizedValues(values: readonly string[] | undefined): Set<string> {
  return new Set((values ?? []).map((value) => value.trim().toLowerCase()).filter(Boolean));
}

/** Filter an already owner-scoped source list by metadata without adding owner routing. */
export function filterOwnerScopedSources(
  sources: readonly SourceMetadataView[],
  filter: SourceMetadataFilter = {},
): SourceMetadataView[] {
  const sourceIds = normalizedValues(filter.sourceIds);
  const sourceTypes = normalizedValues(filter.sourceTypes);
  const sourceFormats = normalizedValues(filter.sourceFormats);
  return sources.filter((source) => (
    (sourceIds.size === 0 || sourceIds.has(source.sourceId.trim().toLowerCase()))
    && (sourceTypes.size === 0 || sourceTypes.has((source.sourceType ?? "").trim().toLowerCase()))
    && (sourceFormats.size === 0 || sourceFormats.has((source.sourceFormat ?? "").trim().toLowerCase()))
  ));
}
