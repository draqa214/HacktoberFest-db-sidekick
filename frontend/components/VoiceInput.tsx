"use client";

import { useEffect, useRef, useState } from "react";

interface RecognitionResult { isFinal: boolean; [index: number]: { transcript: string } }
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: { resultIndex: number; results: { length: number; [index: number]: RecognitionResult } }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type SpeechWindow = Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};

export default function VoiceInput({ disabled, onTranscript, onActiveChange }: {
  disabled: boolean;
  onTranscript: (text: string) => void;
  onActiveChange: (active: boolean) => void;
}) {
  const [supported, setSupported] = useState(false);
  const [active, setActive] = useState(false);
  const [status, setStatus] = useState("");
  const recognitionRef = useRef<Recognition | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcriptRef = useRef(onTranscript);
  const activeRef = useRef(onActiveChange);
  transcriptRef.current = onTranscript;
  activeRef.current = onActiveChange;

  useEffect(() => {
    const browser = window as SpeechWindow;
    setSupported(Boolean(window.isSecureContext && (browser.SpeechRecognition || browser.webkitSpeechRecognition)));
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      const recognition = recognitionRef.current;
      if (recognition) {
        recognition.onend = recognition.onerror = recognition.onresult = null;
        recognition.abort();
      }
    };
  }, []);

  useEffect(() => {
    if (disabled) recognitionRef.current?.stop();
  }, [disabled]);

  function toggle() {
    if (recognitionRef.current) {
      setStatus("Finishing transcription…");
      recognitionRef.current.stop();
      return;
    }
    const browser = window as SpeechWindow;
    const Constructor = browser.SpeechRecognition || browser.webkitSpeechRecognition;
    if (!Constructor || disabled) return;
    const recognition = new Constructor();
    recognitionRef.current = recognition;
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    let heardSpeech = false;
    let failed = false;
    const finish = () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      recognitionRef.current = null;
      setActive(false);
      activeRef.current(false);
      if (!failed) setStatus(heardSpeech ? "Transcript added. Review it, then press Send." : "No speech detected. Tap the microphone to try again.");
    };
    recognition.onresult = (event) => {
      const final: string[] = [];
      const interim: string[] = [];
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        (result.isFinal ? final : interim).push(result[0].transcript);
      }
      if (final.length) {
        heardSpeech = true;
        transcriptRef.current(final.join(" ").trim());
      }
      setStatus(interim.join(" ") || "Listening… Tap Stop when you're done.");
    };
    recognition.onerror = (event) => {
      failed = true;
      const errors: Record<string, string> = {
        "not-allowed": "Microphone permission denied. Allow microphone access in your browser, then try again.",
        "service-not-allowed": "Speech recognition is unavailable in this browser. Try Chrome or Edge, or type your message.",
        "audio-capture": "No microphone is available. Check your microphone connection.",
        network: "The speech service could not connect. Check your connection or type your message.",
        "no-speech": "No speech detected. Tap the microphone to try again.",
      };
      setStatus(errors[event.error] || "Speech recognition stopped. Review any transcribed text or try again.");
    };
    recognition.onend = finish;
    try {
      setActive(true);
      activeRef.current(true);
      setStatus("Listening… Tap Stop when you're done.");
      recognition.start();
      timeoutRef.current = setTimeout(() => recognition.stop(), 60_000);
    } catch {
      failed = true;
      setStatus("Could not start the microphone. Check browser permissions and try again.");
      finish();
    }
  }

  return <div className="voice-control">
    <button type="button" onClick={toggle} disabled={disabled || !supported} aria-pressed={active}
      aria-label={active ? "Stop dictation" : "Dictate message"}
      title={supported ? "Speak in English. Review the transcript before sending. Your browser may send audio to its speech service." : "Voice input requires a supported browser (try Chrome or Edge) on localhost or HTTPS."}
      className={`voice-button ${active ? "voice-active" : ""}`}>
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0014 0v-2M12 19v3M8 22h8"/></svg>
      <span>{active ? "Stop" : "Speak"}</span>
    </button>
    {status && <p role="status" className="voice-status">{status}</p>}
  </div>;
}
