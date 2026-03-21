import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Markdown({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        h1: ({ children }) => <h1 className="text-base font-semibold mt-3 mb-1">{children}</h1>,
        h2: ({ children }) => <h2 className="text-sm font-semibold mt-3 mb-1">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-medium mt-2 mb-1">{children}</h3>,
        strong: ({ children }) => <strong className="font-semibold text-neutral-100">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        code: ({ inline, children }) =>
          inline ? (
            <code className="bg-neutral-700 rounded px-1 py-0.5 text-xs font-mono text-neutral-200">
              {children}
            </code>
          ) : (
            <pre className="bg-neutral-900 rounded p-3 my-2 overflow-x-auto">
              <code className="text-xs font-mono text-neutral-300">{children}</code>
            </pre>
          ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-neutral-600 pl-3 my-2 text-neutral-400 italic">
            {children}
          </blockquote>
        ),
        hr: () => <hr className="border-neutral-700 my-3" />,
        a: ({ href, children }) => (
          <a href={href} className="text-neutral-300 underline hover:text-white" target="_blank" rel="noreferrer">
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
