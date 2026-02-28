import {
  FileText,
  FileType,
  Presentation,
  Sheet,
  FileCode,
  Globe,
  BookOpen,
  Mail,
  Table2,
  Video,
  File,
} from "lucide-react";
import type { ContentType } from "@/lib/types";

interface ContentTypeConfig {
  icon: typeof FileText;
  label: string;
  badgeColor: string;
  bgColor: string;
  textColor: string;
  borderColor: string;
}

const CONTENT_TYPE_MAP: Record<string, ContentTypeConfig> = {
  youtube: {
    icon: Video,
    label: "Video",
    badgeColor: "bg-red-50 text-red-700 border-red-200",
    bgColor: "bg-red-50",
    textColor: "text-red-700",
    borderColor: "border-red-200",
  },
  pdf: {
    icon: FileText,
    label: "PDF",
    badgeColor: "bg-orange-50 text-orange-700 border-orange-200",
    bgColor: "bg-orange-50",
    textColor: "text-orange-700",
    borderColor: "border-orange-200",
  },
  docx: {
    icon: FileType,
    label: "Word",
    badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
    bgColor: "bg-blue-50",
    textColor: "text-blue-700",
    borderColor: "border-blue-200",
  },
  pptx: {
    icon: Presentation,
    label: "PowerPoint",
    badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
    bgColor: "bg-amber-50",
    textColor: "text-amber-700",
    borderColor: "border-amber-200",
  },
  xlsx: {
    icon: Sheet,
    label: "Excel",
    badgeColor: "bg-green-50 text-green-700 border-green-200",
    bgColor: "bg-green-50",
    textColor: "text-green-700",
    borderColor: "border-green-200",
  },
  txt: {
    icon: FileCode,
    label: "Text",
    badgeColor: "bg-gray-50 text-gray-700 border-gray-200",
    bgColor: "bg-gray-50",
    textColor: "text-gray-700",
    borderColor: "border-gray-200",
  },
  md: {
    icon: FileCode,
    label: "Markdown",
    badgeColor: "bg-gray-50 text-gray-700 border-gray-200",
    bgColor: "bg-gray-50",
    textColor: "text-gray-700",
    borderColor: "border-gray-200",
  },
  html: {
    icon: Globe,
    label: "HTML",
    badgeColor: "bg-purple-50 text-purple-700 border-purple-200",
    bgColor: "bg-purple-50",
    textColor: "text-purple-700",
    borderColor: "border-purple-200",
  },
  epub: {
    icon: BookOpen,
    label: "eBook",
    badgeColor: "bg-indigo-50 text-indigo-700 border-indigo-200",
    bgColor: "bg-indigo-50",
    textColor: "text-indigo-700",
    borderColor: "border-indigo-200",
  },
  csv: {
    icon: Table2,
    label: "CSV",
    badgeColor: "bg-teal-50 text-teal-700 border-teal-200",
    bgColor: "bg-teal-50",
    textColor: "text-teal-700",
    borderColor: "border-teal-200",
  },
  rtf: {
    icon: FileType,
    label: "RTF",
    badgeColor: "bg-slate-50 text-slate-700 border-slate-200",
    bgColor: "bg-slate-50",
    textColor: "text-slate-700",
    borderColor: "border-slate-200",
  },
  email: {
    icon: Mail,
    label: "Email",
    badgeColor: "bg-cyan-50 text-cyan-700 border-cyan-200",
    bgColor: "bg-cyan-50",
    textColor: "text-cyan-700",
    borderColor: "border-cyan-200",
  },
};

const DEFAULT_CONFIG: ContentTypeConfig = {
  icon: File,
  label: "File",
  badgeColor: "bg-gray-50 text-gray-700 border-gray-200",
  bgColor: "bg-gray-50",
  textColor: "text-gray-700",
  borderColor: "border-gray-200",
};

export function getContentTypeConfig(contentType: string): ContentTypeConfig {
  return CONTENT_TYPE_MAP[contentType] || DEFAULT_CONFIG;
}

export function getContentTypeIcon(contentType: string) {
  return (CONTENT_TYPE_MAP[contentType] || DEFAULT_CONFIG).icon;
}

export function getContentTypeLabel(contentType: string): string {
  return (CONTENT_TYPE_MAP[contentType] || DEFAULT_CONFIG).label;
}

export function getContentTypeBadgeClass(contentType: string): string {
  return (CONTENT_TYPE_MAP[contentType] || DEFAULT_CONFIG).badgeColor;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function isDocumentType(contentType: string): boolean {
  return contentType !== "youtube";
}

/** Accepted file extensions for document upload */
export const ACCEPTED_FILE_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".pptx",
  ".xlsx",
  ".txt",
  ".md",
  ".html",
  ".htm",
  ".epub",
  ".csv",
  ".rtf",
  ".eml",
];

/** MIME types for the file input accept attribute */
export const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/plain",
  "text/markdown",
  "text/html",
  "application/epub+zip",
  "text/csv",
  "application/rtf",
  "message/rfc822",
].join(",");
