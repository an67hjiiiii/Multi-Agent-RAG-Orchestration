export type AnswerRunStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETE"
  | "COMPLETED"
  | "PARTIAL"
  | "NO_EVIDENCE"
  | "FAILED"
  | "TIMEOUT"
  | string;

/**
 * Presentation projection of the shared Evidence/Provenance contract.
 * The caller maps the backend response into this view model; this component
 * does not define or call a backend endpoint.
 */
export interface CitationViewItem {
  id: string;
  source?: string | null;
  locator?: string | null;
}

export interface AnswerCitationViewProps {
  status: AnswerRunStatus;
  answer?: string | null;
  error?: string | null;
  citations?: readonly CitationViewItem[];
  missingInformation?: readonly string[];
}

function normalizeStatus(status: AnswerRunStatus): string {
  const normalized = status.trim().toUpperCase();
  return normalized === "COMPLETED" ? "COMPLETE" : normalized || "PENDING";
}

function statusLabel(status: string): string {
  switch (status) {
    case "PENDING": return "Pending";
    case "RUNNING": return "Processing";
    case "COMPLETE": return "Complete";
    case "PARTIAL": return "Partial";
    case "NO_EVIDENCE": return "No evidence";
    case "FAILED": return "Failed";
    case "TIMEOUT": return "Timed out";
    default: return status.replace(/_/g, " ");
  }
}

function statusDescription(status: string): string {
  switch (status) {
    case "PENDING": return "The question is queued for processing.";
    case "RUNNING": return "Retrieving evidence and preparing an answer.";
    case "COMPLETE": return "Answer ready.";
    case "PARTIAL": return "The answer is available with missing information.";
    case "NO_EVIDENCE": return "No validated evidence was returned for this question.";
    case "FAILED": return "The run could not produce an answer.";
    case "TIMEOUT": return "The run timed out before an answer was produced.";
    default: return "Run status received.";
  }
}

export function AnswerCitationView({
  status,
  answer,
  error,
  citations = [],
  missingInformation = [],
}: AnswerCitationViewProps) {
  const normalizedStatus = normalizeStatus(status);
  const isProcessing = normalizedStatus === "PENDING" || normalizedStatus === "RUNNING";
  const trimmedAnswer = answer?.trim();

  return (
    <section
      className={`answer-citation-view answer-citation-${normalizedStatus.toLowerCase()}`}
      aria-label="Answer and citations"
      aria-busy={isProcessing}
      aria-live="polite"
    >
      <header className="answer-citation-header">
        <div>
          <span className="answer-citation-eyebrow">Simple Ask result</span>
          <h3>Answer</h3>
        </div>
        <span className="answer-citation-status" role="status">
          {statusLabel(normalizedStatus)}
        </span>
      </header>

      <p className="answer-citation-description">{statusDescription(normalizedStatus)}</p>

      {isProcessing && (
        <div className="answer-citation-pending" role="status">
          <span aria-hidden="true" className="answer-citation-spinner" />
          <span>Processing your question…</span>
        </div>
      )}

      {!isProcessing && normalizedStatus === "FAILED" && (
        <p className="answer-citation-error" role="alert">
          {error?.trim() || "The request failed. Please try again."}
        </p>
      )}

      {!isProcessing && normalizedStatus === "TIMEOUT" && (
        <p className="answer-citation-error" role="alert">
          {error?.trim() || "The request timed out. Please try again."}
        </p>
      )}

      {!isProcessing && normalizedStatus === "NO_EVIDENCE" && (
        <p className="answer-citation-empty">
          {error?.trim() || "No evidence was found for this question."}
        </p>
      )}

      {!isProcessing && normalizedStatus !== "FAILED" && normalizedStatus !== "TIMEOUT" && normalizedStatus !== "NO_EVIDENCE" && (
        <p className={`answer-citation-copy${trimmedAnswer ? "" : " answer-citation-copy-muted"}`}>
          {trimmedAnswer || "No answer was returned."}
        </p>
      )}

      {missingInformation.length > 0 && (
        <div className="answer-citation-missing">
          <strong>Missing information</strong>
          <span>{missingInformation.join(" · ")}</span>
        </div>
      )}

      {citations.length > 0 && (
        <div className="answer-citation-list" aria-label="Citations">
          <span className="answer-citation-list-label">Sources</span>
          <ul>
            {citations.map((citation) => (
              <li key={citation.id}>
                <code>{citation.id}</code>
                {citation.source && <span>{citation.source}</span>}
                {citation.locator && <small>{citation.locator}</small>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
