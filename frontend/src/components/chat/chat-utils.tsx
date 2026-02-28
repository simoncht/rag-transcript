import remarkGfm from "remark-gfm";
import type { ChunkReference } from "@/lib/types";

// Performance: Memoized markdown components to avoid recreation on every render
// Static components that don't depend on props
export const MARKDOWN_STATIC_COMPONENTS = {
  h1: ({ node, ...props }: any) => (
    <h1 className="mt-6 mb-3 text-base font-semibold leading-tight" {...props} />
  ),
  h2: ({ node, ...props }: any) => (
    <h2 className="mt-6 mb-3 text-base font-semibold leading-tight" {...props} />
  ),
  h3: ({ node, ...props }: any) => (
    <h3 className="mt-6 mb-3 text-base font-semibold leading-tight" {...props} />
  ),
  p: ({ node, ...props }: any) => (
    <p className="my-4 text-base leading-relaxed" {...props} />
  ),
  ul: ({ node, ...props }: any) => (
    <ul className="my-4 list-disc space-y-2 pl-5 leading-relaxed text-base" {...props} />
  ),
  ol: ({ node, ...props }: any) => (
    <ol className="my-4 list-decimal space-y-2 pl-5 leading-relaxed text-base" {...props} />
  ),
  li: ({ node, ...props }: any) => (
    <li className="leading-relaxed text-base" {...props} />
  ),
  table: ({ node, ...props }: any) => (
    <div className="my-5 overflow-hidden rounded-lg border border-border">
      <table className="w-full table-auto border-collapse text-sm" {...props} />
    </div>
  ),
  thead: ({ node, ...props }: any) => (
    <thead className="bg-muted/70" {...props} />
  ),
  tbody: ({ node, ...props }: any) => (
    <tbody className="divide-y divide-border" {...props} />
  ),
  tr: ({ node, ...props }: any) => (
    <tr className="divide-x divide-border" {...props} />
  ),
  th: ({ node, ...props }: any) => (
    <th className="px-3 py-2 text-left font-semibold text-foreground align-top whitespace-pre-wrap" {...props} />
  ),
  td: ({ node, ...props }: any) => (
    <td className="px-3 py-2 align-top text-foreground whitespace-pre-wrap" {...props} />
  ),
  hr: () => null,
};

// Performance: Pre-configured remark plugins array to avoid recreation
export const REMARK_PLUGINS = [remarkGfm];

export const MODEL_OPTIONS = [
  {
    id: "deepseek-chat",
    label: "Chat",
    description: "Fast responses (Free tier)",
    tooltip: "Fast & efficient. Best for quick questions, finding quotes, and simple summaries.",
  },
  {
    id: "deepseek-reasoner",
    label: "Reasoner",
    description: "Advanced reasoning (Pro tier)",
    tooltip: "Thinks before answering. Best for complex analysis, comparing sources, and finding patterns.",
  },
];

export const MODE_OPTIONS = [
  {
    id: "summarize",
    label: "Summarize",
    helper: "Highlight core ideas concisely",
  },
  {
    id: "deep_dive",
    label: "Deep Dive",
    helper: "Explain layers, implications, patterns",
  },
  {
    id: "compare_sources",
    label: "Compare Sources",
    helper: "Contrast speakers and highlight agreements",
  },
];
export type ModeId = (typeof MODE_OPTIONS)[number]["id"];

// Helper function: linkify source mentions in markdown content
// Converts "Source N" and "[N]" to clickable footnote-style citations
export const linkifySourceMentions = (
  content: string,
  messageId: string,
  chunkRefs?: ChunkReference[],
) => {
  // First, handle explicit "Source N" mentions (legacy format)
  let result = content.replace(/Source (\d+)/g, (_match, srcNumber) => {
    const rank = Number(srcNumber?.trim());
    if (!chunkRefs || chunkRefs.length === 0 || Number.isNaN(rank)) {
      return `[${srcNumber}]`;
    }
    return `[[${rank}]](#source-${messageId}-${rank})`;
  });

  // Then, handle footnote-style [N] citations (new format from updated prompt)
  // Match [N] but not [[N]] (which we just created above) or [text](url) markdown links
  result = result.replace(/(?<!\[)\[(\d+)\](?!\()/g, (_match, srcNumber) => {
    const rank = Number(srcNumber?.trim());
    if (!chunkRefs || chunkRefs.length === 0 || Number.isNaN(rank)) {
      return `[${srcNumber}]`;
    }
    return `[[${rank}]](#source-${messageId}-${rank})`;
  });

  return result;
};

// Video grouping for multi-video conversations
export interface GroupedSources {
  videoId: string;
  videoTitle: string;
  channelName?: string | null;
  contentType?: string | null;
  sources: ChunkReference[];
}

export const groupSourcesByVideo = (sources: ChunkReference[]): GroupedSources[] => {
  const grouped = new Map<string, GroupedSources>();

  for (const source of sources) {
    const existing = grouped.get(source.video_id);
    if (existing) {
      existing.sources.push(source);
    } else {
      grouped.set(source.video_id, {
        videoId: source.video_id,
        videoTitle: source.video_title,
        channelName: source.channel_name,
        contentType: source.content_type,
        sources: [source],
      });
    }
  }

  // Sort groups by the best-ranked source in each group
  return Array.from(grouped.values()).sort(
    (a, b) => (a.sources[0]?.rank ?? 0) - (b.sources[0]?.rank ?? 0)
  );
};
