"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import Link from "next/link";
import Brand from "@/components/Brand";
import ChatWindow from "@/components/ChatWindow";
import ApprovalCard from "@/components/ApprovalCard";
import QueryStepBlock from "@/components/QueryStepBlock";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";

// ── Shared types (also imported by components) ────────────────────────────────
export interface QueryStep {
  sql: string;
  columns: string[];
  rows: unknown[][];
  error?: string;
  kind?: "auto" | "approved" | "rejected" | "blocked";
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  steps?: QueryStep[];
  images?: ImageAttachment[];
}

export interface ImageAttachment {
  name: string;
  mime_type: string;
  data: string;
}

/**
 * Tracks the state of a response that hasn't finished yet.
 * The loop may run through several SELECTs automatically, then pause
 * at a write query and wait for the user's decision before resuming.
 */
interface InProgress {
  /** Steps completed so far in the current response (auto-SELECTs, etc.) */
  accumulatedSteps: QueryStep[];
  /** Set when the loop is paused waiting for user approval. */
  pendingApproval: { sql: string } | null;
  /** True while a /chat/execute request is in flight. */
  deciding: boolean;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function getAuthHeader(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session ? `Bearer ${session.access_token}` : null;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "I've read your schema. Ask me anything about your database." },
  ]);
  const [input, setInput] = useState("");
  const [images, setImages] = useState<ImageAttachment[]>([]);
  const [attachmentError, setAttachmentError] = useState("");
  const [readingImages, setReadingImages] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [sending, setSending] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [runtime, setRuntime] = useState<{ model: string; provider: string } | null>(null);
  const [inProgress, setInProgress] = useState<InProgress | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Derived: true when the UI is busy (waiting for LLM or for execute round-trip)
  const busy = sending || recovering || (inProgress?.deciding ?? false);
  // Derived: true when input should be blocked (either busy or waiting for user approval)
  const inputBlocked = busy || readingImages || inProgress?.pendingApproval != null;

  async function recoverPending(previousSteps: QueryStep[] = []): Promise<boolean> {
    setRecovering(true);
    try {
      const auth = await getAuthHeader();
      if (!auth) return false;
      const response = await fetch(`${API_URL}/chat/pending`, { headers: { Authorization: auth }, cache: "no-store" });
      if (!response.ok) return false;
      const data = await response.json();
      if (data.status === "needs_approval" && data.pending_sql) {
        setInProgress({ accumulatedSteps: previousSteps, pendingApproval: { sql: data.pending_sql }, deciding: false });
        return true;
      }
      return false;
    } catch {
      return false;
    } finally {
      setRecovering(false);
    }
  }

  async function attachImages(files: FileList | null) {
    if (!files || inputBlocked) return;
    setAttachmentError("");
    if (images.length + files.length > 3) {
      setAttachmentError("Attach up to 3 images per message.");
      return;
    }
    setReadingImages(true);
    try {
      const additions = await Promise.all(Array.from(files).map(async (file) => {
        if (!["image/png", "image/jpeg", "image/webp"].includes(file.type))
          throw new Error("Use PNG, JPEG, or WebP images.");
        if (!file.size || file.size > 4 * 1024 * 1024)
          throw new Error("Each image must be at most 4 MB.");
        const data = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result).split(",")[1]);
          reader.onerror = () => reject(new Error("Could not read this image. Try again."));
          reader.readAsDataURL(file);
        });
        return { name: file.name, mime_type: file.type, data };
      }));
      setImages((current) => [...current, ...additions]);
    } catch (error) {
      setAttachmentError(error instanceof Error ? error.message : "Could not attach image.");
    } finally {
      setReadingImages(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  useEffect(() => {
    fetch(`${API_URL}/runtime`).then((res) => res.ok ? res.json() : null)
      .then(setRuntime).catch(() => setRuntime(null));
    async function guardAuth() {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.replace("/login"); return; }
      const { data } = await supabase
        .from("connections").select("id").eq("user_id", session.user.id).single();
      if (!data) { router.replace("/onboarding"); return; }
      await recoverPending();
    }
    guardAuth();
  }, [router]);

  // ── handleSend: start a new agentic round ──────────────────────────────────
  async function handleSend() {
    const text = input.trim() || (images.length ? "Describe this image and suggest how it relates to my database. Ask before implementing changes." : "");
    if (!text || inputBlocked) return;
    const sentImages = images;

    setMessages((prev) => [...prev, { role: "user", content: text, images: sentImages }]);
    setInput("");
    setImages([]);
    setAttachmentError("");
    setSending(true);
    setInProgress({ accumulatedSteps: [], pendingApproval: null, deciding: false });

    const auth = await getAuthHeader();
    if (!auth) { router.replace("/login"); return; }

    try {
      const res = await fetch(`${API_URL}/chat/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: auth },
        body: JSON.stringify({ message: text, images: sentImages }),
      });
      const data = await res.json();

      if (!res.ok) {
        if (await recoverPending()) return;
        finaliseWithError(typeof data.detail === "string" ? data.detail : "The request was rejected. Check image type and size, then retry.");
        return;
      }

      handleLoopResponse(data, []);
    } catch {
      if (!await recoverPending())
        finaliseWithError("The connection was interrupted. Check pending approval before retrying; do not assume a database change failed.");
    } finally {
      setSending(false);
    }
  }

  // ── handleDecision: user approved or rejected a write query ───────────────
  async function handleDecision(approved: boolean) {
    if (!inProgress?.pendingApproval) return;

    const sql = inProgress.pendingApproval.sql;
    setInProgress((prev) => prev ? { ...prev, deciding: true } : prev);

    const auth = await getAuthHeader();
    if (!auth) { router.replace("/login"); return; }

    try {
      const res = await fetch(`${API_URL}/chat/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: auth },
        body: JSON.stringify({ sql, approved }),
      });
      const data = await res.json();

      if (!res.ok) {
        if (await recoverPending(inProgress.accumulatedSteps)) return;
        finaliseWithError(data.detail || "Execution failed.");
        return;
      }

      handleLoopResponse(data, inProgress.accumulatedSteps);
    } catch {
      if (!await recoverPending(inProgress.accumulatedSteps))
        finaliseWithError("The execution response was lost. A change may already have committed. Check pending approval and verify the database before retrying.");
    }
  }

  /**
   * Process a ChatMessageResponse from either /chat/message or /chat/execute.
   * - "done"            → finalise the assistant message
   * - "needs_approval"  → update inProgress with the pending SQL
   *
   * @param data            The parsed JSON response body
   * @param previousSteps   Steps accumulated from earlier rounds
   */
  function handleLoopResponse(data: {
    status: string;
    reply?: string;
    completed_steps?: QueryStep[];
    pending_sql?: string;
  }, previousSteps: QueryStep[]) {
    const newSteps = data.completed_steps ?? [];
    const allSteps = [...previousSteps, ...newSteps];

    if (data.status === "done") {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply ?? "", steps: allSteps },
      ]);
      setInProgress(null);
    } else if (data.status === "needs_approval") {
      setInProgress({
        accumulatedSteps: allSteps,
        pendingApproval: { sql: data.pending_sql ?? "" },
        deciding: false,
      });
    }
  }

  function finaliseWithError(message: string) {
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: `Error: ${message}`,
        steps: inProgress?.accumulatedSteps ?? [],
      },
    ]);
    setInProgress(null);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="sidekick-workspace">
      <aside className="workspace-sidebar">
        <Brand />
        <div className="workspace-label">WORKSPACE</div>
        <nav aria-label="Workspace navigation">
          <Link href="/chat" className="sidebar-link active" aria-current="page"><span aria-hidden="true">◫</span> Database chat <span className="sidebar-shortcut">AI</span></Link>
          <Link href="/onboarding" className="sidebar-link"><span aria-hidden="true">▤</span> Connection settings <span aria-hidden="true">↗</span></Link>
        </nav>
        <div className="sidebar-session"><div className="workspace-label">THIS CONVERSATION</div>
          <div><span>Messages</span><strong>{messages.filter((message) => message.role === "user").length}</strong></div>
          <div><span>SQL steps</span><strong>{messages.reduce((count, message) => count + (message.steps?.length ?? 0), 0) + (inProgress?.accumulatedSteps.length ?? 0)}</strong></div>
          <div><span>Approval</span><strong className={inProgress?.pendingApproval ? "text-amber-300" : "text-emerald-300"}>{inProgress?.pendingApproval ? "Pending" : "Up to date"}</strong></div>
        </div>
        <div className="sidebar-bottom"><div className="sidebar-tip"><span>YOU'RE IN CONTROL</span><p>Read queries run automatically. Database changes wait for your approval.</p></div>
          <div className="sidebar-model"><span className="status-dot"/><span>{runtime ? "Model configured" : "Checking runtime"}<small>{runtime?.model ?? "Waiting for backend"}</small></span></div>
        </div>
      </aside>
    <main className="flex h-dvh min-h-0 min-w-0 flex-col overflow-hidden bg-gray-900">
      {/* Header */}
      <div className="workspace-topbar flex shrink-0 items-center justify-between gap-3 border-b border-gray-700 px-4 py-4 sm:px-8">
        <div className="workspace-heading"><span className="eyebrow">YOUR WORKSPACE</span><h1>Database chat <Link href="/onboarding" className="ml-2 text-[10px] font-normal text-gray-400 md:hidden">Connection ↗</Link> <span className="workspace-pill">Sidekick</span></h1></div>
        <div className="flex items-center gap-2">
        <button disabled={busy} onClick={async () => {
          if (!await recoverPending(inProgress?.accumulatedSteps ?? [])) {
            setMessages((current) => [...current, { role: "assistant", content: "No pending approval could be recovered. If an execution response was lost, verify the database before repeating the change." }]);
          }
        }} className="rounded-lg border border-gray-600 px-3 py-2 text-xs text-gray-200 hover:bg-gray-700 disabled:opacity-50">
          {recovering ? "Checking…" : "Check pending approval"}
        </button>
        <button onClick={handleSignOut} className="rounded-lg border border-gray-600 bg-gray-700 px-4 py-2 text-sm font-medium text-gray-200 transition-colors hover:bg-gray-600">
          Sign out
        </button>
        </div>
      </div>

      {/* Finalised messages */}
      <ChatWindow messages={messages.length === 1 ? [] : messages} scrollTrigger={inProgress}>

      {messages.length === 1 && !inProgress && (
        <section className="chat-welcome">
          <div className="welcome-symbol" aria-hidden="true">✳</div>
          <span className="eyebrow">MEET YOUR DATABASE SIDEKICK</span>
          <h2>What will you discover?</h2>
          <p>Ask a question. Explore a relationship. Bring a diagram to life.<br className="hidden sm:block"/> Start with your curiosity. We'll handle the SQL.</p>
          <div className="welcome-prompts">
            {[
              { icon: "▤", title: "Explore my database", description: "Understand your tables and relationships", prompt: "Describe my tables and their relationships" },
              { icon: "◈", title: "Find the story in my data", description: "Turn rows into useful insights", prompt: "Show me a useful summary of my data using aggregate queries" },
              { icon: "⌘", title: "Bring a diagram to life", description: "Attach an ER diagram to get started", prompt: "Help me implement an ER diagram. I will attach the image; ask about any unclear details first." },
            ].map((item) => <button key={item.title} disabled={inputBlocked} onClick={() => { setInput(item.prompt); textareaRef.current?.focus(); }} className="welcome-prompt">
              <span className="prompt-icon" aria-hidden="true">{item.icon}</span><strong>{item.title}</strong><span>{item.description}</span><b aria-hidden="true">↗</b>
            </button>)}
          </div>
          <div className="welcome-assurance"><span className="status-dot"/> Your next database change starts with your approval.</div>
        </section>
      )}

      {/* In-progress block — shown while a response is being built */}
      {inProgress && (
        <div className="mx-auto w-full max-w-3xl space-y-3 px-4 pb-3">

          {/* Auto-run steps completed so far */}
          {inProgress.accumulatedSteps.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-gray-400">
                {inProgress.accumulatedSteps.length} SQL step{inProgress.accumulatedSteps.length === 1 ? "" : "s"} completed
              </p>
              {inProgress.accumulatedSteps.map((step, i) => (
                <QueryStepBlock key={i} step={step} index={i} />
              ))}
            </div>
          )}

          {/* Approval card — blocks input until user decides */}
          {inProgress.pendingApproval ? (
            <ApprovalCard
              sql={inProgress.pendingApproval.sql}
              deciding={inProgress.deciding}
              onApprove={() => handleDecision(true)}
              onReject={() => handleDecision(false)}
            />
          ) : (
            /* Thinking indicator — LLM or execute is in flight */
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-500" />
              Thinking…
            </div>
          )}
        </div>
      )}

      </ChatWindow>

      {/* Input bar — disabled while waiting for LLM or user approval */}
      <div className="composer-dock shrink-0 px-4 pb-4 pt-2 sm:px-8 sm:pb-6">
        <div className="mx-auto max-w-3xl">
          {attachmentError && <p role="alert" className="mb-2 text-sm text-red-300">{attachmentError}</p>}
          {images.length > 0 && <div className="mb-3 flex flex-wrap gap-3">
            {images.map((image, index) => <div key={`${image.name}-${index}`} className="relative w-24">
              <img src={`data:${image.mime_type};base64,${image.data}`} alt={image.name} className="h-20 w-24 rounded-lg border border-gray-600 bg-gray-900 object-contain" />
              <button aria-label={`Remove ${image.name}`} disabled={inputBlocked} onClick={() => setImages((current) => current.filter((_, i) => i !== index))}
                className="absolute -right-2 -top-2 rounded-full bg-gray-600 px-2 py-0.5 text-white disabled:opacity-50">×</button>
              <p className="truncate text-xs text-gray-400">{image.name}</p>
            </div>)}
          </div>}
          <p className="composer-hint mb-2 text-xs text-gray-400">PNG, JPEG, WebP · 3 images, 4 MB each · Images sent to Google</p>
        </div>
        <div className="composer-box mx-auto flex max-w-3xl items-end gap-2">
          <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/webp" multiple className="hidden" aria-label="Attach images" onChange={(event) => attachImages(event.target.files)} />
          <button type="button" disabled={inputBlocked || images.length >= 3 || runtime?.provider !== "gemini"} onClick={() => fileInputRef.current?.click()}
            className="rounded-xl border border-gray-600 px-3 py-3 text-sm text-gray-200 hover:bg-gray-700 disabled:opacity-50" title="Attach ER diagrams or other images">
            {readingImages ? "Reading…" : "+ Image"}
          </button>
          <textarea
            ref={textareaRef}
            aria-label="Message your database sidekick"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={inputBlocked}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-600 bg-gray-700 px-4 py-3 text-sm text-white placeholder-gray-400 shadow-sm transition-all focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50"
            placeholder={
              inProgress?.pendingApproval
                ? "Waiting for your decision above…"
                : "Ask your database anything…"
            }
            style={{ maxHeight: "120px", overflowY: "auto" }}
          />
          <button
            onClick={handleSend}
            disabled={inputBlocked || (!input.trim() && images.length === 0)}
            className="sidekick-primary rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-md transition-all hover:shadow-lg hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending && !inProgress?.pendingApproval ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Thinking…
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                Send
              </span>
            )}
          </button>
        </div>
      </div>
    </main>
    </div>
  );
}
