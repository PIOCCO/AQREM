import { useCallback, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { IconCopy } from "../icons/Icons";

function CodeBlock({ children, className }: { children: ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  const text = String(children ?? "").replace(/\n$/, "");
  const lang = className?.replace("language-", "") ?? "";

  const onCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }, [text]);

  return (
    <div className="chat-code-wrap group relative my-3">
      {lang ? (
        <span className="absolute right-2 top-2 text-[10px] uppercase tracking-wide text-chat-muted pointer-events-none">
          {lang}
        </span>
      ) : null}
      <button
        type="button"
        onClick={onCopy}
        className="absolute right-2 bottom-2 rounded-md border border-chat-border bg-chat-surface px-2 py-1 text-xs text-chat-muted opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
        aria-label="Copy code"
      >
        {copied ? "Copied" : <IconCopy className="h-3.5 w-3.5" />}
      </button>
      <pre className="chat-code-block overflow-x-auto">
        <code>{text}</code>
      </pre>
    </div>
  );
}

export default function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="chat-markdown prose-chat">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="chat-link">
              {children}
            </a>
          ),
          code: ({ className, children, ...props }) => {
            const inline = !className;
            if (inline) {
              return (
                <code className="chat-inline-code" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <CodeBlock className={className}>
                {children}
              </CodeBlock>
            );
          },
          pre: ({ children }) => <>{children}</>,
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto">
              <table className="chat-table">{children}</table>
            </div>
          ),
          blockquote: ({ children }) => <blockquote className="chat-blockquote">{children}</blockquote>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
