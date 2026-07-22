"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

export function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-black/10 dark:border-white/10 not-prose">
      <div className="flex items-center justify-between bg-neutral-800 px-4 py-1.5 text-xs text-neutral-300">
        <span>{language || "text"}</span>
        <button onClick={handleCopy} className="flex items-center gap-1 hover:text-white">
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? "Copied" : "Copy code"}
        </button>
      </div>
      <SyntaxHighlighter
        language={language || "text"}
        style={oneDark}
        customStyle={{ margin: 0, borderRadius: 0, fontSize: "13px", padding: "1rem" }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
