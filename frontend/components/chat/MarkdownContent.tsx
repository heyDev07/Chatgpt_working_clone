import type { ComponentProps } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { CodeBlock } from "./CodeBlock";

function CodeRenderer({ className, children, ...rest }: ComponentProps<"code">) {
  const match = /language-(\w+)/.exec(className || "");
  const raw = String(children);
  const isBlock = Boolean(match) || raw.includes("\n");

  if (isBlock) {
    return <CodeBlock language={match?.[1] || ""} code={raw.replace(/\n$/, "")} />;
  }

  return (
    <code
      className="rounded bg-black/[0.06] dark:bg-white/[0.1] px-1.5 py-0.5 text-[0.85em] font-mono"
      {...rest}
    >
      {children}
    </code>
  );
}

const components: Components = {
  code: CodeRenderer,
};

export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="prose prose-neutral dark:prose-invert max-w-none prose-p:my-2 prose-pre:bg-transparent prose-pre:p-0 prose-pre:my-0 text-[15px] prose-headings:font-semibold">
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </Markdown>
    </div>
  );
}
