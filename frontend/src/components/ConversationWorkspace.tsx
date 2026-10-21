import { useEffect, useState, type FormEvent, type ReactNode } from "react";

export interface ConversationWorkspaceProps {
  userEmail?: string | null;
  pendingQuestion?: string | null;
  result?: ReactNode;
  onSubmitQuestion: (question: string) => void | Promise<void>;
}

export default function ConversationWorkspace({
  userEmail,
  pendingQuestion = null,
  result = null,
  onSubmitQuestion,
}: ConversationWorkspaceProps) {
  const [question, setQuestion] = useState(pendingQuestion ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (pendingQuestion !== null) setQuestion(pendingQuestion ?? "");
  }, [pendingQuestion]);

  async function submitQuestion() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await onSubmitQuestion(trimmedQuestion);
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitQuestion();
  }

  return (
    <section className="conversation-workspace" aria-labelledby="conversation-workspace-title">
      <header className="workspace-header">
        <div>
          <span className="workspace-eyebrow">CONVERSATION WORKSPACE</span>
          <h2 id="conversation-workspace-title">Workspace</h2>
        </div>
        <span className="workspace-session">{userEmail ?? "Current session"}</span>
      </header>

      <div className="workspace-result" aria-live="polite" aria-busy={isSubmitting} aria-label="Conversation result">
        {isSubmitting ? (
          <div className="workspace-pending-result" role="status">
            <strong>Question pending</strong>
            <span>{question.trim()}</span>
          </div>
        ) : result ?? (
          <div className="workspace-empty-result">
            <strong>Ready for a question</strong>
            <span>The response area is ready for the Simple Ask integration.</span>
          </div>
        )}
      </div>

      <form className="workspace-composer" aria-busy={isSubmitting} onSubmit={handleSubmit}>
        <label htmlFor="conversation-question">Question</label>
        <div className="workspace-composer-row">
          <textarea
            id="conversation-question"
            value={question}
            rows={2}
            placeholder="Enter a question for this conversation…"
            onChange={(event) => setQuestion(event.target.value)}
            disabled={isSubmitting}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submitQuestion();
              }
            }}
          />
          <button type="submit" disabled={isSubmitting || !question.trim()}>
            {isSubmitting ? "Sending…" : "Send"}
          </button>
        </div>
      </form>
    </section>
  );
}
