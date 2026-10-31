"use client";

import { useEffect, useRef, type ReactNode } from "react";
import MessageBubble from "./MessageBubble";
import type { Message } from "@/app/chat/page";

interface ChatWindowProps {
  messages: Message[];
  children?: ReactNode;
  scrollTrigger?: unknown;
}

export default function ChatWindow({ messages, children, scrollTrigger }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, scrollTrigger]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-8 sm:px-8">
      <div className="mx-auto min-w-0 max-w-3xl space-y-7">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {children}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
